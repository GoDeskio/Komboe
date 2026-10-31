//! Clean-room SCIM 2.0 provider (RFC 7643 / 7644).
//!
//! The bearer token identifies one organization. Creating a user invites that
//! person into the organization. Deprovisioning revokes the membership. The
//! server never receives or stores a vault key, a master-password hash, or an
//! organization encryption key for a provisioned account.

use chrono::Utc;
use diesel::prelude::*;
use rocket::{
    Request, Route,
    data::{Data, ToByteUnit},
    http::Status,
    request::{FromRequest, Outcome},
    response::{self, Responder},
    serde::json::{Json, Value, json},
};

use crate::{
    CONFIG,
    api::{EmptyResult, JsonResult},
    auth::Headers,
    crypto,
    db::{
        DbConn,
        models::{
            Group, GroupId, GroupUser, Invitation, Membership, MembershipId, MembershipStatus, MembershipType,
            Organization, OrganizationId, User,
        },
        schema::komboe_scim_tokens,
    },
    mail,
};

const USER_SCHEMA: &str = "urn:ietf:params:scim:schemas:core:2.0:User";
const GROUP_SCHEMA: &str = "urn:ietf:params:scim:schemas:core:2.0:Group";
const LIST_SCHEMA: &str = "urn:ietf:params:scim:api:messages:2.0:ListResponse";
const ERROR_SCHEMA: &str = "urn:ietf:params:scim:api:messages:2.0:Error";

pub fn admin_routes() -> Vec<Route> {
    routes![get_scim, post_scim_token, delete_scim_token]
}

pub fn provider_routes() -> Vec<Route> {
    routes![
        service_provider_config,
        resource_types,
        list_users,
        get_user,
        create_user,
        replace_user,
        patch_user,
        delete_user,
        list_groups,
        get_group,
        create_group,
        replace_group,
        delete_group,
    ]
}

#[derive(Queryable, Insertable, Clone)]
#[diesel(table_name = komboe_scim_tokens)]
struct ScimToken {
    org_uuid: String,
    token_hash: String,
    created_at: chrono::NaiveDateTime,
}

struct ScimAuth(OrganizationId);

#[rocket::async_trait]
impl<'r> FromRequest<'r> for ScimAuth {
    type Error = ();

    async fn from_request(request: &'r Request<'_>) -> Outcome<Self, ()> {
        let Some(header) = request.headers().get_one("Authorization") else {
            return Outcome::Error((Status::Unauthorized, ()));
        };
        let Some(token) = header.strip_prefix("Bearer ") else {
            return Outcome::Error((Status::Unauthorized, ()));
        };
        let token = token.trim();
        if token.len() < 20 || token.len() > 200 {
            return Outcome::Error((Status::Unauthorized, ()));
        }
        let hash = crypto::sha256_hex(token.as_bytes());
        let Outcome::Success(conn) = DbConn::from_request(request).await else {
            return Outcome::Error((Status::ServiceUnavailable, ()));
        };
        let found = conn
            .run(move |c| {
                komboe_scim_tokens::table
                    .filter(komboe_scim_tokens::token_hash.eq(hash))
                    .select(komboe_scim_tokens::org_uuid)
                    .first::<String>(c)
                    .ok()
            })
            .await;
        match found {
            Some(id) => Outcome::Success(ScimAuth(OrganizationId::from(id))),
            None => Outcome::Error((Status::Unauthorized, ())),
        }
    }
}

#[allow(variant_size_differences)]
enum ScimResp {
    Body(Status, Box<Json<Value>>),
    Empty(Status),
}

impl<'r> Responder<'r, 'static> for ScimResp {
    fn respond_to(self, request: &'r Request<'_>) -> response::Result<'static> {
        match self {
            ScimResp::Body(status, body) => response::status::Custom(status, *body).respond_to(request),
            ScimResp::Empty(status) => status.respond_to(request),
        }
    }
}

