//! Optional login name. It is an alias for the account email.
//! The vault key is still derived from the email. This module never writes `users.email`.

use diesel::prelude::*;
use rocket::{Route, serde::json::Json};
use serde::Deserialize;
use serde_json::json;

use crate::{
    api::{EmptyResult, JsonResult},
    auth::Headers,
    db::{
        DbConn,
        models::{User, UserId},
        schema::komboe_login_names,
    },
    error::MapResult,
};

pub fn routes() -> Vec<Route> {
    routes![get_login_name, put_login_name, delete_login_name]
}

/// A login name is not an email and is not a KDF salt.
pub fn validate_login_name(raw: &str) -> Result<String, &'static str> {
    let name = raw.trim().to_lowercase();
    if name.contains('@') || name.chars().any(|c| c.is_whitespace()) {
        return Err("A login name cannot be an email address.");
    }
    if !(3..=32).contains(&name.len()) {
        return Err("A login name must be 3 to 32 characters.");
    }
    if !name.chars().all(|c| c.is_ascii_alphanumeric() || c == '.' || c == '_' || c == '-') {
        return Err("A login name can use letters, numbers, dots, underscores, and hyphens.");
    }
    Ok(name)
}

/// Email identifiers keep the exact typed value, so existing vault keys do not change.
/// A login name is usable only when the server resolved it to an email.
#[cfg_attr(not(test), allow(dead_code))]
pub fn kdf_email_for_login(typed: &str, canonical_email: Option<&str>) -> Result<String, &'static str> {
    let typed = typed.trim();
    if typed.contains('@') {
        return Ok(typed.to_string());
    }
    match canonical_email.map(str::trim).filter(|email| email.contains('@')) {
        Some(email) => Ok(email.to_string()),
        None => Err("This login name is not an account. Refusing to derive a vault key from it."),
    }
}

pub async fn canonical_email_for_name(name: &str, conn: &DbConn) -> Option<String> {
    let name = name.to_string();
    let user_uuid: Option<String> = conn
        .run(move |c| {
            komboe_login_names::table
                .filter(komboe_login_names::name.eq(name))
                .select(komboe_login_names::user_uuid)
                .first::<String>(c)
                .ok()
        })
        .await;
    let user_uuid = user_uuid?;
    User::find_by_uuid(&UserId::from(user_uuid), conn).await.map(|user| user.email)
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct LoginNameBody {
    name: String,
    master_password_hash: String,
}

#[get("/komboe/login-name")]
async fn get_login_name(headers: Headers, conn: DbConn) -> JsonResult {
    let user_uuid = headers.user.uuid.to_string();
    let name: Option<String> = conn
        .run(move |c| {
            komboe_login_names::table
                .filter(komboe_login_names::user_uuid.eq(user_uuid))
                .select(komboe_login_names::name)
                .first::<String>(c)
                .ok()
        })
        .await;
    Ok(Json(json!({
        "name": name,
        "email": headers.user.email,
        "emailUnchanged": true,
    })))
}

#[put("/komboe/login-name", data = "<body>")]
async fn put_login_name(body: Json<LoginNameBody>, headers: Headers, conn: DbConn) -> JsonResult {
    if !headers.user.check_valid_password(&body.master_password_hash) {
        err!("Invalid master password.");
    }
    let name = match validate_login_name(&body.name) {
        Ok(name) => name,
        Err(message) => err!(message),
    };
    let owner = headers.user.uuid.to_string();
    let taken = conn
        .run({
            let name = name.clone();
            let owner = owner.clone();
            move |c| {
                komboe_login_names::table
                    .filter(komboe_login_names::name.eq(name))
                    .filter(komboe_login_names::user_uuid.ne(owner))
                    .select(komboe_login_names::user_uuid)
                    .first::<String>(c)
                    .ok()
            }
        })
        .await;
    if taken.is_some() {
        err!("That login name is not available.");
    }
    let email_before = headers.user.email.clone();
    conn.run({
        let name = name.clone();
        let owner = owner.clone();
        move |c| -> Result<(), diesel::result::Error> {
            diesel::delete(komboe_login_names::table.filter(komboe_login_names::user_uuid.eq(&owner))).execute(c)?;
            diesel::insert_into(komboe_login_names::table)
                .values((komboe_login_names::user_uuid.eq(owner), komboe_login_names::name.eq(name)))
                .execute(c)?;
            Ok(())
        }
    })
    .await
    .map_res("Error saving the login name")?;
    Ok(Json(json!({
        "name": name,
        "email": email_before,
        "emailUnchanged": true,
    })))
}

#[delete("/komboe/login-name")]
async fn delete_login_name(headers: Headers, conn: DbConn) -> EmptyResult {
    let owner = headers.user.uuid.to_string();
    conn.run(move |c| diesel::delete(komboe_login_names::table.filter(komboe_login_names::user_uuid.eq(owner))).execute(c))
        .await
        .map(|_| ())
        .map_res("Error deleting the login name")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn email_is_not_a_login_name_and_is_not_rewritten() {
        assert!(validate_login_name("ada@example.com").is_err());
        assert_eq!(kdf_email_for_login("Ada@Example.com", Some("other@example.com")).unwrap(), "Ada@Example.com");
    }

    #[test]
    fn login_name_uses_the_server_email_only() {
        assert_eq!(kdf_email_for_login("ada", Some("ada@example.com")).unwrap(), "ada@example.com");
        assert!(kdf_email_for_login("ada", None).is_err());
        assert!(kdf_email_for_login("ada", Some("not-an-email")).is_err());
    }

    #[test]
    fn login_name_shape() {
        assert_eq!(validate_login_name("Ada_1").unwrap(), "ada_1");
        assert!(validate_login_name("ab").is_err());
        assert!(validate_login_name("has space").is_err());
    }
}
