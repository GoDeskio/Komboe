//! Clean-room Komboe security, billing, and secrets-manager APIs.
//! This module contains no Bitwarden licensed-server source or vault decryption logic.
use std::{
    collections::HashMap,
    net::IpAddr,
    sync::{LazyLock, Mutex},
    time::Duration,
};

use chrono::{NaiveDateTime, TimeDelta, Utc};
use data_encoding::{BASE64URL_NOPAD, HEXLOWER};
use diesel::prelude::*;
use ring::{
    digest, hmac,
    rand::{SecureRandom, SystemRandom},
};
use rocket::{
    Data, Route,
    data::ToByteUnit,
    http::Status,
    request::{FromRequest, Outcome, Request},
    serde::json::Json,
};
use serde_json::Value;
use tokio::io::AsyncWriteExt;

use crate::{
    api::{EmptyResult, JsonResult},
    auth::Headers,
    db::{
        DbConn,
        models::{
            Cipher, Event, Membership, MembershipStatus, MembershipType, OrganizationId, TwoFactor, User, UserId,
        },
        schema::{
            komboe_anomalies, komboe_billing, komboe_org_plans, komboe_projects, komboe_secrets,
            komboe_service_accounts, komboe_siem_configs,
        },
    },
    error::MapResult,
    util::get_uuid,
};

pub fn routes() -> Vec<Route> {
    routes![
        put_siem,
        get_siem,
        test_siem,
        list_anomalies,
        risk_report,
        billing_quote,
        billing_checkout,
        stripe_webhook,
        create_project,
        list_projects,
        create_secret,
        list_secrets,
        create_service_account,
        revoke_service_account,
        service_list_secrets,
        service_get_secret,
    ]
}

fn now() -> NaiveDateTime {
    Utc::now().naive_utc()
}

fn sha256_hex(value: &[u8]) -> String {
    HEXLOWER.encode(digest::digest(&digest::SHA256, value).as_ref())
}

fn ct_hmac(secret: &[u8], input: &[u8], expected_hex: &str) -> bool {
    let Ok(expected) = HEXLOWER.decode(expected_hex.as_bytes()) else {
        return false;
    };
    hmac::verify(&hmac::Key::new(hmac::HMAC_SHA256, secret), input, &expected).is_ok()
}

// ---- SIEM -----------------------------------------------------------------

#[derive(Queryable, Insertable, AsChangeset, Clone)]
#[diesel(table_name = komboe_siem_configs)]
struct SiemConfig {
    org_uuid: String,
    kind: String,
    endpoint: String,
    hmac_secret: Option<String>,
    enabled: bool,
    updated_at: NaiveDateTime,
}

static SIEM: LazyLock<Mutex<HashMap<String, SiemConfig>>> = LazyLock::new(|| Mutex::new(HashMap::new()));

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SiemData {
    kind: String,
    endpoint: String,
    hmac_secret: Option<String>,
    enabled: Option<bool>,
}

fn validate_siem(d: &SiemData) -> EmptyResult {
    let local_http = d.endpoint.starts_with("http://127.0.0.1:")
        || d.endpoint.starts_with("http://[::1]:")
        || d.endpoint.starts_with("http://localhost:");
    match d.kind.as_str() {
        "webhook" if d.endpoint.starts_with("https://") || local_http => {
            let parsed = reqwest::Url::parse(&d.endpoint)
                .map_err(|e| crate::error::Error::new("Invalid SIEM webhook URL", e.to_string()))?;
            if parsed.host_str().is_none() {
                err!("SIEM webhook URL needs a host.")
            }
            if d.hmac_secret.as_deref().is_none_or(|s| !(16..=4096).contains(&s.len())) {
                err!("Webhook HMAC secret must be between 16 and 4096 characters.")
            }
            if d.endpoint.split("//").nth(1).and_then(|s| s.split('/').next()).is_some_and(|s| s.contains('@')) {
                err!("Credentials are not allowed in a SIEM endpoint URL.")
            }
        }
        "syslog" if d.endpoint.starts_with("tcp://") || d.endpoint.starts_with("tls://") => {
            let parsed = reqwest::Url::parse(&d.endpoint)
                .map_err(|e| crate::error::Error::new("Invalid SIEM syslog URL", e.to_string()))?;
            if parsed.host_str().is_none() || parsed.port().is_none() || parsed.path() != "" {
                err!("SIEM syslog URL must be host:port with no path.")
            }
        }
        _ => err!("kind/endpoint must be webhook https:// or syslog tcp:// or tls://"),
    }
    if d.endpoint.len() > 2048 {
        err!("SIEM endpoint is too long.")
    }
    Ok(())
}

