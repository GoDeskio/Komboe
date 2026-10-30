//! Komboe additions (AGPL-3.0). Original code, not from Bitwarden or Vaultwarden.
//!
//! * Family / company plans: seat limits, an admin overview of members that never exposes
//!   vault contents, per-member pricing hooks (billing provider is a stub until a Stripe
//!   *test* key is configured), and admin-approved split-off into a new family.
//! * A SimpleLogin-compatible alias API so the stock "forwarded email" generator works
//!   against the Komboe server.
//!
//! Zero-knowledge is preserved: the server never receives keys or plaintext vault data.
//! Split-off completion requires the member to create the new organization client-side
//! (org key generated and wrapped in the browser); the server only moves membership.
use chrono::{NaiveDateTime, Utc};
use diesel::prelude::*;
use rocket::{Route, http::Status, request::{FromRequest, Outcome, Request}, serde::json::Json};
use serde_json::Value;

use crate::{
    CONFIG,
    api::{EmptyResult, JsonResult},
    auth::Headers,
    crypto,
    db::{
        DbConn,
        models::{Cipher, Membership, MembershipStatus, MembershipType, Organization, OrganizationId, TwoFactor, User, UserId},
        schema::{komboe_alias_keys, komboe_aliases, komboe_org_plans, komboe_split_requests},
    },
    error::MapResult,
    util::get_uuid,
};

pub fn routes() -> Vec<Route> {
    routes![
        get_plan, put_plan, get_members, get_quote, create_split, list_splits, approve_split, deny_split,
        complete_split, new_alias_key, sl_user_info, sl_random_alias, sl_custom_alias, sl_list_aliases,
        sl_delete_alias, sl_toggle_alias, family_console, family_console_js, family_console_css
    ]
}

fn now() -> NaiveDateTime {
    Utc::now().naive_utc()
}

// ---------------------------------------------------------------- plans

#[derive(Queryable, Insertable, AsChangeset, Clone)]
#[diesel(table_name = komboe_org_plans)]
pub struct OrgPlan {
    pub org_uuid: String,
    pub kind: String,
    pub seats: i32,
    pub price_cents: i32,
    pub parent_org_uuid: Option<String>,
    pub updated_at: NaiveDateTime,
}

const DEFAULT_FAMILY_SEATS: i32 = 6;
const DEFAULT_FAMILY_PRICE_CENTS: i32 = 100; // per member per month; placeholder until pricing is decided

impl OrgPlan {
    pub async fn find(org: &str, conn: &DbConn) -> Option<Self> {
        let org = org.to_string();
        conn.run(move |c| komboe_org_plans::table.filter(komboe_org_plans::org_uuid.eq(org)).first::<Self>(c).ok()).await
    }
    async fn save(self, conn: &DbConn) -> EmptyResult {
        conn.run(move |c| {
            diesel::delete(komboe_org_plans::table.filter(komboe_org_plans::org_uuid.eq(&self.org_uuid))).execute(c)?;
            diesel::insert_into(komboe_org_plans::table).values(&self).execute(c)
        })
        .await
        .map_res("Error saving plan")
    }
    fn to_json(&self, used: i64) -> Value {
        json!({ "organizationId": self.org_uuid, "kind": self.kind, "seats": self.seats, "seatsUsed": used,
                "pricePerMemberCents": self.price_cents, "parentOrganizationId": self.parent_org_uuid,
                "object": "komboePlan" })
    }
}

/// Members that occupy a seat (everyone except revoked).
async fn seats_used(org: &OrganizationId, conn: &DbConn) -> i64 {
    Membership::find_by_org(org, conn).await.iter().filter(|m| m.status != MembershipStatus::Revoked as i32).count() as i64
}

/// Called from the invite route: refuse invites that would exceed the plan's seat limit.
pub async fn check_seats(org: &OrganizationId, adding: usize, conn: &DbConn) -> EmptyResult {
    if let Some(plan) = OrgPlan::find(org, conn).await {
        let used = seats_used(org, conn).await;
        if used + adding as i64 > plan.seats as i64 {
            err!(format!("Seat limit reached: {used} of {} seats used on this {} plan.", plan.seats, plan.kind))
        }
    }
    Ok(())
}