fn scim_err(status: Status, detail: &str) -> ScimResp {
    ScimResp::Body(
        status,
        Box::new(Json(json!({
            "schemas": [ERROR_SCHEMA],
            "status": status.code.to_string(),
            "detail": detail,
        }))),
    )
}

fn ok(body: Value) -> ScimResp {
    ScimResp::Body(Status::Ok, Box::new(Json(body)))
}

async fn read_json(data: Data<'_>) -> Result<Value, ScimResp> {
    let capped = match data.open(1.mebibytes()).into_string().await {
        Ok(capped) => capped,
        Err(_) => return Err(scim_err(Status::BadRequest, "Could not read the request body")),
    };
    if !capped.is_complete() {
        return Err(scim_err(Status::PayloadTooLarge, "SCIM body is too large"));
    }
    serde_json::from_str(&capped.value).map_err(|_| scim_err(Status::BadRequest, "SCIM body is not JSON"))
}

async fn require_admin(headers: &Headers, org_id: &OrganizationId, conn: &DbConn) -> EmptyResult {
    let Some(member) = Membership::find_by_user_and_org(&headers.user.uuid, org_id, conn).await else {
        err!("Organization not found")
    };
    if member.status != MembershipStatus::Confirmed as i32 || member.atype > MembershipType::Admin as i32 {
        err!("Only an owner or admin can manage SCIM")
    }
    Ok(())
}

#[get("/organizations/<org_id>/scim")]
async fn get_scim(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    require_admin(&headers, &org_id, &conn).await?;
    let id = org_id.to_string();
    let enabled = conn
        .run(move |c| {
            komboe_scim_tokens::table
                .filter(komboe_scim_tokens::org_uuid.eq(id))
                .count()
                .get_result::<i64>(c)
                .unwrap_or(0)
                > 0
        })
        .await;
    Ok(Json(json!({ "enabled": enabled, "object": "scim" })))
}

#[post("/organizations/<org_id>/scim/token")]
async fn post_scim_token(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    require_admin(&headers, &org_id, &conn).await?;
    let token = format!("komboe-scim-{}", data_encoding::BASE64URL_NOPAD.encode(&crypto::get_random_bytes::<32>()));
    let row = ScimToken {
        org_uuid: org_id.to_string(),
        token_hash: crypto::sha256_hex(token.as_bytes()),
        created_at: Utc::now().naive_utc(),
    };
    if let Err(e) = conn
        .run(move |c| {
            diesel::delete(komboe_scim_tokens::table.filter(komboe_scim_tokens::org_uuid.eq(&row.org_uuid)))
                .execute(c)?;
            diesel::insert_into(komboe_scim_tokens::table).values(&row).execute(c)
        })
        .await
    {
        err!(format!("Error saving SCIM token: {e}"));
    }
    Ok(Json(json!({ "enabled": true, "token": token, "object": "scim" })))
}

#[delete("/organizations/<org_id>/scim/token")]
async fn delete_scim_token(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    require_admin(&headers, &org_id, &conn).await?;
    let id = org_id.to_string();
    if let Err(e) = conn
        .run(move |c| diesel::delete(komboe_scim_tokens::table.filter(komboe_scim_tokens::org_uuid.eq(id))).execute(c))
        .await
    {
        err!(format!("Error deleting SCIM token: {e}"));
    }
    Ok(Json(json!({ "enabled": false, "object": "scim" })))
}

fn location(kind: &str, id: &str) -> String {
    format!("{}/scim/v2/{kind}/{id}", CONFIG.domain().trim_end_matches('/'))
}

fn active(status: i32) -> bool {
    status >= MembershipStatus::Invited as i32
}

fn email_of(body: &Value) -> Option<String> {
    if let Some(emails) = body.get("emails").and_then(|v| v.as_array()) {
        let primary = emails.iter().find(|e| e.get("primary").and_then(|p| p.as_bool()).unwrap_or(false));
        let chosen = primary.or_else(|| emails.first());
        if let Some(value) = chosen.and_then(|e| e.get("value")).and_then(|v| v.as_str()) {
            let value = value.trim().to_lowercase();
            if value.contains('@') {
                return Some(value);
            }
        }
    }
    body.get("userName").and_then(|v| v.as_str()).map(|s| s.trim().to_lowercase()).filter(|s| s.contains('@'))
}