#[put("/komboe/organizations/<org_id>/siem", data = "<data>")]
async fn put_siem(org_id: OrganizationId, data: Json<SiemData>, headers: Headers, conn: DbConn) -> JsonResult {
    if super::komboe::require_admin(&headers.user.uuid, &org_id, &conn).await.is_err() {
        err_code!("Organization not found.", 404)
    }
    validate_siem(&data)?;
    let row = SiemConfig {
        org_uuid: org_id.to_string(),
        kind: data.kind.clone(),
        endpoint: data.endpoint.clone(),
        hmac_secret: data.hmac_secret.clone(),
        enabled: data.enabled.unwrap_or(true),
        updated_at: now(),
    };
    let save = row.clone();
    conn.run(move |c| {
        diesel::delete(komboe_siem_configs::table.filter(komboe_siem_configs::org_uuid.eq(&save.org_uuid)))
            .execute(c)?;
        diesel::insert_into(komboe_siem_configs::table).values(&save).execute(c)
    })
    .await
    .map(|_| ()).map_res("Error saving SIEM configuration")?;
    SIEM.lock().unwrap().insert(row.org_uuid.clone(), row.clone());
    Ok(Json(siem_json(&row)))
}

fn siem_json(c: &SiemConfig) -> Value {
    json!({"organizationId": c.org_uuid, "kind": c.kind, "endpoint": c.endpoint,
    "enabled": c.enabled, "hmacConfigured": c.hmac_secret.is_some(), "object": "komboeSiemConfig"})
}

#[get("/komboe/organizations/<org_id>/siem")]
async fn get_siem(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    if super::komboe::require_admin(&headers.user.uuid, &org_id, &conn).await.is_err() {
        err_code!("Organization not found.", 404)
    }
    let id = org_id.to_string();
    let row = conn
        .run(move |c| {
            komboe_siem_configs::table.filter(komboe_siem_configs::org_uuid.eq(id)).first::<SiemConfig>(c).ok()
        })
        .await;
    let Some(row) = row else {
        err_code!("SIEM configuration not found.", 404)
    };
    SIEM.lock().unwrap().insert(row.org_uuid.clone(), row.clone());
    Ok(Json(siem_json(&row)))
}

#[post("/komboe/organizations/<org_id>/siem/test")]
async fn test_siem(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    if super::komboe::require_admin(&headers.user.uuid, &org_id, &conn).await.is_err() {
        err_code!("Organization not found.", 404)
    }
    let _cfg = get_siem(org_id.clone(), headers, conn).await?;
    let payload = json!({"schema":"komboe.siem.v1", "eventType":1600, "organizationId":org_id,
        "actingUserId":null, "deviceType":null, "ipAddress":null, "date":Utc::now().to_rfc3339(), "test":true});
    export_payload(&org_id, payload).await?;
    Ok(Json(json!({"sent":true})))
}

pub async fn export(events: &[Event], conn: &DbConn) {
    for event in events {
        let Some(org) = event.org_uuid.as_ref() else {
            continue;
        };
        let id = org.to_string();
        let config = conn
            .run(move |c| {
                komboe_siem_configs::table.filter(komboe_siem_configs::org_uuid.eq(id)).first::<SiemConfig>(c).ok()
            })
            .await;
        let Some(config) = config.filter(|c| c.enabled) else {
            continue;
        };
        SIEM.lock().unwrap().insert(config.org_uuid.clone(), config);
        let org = org.clone();
        let payload = json!({"schema":"komboe.siem.v1", "eventType":event.event_type, "organizationId":org,
            "actingUserId":&event.act_user_uuid, "deviceType":event.device_type, "ipAddress":&event.ip_address,
            "date":event.event_date.and_utc().to_rfc3339()});
        tokio::spawn(async move {
            if let Err(e) = export_payload(&org, payload).await {
                warn!("SIEM export failed: {e:#?}");
            }
        });
    }
}

