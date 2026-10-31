//! SAML 2.0 service-provider support for SSO (Komboe).
//!
//! The SAML flow is bridged into the existing OIDC-style SSO flow used by the Bitwarden clients:
//! `/identity/connect/authorize` sends the browser to the IdP with an AuthnRequest (HTTP-Redirect binding),
//! the IdP POSTs a Response to `/identity/connect/saml-acs`, the assertion is verified and stored on the
//! `SsoAuth` row, and the browser is then redirected to the client with a one-time code exactly like OIDC.
//! The PKCE verifier is still checked on `/identity/connect/token`.
//!
//! Security rules: only the configured IdP certificate is trusted (`KeyInfo` keys are ignored), the consumed
//! Assertion must be covered by a valid signature (on the Assertion or on the enclosing Response), every
//! signature present must verify, exactly one Assertion is accepted, DTDs are rejected, and Issuer, Destination,
//! Recipient, InResponseTo, Audience and validity windows are all checked. Nothing derived from the IdP is used
//! to decrypt the vault: users still unlock with their master password.
use std::{io::Write, time::Duration};

use bergshamra_dsig::{DsigContext, VerifyResult, verify::verify_all_document_with_source};
use bergshamra_keys::{KeysManager, loader::load_x509_cert_pem};
use chrono::{DateTime, Utc};
use uppsala::{Document, NodeId};
use url::Url;

use crate::{CONFIG, api::ApiResult, crypto, db::models::OIDCAuthenticatedUser, sso::OIDCIdentifier};

const NS_SAMLP: &str = "urn:oasis:names:tc:SAML:2.0:protocol";
const NS_SAML: &str = "urn:oasis:names:tc:SAML:2.0:assertion";
const STATUS_SUCCESS: &str = "urn:oasis:names:tc:SAML:2.0:status:Success";
const BEARER: &str = "urn:oasis:names:tc:SAML:2.0:cm:bearer";
const NAMEID_EMAIL: &str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress";
const MAX_RESPONSE_BYTES: usize = 256 * 1024;
const CLOCK_SKEW_SECS: i64 = 120;

const EMAIL_ATTRS: &[&str] = &[
    "email",
    "mail",
    "emailaddress",
    "urn:oid:0.9.2342.19200300.100.1.3",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
];
const NAME_ATTRS: &[&str] = &[
    "displayname",
    "name",
    "cn",
    "urn:oid:2.16.840.1.113730.3.1.241",
    "urn:oid:2.5.4.3",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
];

pub fn sp_entity_id() -> String {
    format!("{}/identity/saml/metadata", CONFIG.domain())
}

pub fn acs_url() -> String {
    format!("{}/identity/connect/saml-acs", CONFIG.domain())
}

pub fn new_request_id() -> String {
    format!("_{}", data_encoding::HEXLOWER.encode(&crypto::get_random_bytes::<20>()))
}

fn xml_escape(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;").replace('"', "&quot;").replace('\'', "&apos;")
}

pub fn sp_metadata() -> String {
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{entity}">
  <md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" protocolSupportEnumeration="{NS_SAMLP}">
    <md:NameIDFormat>{NAMEID_EMAIL}</md:NameIDFormat>
    <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{acs}" index="0" isDefault="true"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>
"#,
        entity = xml_escape(&sp_entity_id()),
        acs = xml_escape(&acs_url()),
    )
}

/// Build the IdP redirect (HTTP-Redirect binding) carrying an unsigned AuthnRequest.
pub fn authn_request_url(request_id: &str, relay_state: &str) -> ApiResult<Url> {
    let dest = CONFIG.sso_saml_idp_sso_url();
    let now = Utc::now().format("%Y-%m-%dT%H:%M:%SZ");
    let xml = format!(
        r#"<samlp:AuthnRequest xmlns:samlp="{NS_SAMLP}" xmlns:saml="{NS_SAML}" ID="{id}" Version="2.0" IssueInstant="{now}" Destination="{dest}" ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" AssertionConsumerServiceURL="{acs}"><saml:Issuer>{issuer}</saml:Issuer><samlp:NameIDPolicy Format="{NAMEID_EMAIL}" AllowCreate="true"/></samlp:AuthnRequest>"#,
        id = xml_escape(request_id),
        dest = xml_escape(&dest),
        acs = xml_escape(&acs_url()),
        issuer = xml_escape(&sp_entity_id()),
    );
    let mut enc = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::default());
    if enc.write_all(xml.as_bytes()).is_err() {
        err!("Failed to encode SAML AuthnRequest")
    }
    let Ok(deflated) = enc.finish() else {
        err!("Failed to encode SAML AuthnRequest")
    };
    let mut url = match Url::parse(&dest) {
        Ok(u) => u,
        Err(e) => err!(format!("Invalid SSO_SAML_IDP_SSO_URL: {e}")),
    };
    url.query_pairs_mut()
        .append_pair("SAMLRequest", &data_encoding::BASE64.encode(&deflated))
        .append_pair("RelayState", relay_state);
    Ok(url)
}

