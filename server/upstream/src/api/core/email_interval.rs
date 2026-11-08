//! Timed email sign-in code.
//!
//! The timer starts when a code for this device is accepted. It is not moved by a failed
//! login, a resend, or any later request. `None` means Never: this check is off.
//! A standing second factor (authenticator, passkey, security key, always-on email) is
//! handled by the existing login path and is not skipped here.

use std::time::{SystemTime, UNIX_EPOCH};

use diesel::prelude::*;
use ring::digest;
use rocket::{Route, serde::json::Json};
use serde::Deserialize;

use crate::{
    api::{EmptyResult, JsonResult},
    auth::Headers,
    crypto,
    db::{
        DbConn,
        models::{DeviceId, User, UserId},
        schema::{komboe_email_login_codes, komboe_email_login_policy, komboe_email_login_trust},
    },
    error::MapResult,
    mail,
    util::get_uuid,
};

const PURPOSE: &str = "interval_login";
const CODE_TTL_SECS: i64 = 600;
const MAX_ATTEMPTS: i32 = 5;
const RESEND_GAP_SECS: i64 = 30;
pub const ALLOWED_INTERVALS: [i64; 8] = [60, 300, 600, 900, 1800, 3600, 21600, 86400];

pub fn routes() -> Vec<Route> {
    routes![get_interval, put_interval, clear_device_trust]
}

pub fn now_secs() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0)
}

/// `None` is Never. A positive allowed value is the fixed lifetime of one successful code.
pub fn parse_interval(seconds: Option<i64>) -> Result<Option<i64>, &'static str> {
    match seconds {
        None => Ok(None),
        Some(0) => Ok(None),
        Some(value) if ALLOWED_INTERVALS.contains(&value) => Ok(Some(value)),
        Some(_) => Err("Choose 1, 5, 10, 15 or 30 minutes, 1, 6 or 24 hours, or never."),
    }
}