async fn export_payload(org: &OrganizationId, payload: Value) -> EmptyResult {
    let config = SIEM.lock().unwrap().get(&org.to_string()).cloned();
    let Some(c) = config.filter(|c| c.enabled) else {
        return Ok(());
    };
    let body = serde_json::to_vec(&payload)?;
    if c.kind == "webhook" {
        let secret =
            c.hmac_secret.ok_or_else(|| crate::error::Error::new("Missing SIEM HMAC secret", String::new()))?;
        let sig = HEXLOWER.encode(hmac::sign(&hmac::Key::new(hmac::HMAC_SHA256, secret.as_bytes()), &body).as_ref());
        let response = reqwest::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .map_res("SIEM webhook client failed")?
            .post(&c.endpoint)
            .header("X-Komboe-Signature", format!("sha256={sig}"))
            .header("Content-Type", "application/json")
            .body(body)
            .send()
            .await
            .map_res("SIEM webhook failed")?;
        if !response.status().is_success() {
            err!(format!("SIEM webhook returned {}", response.status()))
        }
    } else if let Some(target) = c.endpoint.strip_prefix("tcp://") {
        let mut stream = tokio::time::timeout(Duration::from_secs(5), tokio::net::TcpStream::connect(target))
            .await
            .map_err(|_| crate::error::Error::new("SIEM TCP connect timed out", String::new()))?
            .map_res("SIEM TCP connect failed")?;
        let msg =
            format!("<134>1 {} komboe komboe - KOMBOE - {}\n", Utc::now().to_rfc3339(), String::from_utf8_lossy(&body));
        stream.write_all(msg.as_bytes()).await.map_res("SIEM TCP write failed")?;
    } else {
        send_tls_syslog(c.endpoint.trim_start_matches("tls://"), &body).await?;
    }
    Ok(())
}

async fn send_tls_syslog(target: &str, body: &[u8]) -> EmptyResult {
    use std::io::Write;
    use std::net::ToSocketAddrs;
    let parsed = reqwest::Url::parse(&format!("https://{target}"))
        .map_err(|e| crate::error::Error::new("Invalid SIEM TLS target", e.to_string()))?;
    let host = parsed
        .host_str()
        .ok_or_else(|| crate::error::Error::new("TLS syslog needs a hostname", String::new()))?
        .to_owned();
    let port = parsed.port().ok_or_else(|| crate::error::Error::new("TLS syslog needs a port", String::new()))?;
    let target = if host.contains(':') { format!("[{host}]:{port}") } else { format!("{host}:{port}") };
    let msg =
        format!("<134>1 {} komboe komboe - KOMBOE - {}\n", Utc::now().to_rfc3339(), String::from_utf8_lossy(body));
    tokio::task::spawn_blocking(move || -> Result<(), std::io::Error> {
        let connector = openssl::ssl::SslConnector::builder(openssl::ssl::SslMethod::tls())
            .map_err(|e| std::io::Error::other(e.to_string()))?
            .build();
        let address = target
            .to_socket_addrs()?
            .next()
            .ok_or_else(|| std::io::Error::other("SIEM TLS address did not resolve"))?;
        let tcp = std::net::TcpStream::connect_timeout(&address, Duration::from_secs(5))?;
        tcp.set_write_timeout(Some(Duration::from_secs(5)))?;
        let mut tls = connector.connect(&host, tcp).map_err(|e| std::io::Error::other(e.to_string()))?;
        tls.write_all(msg.as_bytes())
    })
    .await
    .map_err(|e| crate::error::Error::new("SIEM TLS task failed", e.to_string()))??;
    Ok(())
}

// ---- Anomaly detection -----------------------------------------------------

#[derive(Queryable, Insertable)]
#[diesel(table_name = komboe_anomalies)]
struct Anomaly {
    uuid: String,
    user_uuid: String,
    kind: String,
    ip_prefix: String,
    device_id: Option<String>,
    detail: String,
    risk: i32,
    created_at: NaiveDateTime,
}

static LOGIN_STATE: LazyLock<Mutex<HashMap<String, (String, String, i64, u32)>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