fn load_idp_cert() -> ApiResult<Vec<u8>> {
    let raw = CONFIG.sso_saml_idp_cert();
    let pem = if raw.trim_start().starts_with("-----BEGIN") {
        raw.into_bytes()
    } else {
        match std::fs::read(raw.trim()) {
            Ok(b) => b,
            Err(e) => err!(format!("Cannot read SSO_SAML_IDP_CERT file: {e}")),
        }
    };
    Ok(pem)
}

fn elem_is(doc: &Document<'_>, id: NodeId, ns: &str, local: &str) -> bool {
    doc.element(id).is_some_and(|e| e.matches_name_ns(ns, local))
}

fn child(doc: &Document<'_>, parent: NodeId, ns: &str, local: &str) -> Option<NodeId> {
    doc.first_child_element_by_name_ns(parent, ns, local)
}

fn text(doc: &Document<'_>, id: NodeId) -> String {
    doc.text_content_deep(id).trim().to_owned()
}

fn parse_time(v: &str) -> ApiResult<DateTime<Utc>> {
    if let Ok(t) = DateTime::parse_from_rfc3339(v) {
        Ok(t.with_timezone(&Utc))
    } else {
        err!(format!("Invalid SAML timestamp {}", v.escape_debug()))
    }
}

fn is_ancestor(doc: &Document<'_>, ancestor: NodeId, mut node: NodeId) -> bool {
    loop {
        if node == ancestor {
            return true;
        }
        match doc.parent(node) {
            Some(p) => node = p,
            None => return false,
        }
    }
}

