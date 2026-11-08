//! Optional login name. It is an alias for the account, not a KDF salt.
//! The vault-key salt is the email the client sent at registration, including its case.
//! `users.email` is stored lowercased and must not be used as that salt.
//!
//! The unauthenticated open response is an AES-GCM envelope of that email, wrapped by a key
//! derived with the account's own KDF and a random salt. It never contains the email.
//! A stored SHA-256 of a cheaper login-name PBKDF2 is not accepted.

use diesel::prelude::*;
use ring::digest;
use rocket::{Route, serde::json::Json};
use serde::Deserialize;
use serde_json::json;

use crate::{
    api::{EmptyResult, JsonResult},
    auth::Headers,
    db::{
        DbConn,
        models::UserId,
        schema::{komboe_kdf_email, komboe_login_names},
    },
    error::MapResult,
};

/// IV (12) + padded email (128) + GCM tag (16).
const ENVELOPE_LEN: usize = 156;

pub fn routes() -> Vec<Route> {
    routes![get_kdf_email, put_kdf_email, get_login_name, put_login_name, delete_login_name]
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
struct KdfEmailBody {
    kdf_email: String,
    master_password_hash: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct LoginNameBody {
    name: String,
    master_password_hash: String,
    /// AES-GCM envelope of the exact vault-key email. The key is the account KDF, not a cheaper one.
    envelope: String,
    envelope_salt: String,
    kdf: i32,
    kdf_iterations: i32,
    kdf_memory: Option<i32>,
    kdf_parallelism: Option<i32>,
}

fn decoy_bytes(name: &str) -> Vec<u8> {
    let mut block = digest::digest(&digest::SHA256, name.as_bytes()).as_ref().to_vec();
    let mut out = Vec::with_capacity(ENVELOPE_LEN);
    while out.len() < ENVELOPE_LEN {
        block = digest::digest(&digest::SHA256, &block).as_ref().to_vec();
        out.extend_from_slice(&block);
    }
    out.truncate(ENVELOPE_LEN);
    out
}

/// Same shape for a hit and a miss. The email is not in the body. Repeating the call does not
/// change a miss, so the ciphertext is not a boolean oracle.
fn decoy_open(name: &str) -> (i32, i32, Option<i32>, Option<i32>, String, String) {
    let (kdf_type, kdf_iter, kdf_mem, kdf_para) = super::accounts::unknown_email_kdf(name);
    let bytes = decoy_bytes(name);
    let salt = data_encoding::HEXLOWER.encode(&bytes[..16]);
    let envelope = data_encoding::BASE64.encode(&bytes);
    (kdf_type, kdf_iter, kdf_mem, kdf_para, envelope, salt)
}

/// KDF parameters and the envelope for this login name. The email stays inside the envelope.
pub async fn open_login_name(name: &str, conn: &DbConn) -> (i32, i32, Option<i32>, Option<i32>, String, String) {
    let Ok(name) = validate_login_name(name) else {
        return decoy_open(name);
    };
    let name_key = name.clone();
    let row: Option<(Option<String>, Option<String>, Option<i32>, Option<i32>, Option<i32>, Option<i32>)> = conn
        .run(move |c| {
            komboe_login_names::table
                .filter(komboe_login_names::name.eq(name_key))
                .select((
                    komboe_login_names::envelope,
                    komboe_login_names::envelope_salt,
                    komboe_login_names::wrap_kdf_type,
                    komboe_login_names::wrap_kdf_iter,
                    komboe_login_names::wrap_kdf_memory,
                    komboe_login_names::wrap_kdf_parallelism,
                ))
                .first(c)
                .ok()
        })
        .await;
    if let Some((Some(envelope), Some(salt), Some(kdf_type), Some(kdf_iter), kdf_mem, kdf_para)) = row {
        return (kdf_type, kdf_iter, kdf_mem, kdf_para, envelope, salt);
    }
    decoy_open(&name)
}

pub async fn stored_kdf_email(user_id: &UserId, conn: &DbConn) -> Option<String> {
    let user_id = user_id.to_string();
    conn.run(move |c| {
        komboe_kdf_email::table
            .filter(komboe_kdf_email::user_uuid.eq(user_id))
            .select(komboe_kdf_email::kdf_email)
            .first::<String>(c)
            .ok()
    })
    .await
}

pub async fn save_kdf_email(user_id: &UserId, kdf_email: &str, conn: &DbConn) -> EmptyResult {
    let user_id = user_id.to_string();
    let kdf_email = kdf_email.to_string();
    conn.run(move |c| -> Result<(), diesel::result::Error> {
        diesel::delete(komboe_kdf_email::table.filter(komboe_kdf_email::user_uuid.eq(&user_id))).execute(c)?;
        diesel::insert_into(komboe_kdf_email::table)
            .values((komboe_kdf_email::user_uuid.eq(user_id), komboe_kdf_email::kdf_email.eq(kdf_email)))
            .execute(c)?;
        Ok(())
    })
    .await
    .map(|_| ())
    .map_res("Error saving the vault email salt")
}

/// Password and email changes drop the envelope. The name can be saved again while signed in.
pub async fn clear_verifier(user_id: &UserId, conn: &DbConn) -> EmptyResult {
    let user_id = user_id.to_string();
    conn.run(move |c| {
        diesel::update(komboe_login_names::table.filter(komboe_login_names::user_uuid.eq(user_id)))
            .set((
                komboe_login_names::verifier_hash.eq(None::<String>),
                komboe_login_names::envelope.eq(None::<String>),
                komboe_login_names::envelope_salt.eq(None::<String>),
                komboe_login_names::wrap_kdf_type.eq(None::<i32>),
                komboe_login_names::wrap_kdf_iter.eq(None::<i32>),
                komboe_login_names::wrap_kdf_memory.eq(None::<i32>),
                komboe_login_names::wrap_kdf_parallelism.eq(None::<i32>),
            ))
            .execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error clearing the login-name envelope")
}

fn envelope_ok(envelope: &str, salt: &str) -> bool {
    let Ok(bytes) = data_encoding::BASE64.decode(envelope.trim().as_bytes()) else {
        return false;
    };
    bytes.len() == ENVELOPE_LEN
        && salt.len() == 32
        && salt.chars().all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c))
}

#[get("/komboe/kdf-email")]
async fn get_kdf_email(headers: Headers, conn: DbConn) -> JsonResult {
    let kdf_email = stored_kdf_email(&headers.user.uuid, &conn).await;
    Ok(Json(json!({
        "kdfEmail": kdf_email,
        "accountEmail": headers.user.email,
    })))
}

/// Records the exact vault-key salt when this server did not store it at registration.
/// The lowercased value must be the account email. This does not change `users.email`.
#[put("/komboe/kdf-email", data = "<body>")]
async fn put_kdf_email(body: Json<KdfEmailBody>, headers: Headers, conn: DbConn) -> JsonResult {
    if !headers.user.check_valid_password(&body.master_password_hash) {
        err!("Invalid master password.");
    }
    let kdf_email = body.kdf_email.trim();
    if !kdf_email.contains('@') || kdf_email.len() > 256 || kdf_email.to_lowercase() != headers.user.email {
        err!("That email does not match this account.");
    }
    save_kdf_email(&headers.user.uuid, kdf_email, &conn).await?;
    Ok(Json(json!({ "kdfEmail": kdf_email })))
}

#[get("/komboe/login-name")]
async fn get_login_name(headers: Headers, conn: DbConn) -> JsonResult {
    let user_uuid = headers.user.uuid.to_string();
    let row: Option<(String, Option<String>)> = conn
        .run(move |c| {
            komboe_login_names::table
                .filter(komboe_login_names::user_uuid.eq(user_uuid))
                .select((komboe_login_names::name, komboe_login_names::envelope))
                .first::<(String, Option<String>)>(c)
                .ok()
        })
        .await;
    let (name, ready) = match row {
        Some((name, envelope)) => (Some(name), envelope.is_some()),
        None => (None, false),
    };
    Ok(Json(json!({
        "name": name,
        "ready": ready,
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
    if headers.user.client_kdf_type != body.kdf
        || headers.user.client_kdf_iter != body.kdf_iterations
        || headers.user.client_kdf_memory != body.kdf_memory
        || headers.user.client_kdf_parallelism != body.kdf_parallelism
    {
        err!("The login name has to use this account's key derivation. Save it again from a signed-in client.");
    }
    if !envelope_ok(&body.envelope, &body.envelope_salt) {
        err!("The login name was not saved. Confirm the master password and try again.");
    }
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
    let envelope = body.envelope.trim().to_string();
    let envelope_salt = body.envelope_salt.trim().to_string();
    let kdf = body.kdf;
    let kdf_iterations = body.kdf_iterations;
    let kdf_memory = body.kdf_memory;
    let kdf_parallelism = body.kdf_parallelism;
    conn.run({
        let name = name.clone();
        let owner = owner.clone();
        move |c| -> Result<(), diesel::result::Error> {
            diesel::delete(komboe_login_names::table.filter(komboe_login_names::user_uuid.eq(&owner))).execute(c)?;
            diesel::insert_into(komboe_login_names::table)
                .values((
                    komboe_login_names::user_uuid.eq(owner),
                    komboe_login_names::name.eq(name),
                    komboe_login_names::verifier_hash.eq(None::<String>),
                    komboe_login_names::envelope.eq(envelope),
                    komboe_login_names::envelope_salt.eq(envelope_salt),
                    komboe_login_names::wrap_kdf_type.eq(Some(kdf)),
                    komboe_login_names::wrap_kdf_iter.eq(Some(kdf_iterations)),
                    komboe_login_names::wrap_kdf_memory.eq(kdf_memory),
                    komboe_login_names::wrap_kdf_parallelism.eq(kdf_parallelism),
                ))
                .execute(c)?;
            Ok(())
        }
    })
    .await
    .map_res("Error saving the login name")?;
    Ok(Json(json!({
        "name": name,
        "ready": true,
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

    #[test]
    fn a_miss_is_stable_and_has_no_email() {
        // Do not call unknown_email_kdf here. Its HMAC key is filled at server start,
        // and waiting for it from a unit test never returns.
        let first = decoy_bytes("intervalname");
        let second = decoy_bytes("intervalname");
        assert_eq!(first, second);
        assert_eq!(first.len(), ENVELOPE_LEN);
        let envelope = data_encoding::BASE64.encode(&first);
        assert!(!envelope.to_lowercase().contains("komboe"));
    }
}
