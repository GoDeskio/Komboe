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
use bergshamra_enc::EncContext;
use bergshamra_keys::{
    KeysManager,
    loader::{load_pem_auto, load_x509_cert_pem},
};
use chrono::{DateTime, Utc};
use uppsala::{Document, NodeId};
use url::Url;

use crate::{CONFIG, api::ApiResult, crypto, db::models::OIDCAuthenticatedUser, sso::OIDCIdentifier};

const NS_SAMLP: &str = "urn:oasis:names:tc:SAML:2.0:protocol";
const NS_SAML: &str = "urn:oasis:names:tc:SAML:2.0:assertion";
const STATUS_SUCCESS: &str = "urn:oasis:names:tc:SAML:2.0:status:Success";
const BEARER: &str = "urn:oasis:names:tc:SAML:2.0:cm:bearer";
const NAMEID_EMAIL: &str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress";
const NS_XENC: &str = "http://www.w3.org/2001/04/xmlenc#";
const NS_DS: &str = "http://www.w3.org/2000/09/xmldsig#";
const RSA_SHA256: &str = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256";
const RSA_1_5: &str = "http://www.w3.org/2001/04/xmlenc#rsa-1_5";
const BINDING_POST: &str = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST";
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

pub fn slo_url() -> String {
    format!("{}/identity/connect/saml-slo", CONFIG.domain())
}

/// SP signing/decryption key pair configured (`SSO_SAML_SP_KEY` + `SSO_SAML_SP_CERT`).
pub fn sp_key_configured() -> bool {
    !CONFIG.sso_saml_sp_key().trim().is_empty() && !CONFIG.sso_saml_sp_cert().trim().is_empty()
}

fn pem_or_file(raw: String, what: &str) -> ApiResult<Vec<u8>> {
    if raw.trim_start().starts_with("-----BEGIN") {
        Ok(raw.into_bytes())
    } else {
        match std::fs::read(raw.trim()) {
            Ok(b) => Ok(b),
            Err(e) => err!(format!("Cannot read {what} file: {e}")),
        }
    }
}

fn load_idp_cert() -> ApiResult<Vec<u8>> {
    pem_or_file(CONFIG.sso_saml_idp_cert(), "SSO_SAML_IDP_CERT")
}

/// Base64 body of the SP certificate (for metadata KeyDescriptors).
fn sp_cert_b64() -> ApiResult<String> {
    let pem = pem_or_file(CONFIG.sso_saml_sp_cert(), "SSO_SAML_SP_CERT")?;
    let pem = String::from_utf8_lossy(&pem);
    let Some(start) = pem.find("-----BEGIN CERTIFICATE-----") else {
        err!("SSO_SAML_SP_CERT is not a PEM certificate")
    };
    let body = &pem[start + 27..];
    let Some(end) = body.find("-----END CERTIFICATE-----") else {
        err!("SSO_SAML_SP_CERT is not a PEM certificate")
    };
    Ok(body[..end].chars().filter(|c| !c.is_ascii_whitespace()).collect())
}

fn sp_private_key() -> ApiResult<bergshamra_keys::Key> {
    let pem = pem_or_file(CONFIG.sso_saml_sp_key(), "SSO_SAML_SP_KEY")?;
    match load_pem_auto(&pem, None) {
        Ok(k) => Ok(k),
        Err(e) => err!(format!("Invalid SSO_SAML_SP_KEY: {e}")),
    }
}

