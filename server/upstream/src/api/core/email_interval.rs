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
    CONFIG,
    api::{EmptyResult, JsonResult},
    auth::Headers,
    crypto,
    db::{
        DbConn,
        models::{User, UserId},
        schema::{
            komboe_email_login_challenges, komboe_email_login_codes, komboe_email_login_policy, komboe_email_login_trust,
            komboe_email_trust_tokens,
        },
    },
    error::MapResult,
    mail,
};

const CODE_TTL_SECS: i64 = 600;
const MAX_ATTEMPTS: i32 = 5;
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

fn new_secret() -> (String, String) {
    let raw = data_encoding::HEXLOWER.encode(&crypto::get_random_bytes::<32>());
    (raw.clone(), code_hash(&raw))
}

/// A copied device id is not trust. Only this secret, still inside its fixed window, is.
async fn trust_verified_at(user_id: &UserId, token: Option<&str>, conn: &DbConn) -> Option<i64> {
    let Some(token) = token.map(str::trim).filter(|value| !value.is_empty()) else {
        return None;
    };
    let user_id = user_id.to_string();
    let hash = code_hash(token);
    conn.run(move |c| {
        komboe_email_trust_tokens::table
            .filter(komboe_email_trust_tokens::token_hash.eq(hash))
            .filter(komboe_email_trust_tokens::user_uuid.eq(user_id))
            .filter(komboe_email_trust_tokens::revoked_at.is_null())
            .select(komboe_email_trust_tokens::verified_at)
            .first::<i64>(c)
            .ok()
    })
    .await
}