fn display_name(body: &Value, email: &str) -> String {
    if let Some(name) = body.get("name") {
        if let Some(formatted) = name.get("formatted").and_then(|v| v.as_str()).map(str::trim).filter(|s| !s.is_empty())
        {
            return formatted.to_string();
        }
        let given = name.get("givenName").and_then(|v| v.as_str()).unwrap_or("").trim();
        let family = name.get("familyName").and_then(|v| v.as_str()).unwrap_or("").trim();
        let joined = format!("{given} {family}").trim().to_string();
        if !joined.is_empty() {
            return joined;
        }
    }
    body.get("displayName")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or(email)
        .to_string()
}

fn external_id(body: &Value) -> Option<String> {
    body.get("externalId").and_then(|v| v.as_str()).map(str::trim).filter(|s| !s.is_empty()).map(str::to_string)
}

fn wants_active(body: &Value) -> bool {
    body.get("active").and_then(|v| v.as_bool()).unwrap_or(true)
}

async fn user_json(member: &Membership, conn: &DbConn) -> Result<Value, ScimResp> {
    let Some(user) = User::find_by_uuid(&member.user_uuid, conn).await else {
        return Err(scim_err(Status::NotFound, "User not found"));
    };
    let id = member.uuid.to_string();
    Ok(json!({
        "schemas": [USER_SCHEMA],
        "id": id,
        "externalId": member.external_id,
        "userName": user.email,
        "name": { "formatted": user.name },
        "emails": [{ "value": user.email, "primary": true }],
        "active": active(member.status),
        "meta": { "resourceType": "User", "location": location("Users", &id) }
    }))
}

async fn members_of(org: &OrganizationId, conn: &DbConn) -> Vec<Membership> {
    Membership::find_by_org(org, conn).await
}

fn eq_value(filter: &str, attr: &str) -> Option<String> {
    let mut parts = filter.trim().splitn(3, char::is_whitespace);
    let name = parts.next()?.trim();
    let op = parts.next()?.trim();
    let raw = parts.next()?.trim();
    if !name.eq_ignore_ascii_case(attr) || !op.eq_ignore_ascii_case("eq") {
        return None;
    }
    Some(raw.trim_matches('"').trim().to_string())
}

fn page<'a, T>(items: &'a [T], start_index: Option<i64>, count: Option<i64>) -> (i64, &'a [T]) {
    let start = start_index.unwrap_or(1).max(1) as usize;
    let count = count.unwrap_or(100).clamp(0, 200) as usize;
    let offset = start - 1;
    let slice = if offset >= items.len() {
        &[]
    } else {
        &items[offset..]
    };
    let slice = if slice.len() > count {
        &slice[..count]
    } else {
        slice
    };
    (start as i64, slice)
}

#[get("/v2/ServiceProviderConfig")]
fn service_provider_config(_auth: ScimAuth) -> ScimResp {
    ok(json!({
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": { "supported": true },
        "bulk": { "supported": false, "maxOperations": 0, "maxPayloadSize": 0 },
        "filter": { "supported": true, "maxResults": 200 },
        "changePassword": { "supported": false },
        "sort": { "supported": false },
        "etag": { "supported": false },
        "authenticationSchemes": [{
            "type": "oauthbearertoken",
            "name": "Bearer token",
            "description": "Organization SCIM bearer token"
        }]
    }))
}

#[get("/v2/ResourceTypes")]
fn resource_types(_auth: ScimAuth) -> ScimResp {
    ok(json!({
        "schemas": [LIST_SCHEMA],
        "totalResults": 2,
        "Resources": [
            { "id": "User", "name": "User", "endpoint": "/Users", "schema": USER_SCHEMA },
            { "id": "Group", "name": "Group", "endpoint": "/Groups", "schema": GROUP_SCHEMA }
        ]
    }))
}

