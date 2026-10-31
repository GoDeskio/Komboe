//! Clean-room LDAP / Active Directory sync.
//!
//! The server binds to a directory the organization admin configured, reads
//! mail and group membership, and invites or revokes organization members.
//! It never reads `userPassword` and never stores a vault key.

use std::collections::{HashMap, HashSet};

use diesel::prelude::*;
use ldap3::{LdapConnAsync, Scope, SearchEntry};
use rocket::{Route, serde::json::Json};
use serde::Deserialize;

use crate::{
    CONFIG,
    api::JsonResult,
    auth::Headers,
    db::{
        DbConn,
        models::{
            Group, GroupUser, Invitation, Membership, MembershipStatus, MembershipType, Organization, OrganizationId,
            User,
        },
        schema::komboe_ldap_configs,
    },
    mail,
};

pub fn routes() -> Vec<Route> {
    routes![get_ldap, put_ldap, sync_ldap]
}

#[derive(Queryable, Insertable, AsChangeset, Clone)]
#[diesel(table_name = komboe_ldap_configs)]
struct LdapConfig {
    org_uuid: String,
    url: String,
    bind_dn: String,
    bind_password: String,
    user_base: String,
    user_filter: String,
    email_attr: String,
    group_base: String,
    group_filter: String,
    member_attr: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct LdapBody {
    url: String,
    bind_dn: String,
    bind_password: Option<String>,
    user_base: String,
    user_filter: Option<String>,
    email_attr: Option<String>,
    group_base: Option<String>,
    group_filter: Option<String>,
    member_attr: Option<String>,
}

struct DirectoryUser {
    external_id: String,
    email: String,
    name: String,
    dn: String,
}

struct DirectoryGroup {
    external_id: String,
    name: String,
    member_dns: Vec<String>,
}

fn require_admin(member: &Membership) -> crate::api::EmptyResult {
    if member.status != MembershipStatus::Confirmed as i32 || member.atype > MembershipType::Admin as i32 {
        err!("Only an owner or admin can manage directory sync")
    }
    Ok(())
}

fn check_url(url: &str) -> crate::api::EmptyResult {
    let lower = url.trim().to_ascii_lowercase();
    if lower.starts_with("ldap://") || lower.starts_with("ldaps://") {
        Ok(())
    } else {
        err!("Directory URL must start with ldap:// or ldaps://")
    }
}

async fn load(org_id: &OrganizationId, conn: &DbConn) -> Option<LdapConfig> {
    let id = org_id.to_string();
    conn.run(move |c| {
        komboe_ldap_configs::table.filter(komboe_ldap_configs::org_uuid.eq(id)).first::<LdapConfig>(c).ok()
    })
    .await
}

fn public_json(cfg: &LdapConfig) -> serde_json::Value {
    json!({
        "enabled": true,
        "url": cfg.url,
        "bindDn": cfg.bind_dn,
        "hasPassword": !cfg.bind_password.is_empty(),
        "userBase": cfg.user_base,
        "userFilter": cfg.user_filter,
        "emailAttr": cfg.email_attr,
        "groupBase": cfg.group_base,
        "groupFilter": cfg.group_filter,
        "memberAttr": cfg.member_attr,
        "object": "ldap"
    })
}

#[get("/organizations/<org_id>/ldap")]
async fn get_ldap(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    let Some(member) = Membership::find_by_user_and_org(&headers.user.uuid, &org_id, &conn).await else {
        err!("Organization not found")
    };
    require_admin(&member)?;
    match load(&org_id, &conn).await {
        Some(cfg) => Ok(Json(public_json(&cfg))),
        None => Ok(Json(json!({ "enabled": false, "object": "ldap" }))),
    }
}

#[put("/organizations/<org_id>/ldap", data = "<body>")]
async fn put_ldap(org_id: OrganizationId, body: Json<LdapBody>, headers: Headers, conn: DbConn) -> JsonResult {
    let Some(member) = Membership::find_by_user_and_org(&headers.user.uuid, &org_id, &conn).await else {
        err!("Organization not found")
    };
    require_admin(&member)?;
    let body = body.into_inner();
    check_url(&body.url)?;
    let existing = load(&org_id, &conn).await;
    let password = match body.bind_password.filter(|p| !p.is_empty()) {
        Some(password) => password,
        None => existing.as_ref().map(|c| c.bind_password.clone()).unwrap_or_default(),
    };
    if password.is_empty() || body.bind_dn.trim().is_empty() || body.user_base.trim().is_empty() {
        err!("Bind DN, bind password, and user base are required")
    }
    let row = LdapConfig {
        org_uuid: org_id.to_string(),
        url: body.url.trim().to_string(),
        bind_dn: body.bind_dn.trim().to_string(),
        bind_password: password,
        user_base: body.user_base.trim().to_string(),
        user_filter: body.user_filter.unwrap_or_else(|| "(objectClass=inetOrgPerson)".to_string()),
        email_attr: body.email_attr.unwrap_or_else(|| "mail".to_string()),
        group_base: body.group_base.unwrap_or_default(),
        group_filter: body.group_filter.unwrap_or_else(|| "(objectClass=groupOfNames)".to_string()),
        member_attr: body.member_attr.unwrap_or_else(|| "member".to_string()),
    };
    let saved = row.clone();
    if let Err(e) = conn
        .run(move |c| {
            diesel::delete(komboe_ldap_configs::table.filter(komboe_ldap_configs::org_uuid.eq(&row.org_uuid)))
                .execute(c)?;
            diesel::insert_into(komboe_ldap_configs::table).values(&row).execute(c)
        })
        .await
    {
        err!(format!("Error saving directory settings: {e}"));
    }
    Ok(Json(public_json(&saved)))
}

async fn directory(cfg: &LdapConfig) -> Result<(Vec<DirectoryUser>, Vec<DirectoryGroup>), String> {
    if cfg.url.to_ascii_lowercase().starts_with("ldaps://") {
        return Err("ldaps:// needs a TLS build of the directory client; use ldap:// on a trusted network".into());
    }
    let (conn, mut ldap) =
        LdapConnAsync::new(&cfg.url).await.map_err(|e| format!("Directory connection failed: {e}"))?;
    ldap3::drive!(conn);
    ldap.simple_bind(&cfg.bind_dn, &cfg.bind_password)
        .await
        .map_err(|e| format!("Directory bind failed: {e}"))?
        .success()
        .map_err(|e| format!("Directory bind was rejected: {e}"))?;

    let (entries, _) = ldap
        .search(&cfg.user_base, Scope::Subtree, &cfg.user_filter, vec![cfg.email_attr.as_str(), "cn", "entryUUID"])
        .await
        .map_err(|e| format!("User search failed: {e}"))?
        .success()
        .map_err(|e| format!("User search was rejected: {e}"))?;

    let mut users = Vec::new();
    for entry in entries {
        let entry = SearchEntry::construct(entry);
        let Some(email) = entry.attrs.get(&cfg.email_attr).and_then(|v| v.first()).map(|s| s.trim().to_lowercase())
        else {
            continue;
        };
        if !email.contains('@') {
            continue;
        }
        let name = entry.attrs.get("cn").and_then(|v| v.first()).cloned().unwrap_or_else(|| email.clone());
        let external_id =
            entry.attrs.get("entryUUID").and_then(|v| v.first()).cloned().unwrap_or_else(|| entry.dn.clone());
        users.push(DirectoryUser {
            external_id,
            email,
            name,
            dn: entry.dn.to_ascii_lowercase(),
        });
    }

    let mut groups = Vec::new();
    if !cfg.group_base.trim().is_empty() && CONFIG.org_groups_enabled() {
        let (entries, _) = ldap
            .search(&cfg.group_base, Scope::Subtree, &cfg.group_filter, vec![cfg.member_attr.as_str(), "cn"])
            .await
            .map_err(|e| format!("Group search failed: {e}"))?
            .success()
            .map_err(|e| format!("Group search was rejected: {e}"))?;
        for entry in entries {
            let entry = SearchEntry::construct(entry);
            let name = entry.attrs.get("cn").and_then(|v| v.first()).cloned().unwrap_or_else(|| entry.dn.clone());
            let member_dns = entry
                .attrs
                .get(&cfg.member_attr)
                .cloned()
                .unwrap_or_default()
                .into_iter()
                .map(|dn| dn.to_ascii_lowercase())
                .collect();
            groups.push(DirectoryGroup {
                external_id: entry.dn,
                name,
                member_dns,
            });
        }
    }
    drop(ldap.unbind().await);
    Ok((users, groups))
}

async fn invite(
    org: &Organization,
    email: &str,
    name: &str,
    external_id: &str,
    conn: &DbConn,
) -> Result<Membership, String> {
    if let Some(mut member) = Membership::find_by_email_and_org(email, &org.uuid, conn).await {
        if member.atype != MembershipType::Owner as i32 {
            member.restore();
        }
        member.set_external_id(Some(external_id.to_string()));
        member.save(conn).await.map_err(|e| format!("Could not update {email}: {e}"))?;
        return Ok(member);
    }
    let mut created = false;
    let user = if let Some(user) = User::find_by_mail(email, conn).await {
        user
    } else {
        let mut user = User::new(email, Some(name.to_string()));
        user.save(conn).await.map_err(|e| format!("Could not create {email}: {e}"))?;
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
    let mut member = Membership::new(user.uuid.clone(), org.uuid.clone(), Some(org.billing_email.clone()));
    member.access_all = false;
    member.atype = MembershipType::User as i32;
    member.status = status;
    member.set_external_id(Some(external_id.to_string()));
    if let Err(e) = member.save(conn).await {
        if created {
            drop(user.delete(conn).await);
        }
        return Err(format!("Could not invite {email}: {e}"));
    }
    if CONFIG.mail_enabled()
        && let Err(e) =
            mail::send_invite(&user, org.uuid.clone(), member.uuid.clone(), &org.name, Some(org.billing_email.clone()))
                .await
    {
        if created {
            drop(user.delete(conn).await);
        } else {
            drop(member.delete(conn).await);
        }
        return Err(format!("Could not send the invite: {e:?}"));
    }
    Ok(member)
}

#[post("/organizations/<org_id>/ldap/sync")]
async fn sync_ldap(org_id: OrganizationId, headers: Headers, conn: DbConn) -> JsonResult {
    let Some(member) = Membership::find_by_user_and_org(&headers.user.uuid, &org_id, &conn).await else {
        err!("Organization not found")
    };
    require_admin(&member)?;
    let Some(cfg) = load(&org_id, &conn).await else {
        err!("Directory sync is not configured")
    };
    let Some(org) = Organization::find_by_uuid(&org_id, &conn).await else {
        err!("Organization not found")
    };
    let (users, groups) = match directory(&cfg).await {
        Ok(found) => found,
        Err(detail) => err!(detail),
    };

    let mut dn_to_member: HashMap<String, Membership> = HashMap::new();
    let mut seen: HashSet<String> = HashSet::new();
    let mut invited = 0i64;
    for user in &users {
        let member = match invite(&org, &user.email, &user.name, &user.external_id, &conn).await {
            Ok(member) => member,
            Err(detail) => err!(detail),
        };
        if member.status == MembershipStatus::Invited as i32 || member.status == MembershipStatus::Accepted as i32 {
            invited += 1;
        }
        seen.insert(user.external_id.clone());
        dn_to_member.insert(user.dn.clone(), member);
    }

    let mut revoked = 0i64;
    for mut existing in Membership::find_by_org(&org_id, &conn).await {
        if existing.atype == MembershipType::Owner as i32 {
            continue;
        }
        if let Some(ext) = existing.external_id.clone()
            && !seen.contains(&ext)
            && existing.revoke()
        {
            existing.save(&conn).await?;
            revoked += 1;
        }
    }

    let mut group_count = 0i64;
    let mut seen_groups: HashSet<String> = HashSet::new();
    for group in &groups {
        seen_groups.insert(group.external_id.clone());
        let mut model =
            if let Some(existing) = Group::find_by_external_id_and_org(&group.external_id, &org_id, &conn).await {
                let mut existing = existing;
                existing.name = group.name.clone();
                existing.access_all = false;
                existing
            } else {
                Group::new(org_id.clone(), group.name.clone(), false, Some(group.external_id.clone()))
            };
        model.save(&conn).await?;
        GroupUser::delete_all_by_group(&model.uuid, &org_id, &conn).await?;
        for dn in &group.member_dns {
            if let Some(member) = dn_to_member.get(dn) {
                let mut link = GroupUser::new(model.uuid.clone(), member.uuid.clone());
                link.save(&conn).await?;
            }
        }
        group_count += 1;
    }
    if CONFIG.org_groups_enabled() {
        for existing in Group::find_by_organization(&org_id, &conn).await {
            if let Some(ext) = existing.external_id.clone()
                && !seen_groups.contains(&ext)
            {
                existing.delete(&org_id, &conn).await?;
            }
        }
    }

    Ok(Json(json!({
        "invited": invited,
        "revoked": revoked,
        "users": users.len(),
        "groups": group_count,
        "object": "ldapSync"
    })))
}