fn ip_prefix(ip: IpAddr) -> String {
    match ip {
        IpAddr::V4(v) => {
            let o = v.octets();
            format!("{}.{}.{}.0/24", o[0], o[1], o[2])
        }
        IpAddr::V6(v) => {
            let s = v.segments();
            format!("{:x}:{:x}:{:x}:{:x}::/64", s[0], s[1], s[2], s[3])
        }
    }
}

pub async fn assess_login(user: &UserId, device: Option<&str>, ip: IpAddr, success: bool, conn: &DbConn) -> bool {
    let prefix = ip_prefix(ip);
    let device = device.unwrap_or("unknown").to_string();
    let ts = Utc::now().timestamp();
    let (kind, risk, detail) = {
        let mut states = LOGIN_STATE.lock().unwrap();
        let old = states.get(&user.to_string()).cloned();
        let failures = if success {
            0
        } else {
            old.as_ref().map_or(1, |x| x.3 + 1)
        };
        states.insert(user.to_string(), (device.clone(), prefix.clone(), ts, failures));
        match old {
            Some((od, op, ot, _)) if success && od != device && op != prefix => {
                ("new_device_and_network", 70, format!("new device and IP prefix; {}s since prior login", ts - ot))
            }
            Some((_, op, ot, _)) if success && op != prefix && ts - ot < 3600 => {
                ("impossible_travel", 80, "IP prefix changed within one hour".into())
            }
            _ if !success && failures == 5 => ("repeated_failures", 60, format!("{failures} consecutive failures")),
            _ => return false,
        }
    };
    let row = Anomaly {
        uuid: get_uuid(),
        user_uuid: user.to_string(),
        kind: kind.into(),
        ip_prefix: prefix,
        device_id: Some(device),
        detail,
        risk,
        created_at: now(),
    };
    let uid = row.user_uuid.clone();
    if conn.run(move |c| diesel::insert_into(komboe_anomalies::table).values(&row).execute(c)).await.is_ok() {
        super::komboe::notify_user(
            &uid,
            "Komboe detected an unusual sign-in",
            "Review your recent sign-ins and rotate your password if this was not you.",
            conn,
        )
        .await;
    }
    std::env::var("KOMBOE_ANOMALY_STEP_UP").is_ok_and(|v| v == "true") && risk >= 70
}

#[get("/komboe/anomalies")]
async fn list_anomalies(headers: Headers, conn: DbConn) -> JsonResult {
    let uid = headers.user.uuid.to_string();
    let rows = conn
        .run(move |c| {
            komboe_anomalies::table
                .filter(komboe_anomalies::user_uuid.eq(uid))
                .order(komboe_anomalies::created_at.desc())
                .limit(100)
                .load::<Anomaly>(c)
                .unwrap_or_default()
        })
        .await;
    Ok(Json(
        json!({"data":rows.into_iter().map(|a|json!({"id":a.uuid,"type":a.kind,"ipPrefix":a.ip_prefix,"deviceId":a.device_id,"detail":a.detail,"risk":a.risk,"createdAt":a.created_at.and_utc().to_rfc3339()})).collect::<Vec<_>>() }),
    ))
}

// ---- Access intelligence --------------------------------------------------

#[get("/komboe/organizations/<org_id>/risk-report")]
async fn risk_report(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    if super::komboe::require_admin(&headers.user.uuid, &org_id, &conn).await.is_err() {
        err_code!("Organization not found.", 404)
    }
    let mut no_2fa = Vec::new();
    let mut stale = Vec::new();
    let mut broad = Vec::new();
    for m in Membership::find_by_org(&org_id, &conn)
        .await
        .into_iter()
        .filter(|m| m.status == MembershipStatus::Confirmed as i32)
    {
        let Some(u) = User::find_by_uuid(&m.user_uuid, &conn).await else {
            continue;
        };
        if !TwoFactor::find_by_user(&u.uuid, &conn).await.iter().any(|t| t.enabled && t.atype < 1000) {
            no_2fa.push(u.uuid.clone())
        }
        if u.last_active(&conn).await.is_none_or(|d| d < now() - TimeDelta::try_days(90).unwrap()) {
            stale.push(u.uuid.clone())
        }
        if m.access_all && m.atype >= MembershipType::User as i32 {
            broad.push(u.uuid.clone())
        }
    }
    Ok(Json(json!({"organizationId":org_id,"generatedAt":Utc::now().to_rfc3339(),"metadataOnly":true,
        "membersWithout2fa":no_2fa,"staleMembers":stale,"overBroadCollectionAccess":broad,
        "sharedItemCount":Cipher::count_by_org(&org_id,&conn).await,"vaultDataRead":false})))
}

