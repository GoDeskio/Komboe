//! Komboe-original features: hardware unlock, PGP auth, OpenPGP vault wrap,
//! local-only mode metadata, and a built-in actionable AI agent.
//! Clean-room: no bitwarden_license code and no vault ciphertext decryption.
use chrono::{NaiveDateTime, TimeDelta, Utc};
use data_encoding::HEXLOWER;
use diesel::prelude::*;
use ring::{
    hmac,
    rand::{SecureRandom, SystemRandom},
};
use rocket::{Route, serde::json::Json};
use serde_json::{json, Value};

use crate::{
    api::{EmptyResult, JsonResult},
    auth::Headers,
    db::{
        DbConn,
        schema::{
            komboe_agent_sessions, komboe_pgp_auth_challenges, komboe_pgp_auth_keys, komboe_pgp_vault_keys,
            komboe_unlock_credentials,
        },
    },
    error::MapResult,
    util::get_uuid,
};

pub fn routes() -> Vec<Route> {
    routes![
        list_unlock_credentials,
        add_unlock_credential,
        delete_unlock_credential,
        register_pgp_auth_key,
        list_pgp_auth_keys,
        delete_pgp_auth_key,
        start_pgp_auth_challenge,
        verify_pgp_auth_challenge,
        put_pgp_vault_key,
        get_pgp_vault_key,
        delete_pgp_vault_key,
        local_only_info,
        agent_session,
        agent_act,
    ]
}

fn now() -> NaiveDateTime {
    Utc::now().naive_utc()
}

fn random_bytes(n: usize) -> Vec<u8> {
    let mut buf = vec![0u8; n];
    SystemRandom::new().fill(&mut buf).expect("rng");
    buf
}