#[derive(FromForm)]
struct ScimList {
    filter: Option<String>,
    #[field(name = "startIndex")]
    start_index: Option<i64>,
    count: Option<i64>,
}

#[get("/v2/Users?<list..>")]
async fn list_users(auth: ScimAuth, list: ScimList, conn: DbConn) -> ScimResp {
    let mut members = members_of(&auth.0, &conn).await;
    if let Some(filter) = list.filter.as_deref() {
        if let Some(email) = eq_value(filter, "userName") {
            let email = email.to_lowercase();
            let mut kept = Vec::new();
            for member in members {
                if let Some(user) = User::find_by_uuid(&member.user_uuid, &conn).await
                    && user.email == email
                {
                    kept.push(member);
                }
            }
            members = kept;
        } else if let Some(ext) = eq_value(filter, "externalId") {
            members.retain(|m| m.external_id.as_deref() == Some(ext.as_str()));
        } else {
            return scim_err(Status::BadRequest, "Unsupported filter");
        }
    }
    let total = members.len();
    let (start, slice) = page(&members, list.start_index, list.count);
    let mut resources = Vec::new();
    for member in slice {
        match user_json(member, &conn).await {
            Ok(value) => resources.push(value),
            Err(err) => return err,
        }
    }
    ok(json!({
        "schemas": [LIST_SCHEMA],
        "totalResults": total,
        "startIndex": start,
        "itemsPerPage": resources.len(),
        "Resources": resources,
    }))
}

#[get("/v2/Users/<id>")]
async fn get_user(auth: ScimAuth, id: &str, conn: DbConn) -> ScimResp {
    let Some(member) = Membership::find_by_uuid_and_org(&MembershipId::from(id.to_string()), &auth.0, &conn).await
    else {
        return scim_err(Status::NotFound, "User not found");
    };
    match user_json(&member, &conn).await {
        Ok(value) => ok(value),
        Err(err) => err,
    }
}

async fn provision(org_id: &OrganizationId, body: &Value, conn: &DbConn) -> Result<Membership, ScimResp> {
    let Some(email) = email_of(body) else {
        return Err(scim_err(Status::BadRequest, "userName or emails must contain an email address"));
    };
    let name = display_name(body, &email);
    let external = external_id(body);
    let make_active = wants_active(body);

    if let Some(mut member) = Membership::find_by_email_and_org(&email, org_id, conn).await {
        if member.atype != MembershipType::Owner as i32 {
            if make_active {
                member.restore();
            } else {
                member.revoke();
            }
        } else if !make_active {
            return Err(scim_err(Status::BadRequest, "The organization owner cannot be deprovisioned"));
        }
        member.set_external_id(external);
        member.save(conn).await.map_err(|_| scim_err(Status::InternalServerError, "Could not update the member"))?;
        if let Some(mut user) = User::find_by_uuid(&member.user_uuid, conn).await {
            user.name = name;
            user.save(conn).await.map_err(|_| scim_err(Status::InternalServerError, "Could not update the user"))?;
        }
        return Ok(member);
    }

    let mut created = false;
    let user = if let Some(user) = User::find_by_mail(&email, conn).await {
        user
    } else {
        let mut user = User::new(&email, Some(name));
        user.save(conn).await.map_err(|_| scim_err(Status::InternalServerError, "Could not create the user"))?;
        if !CONFIG.mail_enabled() {
            drop(Invitation::new(&user.email).save(conn).await);
        }
        created = true;
        user
    };

    let status = if CONFIG.mail_enabled() || user.password_hash.is_empty() {
        MembershipStatus::Invited as i32
    } else {
        MembershipStatus::Accepted as i32
    };
    let Some(org) = Organization::find_by_uuid(org_id, conn).await else {
        return Err(scim_err(Status::NotFound, "Organization not found"));
    };
    let mut member = Membership::new(user.uuid.clone(), org_id.clone(), Some(org.billing_email.clone()));
    member.access_all = false;
    member.atype = MembershipType::User as i32;
    member.status = status;
    member.set_external_id(external);
    if !make_active {
        member.revoke();
    }
    if let Err(e) = member.save(conn).await {
        if created {
            drop(user.delete(conn).await);
        }
        return Err(scim_err(Status::InternalServerError, &format!("Could not create the membership: {e}")));
    }
    if CONFIG.mail_enabled()
        && let Err(e) =
            mail::send_invite(&user, org_id.clone(), member.uuid.clone(), &org.name, Some(org.billing_email)).await
    {
        if created {
            drop(user.delete(conn).await);
        } else {
            drop(member.delete(conn).await);
        }
        return Err(scim_err(Status::InternalServerError, &format!("Could not send the invite: {e:?}")));
    }
    Ok(member)
}