/// Verify a base64 `SAMLResponse` posted to the ACS and return the authenticated user.
pub fn verify_response(saml_response_b64: &str, expected_request_id: &str) -> ApiResult<OIDCAuthenticatedUser> {
    let cleaned: String = saml_response_b64.chars().filter(|c| !c.is_ascii_whitespace()).collect();
    if cleaned.len() > MAX_RESPONSE_BYTES * 4 / 3 + 4 {
        err!("SAML response too large")
    }
    let Ok(bytes) = data_encoding::BASE64.decode(cleaned.as_bytes()) else {
        err!("SAML response is not valid base64")
    };
    let Ok(xml) = String::from_utf8(bytes) else {
        err!("SAML response is not UTF-8")
    };
    // No DTDs or entity declarations in SAML protocol messages
    if xml.contains("<!") {
        err!("SAML response contains a DTD, entity or CDATA section")
    }
    let doc = match uppsala::parse(&xml) {
        Ok(d) => d,
        Err(e) => err!(format!("SAML response is not well-formed XML: {e}")),
    };
    let Some(root) = doc.document_element() else {
        err!("Empty SAML response")
    };
    if !elem_is(&doc, root, NS_SAMLP, "Response") {
        err!("SAML message is not a Response")
    }
    let acs = acs_url();
    if doc.get_attribute(root, "Destination") != Some(acs.as_str()) {
        err!("SAML Response Destination does not match this server")
    }
    if doc.get_attribute(root, "InResponseTo") != Some(expected_request_id) {
        err!("SAML Response InResponseTo does not match the request")
    }
    let status_ok = child(&doc, root, NS_SAMLP, "Status")
        .and_then(|s| child(&doc, s, NS_SAMLP, "StatusCode"))
        .and_then(|c| doc.get_attribute(c, "Value"))
        == Some(STATUS_SUCCESS);
    if !status_ok {
        err!("SAML Response status is not Success")
    }
    if !doc.get_elements_by_tag_name_ns(NS_SAML, "EncryptedAssertion").is_empty() {
        err!("Encrypted SAML assertions are not supported")
    }
    let assertions = doc.get_elements_by_tag_name_ns(NS_SAML, "Assertion");
    if assertions.len() != 1 {
        err!("SAML Response must contain exactly one Assertion")
    }
    let assertion = assertions[0];
    if doc.parent(assertion) != Some(root) {
        err!("SAML Assertion is not a direct child of the Response")
    }

    // Signature verification against the configured IdP certificate only
    let pem = load_idp_cert()?;
    let key = match load_x509_cert_pem(&pem) {
        Ok(k) => k,
        Err(e) => err!(format!("Invalid SSO_SAML_IDP_CERT: {e}")),
    };
    let mut km = KeysManager::new();
    km.add_key(key);
    let mut ctx = DsigContext::new(km);
    ctx.trusted_keys_only = true;
    ctx.strict_verification = true;
    ctx.require_reference_digests = true;
    let results = match verify_all_document_with_source(&ctx, &doc, Some(&xml)) {
        Ok(r) => r,
        Err(e) => err!(format!("SAML signature verification failed: {e}")),
    };
    let mut covered = false;
    for r in &results {
        match r {
            VerifyResult::Valid {
                references,
                ..
            } => {
                if !r.all_reference_digests_verified() {
                    err!("SAML signature has unverified references")
                }
                if references.iter().any(|rf| {
                    rf.resolved_node
                        .is_some_and(|n| n == assertion || (n == root && is_ancestor(&doc, root, assertion)))
                }) {
                    covered = true;
                }
            }
            VerifyResult::Invalid {
                reason,
            } => err!(format!("Invalid SAML signature: {reason}")),
        }
    }
    if !covered {
        err!("SAML Assertion is not covered by a valid IdP signature")
    }

    // Assertion content (read only from the verified Assertion node)
    let idp_entity = CONFIG.sso_saml_idp_entity_id();
    let issuer = child(&doc, assertion, NS_SAML, "Issuer").map(|i| text(&doc, i));
    if issuer.as_deref() != Some(idp_entity.as_str()) {
        err!("SAML Assertion Issuer does not match SSO_SAML_IDP_ENTITY_ID")
    }

    let now = Utc::now();
    let skew = chrono::TimeDelta::try_seconds(CLOCK_SKEW_SECS).unwrap();

    let Some(subject) = child(&doc, assertion, NS_SAML, "Subject") else {
        err!("SAML Assertion has no Subject")
    };
    let Some(name_id) = child(&doc, subject, NS_SAML, "NameID") else {
        err!("SAML Assertion has no NameID")
    };
    let name_id_value = text(&doc, name_id);
    if name_id_value.is_empty() {
        err!("SAML NameID is empty")
    }
    let mut bearer_ok = false;
    for sc in doc.child_elements_by_name_ns(subject, NS_SAML, "SubjectConfirmation") {
        if doc.get_attribute(sc, "Method") != Some(BEARER) {
            continue;
        }
        let Some(data) = child(&doc, sc, NS_SAML, "SubjectConfirmationData") else {
            continue;
        };
        let recipient_ok = doc.get_attribute(data, "Recipient") == Some(acs.as_str());
        let irt_ok = doc.get_attribute(data, "InResponseTo") == Some(expected_request_id);
        let exp_ok = match doc.get_attribute(data, "NotOnOrAfter") {
            Some(t) => now - skew < parse_time(t)?,
            None => false,
        };
        if recipient_ok && irt_ok && exp_ok {
            bearer_ok = true;
            break;
        }
    }
    if !bearer_ok {
        err!("SAML Assertion has no valid bearer SubjectConfirmation for this request")
    }

    let Some(conditions) = child(&doc, assertion, NS_SAML, "Conditions") else {
        err!("SAML Assertion has no Conditions")
    };
    if let Some(nb) = doc.get_attribute(conditions, "NotBefore")
        && parse_time(nb)? > now + skew
    {
        err!("SAML Assertion is not yet valid")
    }
    match doc.get_attribute(conditions, "NotOnOrAfter") {
        Some(na) if parse_time(na)? > now - skew => {}
        _ => err!("SAML Assertion is expired or has no NotOnOrAfter"),
    }
    let sp = sp_entity_id();
    let restrictions = doc.child_elements_by_name_ns(conditions, NS_SAML, "AudienceRestriction");
    if restrictions.is_empty() {
        err!("SAML Assertion has no AudienceRestriction")
    }
    for ar in restrictions {
        if !doc.child_elements_by_name_ns(ar, NS_SAML, "Audience").into_iter().any(|a| text(&doc, a) == sp) {
            err!("SAML Assertion audience does not include this server")
        }
    }

    // Attributes
    let mut email: Option<String> = None;
    let mut user_name: Option<String> = None;
    if let Some(stmt) = child(&doc, assertion, NS_SAML, "AttributeStatement") {
        for attr in doc.child_elements_by_name_ns(stmt, NS_SAML, "Attribute") {
            let name = doc.get_attribute(attr, "Name").unwrap_or_default().to_lowercase();
            let friendly = doc.get_attribute(attr, "FriendlyName").unwrap_or_default().to_lowercase();
            let value = doc.child_elements_by_name_ns(attr, NS_SAML, "AttributeValue").first().map(|v| text(&doc, *v));
            let is = |list: &[&str]| list.contains(&name.as_str()) || list.contains(&friendly.as_str());
            if email.is_none() && is(EMAIL_ATTRS) {
                email.clone_from(&value);
            } else if user_name.is_none() && is(NAME_ATTRS) {
                user_name.clone_from(&value);
            }
        }
    }
    if email.is_none() && doc.get_attribute(name_id, "Format") == Some(NAMEID_EMAIL) {
        email = Some(name_id_value.clone());
    }
    let Some(email) = email.map(|e| e.to_lowercase()).filter(|e| e.contains('@')) else {
        err!("SAML Assertion contains no email (attribute `email`/`mail` or an emailAddress NameID)")
    };

    Ok(OIDCAuthenticatedUser {
        refresh_token: None,
        access_token: String::new(),
        expires_in: Some(Duration::from_secs(300)),
        identifier: OIDCIdentifier::new(&format!("saml:{idp_entity}"), &name_id_value),
        email,
        email_verified: CONFIG.sso_saml_email_verified().then_some(true),
        user_name,
    })
}