// ---- Billing --------------------------------------------------------------

#[derive(Queryable, Insertable, AsChangeset, Clone)]
#[diesel(table_name=komboe_billing)]
struct Billing {
    org_uuid: String,
    plan: String,
    billing_interval: String,
    status: String,
    stripe_customer_id: Option<String>,
    stripe_subscription_id: Option<String>,
    updated_at: NaiveDateTime,
}

fn require_test_key() -> EmptyResult {
    match std::env::var("STRIPE_SECRET_KEY") {
        Ok(k) if k.starts_with("sk_test_") => Ok(()),
        Ok(_) => err!("Stripe live/restricted keys are refused; use sk_test_."),
        Err(_) => err!("STRIPE_SECRET_KEY is not configured."),
    }
}

#[get("/komboe/organizations/<org_id>/billing")]
async fn billing_quote(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    if super::komboe::require_admin(&headers.user.uuid, &org_id, &conn).await.is_err() {
        err_code!("Organization not found.", 404)
    }
    let id = org_id.to_string();
    let b =
        conn.run(move |c| komboe_billing::table.filter(komboe_billing::org_uuid.eq(id)).first::<Billing>(c).ok()).await;
    Ok(Json(
        json!({"organizationId":org_id,"plan":b.as_ref().map_or("free",|x|x.plan.as_str()),"interval":b.as_ref().map_or("monthly",|x|x.billing_interval.as_str()),"status":b.as_ref().map_or("active",|x|x.status.as_str()),"freeSeats":3,"testMode":true}),
    ))
}

#[derive(Deserialize)]
struct CheckoutData {
    plan: String,
    interval: String,
}
#[post("/komboe/organizations/<org_id>/billing/checkout", data = "<data>")]
async fn billing_checkout(
    org_id: OrganizationId,
    data: Json<CheckoutData>,
    headers: Headers,
    conn: DbConn,
) -> JsonResult {
    if super::komboe::require_admin(&headers.user.uuid, &org_id, &conn).await.is_err() {
        err_code!("Organization not found.", 404)
    }
    require_test_key()?;
    if !["team", "business"].contains(&data.plan.as_str()) || !["monthly", "annual"].contains(&data.interval.as_str()) {
        err!("Invalid plan or billing interval.")
    }
    let b = Billing {
        org_uuid: org_id.to_string(),
        plan: data.plan.clone(),
        billing_interval: data.interval.clone(),
        status: "checkout_pending".into(),
        stripe_customer_id: None,
        stripe_subscription_id: None,
        updated_at: now(),
    };
    let save = b.clone();
    conn.run(move |c| {
        diesel::delete(komboe_billing::table.filter(komboe_billing::org_uuid.eq(&save.org_uuid))).execute(c)?;
        diesel::insert_into(komboe_billing::table).values(&save).execute(c)
    })
    .await
    .map(|_| ()).map_res("Error saving checkout")?;
    Ok(Json(
        json!({"id":format!("cs_test_{}",get_uuid().replace('-', "")),"mode":"subscription","testMode":true,"plan":b.plan,"interval":b.billing_interval}),
    ))
}

struct StripeSig(String);
#[rocket::async_trait]
impl<'r> FromRequest<'r> for StripeSig {
    type Error = ();
    async fn from_request(r: &'r Request<'_>) -> Outcome<Self, ()> {
        match r.headers().get_one("Stripe-Signature") {
            Some(v) => Outcome::Success(Self(v.into())),
            None => Outcome::Error((Status::BadRequest, ())),
        }
    }
}