#[post("/v2/Users", data = "<data>")]
async fn create_user(auth: ScimAuth, data: Data<'_>, conn: DbConn) -> ScimResp {
    let body = match read_json(data).await {
        Ok(body) => body,
        Err(err) => return err,
    };
    let email = email_of(&body);
    if let Some(email) = email.as_deref()
        && let Some(existing) = Membership::find_by_email_and_org(email, &auth.0, &conn).await
        && active(existing.status)
    {
        return scim_err(Status::Conflict, "A user with that email is already in the organization");
    }
    let member = match provision(&auth.0, &body, &conn).await {
        Ok(member) => member,
        Err(err) => return err,
    };
    match user_json(&member, &conn).await {
        Ok(value) => ScimResp::Body(Status::Created, Box::new(Json(value))),
        Err(err) => err,
    }
}

async fn load_member(auth: &ScimAuth, id: &str, conn: &DbConn) -> Result<Membership, ScimResp> {
    Membership::find_by_uuid_and_org(&MembershipId::from(id.to_string()), &auth.0, conn)
        .await
        .ok_or_else(|| scim_err(Status::NotFound, "User not found"))
}

fn apply_active(member: &mut Membership, make_active: bool) -> Result<(), ScimResp> {
    if member.atype == MembershipType::Owner as i32 && !make_active {
        return Err(scim_err(Status::BadRequest, "The organization owner cannot be deprovisioned"));
    }
    if member.atype != MembershipType::Owner as i32 {
        if make_active {
            member.restore();
        } else {
            member.revoke();
        }
    }
    Ok(())
}

#[put("/v2/Users/<id>", data = "<data>")]
async fn replace_user(auth: ScimAuth, id: &str, data: Data<'_>, conn: DbConn) -> ScimResp {
    let body = match read_json(data).await {
        Ok(body) => body,
        Err(err) => return err,
    };
    let mut member = match load_member(&auth, id, &conn).await {
        Ok(member) => member,
        Err(err) => return err,
    };
    if let Some(email) = email_of(&body)
        && let Some(user) = User::find_by_uuid(&member.user_uuid, &conn).await
        && user.email != email
    {
        return scim_err(Status::BadRequest, "SCIM cannot change an account email");
    }
    if let Err(err) = apply_active(&mut member, wants_active(&body)) {
        return err;
    }
    member.set_external_id(external_id(&body));
    if member.save(&conn).await.is_err() {
        return scim_err(Status::InternalServerError, "Could not update the member");
    }
    if let Some(mut user) = User::find_by_uuid(&member.user_uuid, &conn).await {
        user.name = display_name(&body, &user.email);
        if user.save(&conn).await.is_err() {
            return scim_err(Status::InternalServerError, "Could not update the user");
        }
    }
    match user_json(&member, &conn).await {
        Ok(value) => ok(value),
        Err(err) => err,
    }
}