/// True when this login must ask for a new email code.
/// Equal to `verified_at + interval` is already due. Failed logins do not change `verified_at`.
pub fn challenge_due(interval_secs: Option<i64>, verified_at: Option<i64>, now: i64) -> bool {
    let Some(interval_secs) = interval_secs.filter(|value| *value > 0) else {
        return false;
    };
    match verified_at {
        None => true,
        Some(verified_at) => now >= verified_at.saturating_add(interval_secs),
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum CodeState {
    Ok,
    Expired,
    Used,
    TooManyAttempts,
    Mismatch,
}

pub fn judge_code(expires_at: i64, used_at: Option<i64>, attempts: i32, matches: bool, now: i64) -> CodeState {
    if used_at.is_some() {
        return CodeState::Used;
    }
    if now >= expires_at {
        return CodeState::Expired;
    }
    if attempts >= MAX_ATTEMPTS {
        return CodeState::TooManyAttempts;
    }
    if matches {
        CodeState::Ok
    } else {
        CodeState::Mismatch
    }
}

fn code_hash(code: &str) -> String {
    let digest = digest::digest(&digest::SHA256, code.as_bytes());
    data_encoding::HEXLOWER.encode(digest.as_ref())
}

pub async fn interval_for(user_id: &UserId, conn: &DbConn) -> Option<i64> {
    let user_id = user_id.to_string();
    conn.run(move |c| {
        komboe_email_login_policy::table
            .filter(komboe_email_login_policy::user_uuid.eq(user_id))
            .select(komboe_email_login_policy::interval_secs)
            .first::<Option<i64>>(c)
            .ok()
            .flatten()
            .filter(|value| *value > 0)
    })
    .await
}

async fn verified_at(user_id: &UserId, device_id: &DeviceId, conn: &DbConn) -> Option<i64> {
    let user_id = user_id.to_string();
    let device_id = device_id.to_string();
    conn.run(move |c| {
        komboe_email_login_trust::table
            .filter(komboe_email_login_trust::user_uuid.eq(user_id))
            .filter(komboe_email_login_trust::device_uuid.eq(device_id))
            .select(komboe_email_login_trust::verified_at)
            .first::<i64>(c)
            .ok()
    })
    .await
}

pub async fn clear_user(user_id: &UserId, conn: &DbConn) -> EmptyResult {
    let user_id = user_id.to_string();
    conn.run(move |c| {
        diesel::delete(komboe_email_login_trust::table.filter(komboe_email_login_trust::user_uuid.eq(&user_id)))
            .execute(c)?;
        diesel::delete(komboe_email_login_codes::table.filter(komboe_email_login_codes::user_uuid.eq(&user_id)))
            .execute(c)?;
        Ok(())
    })
    .await
    .map_res("Error clearing email sign-in trust")
}

async fn clear_device(user_id: &UserId, device_id: &DeviceId, conn: &DbConn) -> EmptyResult {
    let user_id = user_id.to_string();
    let device_id = device_id.to_string();
    conn.run(move |c| {
        diesel::delete(
            komboe_email_login_trust::table
                .filter(komboe_email_login_trust::user_uuid.eq(&user_id))
                .filter(komboe_email_login_trust::device_uuid.eq(&device_id)),
        )
        .execute(c)?;
        diesel::delete(
            komboe_email_login_codes::table
                .filter(komboe_email_login_codes::user_uuid.eq(&user_id))
                .filter(komboe_email_login_codes::device_uuid.eq(&device_id)),
        )
        .execute(c)?;
        Ok(())
    })
    .await
    .map_res("Error clearing this device's email sign-in trust")
}

async fn stamp(user_id: &UserId, device_id: &DeviceId, now: i64, conn: &DbConn) -> EmptyResult {
    let user_id = user_id.to_string();
    let device_id = device_id.to_string();
    conn.run(move |c| {
        diesel::delete(
            komboe_email_login_trust::table
                .filter(komboe_email_login_trust::user_uuid.eq(&user_id))
                .filter(komboe_email_login_trust::device_uuid.eq(&device_id)),
        )
        .execute(c)?;
        diesel::insert_into(komboe_email_login_trust::table)
            .values((
                komboe_email_login_trust::user_uuid.eq(user_id),
                komboe_email_login_trust::device_uuid.eq(device_id),
                komboe_email_login_trust::verified_at.eq(now),
            ))
            .execute(c)?;
        Ok(())
    })
    .await
    .map_res("Error recording email sign-in")
}

fn providers() -> serde_json::Value {
    serde_json::json!({
        "error": "invalid_grant",
        "error_description": "Two factor required.",
        "TwoFactorProviders": ["1"],
        "TwoFactorProviders2": { "1": null },
    })
}

/// Called only after the password (or equivalent) has already been accepted and no standing
/// second factor is enabled. Does not refresh trust when the code is missing or wrong.
pub async fn enforce(user: &User, device_id: &DeviceId, code: Option<&str>, conn: &DbConn) -> EmptyResult {
    let interval = interval_for(&user.uuid, conn).await;
    let verified = verified_at(&user.uuid, device_id, conn).await;
    if !challenge_due(interval, verified, now_secs()) {
        return Ok(());
    }
    if user.verified_at.is_none() {
        err!("This email address is not verified, so a sign-in code cannot be sent. Sign-in was not completed.");
    }
    let Some(code) = code.map(str::trim).filter(|value| !value.is_empty()) else {
        err_json!(providers(), "Email sign-in code required");
    };
    match consume_code(&user.uuid, device_id, code, conn).await? {
        CodeState::Ok => stamp(&user.uuid, device_id, now_secs(), conn).await,
        CodeState::Expired => err!("That sign-in code has expired. Request another."),
        CodeState::Used => err!("That sign-in code was already used. Request another."),
        CodeState::TooManyAttempts => err!("Too many attempts. Request another sign-in code."),
        CodeState::Mismatch => err!("That sign-in code is incorrect."),
    }
}

pub async fn send_if_due(user: &User, device_id: &DeviceId, conn: &DbConn) -> EmptyResult {
    let interval = interval_for(&user.uuid, conn).await;
    let verified = verified_at(&user.uuid, device_id, conn).await;
    if !challenge_due(interval, verified, now_secs()) {
        err!("Two factor not found");
    }
    if user.verified_at.is_none() {
        err!("This email address is not verified, so a sign-in code cannot be sent. Sign-in was not completed.");
    }
    issue_and_send(user, device_id, conn).await
}

async fn issue_and_send(user: &User, device_id: &DeviceId, conn: &DbConn) -> EmptyResult {
    let now = now_secs();
    let user_id = user.uuid.to_string();
    let device_key = device_id.to_string();
    let latest: Option<i64> = conn
        .run({
            let user_id = user_id.clone();
            let device_key = device_key.clone();
            move |c| {
                komboe_email_login_codes::table
                    .filter(komboe_email_login_codes::user_uuid.eq(user_id))
                    .filter(komboe_email_login_codes::device_uuid.eq(device_key))
                    .filter(komboe_email_login_codes::purpose.eq(PURPOSE))
                    .select(komboe_email_login_codes::created_at)
                    .order(komboe_email_login_codes::created_at.desc())
                    .first::<i64>(c)
                    .ok()
            }
        })
        .await;
    if let Some(created) = latest {
        if now.saturating_sub(created) < RESEND_GAP_SECS {
            err!("Wait a moment before requesting another sign-in code.");
        }
    }
    let code = crypto::generate_email_token(8);
    let hash = code_hash(&code);
    let uuid = get_uuid();
    conn.run({
        let user_id = user_id.clone();
        let device_key = device_key.clone();
        let hash = hash.clone();
        let uuid = uuid.clone();
        move |c| {
            diesel::update(
                komboe_email_login_codes::table
                    .filter(komboe_email_login_codes::user_uuid.eq(&user_id))
                    .filter(komboe_email_login_codes::device_uuid.eq(&device_key))
                    .filter(komboe_email_login_codes::purpose.eq(PURPOSE))
                    .filter(komboe_email_login_codes::used_at.is_null()),
            )
            .set(komboe_email_login_codes::used_at.eq(Some(now)))
            .execute(c)?;
            diesel::insert_into(komboe_email_login_codes::table)
                .values((
                    komboe_email_login_codes::uuid.eq(uuid),
                    komboe_email_login_codes::user_uuid.eq(user_id),
                    komboe_email_login_codes::device_uuid.eq(device_key),
                    komboe_email_login_codes::code_hash.eq(hash),
                    komboe_email_login_codes::purpose.eq(PURPOSE),
                    komboe_email_login_codes::expires_at.eq(now + CODE_TTL_SECS),
                    komboe_email_login_codes::used_at.eq(None::<i64>),
                    komboe_email_login_codes::attempts.eq(0),
                    komboe_email_login_codes::created_at.eq(now),
                ))
                .execute(c)?;
            Ok(())
        }
    })
    .await
    .map_res("Error preparing the sign-in code")?;
    if let Err(err) = mail::send_token(&user.email, &code).await {
        let uuid = uuid.clone();
        let _ = conn
            .run(move |c| diesel::delete(komboe_email_login_codes::table.filter(komboe_email_login_codes::uuid.eq(uuid))).execute(c))
            .await;
        return Err(err);
    }
    Ok(())
}

async fn consume_code(user_id: &UserId, device_id: &DeviceId, code: &str, conn: &DbConn) -> crate::api::ApiResult<CodeState> {
    let now = now_secs();
    let user_id = user_id.to_string();
    let device_id = device_id.to_string();
    let hash = code_hash(code);
    let row: Option<(String, i64, Option<i64>, i32, String)> = conn
        .run({
            let user_id = user_id.clone();
            let device_id = device_id.clone();
            move |c| {
                komboe_email_login_codes::table
                    .filter(komboe_email_login_codes::user_uuid.eq(user_id))
                    .filter(komboe_email_login_codes::device_uuid.eq(device_id))
                    .filter(komboe_email_login_codes::purpose.eq(PURPOSE))
                    .order(komboe_email_login_codes::created_at.desc())
                    .select((
                        komboe_email_login_codes::uuid,
                        komboe_email_login_codes::expires_at,
                        komboe_email_login_codes::used_at,
                        komboe_email_login_codes::attempts,
                        komboe_email_login_codes::code_hash,
                    ))
                    .first::<(String, i64, Option<i64>, i32, String)>(c)
                    .ok()
            }
        })
        .await;
    let Some((uuid, expires_at, used_at, attempts, stored_hash)) = row else {
        return Ok(CodeState::Mismatch);
    };
    let matches = crypto::ct_eq(&stored_hash, &hash);
    let state = judge_code(expires_at, used_at, attempts, matches, now);
    match state {
        CodeState::Ok => {
            conn.run(move |c| {
                diesel::update(komboe_email_login_codes::table.filter(komboe_email_login_codes::uuid.eq(uuid)))
                    .set(komboe_email_login_codes::used_at.eq(Some(now)))
                    .execute(c)
            })
            .await
            .map_res("Error closing the sign-in code")?;
        }
        CodeState::Mismatch => {
            let attempts = attempts.saturating_add(1);
            let used = if attempts >= MAX_ATTEMPTS { Some(now) } else { None };
            conn.run(move |c| {
                diesel::update(komboe_email_login_codes::table.filter(komboe_email_login_codes::uuid.eq(uuid)))
                    .set((
                        komboe_email_login_codes::attempts.eq(attempts),
                        komboe_email_login_codes::used_at.eq(used),
                    ))
                    .execute(c)
            })
            .await
            .map_res("Error recording a sign-in attempt")?;
        }
        _ => {}
    }
    Ok(state)
}

#[get("/komboe/email-login-interval")]
async fn get_interval(headers: Headers, conn: DbConn) -> JsonResult {
    let seconds = interval_for(&headers.user.uuid, &conn).await;
    Ok(Json(serde_json::json!({
        "intervalSeconds": seconds,
        "never": seconds.is_none(),
        "options": ALLOWED_INTERVALS,
        "meaning": "The timer starts when an email code is accepted on this device. It is not extended by failed sign-ins or by using the vault. Never turns off this timer only.",
    })))
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IntervalBody {
    interval_seconds: Option<i64>,
    master_password_hash: String,
}

#[put("/komboe/email-login-interval", data = "<body>")]
async fn put_interval(body: Json<IntervalBody>, headers: Headers, conn: DbConn) -> JsonResult {
    if !headers.user.check_valid_password(&body.master_password_hash) {
        err!("Invalid master password.");
    }
    let seconds = match parse_interval(body.interval_seconds) {
        Ok(seconds) => seconds,
        Err(message) => err!(message),
    };
    let user_id = headers.user.uuid.to_string();
    conn.run({
        let user_id = user_id.clone();
        move |c| {
            diesel::delete(komboe_email_login_policy::table.filter(komboe_email_login_policy::user_uuid.eq(&user_id)))
                .execute(c)?;
            diesel::insert_into(komboe_email_login_policy::table)
                .values((
                    komboe_email_login_policy::user_uuid.eq(user_id),
                    komboe_email_login_policy::interval_secs.eq(seconds),
                ))
                .execute(c)?;
            Ok(())
        }
    })
    .await
    .map_res("Error saving the email sign-in interval")?;
    clear_user(&headers.user.uuid, &conn).await?;
    Ok(Json(serde_json::json!({
        "intervalSeconds": seconds,
        "never": seconds.is_none(),
        "emailUnchanged": true,
    })))
}

#[post("/komboe/email-login-trust/clear")]
async fn clear_device_trust(headers: Headers, conn: DbConn) -> EmptyResult {
    clear_device(&headers.user.uuid, &headers.device.uuid, &conn).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn never_and_window_and_boundary() {
        assert!(!challenge_due(None, None, 1_000));
        assert!(!challenge_due(Some(0), None, 1_000));
        assert!(challenge_due(Some(60), None, 1_000));
        assert!(!challenge_due(Some(60), Some(1_000), 1_059));
        assert!(challenge_due(Some(60), Some(1_000), 1_060));
        assert!(parse_interval(Some(60)).unwrap() == Some(60));
        assert!(parse_interval(None).unwrap().is_none());
        assert!(parse_interval(Some(7)).is_err());
    }

    #[test]
    fn codes_expire_once_and_do_not_replay() {
        assert_eq!(judge_code(1_100, None, 0, true, 1_000), CodeState::Ok);
        assert_eq!(judge_code(1_000, None, 0, true, 1_000), CodeState::Expired);
        assert_eq!(judge_code(1_100, Some(1), 0, true, 1_050), CodeState::Used);
        assert_eq!(judge_code(1_100, None, 5, true, 1_050), CodeState::TooManyAttempts);
        assert_eq!(judge_code(1_100, None, 1, false, 1_050), CodeState::Mismatch);
    }
}