async fn membership(user: &UserId, org: &OrganizationId, conn: &DbConn) -> Option<Membership> {
    Membership::find_by_user_and_org(user, org, conn).await.filter(|m| m.status == MembershipStatus::Confirmed as i32)
}

async fn require_admin(user: &UserId, org: &OrganizationId, conn: &DbConn) -> Result<Membership, crate::error::Error> {
    match membership(user, org, conn).await {
        Some(m) if m.atype == MembershipType::Owner as i32 || m.atype == MembershipType::Admin as i32 => Ok(m),
        Some(_) => err_code!("Only organization owners and admins can do this.", 403),
        None => err_code!("Organization not found.", 404),
    }
}

#[get("/komboe/organizations/<org_id>/plan")]
async fn get_plan(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    if membership(&headers.user.uuid, &org_id, &conn).await.is_none() {
        err_code!("Organization not found.", 404)
    }
    let used = seats_used(&org_id, &conn).await;
    match OrgPlan::find(&org_id, &conn).await {
        Some(p) => Ok(Json(p.to_json(used))),
        None => Ok(Json(json!({ "organizationId": org_id, "kind": "none", "seats": null, "seatsUsed": used, "object": "komboePlan" }))),
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PlanData {
    kind: String,
    seats: Option<i32>,
    price_per_member_cents: Option<i32>,
}

#[put("/komboe/organizations/<org_id>/plan", data = "<data>")]
async fn put_plan(org_id: OrganizationId, data: Json<PlanData>, headers: Headers, conn: DbConn) -> JsonResult {
    let m = require_admin(&headers.user.uuid, &org_id, &conn).await?;
    if m.atype != MembershipType::Owner as i32 {
        err_code!("Only the owner can change the plan.", 403)
    }
    let d = data.into_inner();
    if d.kind != "family" && d.kind != "company" {
        err!("kind must be \"family\" or \"company\"")
    }
    let seats = d.seats.unwrap_or(if d.kind == "family" { DEFAULT_FAMILY_SEATS } else { 25 });
    let used = seats_used(&org_id, &conn).await;
    if seats < 1 || (seats as i64) < used {
        err!(format!("Seats must be at least the {used} members already in the organization."))
    }
    let parent = OrgPlan::find(&org_id, &conn).await.and_then(|p| p.parent_org_uuid);
    let plan = OrgPlan { org_uuid: org_id.to_string(), kind: d.kind, seats,
        price_cents: d.price_per_member_cents.unwrap_or(DEFAULT_FAMILY_PRICE_CENTS).max(0), parent_org_uuid: parent, updated_at: now() };
    plan.clone().save(&conn).await?;
    Ok(Json(plan.to_json(used)))
}

/// Admin overview of sub-accounts. Deliberately returns account metadata only:
/// no ciphers, no keys, no names of items. Personal vault contents stay unreadable.
#[get("/komboe/organizations/<org_id>/members")]
async fn get_members(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    require_admin(&headers.user.uuid, &org_id, &conn).await?;
    let mut out = Vec::new();
    for m in Membership::find_by_org(&org_id, &conn).await {
        let Some(u) = User::find_by_uuid(&m.user_uuid, &conn).await else { continue };
        let tfa = TwoFactor::find_by_user(&u.uuid, &conn).await.iter().any(|t| t.enabled && t.atype < 1000);
        out.push(json!({
            "membershipId": m.uuid, "userId": u.uuid, "email": u.email, "name": u.name,
            "type": m.atype, "status": m.status, "twoFactorEnabled": tfa,
            "personalItemCount": Cipher::count_owned_by_user(&u.uuid, &conn).await,
            "accountCreated": u.created_at.and_utc().to_rfc3339(), "lastActivity": u.updated_at.and_utc().to_rfc3339(),
            "vaultReadable": false,
        }));
    }
    Ok(Json(json!({ "data": out, "object": "list", "note": "Komboe is zero-knowledge: admins see account metadata, never vault contents." })))
}

/// Pricing hook. The billing provider is a stub unless STRIPE_SECRET_KEY holds a *test* key.
#[get("/komboe/organizations/<org_id>/billing/quote")]
async fn get_quote(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    require_admin(&headers.user.uuid, &org_id, &conn).await?;
    let Some(plan) = OrgPlan::find(&org_id, &conn).await else { err!("No Komboe plan set for this organization.") };
    let used = seats_used(&org_id, &conn).await;
    let key = std::env::var("STRIPE_SECRET_KEY").unwrap_or_default();
    let (provider, status) = if key.starts_with("sk_test_") {
        ("stripe-test", "test mode key present; checkout not yet implemented")
    } else if key.starts_with("sk_live_") || key.starts_with("rk_live_") {
        ("disabled", "live Stripe keys are refused: Komboe billing runs in test mode only")
    } else {
        ("stub", "needs Stripe test key")
    };
    Ok(Json(json!({
        "organizationId": org_id, "kind": plan.kind, "seats": plan.seats, "seatsUsed": used,
        "pricePerMemberCents": plan.price_cents, "monthlyTotalCents": used * plan.price_cents as i64,
        "currency": "usd", "provider": provider, "providerStatus": status, "object": "komboeQuote"
    })))
}

// ---------------------------------------------------------------- split-off

#[derive(Queryable, Insertable, AsChangeset, Clone)]
#[diesel(table_name = komboe_split_requests)]
pub struct SplitRequest {
    pub uuid: String,
    pub org_uuid: String,
    pub user_uuid: String,
    pub status: String,
    pub note: Option<String>,
    pub new_org_uuid: Option<String>,
    pub decided_by: Option<String>,
    pub created_at: NaiveDateTime,
    pub decided_at: Option<NaiveDateTime>,
}

impl SplitRequest {
    async fn find(id: &str, conn: &DbConn) -> Option<Self> {
        let id = id.to_string();
        conn.run(move |c| komboe_split_requests::table.filter(komboe_split_requests::uuid.eq(id)).first::<Self>(c).ok()).await
    }
    async fn by_org(org: &str, conn: &DbConn) -> Vec<Self> {
        let org = org.to_string();
        conn.run(move |c| {
            komboe_split_requests::table.filter(komboe_split_requests::org_uuid.eq(org)).load::<Self>(c).unwrap_or_default()
        })
        .await
    }
    async fn save(self, conn: &DbConn) -> EmptyResult {
        conn.run(move |c| {
            diesel::delete(komboe_split_requests::table.filter(komboe_split_requests::uuid.eq(&self.uuid))).execute(c)?;
            diesel::insert_into(komboe_split_requests::table).values(&self).execute(c)
        })
        .await
        .map_res("Error saving split request")
    }
    async fn to_json(&self, conn: &DbConn) -> Value {
        let email = User::find_by_uuid(&UserId::from(self.user_uuid.clone()), conn).await.map(|u| u.email);
        json!({ "id": self.uuid, "organizationId": self.org_uuid, "userId": self.user_uuid, "email": email,
                "status": self.status, "note": self.note, "newOrganizationId": self.new_org_uuid,
                "createdAt": self.created_at.and_utc().to_rfc3339(), "object": "komboeSplitRequest" })
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SplitData {
    note: Option<String>,
}

/// A member asks to leave with their personal vault and start their own family.
#[post("/komboe/organizations/<org_id>/split-requests", data = "<data>")]
async fn create_split(org_id: OrganizationId, data: Json<SplitData>, headers: Headers, conn: DbConn) -> JsonResult {
    let Some(m) = membership(&headers.user.uuid, &org_id, &conn).await else { err_code!("Organization not found.", 404) };
    if m.atype == MembershipType::Owner as i32 {
        err!("Owners cannot split off; transfer ownership first.")
    }
    if SplitRequest::by_org(&org_id, &conn).await.iter().any(|r| r.user_uuid == *headers.user.uuid && (r.status == "pending" || r.status == "approved")) {
        err!("You already have an open split-off request.")
    }
    let r = SplitRequest { uuid: get_uuid(), org_uuid: org_id.to_string(), user_uuid: headers.user.uuid.to_string(),
        status: "pending".into(), note: data.into_inner().note.map(|n| n.chars().take(500).collect()), new_org_uuid: None,
        decided_by: None, created_at: now(), decided_at: None };
    r.clone().save(&conn).await?;
    Ok(Json(r.to_json(&conn).await))
}

#[get("/komboe/organizations/<org_id>/split-requests")]
async fn list_splits(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    let Some(m) = membership(&headers.user.uuid, &org_id, &conn).await else { err_code!("Organization not found.", 404) };
    let admin = m.atype == MembershipType::Owner as i32 || m.atype == MembershipType::Admin as i32;
    let mut out = Vec::new();
    for r in SplitRequest::by_org(&org_id, &conn).await {
        if admin || r.user_uuid == *headers.user.uuid {
            out.push(r.to_json(&conn).await);
        }
    }
    Ok(Json(json!({ "data": out, "object": "list" })))
}

async fn decide(id: &str, approve: bool, headers: &Headers, conn: &DbConn) -> JsonResult {
    let Some(mut r) = SplitRequest::find(id, conn).await else { err_code!("Request not found.", 404) };
    require_admin(&headers.user.uuid, &OrganizationId::from(r.org_uuid.clone()), conn).await?;
    if r.status != "pending" {
        err!("This request was already decided.")
    }
    if r.user_uuid == *headers.user.uuid {
        err!("You cannot approve your own split-off request.")
    }
    r.status = if approve { "approved" } else { "denied" }.into();
    r.decided_by = Some(headers.user.uuid.to_string());
    r.decided_at = Some(now());
    r.clone().save(conn).await?;
    Ok(Json(r.to_json(conn).await))
}

#[post("/komboe/split-requests/<id>/approve")]
async fn approve_split(id: &str, headers: Headers, conn: DbConn) -> JsonResult {
    decide(id, true, &headers, &conn).await
}

#[post("/komboe/split-requests/<id>/deny")]
async fn deny_split(id: &str, headers: Headers, conn: DbConn) -> JsonResult {
    decide(id, false, &headers, &conn).await
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct CompleteData {
    new_organization_id: OrganizationId,
}

/// Finish an approved split-off. The member has already created `newOrganizationId`
/// client-side (keys generated in their browser) and is its confirmed owner.
/// The server marks it a family plan, then removes the member from the old organization.
/// Their personal vault is untouched; organization-owned items stay with the old organization.
#[post("/komboe/split-requests/<id>/complete", data = "<data>")]
async fn complete_split(id: &str, data: Json<CompleteData>, headers: Headers, conn: DbConn) -> JsonResult {
    let Some(mut r) = SplitRequest::find(id, &conn).await else { err_code!("Request not found.", 404) };
    if r.user_uuid != *headers.user.uuid {
        err_code!("Request not found.", 404)
    }
    if r.status != "approved" {
        err!("This split-off has not been approved by an organization admin.")
    }
    let new_org = data.into_inner().new_organization_id;
    if *new_org == r.org_uuid || Organization::find_by_uuid(&new_org, &conn).await.is_none() {
        err!("New organization not found.")
    }
    match membership(&headers.user.uuid, &new_org, &conn).await {
        Some(m) if m.atype == MembershipType::Owner as i32 => {}
        _ => err!("You must be the owner of the new organization."),
    }
    if Membership::find_by_org(&new_org, &conn).await.len() != 1 {
        err!("The new organization must be newly created (only you as a member).")
    }
    let old_org = OrganizationId::from(r.org_uuid.clone());
    OrgPlan { org_uuid: new_org.to_string(), kind: "family".into(), seats: DEFAULT_FAMILY_SEATS,
        price_cents: OrgPlan::find(&old_org, &conn).await.map(|p| p.price_cents).unwrap_or(DEFAULT_FAMILY_PRICE_CENTS),
        parent_org_uuid: Some(r.org_uuid.clone()), updated_at: now() }
    .save(&conn)
    .await?;
    if let Some(old) = Membership::find_by_user_and_org(&headers.user.uuid, &old_org, &conn).await {
        old.delete(&conn).await?;
    }
    User::update_uuid_revision(&headers.user.uuid, &conn).await;
    r.status = "completed".into();
    r.new_org_uuid = Some(new_org.to_string());
    r.clone().save(&conn).await?;
    Ok(Json(r.to_json(&conn).await))
}

// ---------------------------------------------------------------- aliases (SimpleLogin-compatible subset)

#[derive(Queryable, Insertable, Clone)]
#[diesel(table_name = komboe_aliases)]
pub struct Alias {
    pub uuid: String,
    pub user_uuid: String,
    pub email: String,
    pub note: Option<String>,
    pub hostname: Option<String>,
    pub enabled: bool,
    pub created_at: NaiveDateTime,
}

impl Alias {
    fn to_json(&self) -> Value {
        json!({ "id": self.uuid, "email": self.email, "alias": self.email, "enabled": self.enabled, "note": self.note,
                "name": null, "creation_date": self.created_at.and_utc().to_rfc3339(),
                "creation_timestamp": self.created_at.and_utc().timestamp(), "nb_forward": 0, "nb_block": 0, "nb_reply": 0 })
    }
}

fn alias_domain() -> String {
    std::env::var("KOMBOE_ALIAS_DOMAIN").unwrap_or_else(|_| "alias.komboe.localhost".into())
}

/// Create (or rotate) the caller's alias API key. Shown once; only its SHA-256 is stored.
#[post("/komboe/alias/api-key")]
async fn new_alias_key(headers: Headers, conn: DbConn) -> JsonResult {
    let key = format!("kmb_{}", crypto::get_random_string_alphanum(40));
    let (uid, hash) = (headers.user.uuid.to_string(), crypto::sha256_hex(key.as_bytes()));
    conn.run(move |c| {
        diesel::delete(komboe_alias_keys::table.filter(komboe_alias_keys::user_uuid.eq(&uid))).execute(c)?;
        diesel::insert_into(komboe_alias_keys::table)
            .values((komboe_alias_keys::user_uuid.eq(uid), komboe_alias_keys::key_hash.eq(hash), komboe_alias_keys::created_at.eq(now())))
            .execute(c)
    })
    .await
    .map(|_| ()).map_res("Error saving alias key")?;
    Ok(Json(json!({ "apiKey": key, "baseUrl": CONFIG.domain(), "aliasDomain": alias_domain(), "object": "komboeAliasKey" })))
}

/// SimpleLogin clients send the key in the `Authentication` header.
pub struct AliasUser(User);

#[rocket::async_trait]
impl<'r> FromRequest<'r> for AliasUser {
    type Error = &'static str;
    async fn from_request(req: &'r Request<'_>) -> Outcome<Self, Self::Error> {
        let Some(key) = req.headers().get_one("Authentication") else { return Outcome::Error((Status::Unauthorized, "missing key")) };
        let hash = crypto::sha256_hex(key.trim().as_bytes());
        let Outcome::Success(conn) = req.guard::<DbConn>().await else { return Outcome::Error((Status::ServiceUnavailable, "db")) };
        let uid = conn.run(move |c| {
            komboe_alias_keys::table.filter(komboe_alias_keys::key_hash.eq(hash)).select(komboe_alias_keys::user_uuid).first::<String>(c).ok()
        })
        .await;
        match uid {
            Some(u) => match User::find_by_uuid(&UserId::from(u), &conn).await {
                Some(user) if user.enabled => Outcome::Success(AliasUser(user)),
                _ => Outcome::Error((Status::Unauthorized, "invalid key")),
            },
            None => Outcome::Error((Status::Unauthorized, "invalid key")),
        }
    }
}

#[get("/user_info")]
async fn sl_user_info(u: AliasUser) -> Json<Value> {
    Json(json!({ "name": u.0.name, "email": u.0.email, "is_premium": true, "in_trial": false, "max_alias_free_plan": null }))
}

#[derive(Deserialize, Default)]
struct AliasNote {
    note: Option<String>,
}

async fn create_alias(user: &User, local: String, note: Option<String>, hostname: Option<String>, conn: &DbConn) -> Result<Alias, crate::error::Error> {
    let a = Alias { uuid: get_uuid(), user_uuid: user.uuid.to_string(), email: format!("{local}@{}", alias_domain()),
        note: note.map(|n| n.chars().take(500).collect()), hostname: hostname.map(|h| h.chars().take(253).collect()), enabled: true, created_at: now() };
    let ins = a.clone();
    conn.run(move |c| diesel::insert_into(komboe_aliases::table).values(&ins).execute(c)).await.map(|_| ()).map_res("Alias already exists")?;
    Ok(a)
}

#[post("/alias/random/new?<hostname>", data = "<data>")]
async fn sl_random_alias(hostname: Option<String>, data: Option<Json<AliasNote>>, u: AliasUser, conn: DbConn) -> Result<(Status, Json<Value>), crate::error::Error> {
    let local = format!("{}.{}", crypto::get_random_string(b"abcdefghijklmnopqrstuvwxyz", 8), crypto::get_random_string_numeric(4));
    let a = create_alias(&u.0, local, data.and_then(|d| d.into_inner().note), hostname, &conn).await?;
    Ok((Status::Created, Json(a.to_json())))
}

#[derive(Deserialize)]
struct CustomAlias {
    alias_prefix: String,
    note: Option<String>,
}

#[post("/v3/alias/custom/new?<hostname>", data = "<data>")]
async fn sl_custom_alias(hostname: Option<String>, data: Json<CustomAlias>, u: AliasUser, conn: DbConn) -> Result<(Status, Json<Value>), crate::error::Error> {
    let d = data.into_inner();
    let prefix: String = d.alias_prefix.to_lowercase().chars().filter(|c| c.is_ascii_alphanumeric() || *c == '.' || *c == '-' || *c == '_').take(40).collect();
    if prefix.is_empty() {
        err!("alias_prefix is required")
    }
    let local = format!("{prefix}.{}", crypto::get_random_string_numeric(4));
    let a = create_alias(&u.0, local, d.note, hostname, &conn).await?;
    Ok((Status::Created, Json(a.to_json())))
}

#[get("/v2/aliases?<page_id>")]
async fn sl_list_aliases(page_id: Option<i64>, u: AliasUser, conn: DbConn) -> Json<Value> {
    let uid = u.0.uuid.to_string();
    let page = page_id.unwrap_or(0).max(0);
    let list = conn.run(move |c| {
        komboe_aliases::table.filter(komboe_aliases::user_uuid.eq(uid)).order(komboe_aliases::created_at.desc())
            .offset(page * 20).limit(20).load::<Alias>(c).unwrap_or_default()
    })
    .await;
    Json(json!({ "aliases": list.iter().map(Alias::to_json).collect::<Vec<_>>() }))
}

async fn own_alias(id: &str, u: &AliasUser, conn: &DbConn) -> Option<Alias> {
    let (id, uid) = (id.to_string(), u.0.uuid.to_string());
    conn.run(move |c| komboe_aliases::table.filter(komboe_aliases::uuid.eq(id)).filter(komboe_aliases::user_uuid.eq(uid)).first::<Alias>(c).ok()).await
}

#[delete("/aliases/<id>")]
async fn sl_delete_alias(id: &str, u: AliasUser, conn: DbConn) -> JsonResult {
    let Some(a) = own_alias(id, &u, &conn).await else { err_code!("Alias not found", 404) };
    conn.run(move |c| diesel::delete(komboe_aliases::table.filter(komboe_aliases::uuid.eq(a.uuid))).execute(c)).await.map(|_| ()).map_res("Error deleting alias")?;
    Ok(Json(json!({ "deleted": true })))
}

#[post("/aliases/<id>/toggle")]
async fn sl_toggle_alias(id: &str, u: AliasUser, conn: DbConn) -> JsonResult {
    let Some(a) = own_alias(id, &u, &conn).await else { err_code!("Alias not found", 404) };
    let enabled = !a.enabled;
    conn.run(move |c| diesel::update(komboe_aliases::table.filter(komboe_aliases::uuid.eq(a.uuid))).set(komboe_aliases::enabled.eq(enabled)).execute(c))
        .await
        .map(|_| ()).map_res("Error updating alias")?;
    Ok(Json(json!({ "enabled": enabled })))
}

// ---------------------------------------------------------------- family console (static, client-side crypto)
#[get("/komboe/family-console")]
fn family_console() -> rocket::response::content::RawHtml<&'static str> {
    rocket::response::content::RawHtml(include_str!("../../static/komboe/family.html"))
}
#[get("/komboe/family-console.js")]
fn family_console_js() -> rocket::response::content::RawJavaScript<&'static str> {
    rocket::response::content::RawJavaScript(include_str!("../../static/komboe/family.js"))
}
#[get("/komboe/family-console.css")]
fn family_console_css() -> rocket::response::content::RawCss<&'static str> {
    rocket::response::content::RawCss(include_str!("../../static/komboe/family.css"))
}