fn patch_active(body: &Value) -> Option<bool> {
    let ops = body.get("Operations").and_then(|v| v.as_array())?;
    for op in ops {
        let name = op.get("op").and_then(|v| v.as_str()).unwrap_or("").to_ascii_lowercase();
        if name != "replace" && name != "add" {
            continue;
        }
        let path = op.get("path").and_then(|v| v.as_str()).unwrap_or("");
        if path.eq_ignore_ascii_case("active")
            && let Some(value) = op.get("value").and_then(|v| v.as_bool())
        {
            return Some(value);
        }
        if path.is_empty()
            && let Some(value) = op.get("value").and_then(|v| v.get("active")).and_then(|v| v.as_bool())
        {
            return Some(value);
        }
    }
    None
}

#[patch("/v2/Users/<id>", data = "<data>")]
async fn patch_user(auth: ScimAuth, id: &str, data: Data<'_>, conn: DbConn) -> ScimResp {
    let body = match read_json(data).await {
        Ok(body) => body,
        Err(err) => return err,
    };
    let mut member = match load_member(&auth, id, &conn).await {
        Ok(member) => member,
        Err(err) => return err,
    };
    let Some(make_active) = patch_active(&body) else {
        return scim_err(Status::BadRequest, "Only the active attribute can be patched");
    };
    if let Err(err) = apply_active(&mut member, make_active) {
        return err;
    }
    if member.save(&conn).await.is_err() {
        return scim_err(Status::InternalServerError, "Could not update the member");
    }
    match user_json(&member, &conn).await {
        Ok(value) => ok(value),
        Err(err) => err,
    }
}

#[delete("/v2/Users/<id>")]
async fn delete_user(auth: ScimAuth, id: &str, conn: DbConn) -> ScimResp {
    let mut member = match load_member(&auth, id, &conn).await {
        Ok(member) => member,
        Err(err) => return err,
    };
    if let Err(err) = apply_active(&mut member, false) {
        return err;
    }
    if member.save(&conn).await.is_err() {
        return scim_err(Status::InternalServerError, "Could not revoke the member");
    }
    ScimResp::Empty(Status::NoContent)
}

async fn group_json(group: &Group, conn: &DbConn) -> Value {
    let links = GroupUser::find_by_group(&group.uuid, &group.organizations_uuid, conn).await;
    let mut members = Vec::new();
    for link in links {
        let mut entry = json!({ "value": link.users_organizations_uuid.to_string() });
        if let Some(member) = Membership::find_by_uuid(&link.users_organizations_uuid, conn).await
            && let Some(user) = User::find_by_uuid(&member.user_uuid, conn).await
        {
            entry["display"] = json!(user.email);
        }
        members.push(entry);
    }
    let id = group.uuid.to_string();
    json!({
        "schemas": [GROUP_SCHEMA],
        "id": id,
        "displayName": group.name,
        "externalId": group.external_id,
        "members": members,
        "meta": { "resourceType": "Group", "location": location("Groups", &id) }
    })
}

fn member_ids(body: &Value) -> Vec<String> {
    body.get("members")
        .and_then(|v| v.as_array())
        .map(|items| {
            items.iter().filter_map(|item| item.get("value").and_then(|v| v.as_str()).map(str::to_string)).collect()
        })
        .unwrap_or_default()
}

async fn set_group_members(group: &Group, ids: &[String], conn: &DbConn) -> Result<(), ScimResp> {
    GroupUser::delete_all_by_group(&group.uuid, &group.organizations_uuid, conn)
        .await
        .map_err(|_| scim_err(Status::InternalServerError, "Could not update group members"))?;
    for id in ids {
        let Some(member) =
            Membership::find_by_uuid_and_org(&MembershipId::from(id.clone()), &group.organizations_uuid, conn).await
        else {
            return Err(scim_err(Status::BadRequest, "Group member is not in this organization"));
        };
        let mut link = GroupUser::new(group.uuid.clone(), member.uuid);
        link.save(conn).await.map_err(|_| scim_err(Status::InternalServerError, "Could not add the group member"))?;
    }
    Ok(())
}