#[post("/komboe/billing/stripe-webhook", data = "<data>")]
async fn stripe_webhook(sig: StripeSig, data: Data<'_>, conn: DbConn) -> JsonResult {
    require_test_key()?;
    let secret = std::env::var("STRIPE_WEBHOOK_SECRET")
        .map_err(|_| crate::error::Error::new("STRIPE_WEBHOOK_SECRET is not configured", String::new()))?;
    let body = data.open(1.mebibytes()).into_string().await.map_res("Invalid webhook body")?.into_inner();
    let mut t = None;
    let mut v1 = None;
    for p in sig.0.split(',') {
        if let Some(x) = p.strip_prefix("t=") {
            t = x.parse::<i64>().ok()
        }
        if let Some(x) = p.strip_prefix("v1=") {
            v1 = Some(x)
        }
    }
    let ts = t.ok_or_else(|| crate::error::Error::new("Invalid Stripe signature", String::new()))?;
    if (Utc::now().timestamp() - ts).abs() > 300 {
        err_code!("Stale Stripe signature.", 400)
    }
    let signed = format!("{ts}.{body}");
    if !ct_hmac(secret.as_bytes(), signed.as_bytes(), v1.unwrap_or("")) {
        err_code!("Invalid Stripe signature.", 400)
    }
    let event: Value = serde_json::from_str(&body)?;
    let obj = &event["data"]["object"];
    let org = obj["metadata"]["organization_id"]
        .as_str()
        .ok_or_else(|| crate::error::Error::new("Missing organization metadata", String::new()))?
        .to_string();
    let status = match event["type"].as_str().unwrap_or("") {
        "checkout.session.completed" | "customer.subscription.updated" => "active",
        "customer.subscription.deleted" => "canceled",
        _ => return Ok(Json(json!({"received":true,"ignored":true}))),
    };
    let id = org.clone();
    let plan_id = org.clone();
    let billing = conn
        .run(move |c| komboe_billing::table.filter(komboe_billing::org_uuid.eq(plan_id)).first::<Billing>(c).ok())
        .await;
    conn.run(move |c| {
        diesel::update(komboe_billing::table.filter(komboe_billing::org_uuid.eq(id)))
            .set((komboe_billing::status.eq(status), komboe_billing::updated_at.eq(now())))
            .execute(c)
    })
    .await
    .map(|_| ()).map_res("Error applying billing event")?;
    if status == "active" {
        let b = billing.ok_or_else(|| crate::error::Error::new("Checkout was not initialized", String::new()))?;
        let (seats, cents) = if b.plan == "business" {
            (100, 1200)
        } else {
            (25, 600)
        };
        super::komboe::OrgPlan {
            org_uuid: org.clone(),
            kind: b.plan,
            seats,
            price_cents: cents,
            parent_org_uuid: None,
            updated_at: now(),
        }
        .save(&conn)
        .await?;
    } else if status == "canceled" {
        let id = org.clone();
        conn.run(move |c| diesel::delete(komboe_org_plans::table.filter(komboe_org_plans::org_uuid.eq(id))).execute(c))
            .await
            .map(|_| ()).map_res("Error restoring free plan")?;
    }
    Ok(Json(json!({"received":true,"organizationId":org,"status":status})))
}

// ---- Secrets manager ------------------------------------------------------

#[derive(Queryable, Insertable)]
#[diesel(table_name=komboe_projects)]
struct Project {
    uuid: String,
    org_uuid: String,
    name: String,
    created_by: String,
    created_at: NaiveDateTime,
}
#[derive(Queryable, Insertable)]
#[diesel(table_name=komboe_secrets)]
struct Secret {
    uuid: String,
    project_uuid: String,
    name: String,
    ciphertext: String,
    created_by: String,
    created_at: NaiveDateTime,
    updated_at: NaiveDateTime,
}
#[derive(Queryable, Insertable)]
#[diesel(table_name=komboe_service_accounts)]
struct ServiceAccount {
    uuid: String,
    project_uuid: String,
    name: String,
    token_hash: String,
    created_by: String,
    created_at: NaiveDateTime,
    revoked_at: Option<NaiveDateTime>,
}
#[derive(Deserialize)]
struct NameData {
    name: String,
}
#[derive(Deserialize)]
struct SecretData {
    name: String,
    ciphertext: String,
}
fn valid_name(s: &str) -> bool {
    !s.trim().is_empty() && s.len() <= 200
}