async fn issue_trust_token(user_id: &UserId, now: i64, conn: &DbConn) -> crate::api::ApiResult<String> {
    let (raw, hash) = new_secret();
    let user_id = user_id.to_string();
    conn.run(move |c| {
        diesel::insert_into(komboe_email_trust_tokens::table)
            .values((
                komboe_email_trust_tokens::token_hash.eq(hash),
                komboe_email_trust_tokens::user_uuid.eq(user_id),
                komboe_email_trust_tokens::verified_at.eq(now),
                komboe_email_trust_tokens::revoked_at.eq(None::<i64>),
            ))
            .execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error recording email sign-in")?;
    Ok(raw)
}

pub async fn clear_user(user_id: &UserId, conn: &DbConn) -> EmptyResult {
    let user_id = user_id.to_string();
    conn.run(move |c| {
        diesel::delete(komboe_email_login_trust::table.filter(komboe_email_login_trust::user_uuid.eq(&user_id)))
            .execute(c)?;
        diesel::delete(komboe_email_trust_tokens::table.filter(komboe_email_trust_tokens::user_uuid.eq(&user_id)))
            .execute(c)?;
        diesel::delete(komboe_email_login_challenges::table.filter(komboe_email_login_challenges::user_uuid.eq(&user_id)))
            .execute(c)?;
        diesel::delete(komboe_email_login_codes::table.filter(komboe_email_login_codes::user_uuid.eq(&user_id)))
            .execute(c)?;
        Ok::<(), diesel::result::Error>(())
    })
    .await
    .map_res("Error clearing email sign-in trust")
}

async fn revoke_trust_token(user_id: &UserId, token: &str, conn: &DbConn) -> EmptyResult {
    let user_id = user_id.to_string();
    let hash = code_hash(token.trim());
    let now = now_secs();
    conn.run(move |c| {
        diesel::update(
            komboe_email_trust_tokens::table
                .filter(komboe_email_trust_tokens::token_hash.eq(hash))
                .filter(komboe_email_trust_tokens::user_uuid.eq(user_id)),
        )
        .set(komboe_email_trust_tokens::revoked_at.eq(Some(now)))
        .execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error revoking email sign-in trust")
}

fn challenge_body(challenge_id: &str) -> serde_json::Value {
    serde_json::json!({
        "error": "invalid_grant",
        "error_description": "Two factor required.",
        "TwoFactorProviders": ["1"],
        "TwoFactorProviders2": { "1": null },
        "KomboeLoginChallenge": challenge_id,
    })
}

fn mail_can_send(user: &User) -> bool {
    CONFIG.mail_enabled() && CONFIG._enable_email_2fa() && user.verified_at.is_some()
}

async fn create_challenge(user_id: &UserId, conn: &DbConn) -> crate::api::ApiResult<String> {
    let (raw, _) = new_secret();
    let now = now_secs();
    let user_id = user_id.to_string();
    let id = raw.clone();
    conn.run(move |c| {
        diesel::insert_into(komboe_email_login_challenges::table)
            .values((
                komboe_email_login_challenges::challenge_id.eq(id),
                komboe_email_login_challenges::user_uuid.eq(user_id),
                komboe_email_login_challenges::code_hash.eq(None::<String>),
                komboe_email_login_challenges::expires_at.eq(now + CODE_TTL_SECS),
                komboe_email_login_challenges::used_at.eq(None::<i64>),
                komboe_email_login_challenges::attempts.eq(0),
                komboe_email_login_challenges::created_at.eq(now),
            ))
            .execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error starting the email sign-in challenge")?;
    Ok(raw)
}

/// Password was already accepted and no standing second factor is enabled.
/// Returns a new trust secret when a code is accepted. A device id is ignored.
pub async fn enforce(
    user: &User,
    trust_token: Option<&str>,
    challenge_id: Option<&str>,
    code: Option<&str>,
    conn: &DbConn,
) -> crate::api::ApiResult<Option<String>> {
    let interval = interval_for(&user.uuid, conn).await;
    if interval.is_none() {
        return Ok(None);
    }
    // Mail that cannot send must not trap the account. Stronger factors are handled by the caller.
    if !mail_can_send(user) {
        return Ok(None);
    }
    let verified = trust_verified_at(&user.uuid, trust_token, conn).await;
    if !challenge_due(interval, verified, now_secs()) {
        return Ok(None);
    }
    let Some(code) = code.map(str::trim).filter(|value| !value.is_empty()) else {
        let challenge = create_challenge(&user.uuid, conn).await?;
        err_json!(challenge_body(&challenge), "Email sign-in code required");
    };
    let Some(challenge_id) = challenge_id.map(str::trim).filter(|value| !value.is_empty()) else {
        err!("This sign-in code is not for this attempt.");
    };
    match consume_challenge(&user.uuid, challenge_id, code, conn).await? {
        CodeState::Ok => Ok(Some(issue_trust_token(&user.uuid, now_secs(), conn).await?)),
        CodeState::Expired => err!("That sign-in code has expired. Request another."),
        CodeState::Used => err!("That sign-in code was already used. Request another."),
        CodeState::TooManyAttempts => err!("Too many attempts. Request another sign-in code."),
        CodeState::Mismatch => err!("That sign-in code is incorrect."),
    }
}

pub async fn send_if_due(user: &User, challenge_id: &str, conn: &DbConn) -> EmptyResult {
    if interval_for(&user.uuid, conn).await.is_none() || !mail_can_send(user) {
        err!("Two factor not found");
    }
    let challenge_id = challenge_id.trim();
    if challenge_id.is_empty() {
        err!("This sign-in code is not for this attempt.");
    }
    issue_challenge_code(user, challenge_id, conn).await
}

async fn issue_challenge_code(user: &User, challenge_id: &str, conn: &DbConn) -> EmptyResult {
    let now = now_secs();
    let user_id = user.uuid.to_string();
    let challenge_id = challenge_id.to_string();
    let row: Option<(i64, Option<i64>, Option<String>)> = conn
        .run({
            let user_id = user_id.clone();
            let challenge_id = challenge_id.clone();
            move |c| {
                komboe_email_login_challenges::table
                    .filter(komboe_email_login_challenges::challenge_id.eq(challenge_id))
                    .filter(komboe_email_login_challenges::user_uuid.eq(user_id))
                    .select((
                        komboe_email_login_challenges::expires_at,
                        komboe_email_login_challenges::used_at,
                        komboe_email_login_challenges::code_hash,
                    ))
                    .first::<(i64, Option<i64>, Option<String>)>(c)
                    .ok()
            }
        })
        .await;
    let Some((expires_at, used_at, _)) = row else {
        err!("This sign-in code is not for this attempt.");
    };
    if used_at.is_some() || now >= expires_at {
        err!("That sign-in challenge has expired. Start sign-in again.");
    }
    let code = crypto::generate_email_token(8);
    let hash = code_hash(&code);
    let user_id2 = user.uuid.to_string();
    let challenge_key = challenge_id.clone();
    conn.run(move |c| {
        diesel::update(
            komboe_email_login_challenges::table
                .filter(komboe_email_login_challenges::challenge_id.eq(challenge_key))
                .filter(komboe_email_login_challenges::user_uuid.eq(user_id2)),
        )
        .set((
            komboe_email_login_challenges::code_hash.eq(Some(hash)),
            komboe_email_login_challenges::attempts.eq(0),
        ))
        .execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error preparing the sign-in code")?;
    if let Err(err) = mail::send_token(&user.email, &code).await {
        let user_id3 = user.uuid.to_string();
        let challenge_key = challenge_id.clone();
        conn.run(move |c| {
            diesel::update(
                komboe_email_login_challenges::table
                    .filter(komboe_email_login_challenges::challenge_id.eq(challenge_key))
                    .filter(komboe_email_login_challenges::user_uuid.eq(user_id3)),
            )
            .set(komboe_email_login_challenges::code_hash.eq(None::<String>))
            .execute(c)
        })
        .await
        .ok();
        return Err(err);
    }
    Ok(())
}

async fn consume_challenge(
    user_id: &UserId,
    challenge_id: &str,
    code: &str,
    conn: &DbConn,
) -> crate::api::ApiResult<CodeState> {
    let now = now_secs();
    let user_id = user_id.to_string();
    let challenge_id = challenge_id.to_string();
    let hash = code_hash(code);
    let row: Option<(i64, Option<i64>, i32, Option<String>)> = conn
        .run({
            let user_id = user_id.clone();
            let challenge_id = challenge_id.clone();
            move |c| {
                komboe_email_login_challenges::table
                    .filter(komboe_email_login_challenges::challenge_id.eq(challenge_id))
                    .filter(komboe_email_login_challenges::user_uuid.eq(user_id))
                    .select((
                        komboe_email_login_challenges::expires_at,
                        komboe_email_login_challenges::used_at,
                        komboe_email_login_challenges::attempts,
                        komboe_email_login_challenges::code_hash,
                    ))
                    .first::<(i64, Option<i64>, i32, Option<String>)>(c)
                    .ok()
            }
        })
        .await;
    let Some((expires_at, used_at, attempts, stored_hash)) = row else {
        return Ok(CodeState::Mismatch);
    };
    let matches = stored_hash.as_deref().is_some_and(|stored| crypto::ct_eq(stored, &hash));
    let state = judge_code(expires_at, used_at, attempts, matches, now);
    match state {
        CodeState::Ok => {
            let user_id = user_id.clone();
            let challenge_id = challenge_id.clone();
            conn.run(move |c| {
                diesel::update(
                    komboe_email_login_challenges::table
                        .filter(komboe_email_login_challenges::challenge_id.eq(challenge_id))
                        .filter(komboe_email_login_challenges::user_uuid.eq(user_id)),
                )
                .set(komboe_email_login_challenges::used_at.eq(Some(now)))
                .execute(c)
            })
            .await
            .map(|_| ())
            .map_res("Error closing the sign-in code")?;
        }
        CodeState::Mismatch => {
            let attempts = attempts.saturating_add(1);
            let used = if attempts >= MAX_ATTEMPTS { Some(now) } else { None };
            let user_id = user_id.clone();
            let challenge_id = challenge_id.clone();
            conn.run(move |c| {
                diesel::update(
                    komboe_email_login_challenges::table
                        .filter(komboe_email_login_challenges::challenge_id.eq(challenge_id))
                        .filter(komboe_email_login_challenges::user_uuid.eq(user_id)),
                )
                .set((
                    komboe_email_login_challenges::attempts.eq(attempts),
                    komboe_email_login_challenges::used_at.eq(used),
                ))
                .execute(c)
            })
            .await
            .map(|_| ())
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
        "meaning": "The timer starts when an email code is accepted. It is not extended by failed sign-ins or by using the vault. The proof is a server-issued secret, not the device id. Never turns off this timer only. A copied browser profile can still guess a short PIN offline; the wrong-attempt counter only applies in that browser.",
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
    if seconds.is_some() && !mail_can_send(&headers.user) {
        err!("Email sign-in codes are not available for this account, so the timer was not turned on.");
    }
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
            Ok::<(), diesel::result::Error>(())
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

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct ClearTrustBody {
    token: String,
}

#[post("/komboe/email-login-trust/clear", data = "<body>")]
async fn clear_device_trust(body: Json<ClearTrustBody>, headers: Headers, conn: DbConn) -> EmptyResult {
    revoke_trust_token(&headers.user.uuid, &body.token, &conn).await
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