#[get("/v2/Groups?<list..>")]
async fn list_groups(auth: ScimAuth, list: ScimList, conn: DbConn) -> ScimResp {
    if !CONFIG.org_groups_enabled() {
        return scim_err(Status::NotFound, "Groups are disabled");
    }
    let mut groups = Group::find_by_organization(&auth.0, &conn).await;
    if let Some(filter) = list.filter.as_deref() {
        if let Some(name) = eq_value(filter, "displayName") {
            groups.retain(|g| g.name.eq_ignore_ascii_case(&name));
        } else if let Some(ext) = eq_value(filter, "externalId") {
            groups.retain(|g| g.external_id.as_deref() == Some(ext.as_str()));
        } else {
            return scim_err(Status::BadRequest, "Unsupported filter");
        }
    }
    let total = groups.len();
    let (start, slice) = page(&groups, list.start_index, list.count);
    let mut resources = Vec::new();
    for group in slice {
        resources.push(group_json(group, &conn).await);
    }
    ok(json!({
        "schemas": [LIST_SCHEMA],
        "totalResults": total,
        "startIndex": start,
        "itemsPerPage": resources.len(),
        "Resources": resources,
    }))
}

#[get("/v2/Groups/<id>")]
async fn get_group(auth: ScimAuth, id: &str, conn: DbConn) -> ScimResp {
    let Some(group) = Group::find_by_uuid_and_org(&GroupId::from(id.to_string()), &auth.0, &conn).await else {
        return scim_err(Status::NotFound, "Group not found");
    };
    ok(group_json(&group, &conn).await)
}

#[post("/v2/Groups", data = "<data>")]
async fn create_group(auth: ScimAuth, data: Data<'_>, conn: DbConn) -> ScimResp {
    if !CONFIG.org_groups_enabled() {
        return scim_err(Status::NotFound, "Groups are disabled");
    }
    let body = match read_json(data).await {
        Ok(body) => body,
        Err(err) => return err,
    };
    let Some(name) = body.get("displayName").and_then(|v| v.as_str()).map(str::trim).filter(|s| !s.is_empty()) else {
        return scim_err(Status::BadRequest, "displayName is required");
    };
    let mut group = Group::new(auth.0.clone(), name.to_string(), false, external_id(&body));
    if group.save(&conn).await.is_err() {
        return scim_err(Status::InternalServerError, "Could not create the group");
    }
    if let Err(err) = set_group_members(&group, &member_ids(&body), &conn).await {
        drop(group.delete(&auth.0, &conn).await);
        return err;
    }
    ScimResp::Body(Status::Created, Box::new(Json(group_json(&group, &conn).await)))
}

#[put("/v2/Groups/<id>", data = "<data>")]
async fn replace_group(auth: ScimAuth, id: &str, data: Data<'_>, conn: DbConn) -> ScimResp {
    let body = match read_json(data).await {
        Ok(body) => body,
        Err(err) => return err,
    };
    let Some(mut group) = Group::find_by_uuid_and_org(&GroupId::from(id.to_string()), &auth.0, &conn).await else {
        return scim_err(Status::NotFound, "Group not found");
    };
    if let Some(name) = body.get("displayName").and_then(|v| v.as_str()).map(str::trim).filter(|s| !s.is_empty()) {
        group.name = name.to_string();
    }
    group.set_external_id(external_id(&body));
    group.access_all = false;
    if group.save(&conn).await.is_err() {
        return scim_err(Status::InternalServerError, "Could not update the group");
    }
    if let Err(err) = set_group_members(&group, &member_ids(&body), &conn).await {
        return err;
    }
    ok(group_json(&group, &conn).await)
}

#[delete("/v2/Groups/<id>")]
async fn delete_group(auth: ScimAuth, id: &str, conn: DbConn) -> ScimResp {
    let Some(group) = Group::find_by_uuid_and_org(&GroupId::from(id.to_string()), &auth.0, &conn).await else {
        return scim_err(Status::NotFound, "Group not found");
    };
    if group.delete(&auth.0, &conn).await.is_err() {
        return scim_err(Status::InternalServerError, "Could not delete the group");
    }
    ScimResp::Empty(Status::NoContent)
}