pub fn sp_metadata() -> ApiResult<String> {
    let keys = if sp_key_configured() {
        let cert = sp_cert_b64()?;
        format!(
            r#"
    <md:KeyDescriptor use="signing"><ds:KeyInfo xmlns:ds="{NS_DS}"><ds:X509Data><ds:X509Certificate>{cert}</ds:X509Certificate></ds:X509Data></ds:KeyInfo></md:KeyDescriptor>
    <md:KeyDescriptor use="encryption"><ds:KeyInfo xmlns:ds="{NS_DS}"><ds:X509Data><ds:X509Certificate>{cert}</ds:X509Certificate></ds:X509Data></ds:KeyInfo></md:KeyDescriptor>"#
        )
    } else {
        String::new()
    };
    let slo = if CONFIG.sso_saml_idp_slo_url().is_empty() {
        String::new()
    } else {
        format!(
            r#"
    <md:SingleLogoutService Binding="{BINDING_POST}" Location="{}"/>"#,
            xml_escape(&slo_url())
        )
    };
    Ok(format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{entity}">
  <md:SPSSODescriptor AuthnRequestsSigned="{signed}" WantAssertionsSigned="true" protocolSupportEnumeration="{NS_SAMLP}">{keys}{slo}
    <md:NameIDFormat>{NAMEID_EMAIL}</md:NameIDFormat>
    <md:AssertionConsumerService Binding="{BINDING_POST}" Location="{acs}" index="0" isDefault="true"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>
"#,
        entity = xml_escape(&sp_entity_id()),
        acs = xml_escape(&acs_url()),
        signed = sp_key_configured(),
    ))
}

fn enc(v: &str) -> String {
    url::form_urlencoded::byte_serialize(v.as_bytes()).collect()
}

/// HTTP-Redirect binding: deflate + base64 the message, and sign
/// `SAMLRequest=..&RelayState=..&SigAlg=..` with the SP key (RSA-SHA256) when one is configured.
fn redirect_binding_url(dest: &str, param: &str, xml: &str, relay_state: Option<&str>) -> ApiResult<Url> {
    let mut deflater = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::default());
    if deflater.write_all(xml.as_bytes()).is_err() {
        err!("Failed to encode SAML message")
    }
    let Ok(deflated) = deflater.finish() else {
        err!("Failed to encode SAML message")
    };
    let mut url = match Url::parse(dest) {
        Ok(u) => u,
        Err(e) => err!(format!("Invalid SAML IdP URL: {e}")),
    };
    let mut q = format!("{param}={}", enc(&data_encoding::BASE64.encode(&deflated)));
    if let Some(rs) = relay_state {
        q.push_str(&format!("&RelayState={}", enc(rs)));
    }
    if sp_key_configured() {
        q.push_str(&format!("&SigAlg={}", enc(RSA_SHA256)));
        let key = sp_private_key()?;
        let sk = match key.to_signing_key() {
            Ok(Some(k)) => k,
            _ => err!("SSO_SAML_SP_KEY has no usable private key"),
        };
        let sig = match bergshamra_crypto::sign::from_uri(RSA_SHA256).and_then(|a| a.sign(&sk, q.as_bytes())) {
            Ok(s) => s,
            Err(e) => err!(format!("Failed to sign SAML message: {e}")),
        };
        q.push_str(&format!("&Signature={}", enc(&data_encoding::BASE64.encode(&sig))));
    }
    let full = match url.query() {
        Some(existing) if !existing.is_empty() => format!("{existing}&{q}"),
        _ => q,
    };
    url.set_query(Some(&full));
    Ok(url)
}

/// Build the IdP redirect (HTTP-Redirect binding) carrying an AuthnRequest, signed when an SP key is configured.
pub fn authn_request_url(request_id: &str, relay_state: &str) -> ApiResult<Url> {
    let dest = CONFIG.sso_saml_idp_sso_url();
    let now = Utc::now().format("%Y-%m-%dT%H:%M:%SZ");
    let xml = format!(
        r#"<samlp:AuthnRequest xmlns:samlp="{NS_SAMLP}" xmlns:saml="{NS_SAML}" ID="{id}" Version="2.0" IssueInstant="{now}" Destination="{dest}" ProtocolBinding="{BINDING_POST}" AssertionConsumerServiceURL="{acs}"><saml:Issuer>{issuer}</saml:Issuer><samlp:NameIDPolicy Format="{NAMEID_EMAIL}" AllowCreate="true"/></samlp:AuthnRequest>"#,
        id = xml_escape(request_id),
        dest = xml_escape(&dest),
        acs = xml_escape(&acs_url()),
        issuer = xml_escape(&sp_entity_id()),
    );
    redirect_binding_url(&dest, "SAMLRequest", &xml, Some(relay_state))
}