#[post("/komboe/organizations/<org_id>/projects", data = "<data>")]
async fn create_project(
    org_id: OrganizationId,
    data: Json<NameData>,
    headers: Headers,
    conn: DbConn,
) -> JsonResult {
    if super::komboe::require_admin(&headers.user.uuid, &org_id, &conn).await.is_err() {
        err_code!("Organization not found.", 404)
    }
    if !valid_name(&data.name) {
        err!("Invalid project name.")
    }
    let p = Project {
        uuid: get_uuid(),
        org_uuid: org_id.to_string(),
        name: data.name.clone(),
        created_by: headers.user.uuid.to_string(),
        created_at: now(),
    };
    let out = json!({"id":p.uuid,"organizationId":p.org_uuid,"name":p.name});
    conn.run(move |c| diesel::insert_into(komboe_projects::table).values(&p).execute(c))
        .await
        .map(|_| ()).map_res("Error creating project")?;
    Ok(Json(out))
}

#[get("/komboe/organizations/<org_id>/projects")]
async fn list_projects(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    if super::komboe::require_admin(&headers.user.uuid, &org_id, &conn).await.is_err() {
        err_code!("Organization not found.", 404)
    }
    let id = org_id.to_string();
    let rows = conn
        .run(move |c| {
            komboe_projects::table.filter(komboe_projects::org_uuid.eq(id)).load::<Project>(c).unwrap_or_default()
        })
        .await;
    Ok(Json(json!({"data":rows.into_iter().map(|p|json!({"id":p.uuid,"name":p.name})).collect::<Vec<_>>() })))
}

async fn admin_project(id: &str, user: &UserId, conn: &DbConn) -> Result<Project, crate::error::Error> {
    let key = id.to_string();
    let Some(p) =
        conn.run(move |c| komboe_projects::table.filter(komboe_projects::uuid.eq(key)).first::<Project>(c).ok()).await
    else {
        err_code!("Project not found.", 404)
    };
    let org = OrganizationId::from(p.org_uuid.clone());
    let Some(m) = Membership::find_by_user_and_org(user, &org, conn).await else {
        err_code!("Project not found.", 404)
    };
    if m.atype > MembershipType::Admin as i32 {
        err_code!("Administrator access required.", 403)
    }
    Ok(p)
}

#[post("/komboe/projects/<project_id>/secrets", data = "<data>")]
async fn create_secret(project_id: &str, data: Json<SecretData>, headers: Headers, conn: DbConn) -> JsonResult {
    admin_project(project_id, &headers.user.uuid, &conn).await?;
    if !valid_name(&data.name) || data.ciphertext.len() < 16 || data.ciphertext.len() > 1_000_000 {
        err!("Invalid name or ciphertext.")
    }
    let s = Secret {
        uuid: get_uuid(),
        project_uuid: project_id.into(),
        name: data.name.clone(),
        ciphertext: data.ciphertext.clone(),
        created_by: headers.user.uuid.to_string(),
        created_at: now(),
        updated_at: now(),
    };
    let out = secret_json(&s);
    conn.run(move |c| diesel::insert_into(komboe_secrets::table).values(&s).execute(c))
        .await
        .map(|_| ()).map_res("Error creating secret")?;
    Ok(Json(out))
}
fn secret_json(s: &Secret) -> Value {
    json!({"id":s.uuid,"projectId":s.project_uuid,"name":s.name,"ciphertext":s.ciphertext,"createdAt":s.created_at.and_utc().to_rfc3339(),"serverCanDecrypt":false})
}

#[get("/komboe/projects/<project_id>/secrets")]
async fn list_secrets(project_id: &str, headers: Headers, conn: DbConn) -> JsonResult {
    admin_project(project_id, &headers.user.uuid, &conn).await?;
    Ok(Json(
        json!({"data":secrets_for(project_id,&conn).await.into_iter().map(|s|secret_json(&s)).collect::<Vec<_>>() }),
    ))
}
async fn secrets_for(id: &str, conn: &DbConn) -> Vec<Secret> {
    let id = id.to_string();
    conn.run(move |c| {
        komboe_secrets::table.filter(komboe_secrets::project_uuid.eq(id)).load::<Secret>(c).unwrap_or_default()
    })
    .await
}

