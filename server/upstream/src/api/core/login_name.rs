//! Optional login name. It is an alias for the account email.
//! The vault key is still derived from the email. This module never writes `users.email`.

use diesel::prelude::*;
use ring::digest;
use rocket::{Route, serde::json::Json};
use serde::Deserialize;
use serde_json::json;

use crate::{
    api::{EmptyResult, JsonResult},
    auth::Headers,
    crypto,
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

/// The typed email is the KDF salt. A login name is never rewritten to the account email.
#[cfg_attr(not(test), allow(dead_code))]
pub fn kdf_email_for_login(typed: &str, _canonical_email: Option<&str>) -> Result<String, &'static str> {
    let typed = typed.trim();
    if typed.contains('@') {
        return Ok(typed.to_string());
    }
    Err("Sign in with the email for this vault. A login name is not the key.")
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct LoginNameBody {
    name: String,
    master_password_hash: String,
    /// PBKDF2-SHA256 of the master password with the login name as salt, 100000 iterations, base64.
    /// Stored only as SHA-256. Unauthenticated prelogin never returns the email.
    login_verifier: String,
}

fn verifier_hash(verifier: &str) -> String {
    let digest = digest::digest(&digest::SHA256, verifier.as_bytes());
    data_encoding::HEXLOWER.encode(digest.as_ref())
}

/// Password proof for a login name. `None` means the name or the verifier did not match.
/// The email and KDF are returned only after that proof. A miss is not distinguishable in the body.
pub async fn prove_login_name(name: &str, verifier: &str, conn: &DbConn) -> Option<(String, i32, i32, Option<i32>, Option<i32>)> {
    let Ok(name) = validate_login_name(name) else {
        drop(verifier_hash(verifier));
        return None;
    };
    let hash = verifier_hash(verifier);
    let name_key = name.clone();
    let row: Option<(String, Option<String>)> = conn
        .run(move |c| {
            komboe_login_names::table
                .filter(komboe_login_names::name.eq(name_key))
                .select((komboe_login_names::user_uuid, komboe_login_names::verifier_hash))
                .first::<(String, Option<String>)>(c)
                .ok()
        })
        .await;
    let Some((user_uuid, stored)) = row else {
        return None;
    };
    let Some(stored) = stored else {
        return None;
    };
    if !crypto::ct_eq(&stored, &hash) {
        return None;
    }
    let user = User::find_by_uuid(&UserId::from(user_uuid), conn).await?;
    Some((user.email, user.client_kdf_type, user.client_kdf_iter, user.client_kdf_memory, user.client_kdf_parallelism))
}

pub async fn clear_verifier(user_id: &UserId, conn: &DbConn) -> EmptyResult {
    let user_id = user_id.to_string();
    conn.run(move |c| {
        diesel::update(komboe_login_names::table.filter(komboe_login_names::user_uuid.eq(user_id)))
            .set(komboe_login_names::verifier_hash.eq(None::<String>))
            .execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error clearing the login-name verifier")
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
    let verifier = body.login_verifier.trim();
    if verifier.len() < 16 {
        err!("The login name was not saved. Confirm the master password and try again.");
    }
    let verifier_hash = verifier_hash(verifier);
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
                .values((
                    komboe_login_names::user_uuid.eq(owner),
                    komboe_login_names::name.eq(name),
                    komboe_login_names::verifier_hash.eq(verifier_hash),
                ))
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
        assert!(kdf_email_for_login("ada", Some("ada@example.com")).is_err());
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