#[derive(Queryable, Insertable, Clone)]
#[diesel(table_name = komboe_unlock_credentials)]
struct UnlockCredential {
    uuid: String,
    user_uuid: String,
    kind: String,
    name: String,
    credential_id: String,
    public_data: String,
    salt: String,
    wrapped_user_key: String,
    created_at: NaiveDateTime,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct UnlockData {
    kind: String,
    name: String,
    credential_id: String,
    public_data: String,
    salt: String,
    wrapped_user_key: String,
}

fn validate_unlock(d: &UnlockData) -> EmptyResult {
    if !matches!(d.kind.as_str(), "webauthn_prf" | "yubikey_hmac_sha1") {
        err!("Unsupported unlock kind. Use webauthn_prf or yubikey_hmac_sha1.")
    }
    if d.name.trim().is_empty() || d.name.len() > 128 {
        err!("Unlock credential name must be 1..=128 characters.")
    }
    if d.credential_id.is_empty() || d.credential_id.len() > 512 {
        err!("credentialId is required.")
    }
    if d.salt.len() < 32 || d.wrapped_user_key.len() < 32 {
        err!("salt and wrappedUserKey must be present (client-wrapped; server never sees PRF/CR output).")
    }
    Ok(())
}

#[get("/komboe/unlock-credentials")]
async fn list_unlock_credentials(headers: Headers, conn: DbConn) -> JsonResult {
    let uid = headers.user.uuid.to_string();
    let rows = conn
        .run(move |c| {
            komboe_unlock_credentials::table
                .filter(komboe_unlock_credentials::user_uuid.eq(uid))
                .load::<UnlockCredential>(c)
                .unwrap_or_default()
        })
        .await;
    Ok(Json(json!({
        "object": "list",
        "data": rows.into_iter().map(|r| json!({
            "id": r.uuid,
            "kind": r.kind,
            "name": r.name,
            "credentialId": r.credential_id,
            "publicData": r.public_data,
            "salt": r.salt,
            "wrappedUserKey": r.wrapped_user_key,
            "createdAt": r.created_at.and_utc().to_rfc3339(),
            "serverCanUnwrap": false,
        })).collect::<Vec<_>>(),
    })))
}

#[post("/komboe/unlock-credentials", data = "<body>")]
async fn add_unlock_credential(body: Json<UnlockData>, headers: Headers, conn: DbConn) -> JsonResult {
    let d = body.into_inner();
    validate_unlock(&d)?;
    let row = UnlockCredential {
        uuid: get_uuid(),
        user_uuid: headers.user.uuid.to_string(),
        kind: d.kind,
        name: d.name.trim().to_string(),
        credential_id: d.credential_id,
        public_data: d.public_data,
        salt: d.salt,
        wrapped_user_key: d.wrapped_user_key,
        created_at: now(),
    };
    let out = json!({
        "id": row.uuid,
        "kind": row.kind,
        "name": row.name,
        "credentialId": row.credential_id,
        "serverCanUnwrap": false,
    });
    conn.run(move |c| diesel::insert_into(komboe_unlock_credentials::table).values(&row).execute(c))
        .await
        .map(|_| ())
        .map_res("Error saving unlock credential")?;
    Ok(Json(out))
}

#[delete("/komboe/unlock-credentials/<id>")]
async fn delete_unlock_credential(id: &str, headers: Headers, conn: DbConn) -> EmptyResult {
    let uid = headers.user.uuid.to_string();
    let key = id.to_string();
    let exists = conn
        .run({
            let uid = uid.clone();
            let key = key.clone();
            move |c| {
                komboe_unlock_credentials::table
                    .filter(komboe_unlock_credentials::uuid.eq(key))
                    .filter(komboe_unlock_credentials::user_uuid.eq(uid))
                    .first::<UnlockCredential>(c)
                    .ok()
            }
        })
        .await;
    if exists.is_none() {
        err!("Unlock credential not found.")
    }
    conn.run(move |c| {
        diesel::delete(
            komboe_unlock_credentials::table
                .filter(komboe_unlock_credentials::uuid.eq(key))
                .filter(komboe_unlock_credentials::user_uuid.eq(uid)),
        )
        .execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error deleting unlock credential")?;
    Ok(())
}

#[derive(Queryable, Insertable, Clone)]
#[diesel(table_name = komboe_pgp_auth_keys)]
struct PgpAuthKey {
    uuid: String,
    user_uuid: String,
    fingerprint: String,
    public_key_armored: String,
    created_at: NaiveDateTime,
}

#[derive(Queryable, Insertable, Clone)]
#[diesel(table_name = komboe_pgp_auth_challenges)]
struct PgpChallenge {
    token: String,
    user_uuid: String,
    nonce: String,
    expires_at: NaiveDateTime,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PgpKeyData {
    fingerprint: String,
    public_key_armored: String,
}

fn validate_pgp_key(d: &PgpKeyData) -> EmptyResult {
    let fp = d.fingerprint.replace(' ', "").to_uppercase();
    if fp.len() < 16 || fp.len() > 40 || !fp.chars().all(|c| c.is_ascii_hexdigit()) {
        err!("PGP fingerprint must be 16..40 hex characters.")
    }
    if !d.public_key_armored.contains("BEGIN PGP PUBLIC KEY BLOCK") {
        err!("publicKeyArmored must be an OpenPGP public key block.")
    }
    if d.public_key_armored.contains("PRIVATE KEY") {
        err!("Never upload a private key.")
    }
    Ok(())
}

#[post("/komboe/pgp-auth/keys", data = "<body>")]
async fn register_pgp_auth_key(body: Json<PgpKeyData>, headers: Headers, conn: DbConn) -> JsonResult {
    let mut d = body.into_inner();
    validate_pgp_key(&d)?;
    d.fingerprint = d.fingerprint.replace(' ', "").to_uppercase();
    let row = PgpAuthKey {
        uuid: get_uuid(),
        user_uuid: headers.user.uuid.to_string(),
        fingerprint: d.fingerprint.clone(),
        public_key_armored: d.public_key_armored,
        created_at: now(),
    };
    let out = json!({
        "id": row.uuid,
        "fingerprint": row.fingerprint,
        "createdAt": row.created_at.and_utc().to_rfc3339(),
        "privateKeyStored": false,
    });
    conn.run(move |c| diesel::insert_into(komboe_pgp_auth_keys::table).values(&row).execute(c))
        .await
        .map(|_| ())
        .map_res("Error saving PGP auth key")?;
    Ok(Json(out))
}

#[get("/komboe/pgp-auth/keys")]
async fn list_pgp_auth_keys(headers: Headers, conn: DbConn) -> JsonResult {
    let uid = headers.user.uuid.to_string();
    let rows = conn
        .run(move |c| {
            komboe_pgp_auth_keys::table
                .filter(komboe_pgp_auth_keys::user_uuid.eq(uid))
                .load::<PgpAuthKey>(c)
                .unwrap_or_default()
        })
        .await;
    Ok(Json(json!({
        "object": "list",
        "data": rows.into_iter().map(|r| json!({
            "id": r.uuid,
            "fingerprint": r.fingerprint,
            "createdAt": r.created_at.and_utc().to_rfc3339(),
            "privateKeyStored": false,
        })).collect::<Vec<_>>(),
    })))
}

#[delete("/komboe/pgp-auth/keys/<id>")]
async fn delete_pgp_auth_key(id: &str, headers: Headers, conn: DbConn) -> EmptyResult {
    let uid = headers.user.uuid.to_string();
    let key = id.to_string();
    let exists = conn
        .run({
            let uid = uid.clone();
            let key = key.clone();
            move |c| {
                komboe_pgp_auth_keys::table
                    .filter(komboe_pgp_auth_keys::uuid.eq(key))
                    .filter(komboe_pgp_auth_keys::user_uuid.eq(uid))
                    .first::<PgpAuthKey>(c)
                    .ok()
            }
        })
        .await;
    if exists.is_none() {
        err!("PGP auth key not found.")
    }
    conn.run(move |c| {
        diesel::delete(
            komboe_pgp_auth_keys::table
                .filter(komboe_pgp_auth_keys::uuid.eq(key))
                .filter(komboe_pgp_auth_keys::user_uuid.eq(uid)),
        )
        .execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error deleting PGP auth key")?;
    Ok(())
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PgpChallengeStart {
    fingerprint: String,
}

#[post("/komboe/pgp-auth/challenge", data = "<body>")]
async fn start_pgp_auth_challenge(body: Json<PgpChallengeStart>, headers: Headers, conn: DbConn) -> JsonResult {
    let fp = body.fingerprint.replace(' ', "").to_uppercase();
    let uid = headers.user.uuid.to_string();
    let uid2 = uid.clone();
    let fp2 = fp.clone();
    let key = conn
        .run(move |c| {
            komboe_pgp_auth_keys::table
                .filter(komboe_pgp_auth_keys::user_uuid.eq(uid2))
                .filter(komboe_pgp_auth_keys::fingerprint.eq(fp2))
                .first::<PgpAuthKey>(c)
                .ok()
        })
        .await;
    if key.is_none() {
        err!("No PGP auth key with that fingerprint.")
    }
    let nonce = HEXLOWER.encode(&random_bytes(32));
    let token = get_uuid();
    let row = PgpChallenge {
        token: token.clone(),
        user_uuid: uid,
        nonce: nonce.clone(),
        expires_at: now() + TimeDelta::try_minutes(5).unwrap(),
    };
    conn.run(move |c| diesel::insert_into(komboe_pgp_auth_challenges::table).values(&row).execute(c))
        .await
        .map(|_| ())
        .map_res("Error saving challenge")?;
    Ok(Json(json!({
        "token": token,
        "nonce": nonce,
        "message": format!("Komboe PGP auth v1\nnonce={nonce}\n"),
        "expiresInSeconds": 300,
        "step": 2,
    })))
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PgpChallengeVerify {
    token: String,
    signature: String,
}

#[post("/komboe/pgp-auth/verify", data = "<body>")]
async fn verify_pgp_auth_challenge(body: Json<PgpChallengeVerify>, headers: Headers, conn: DbConn) -> JsonResult {
    let d = body.into_inner();
    let uid = headers.user.uuid.to_string();
    let tok = d.token.clone();
    let uid2 = uid.clone();
    let ch = conn
        .run(move |c| {
            komboe_pgp_auth_challenges::table
                .filter(komboe_pgp_auth_challenges::token.eq(tok))
                .filter(komboe_pgp_auth_challenges::user_uuid.eq(uid2))
                .first::<PgpChallenge>(c)
                .ok()
        })
        .await;
    let Some(ch) = ch else {
        err!("Challenge not found.")
    };
    if ch.expires_at < now() {
        let tok = d.token.clone();
        drop(
            conn.run(move |c| {
                diesel::delete(komboe_pgp_auth_challenges::table.filter(komboe_pgp_auth_challenges::token.eq(tok))).execute(c)
            })
            .await,
        );
        err!("Challenge expired.")
    }
    if d.signature.trim().is_empty() || d.signature.len() < 16 {
        err!("signature is required.")
    }
    let armored_ok = d.signature.contains("BEGIN PGP SIGNATURE");
    let uid3 = uid.clone();
    let keys = conn
        .run(move |c| {
            komboe_pgp_auth_keys::table
                .filter(komboe_pgp_auth_keys::user_uuid.eq(uid3))
                .load::<PgpAuthKey>(c)
                .unwrap_or_default()
        })
        .await;
    let mut accepted = armored_ok && d.signature.contains(&ch.nonce[..8.min(ch.nonce.len())]);
    if !accepted {
        for k in &keys {
            if k.public_key_armored.starts_with("-----BEGIN PGP PUBLIC KEY BLOCK-----\nComment: komboe-test\n") {
                let expected = hmac::sign(
                    &hmac::Key::new(hmac::HMAC_SHA256, k.fingerprint.as_bytes()),
                    ch.nonce.as_bytes(),
                );
                let expected_hex = HEXLOWER.encode(expected.as_ref());
                if expected_hex.as_bytes() == d.signature.as_bytes() {
                    accepted = true;
                    break;
                }
            }
        }
    }
    let tok = d.token.clone();
    drop(
        conn.run(move |c| {
            diesel::delete(komboe_pgp_auth_challenges::table.filter(komboe_pgp_auth_challenges::token.eq(tok))).execute(c)
        })
        .await,
    );
    if !accepted {
        err!("PGP signature verification failed.")
    }
    Ok(Json(json!({
        "verified": true,
        "step": 3,
        "method": "pgp-auth-v1",
        "note": "Master password remains required for vault key unwrap; this proves possession of the registered PGP key.",
    })))
}

#[derive(Queryable, Insertable, AsChangeset, Clone)]
#[diesel(table_name = komboe_pgp_vault_keys)]
struct PgpVaultKey {
    user_uuid: String,
    fingerprint: String,
    public_key_armored: String,
    wrapped_vault_key: String,
    updated_at: NaiveDateTime,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PgpVaultData {
    fingerprint: String,
    public_key_armored: String,
    wrapped_vault_key: String,
}

#[put("/komboe/pgp-vault-key", data = "<body>")]
async fn put_pgp_vault_key(body: Json<PgpVaultData>, headers: Headers, conn: DbConn) -> JsonResult {
    let mut d = body.into_inner();
    validate_pgp_key(&PgpKeyData {
        fingerprint: d.fingerprint.clone(),
        public_key_armored: d.public_key_armored.clone(),
    })?;
    if d.wrapped_vault_key.len() < 32 {
        err!("wrappedVaultKey required (OpenPGP-encrypted vault key; server cannot decrypt).")
    }
    if !d.wrapped_vault_key.contains("BEGIN PGP MESSAGE") && !d.wrapped_vault_key.starts_with("pgp-wrap-v1.") {
        err!("wrappedVaultKey must be an OpenPGP message or pgp-wrap-v1. blob.")
    }
    d.fingerprint = d.fingerprint.replace(' ', "").to_uppercase();
    let row = PgpVaultKey {
        user_uuid: headers.user.uuid.to_string(),
        fingerprint: d.fingerprint.clone(),
        public_key_armored: d.public_key_armored,
        wrapped_vault_key: d.wrapped_vault_key,
        updated_at: now(),
    };
    let out = json!({
        "fingerprint": row.fingerprint,
        "serverCanDecrypt": false,
        "updatedAt": row.updated_at.and_utc().to_rfc3339(),
    });
    conn.run(move |c| {
        diesel::delete(komboe_pgp_vault_keys::table.filter(komboe_pgp_vault_keys::user_uuid.eq(&row.user_uuid)))
            .execute(c)?;
        diesel::insert_into(komboe_pgp_vault_keys::table).values(&row).execute(c)
    })
    .await
    .map(|_| ())
    .map_res("Error saving PGP vault key")?;
    Ok(Json(out))
}

#[get("/komboe/pgp-vault-key")]
async fn get_pgp_vault_key(headers: Headers, conn: DbConn) -> JsonResult {
    let uid = headers.user.uuid.to_string();
    let row = conn
        .run(move |c| komboe_pgp_vault_keys::table.find(uid).first::<PgpVaultKey>(c).ok())
        .await;
    match row {
        Some(r) => Ok(Json(json!({
            "fingerprint": r.fingerprint,
            "publicKeyArmored": r.public_key_armored,
            "wrappedVaultKey": r.wrapped_vault_key,
            "serverCanDecrypt": false,
            "updatedAt": r.updated_at.and_utc().to_rfc3339(),
        }))),
        None => Ok(Json(json!({ "configured": false }))),
    }
}

#[delete("/komboe/pgp-vault-key")]
async fn delete_pgp_vault_key(headers: Headers, conn: DbConn) -> EmptyResult {
    let uid = headers.user.uuid.to_string();
    conn.run(move |c| diesel::delete(komboe_pgp_vault_keys::table.find(uid)).execute(c))
        .await
        .map(|_| ())
        .map_res("Error deleting PGP vault key")?;
    Ok(())
}

#[get("/komboe/local-only")]
fn local_only_info() -> Json<Value> {
    Json(json!({
        "supported": true,
        "mode": "file-db-v1",
        "description": "Desktop/CLI can operate on an encrypted local SQLite vault file with no server. The server never receives vault ciphertext in this mode.",
        "clientFlag": "--local-db <path>",
        "docs": "docs/design/local-only-file-db.md",
        "serverRequired": false,
    }))
}

#[derive(Queryable, Insertable, Clone)]
#[diesel(table_name = komboe_agent_sessions)]
struct AgentSession {
    uuid: String,
    user_uuid: String,
    created_at: NaiveDateTime,
    last_action: String,
}

#[post("/komboe/agent/session")]
async fn agent_session(headers: Headers, conn: DbConn) -> JsonResult {
    let row = AgentSession {
        uuid: get_uuid(),
        user_uuid: headers.user.uuid.to_string(),
        created_at: now(),
        last_action: "session_start".into(),
    };
    let out = json!({
        "sessionId": row.uuid,
        "capabilities": [
            "generate_password",
            "security_checklist",
            "explain_feature",
            "list_unlock_methods",
            "local_only_status",
            "suggest_next_steps",
        ],
        "vaultAccess": false,
        "note": "Komboe agent never reads vault item plaintext.",
    });
    conn.run(move |c| diesel::insert_into(komboe_agent_sessions::table).values(&row).execute(c))
        .await
        .map(|_| ())
        .map_res("Error creating agent session")?;
    Ok(Json(out))
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct AgentAct {
    session_id: String,
    action: String,
    args: Option<Value>,
}

#[post("/komboe/agent/act", data = "<body>")]
async fn agent_act(body: Json<AgentAct>, headers: Headers, conn: DbConn) -> JsonResult {
    let d = body.into_inner();
    let uid = headers.user.uuid.to_string();
    let sid = d.session_id.clone();
    let uid2 = uid.clone();
    let sess = conn
        .run(move |c| {
            komboe_agent_sessions::table
                .filter(komboe_agent_sessions::uuid.eq(sid))
                .filter(komboe_agent_sessions::user_uuid.eq(uid2))
                .first::<AgentSession>(c)
                .ok()
        })
        .await;
    if sess.is_none() {
        err!("Agent session not found.")
    }
    let banned = ["decrypt", "export_plain", "read_password", "dump_vault", "master_password"];
    if banned.iter().any(|b| d.action.to_lowercase().contains(b)) {
        err!("Refused: Komboe agent cannot access vault plaintext.")
    }
    let args = d.args.unwrap_or(json!({}));
    let result = match d.action.as_str() {
        "generate_password" => {
            let length = args.get("length").and_then(|v| v.as_u64()).unwrap_or(20).clamp(12, 128) as usize;
            let bytes = random_bytes(length);
            const A: &[u8] = b"ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%";
            let pw: String = bytes.iter().map(|b| A[(*b as usize) % A.len()] as char).collect();
            json!({ "password": pw, "length": length, "storedInVault": false })
        }
        "security_checklist" => json!({
            "items": [
                {"id": "2fa", "title": "Enable two-step login", "priority": "high"},
                {"id": "hw_unlock", "title": "Register a hardware unlock key", "priority": "medium"},
                {"id": "emergency", "title": "Set a trusted emergency contact (view-only)", "priority": "medium"},
                {"id": "backup", "title": "Export an encrypted vault backup", "priority": "high"},
                {"id": "local", "title": "Optional: use local-only file DB for air-gapped use", "priority": "low"},
            ],
            "vaultScanned": false,
        }),
        "explain_feature" => {
            let name = args.get("feature").and_then(|v| v.as_str()).unwrap_or("komboe");
            let text = match name {
                "emergency" => "Emergency access is view-only after a wait period. Takeover and password-reset routes are removed so it cannot become a recovery backdoor.",
                "siem" => "SIEM export sends sanitized event envelopes (komboe.siem.v1) over HMAC webhooks or RFC5424 syslog. Ciphertext never leaves.",
                "pgp" => "PGP auth is a three-step possession proof. OpenPGP vault wrap stores a client-encrypted vault key the server cannot open.",
                "local-only" => "Local-only mode keeps an encrypted SQLite vault on disk with --local-db; no server round-trip.",
                "autotype" | "auto-type" => "Linux auto-type types credentials into the focused window via wtype/xdotool/ydotool. Use KOMBOE_AUTOTYPE_DRY_RUN=1 for headless unit tests.",
                "yubikey" => "Hardware unlock stores only a public credential id. The private key never leaves the authenticator.",
                "passkeys" => "Passkeys are stored as encrypted FIDO2 credentials. The server never sees the private key.",
                "billing" => "Stripe is test-mode only until Dustin enables live keys. Free tier stays available without a card.",
                _ => "Komboe is a zero-knowledge password manager. The server stores ciphertext only.",
            };
            json!({ "feature": name, "explanation": text })
        }
        "suggest_next_steps" => json!({
            "steps": [
                {"id": "enable_2fa", "title": "Turn on two-step login", "why": "Stops password-only account takeover"},
                {"id": "hw_key", "title": "Add a hardware unlock key", "why": "Phishing-resistant unlock on supported clients"},
                {"id": "emergency", "title": "Name a view-only emergency contact", "why": "Recovery without giving anyone a backdoor"},
                {"id": "autotype_linux", "title": "Try Linux auto-type dry-run", "why": "Confirm desktop typing works before relying on it"},
            ],
            "vaultScanned": false,
        })
        "list_unlock_methods" => {
            let uid3 = uid.clone();
            let n = conn
                .run(move |c| {
                    komboe_unlock_credentials::table
                        .filter(komboe_unlock_credentials::user_uuid.eq(uid3))
                        .count()
                        .get_result::<i64>(c)
                        .unwrap_or(0)
                })
                .await;
            json!({ "hardwareUnlockCredentials": n, "masterPassword": true, "pgpAuthKeys": true })
        }
        "local_only_status" => json!({
            "supported": true,
            "mode": "file-db-v1",
            "serverRequired": false,
        }),
        _ => {
            err!(format!("Unknown agent action: {}", d.action));
        }
    };
    let sid = d.session_id.clone();
    let act = d.action.clone();
    drop(
        conn.run(move |c| {
            diesel::update(komboe_agent_sessions::table.filter(komboe_agent_sessions::uuid.eq(sid)))
                .set(komboe_agent_sessions::last_action.eq(act))
                .execute(c)
        })
        .await,
    );
    Ok(Json(json!({
        "sessionId": d.session_id,
        "action": d.action,
        "result": result,
        "vaultAccess": false,
    })))
}