fn random_token() -> Result<String, crate::error::Error> {
    let mut b = [0u8; 32];
    SystemRandom::new().fill(&mut b).map_err(|_| crate::error::Error::new("Random generator failed", String::new()))?;
    Ok(format!("ksm_{}", BASE64URL_NOPAD.encode(&b)))
}
#[post("/komboe/projects/<project_id>/service-accounts", data = "<data>")]
async fn create_service_account(project_id: &str, data: Json<NameData>, headers: Headers, conn: DbConn) -> JsonResult {
    admin_project(project_id, &headers.user.uuid, &conn).await?;
    if !valid_name(&data.name) {
        err!("Invalid service account name.")
    }
    let token = random_token()?;
    let s = ServiceAccount {
        uuid: get_uuid(),
        project_uuid: project_id.into(),
        name: data.name.clone(),
        token_hash: sha256_hex(token.as_bytes()),
        created_by: headers.user.uuid.to_string(),
        created_at: now(),
        revoked_at: None,
    };
    let id = s.uuid.clone();
    conn.run(move |c| diesel::insert_into(komboe_service_accounts::table).values(&s).execute(c))
        .await
        .map(|_| ()).map_res("Error creating service account")?;
    Ok(Json(json!({"id":id,"token":token,"warning":"This token is shown once; only its SHA-256 hash is stored."})))
}

#[delete("/komboe/projects/<project_id>/service-accounts/<account_id>")]
async fn revoke_service_account(project_id: &str, account_id: &str, headers: Headers, conn: DbConn) -> EmptyResult {
    admin_project(project_id, &headers.user.uuid, &conn).await?;
    let p = project_id.to_string();
    let a = account_id.to_string();
    conn.run(move |c| {
        diesel::update(
            komboe_service_accounts::table
                .filter(komboe_service_accounts::uuid.eq(a))
                .filter(komboe_service_accounts::project_uuid.eq(p)),
        )
        .set(komboe_service_accounts::revoked_at.eq(now()))
        .execute(c)
    })
    .await
    .map(|_| ()).map_res("Error revoking service account")?;
    Ok(())
}

struct ServiceToken(String);
#[rocket::async_trait]
impl<'r> FromRequest<'r> for ServiceToken {
    type Error = ();
    async fn from_request(r: &'r Request<'_>) -> Outcome<Self, ()> {
        match r.headers().get_one("Authorization").and_then(|v| v.strip_prefix("Bearer ksm_")) {
            Some(v) => Outcome::Success(Self(format!("ksm_{v}"))),
            None => Outcome::Error((Status::Unauthorized, ())),
        }
    }
}
async fn service_account(t: &ServiceToken, conn: &DbConn) -> Result<ServiceAccount, crate::error::Error> {
    let h = sha256_hex(t.0.as_bytes());
    conn.run(move |c| {
        komboe_service_accounts::table
            .filter(komboe_service_accounts::token_hash.eq(h))
            .filter(komboe_service_accounts::revoked_at.is_null())
            .first::<ServiceAccount>(c)
    })
    .await
    .map_res("Invalid service token")
}
#[get("/komboe/service/v1/secrets")]
async fn service_list_secrets(token: ServiceToken, conn: DbConn) -> JsonResult {
    let a = service_account(&token, &conn).await?;
    Ok(Json(
        json!({"data":secrets_for(&a.project_uuid,&conn).await.into_iter().map(|s|secret_json(&s)).collect::<Vec<_>>() }),
    ))
}
#[get("/komboe/service/v1/secrets/<secret_id>")]
async fn service_get_secret(secret_id: &str, token: ServiceToken, conn: DbConn) -> JsonResult {
    let a = service_account(&token, &conn).await?;
    let id = secret_id.to_string();
    let p = a.project_uuid;
    let s = conn
        .run(move |c| {
            komboe_secrets::table
                .filter(komboe_secrets::uuid.eq(id))
                .filter(komboe_secrets::project_uuid.eq(p))
                .first::<Secret>(c)
                .ok()
        })
        .await
        .ok_or_else(|| crate::error::Error::new("Secret not found", String::new()))?;
    Ok(Json(secret_json(&s)))
}