/// SP-initiated single logout: signed LogoutRequest for `name_id` (HTTP-Redirect binding).
pub fn logout_request_url(name_id: &str, relay_state: &str) -> ApiResult<Url> {
    let dest = CONFIG.sso_saml_idp_slo_url();
    if dest.is_empty() {
        err!("SSO_SAML_IDP_SLO_URL is not set")
    }
    let now = Utc::now().format("%Y-%m-%dT%H:%M:%SZ");
    let xml = format!(
        r#"<samlp:LogoutRequest xmlns:samlp="{NS_SAMLP}" xmlns:saml="{NS_SAML}" ID="{id}" Version="2.0" IssueInstant="{now}" Destination="{dest}"><saml:Issuer>{issuer}</saml:Issuer><saml:NameID Format="{NAMEID_EMAIL}">{nid}</saml:NameID></samlp:LogoutRequest>"#,
        id = new_request_id(),
        dest = xml_escape(&dest),
        issuer = xml_escape(&sp_entity_id()),
        nid = xml_escape(name_id),
    );
    redirect_binding_url(&dest, "SAMLRequest", &xml, Some(relay_state))
}

/// Answer to an IdP-initiated LogoutRequest (HTTP-Redirect binding, signed when an SP key is configured).
pub fn logout_response_url(in_response_to: &str, relay_state: Option<&str>) -> ApiResult<Url> {
    let dest = CONFIG.sso_saml_idp_slo_url();
    if dest.is_empty() {
        err!("SSO_SAML_IDP_SLO_URL is not set")
    }
    let now = Utc::now().format("%Y-%m-%dT%H:%M:%SZ");
    let xml = format!(
        r#"<samlp:LogoutResponse xmlns:samlp="{NS_SAMLP}" xmlns:saml="{NS_SAML}" ID="{id}" Version="2.0" IssueInstant="{now}" Destination="{dest}" InResponseTo="{irt}"><saml:Issuer>{issuer}</saml:Issuer><samlp:Status><samlp:StatusCode Value="{STATUS_SUCCESS}"/></samlp:Status></samlp:LogoutResponse>"#,
        id = new_request_id(),
        dest = xml_escape(&dest),
        irt = xml_escape(in_response_to),
        issuer = xml_escape(&sp_entity_id()),
    );
    redirect_binding_url(&dest, "SAMLResponse", &xml, relay_state)
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

/// Decode and parse a POST-binding SAML message, rejecting DTDs/entities/CDATA and oversized input.
fn decode_post_message(b64: &str) -> ApiResult<String> {
    let cleaned: String = b64.chars().filter(|c| !c.is_ascii_whitespace()).collect();
    if cleaned.len() > MAX_RESPONSE_BYTES * 4 / 3 + 4 {
        err!("SAML message too large")
    }
    let Ok(bytes) = data_encoding::BASE64.decode(cleaned.as_bytes()) else {
        err!("SAML message is not valid base64")
    };
    let Ok(xml) = String::from_utf8(bytes) else {
        err!("SAML message is not UTF-8")
    };
    if xml.contains("<!") {
        err!("SAML message contains a DTD, entity or CDATA section")
    }
    Ok(xml)
}

fn idp_dsig_context() -> ApiResult<DsigContext> {
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
    Ok(ctx)
}

/// Verify every signature in `doc` against the IdP certificate only. Any invalid signature fails.
/// Returns the nodes covered by valid signatures (empty when the document carries no signature).
fn verified_nodes(doc: &Document<'_>, xml: &str) -> ApiResult<Vec<NodeId>> {
    if doc.get_elements_by_tag_name_ns(NS_DS, "Signature").is_empty() {
        return Ok(Vec::new());
    }
    let ctx = idp_dsig_context()?;
    let results = match verify_all_document_with_source(&ctx, doc, Some(xml)) {
        Ok(r) => r,
        Err(e) => err!(format!("SAML signature verification failed: {e}")),
    };
    let mut nodes = Vec::new();
    for r in &results {
        match r {
            VerifyResult::Valid {
                references,
                ..
            } => {
                if !r.all_reference_digests_verified() {
                    err!("SAML signature has unverified references")
                }
                nodes.extend(references.iter().filter_map(|rf| rf.resolved_node));
            }
            VerifyResult::Invalid {
                reason,
            } => err!(format!("Invalid SAML signature: {reason}")),
        }
    }
    Ok(nodes)
}

/// Decrypt an `EncryptedAssertion` with the SP key; returns the standalone Assertion XML.
fn decrypt_assertion(doc: &Document<'_>, xml: &str) -> ApiResult<String> {
    if !sp_key_configured() {
        err!("Encrypted SAML assertion received but SSO_SAML_SP_KEY/SSO_SAML_SP_CERT are not set")
    }
    // The whole Response is decrypted (exactly one EncryptedData exists) so in-scope namespaces survive.
    if xml.contains(RSA_1_5) {
        err!("RSA PKCS#1 v1.5 key transport is not accepted; use RSA-OAEP")
    }
    if !doc.get_elements_by_tag_name_ns(NS_XENC, "CipherReference").is_empty() {
        err!("CipherReference is not accepted in SAML assertions")
    }
    if doc.get_elements_by_tag_name_ns(NS_XENC, "EncryptedData").len() != 1 {
        err!("SAML EncryptedAssertion must contain exactly one EncryptedData")
    }
    let mut km = KeysManager::new();
    km.add_key(sp_private_key()?);
    let ctx = EncContext::new(km).with_disable_cipher_reference(true).with_max_pbkdf2_iterations(0);
    let plain = match bergshamra_enc::decrypt::decrypt(&ctx, xml) {
        Ok(p) => p,
        Err(e) => {
            warn!("SAML assertion decryption failed: {e}");
            err!("Unable to decrypt SAML assertion")
        }
    };
    if plain.contains("<!") {
        err!("Decrypted SAML assertion contains a DTD, entity or CDATA section")
    }
    Ok(plain)
}

/// Verify a base64 `SAMLResponse` posted to the ACS and return the authenticated user.
pub fn verify_response(saml_response_b64: &str, expected_request_id: &str) -> ApiResult<OIDCAuthenticatedUser> {
    let xml = decode_post_message(saml_response_b64)?;
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
    let encrypted = doc.get_elements_by_tag_name_ns(NS_SAML, "EncryptedAssertion");
    let plain = doc.get_elements_by_tag_name_ns(NS_SAML, "Assertion");
    if encrypted.len() + plain.len() != 1 {
        err!("SAML Response must contain exactly one Assertion")
    }
    if encrypted.is_empty() && CONFIG.sso_saml_require_encrypted_assertions() {
        err!("SAML assertion must be encrypted (SSO_SAML_REQUIRE_ENCRYPTED_ASSERTIONS)")
    }

    // Signatures on the Response document, against the configured IdP certificate only
    let response_signed_nodes = verified_nodes(&doc, &xml)?;
    let response_signed = response_signed_nodes.contains(&root);

    if let Some(&enc_node) = encrypted.first() {
        if doc.parent(enc_node) != Some(root) {
            err!("SAML EncryptedAssertion is not a direct child of the Response")
        }
        let plain_xml = decrypt_assertion(&doc, &xml)?;
        let pdoc = match uppsala::parse(&plain_xml) {
            Ok(d) => d,
            Err(e) => err!(format!("Decrypted SAML response is not well-formed XML: {e}")),
        };
        let Some(proot) = pdoc.document_element() else {
            err!("Empty decrypted SAML response")
        };
        if !pdoc.get_elements_by_tag_name_ns(NS_XENC, "EncryptedData").is_empty() {
            err!("Nested encryption in SAML assertion is not supported")
        }
        let found = pdoc.get_elements_by_tag_name_ns(NS_SAML, "Assertion");
        if found.len() != 1 {
            err!("EncryptedAssertion must decrypt to exactly one Assertion")
        }
        let assertion = found[0];
        let wrapper = pdoc.parent(assertion);
        if wrapper.is_none_or(|w| !elem_is(&pdoc, w, NS_SAML, "EncryptedAssertion") || pdoc.parent(w) != Some(proot)) {
            err!("Decrypted SAML Assertion is not where the EncryptedAssertion was")
        }
        // Assertion signature is checked on the decrypted document; a Response-level signature
        // (verified above, over the ciphertext) also covers it.
        let signed = verified_nodes(&pdoc, &plain_xml)?.contains(&assertion);
        if !(signed || response_signed) {
            err!("SAML Assertion is not covered by a valid IdP signature")
        }
        return check_assertion(&pdoc, assertion, expected_request_id, &acs);
    }

    let assertion = plain[0];
    if doc.parent(assertion) != Some(root) {
        err!("SAML Assertion is not a direct child of the Response")
    }
    let covered =
        response_signed_nodes.iter().any(|&n| n == assertion || (n == root && is_ancestor(&doc, root, assertion)));
    if !covered {
        err!("SAML Assertion is not covered by a valid IdP signature")
    }
    check_assertion(&doc, assertion, expected_request_id, &acs)
}

/// Validate the content of an Assertion whose signature has already been verified.
fn check_assertion(
    doc: &Document<'_>,
    assertion: NodeId,
    expected_request_id: &str,
    acs: &str,
) -> ApiResult<OIDCAuthenticatedUser> {
    // Assertion content (read only from the verified Assertion node)
    let idp_entity = CONFIG.sso_saml_idp_entity_id();
    let issuer = child(doc, assertion, NS_SAML, "Issuer").map(|i| text(doc, i));
    if issuer.as_deref() != Some(idp_entity.as_str()) {
        err!("SAML Assertion Issuer does not match SSO_SAML_IDP_ENTITY_ID")
    }

    let now = Utc::now();
    let skew = chrono::TimeDelta::try_seconds(CLOCK_SKEW_SECS).unwrap();

    let Some(subject) = child(doc, assertion, NS_SAML, "Subject") else {
        err!("SAML Assertion has no Subject")
    };
    let Some(name_id) = child(doc, subject, NS_SAML, "NameID") else {
        err!("SAML Assertion has no NameID")
    };
    let name_id_value = text(doc, name_id);
    if name_id_value.is_empty() {
        err!("SAML NameID is empty")
    }
    let mut bearer_ok = false;
    for sc in doc.child_elements_by_name_ns(subject, NS_SAML, "SubjectConfirmation") {
        if doc.get_attribute(sc, "Method") != Some(BEARER) {
            continue;
        }
        let Some(data) = child(doc, sc, NS_SAML, "SubjectConfirmationData") else {
            continue;
        };
        let recipient_ok = doc.get_attribute(data, "Recipient") == Some(acs);
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

    let Some(conditions) = child(doc, assertion, NS_SAML, "Conditions") else {
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
        if !doc.child_elements_by_name_ns(ar, NS_SAML, "Audience").into_iter().any(|a| text(doc, a) == sp) {
            err!("SAML Assertion audience does not include this server")
        }
    }

    // Attributes
    let mut email: Option<String> = None;
    let mut user_name: Option<String> = None;
    if let Some(stmt) = child(doc, assertion, NS_SAML, "AttributeStatement") {
        for attr in doc.child_elements_by_name_ns(stmt, NS_SAML, "Attribute") {
            let name = doc.get_attribute(attr, "Name").unwrap_or_default().to_lowercase();
            let friendly = doc.get_attribute(attr, "FriendlyName").unwrap_or_default().to_lowercase();
            let value = doc.child_elements_by_name_ns(attr, NS_SAML, "AttributeValue").first().map(|v| text(doc, *v));
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

pub struct LogoutRequestInfo {
    pub id: String,
    pub name_id: String,
}

fn check_logout_common(doc: &Document<'_>, xml: &str, root: NodeId) -> ApiResult<()> {
    if !verified_nodes(doc, xml)?.contains(&root) {
        err!("SAML logout message must be signed by the IdP")
    }
    let idp_entity = CONFIG.sso_saml_idp_entity_id();
    if child(doc, root, NS_SAML, "Issuer").map(|i| text(doc, i)).as_deref() != Some(idp_entity.as_str()) {
        err!("SAML logout Issuer does not match SSO_SAML_IDP_ENTITY_ID")
    }
    let slo = slo_url();
    if let Some(d) = doc.get_attribute(root, "Destination")
        && d != slo
    {
        err!("SAML logout Destination does not match this server")
    }
    let now = Utc::now();
    let skew = chrono::TimeDelta::try_seconds(CLOCK_SKEW_SECS).unwrap();
    match doc.get_attribute(root, "IssueInstant") {
        Some(t) => {
            let t = parse_time(t)?;
            if t > now + skew || t < now - chrono::TimeDelta::try_minutes(10).unwrap() {
                err!("SAML logout message IssueInstant out of range")
            }
        }
        None => err!("SAML logout message has no IssueInstant"),
    }
    Ok(())
}

/// Verify an IdP-initiated LogoutRequest (HTTP-POST binding, signed by the IdP).
pub fn verify_logout_request(b64: &str) -> ApiResult<LogoutRequestInfo> {
    let xml = decode_post_message(b64)?;
    let doc = match uppsala::parse(&xml) {
        Ok(d) => d,
        Err(e) => err!(format!("SAML LogoutRequest is not well-formed XML: {e}")),
    };
    let Some(root) = doc.document_element() else {
        err!("Empty SAML LogoutRequest")
    };
    if !elem_is(&doc, root, NS_SAMLP, "LogoutRequest") {
        err!("SAML message is not a LogoutRequest")
    }
    check_logout_common(&doc, &xml, root)?;
    if let Some(na) = doc.get_attribute(root, "NotOnOrAfter")
        && parse_time(na)? <= Utc::now() - chrono::TimeDelta::try_seconds(CLOCK_SKEW_SECS).unwrap()
    {
        err!("SAML LogoutRequest expired")
    }
    let Some(id) = doc.get_attribute(root, "ID").map(str::to_owned) else {
        err!("SAML LogoutRequest has no ID")
    };
    let Some(nid) = child(&doc, root, NS_SAML, "NameID").map(|n| text(&doc, n)).filter(|n| !n.is_empty()) else {
        err!("SAML LogoutRequest has no NameID (encrypted NameIDs are not supported)")
    };
    Ok(LogoutRequestInfo {
        id,
        name_id: nid,
    })
}

/// Verify the IdP's LogoutResponse to our SP-initiated LogoutRequest.
pub fn verify_logout_response(b64: &str) -> ApiResult<()> {
    let xml = decode_post_message(b64)?;
    let doc = match uppsala::parse(&xml) {
        Ok(d) => d,
        Err(e) => err!(format!("SAML LogoutResponse is not well-formed XML: {e}")),
    };
    let Some(root) = doc.document_element() else {
        err!("Empty SAML LogoutResponse")
    };
    if !elem_is(&doc, root, NS_SAMLP, "LogoutResponse") {
        err!("SAML message is not a LogoutResponse")
    }
    check_logout_common(&doc, &xml, root)?;
    let status_ok = child(&doc, root, NS_SAMLP, "Status")
        .and_then(|s| child(&doc, s, NS_SAMLP, "StatusCode"))
        .and_then(|c| doc.get_attribute(c, "Value"))
        == Some(STATUS_SUCCESS);
    if !status_ok {
        err!("SAML LogoutResponse status is not Success")
    }
    Ok(())
}

/// The `sso_users.identifier` used for a SAML NameID.
pub fn identifier_for(name_id: &str) -> OIDCIdentifier {
    OIDCIdentifier::new(&format!("saml:{}", CONFIG.sso_saml_idp_entity_id()), name_id)
}

/// Recover the NameID from a stored SAML identifier.
pub fn name_id_from_identifier(identifier: &str) -> Option<String> {
    identifier.strip_prefix(&format!("saml:{}/", CONFIG.sso_saml_idp_entity_id())).map(str::to_owned)
}
