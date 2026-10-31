//! Komboe: log in with a passkey (Bitwarden-compatible `/api/webauthn` and
//! `grant_type=webauthn`). Passkeys live in their own table, not in `twofactor`,
//! so adding one never turns on two-step login. The PRF key set is ciphertext the
//! client wrapped itself; the server never sees PRF output or the user key.

use std::{sync::LazyLock, time::Duration};

use diesel::prelude::*;
use rocket::{
    Route,
    serde::json::{Json, Value, json},
};
use serde::{Deserialize, Serialize};
use url::Url;
use webauthn_rs::{
    Webauthn, WebauthnBuilder,
    prelude::{
        DiscoverableAuthentication, DiscoverableKey, Passkey, PasskeyAuthentication, PasskeyRegistration,
        PublicKeyCredential, RegisterPublicKeyCredential,
    },
};
use webauthn_rs_proto::{ResidentKeyRequirement, UserVerificationPolicy};

use crate::{
    CONFIG,
    api::{EmptyResult, JsonResult, PasswordOrOtpData},
    auth::Headers,
    crypto,
    db::{
        DbConn,
        models::{User, UserId},
        schema::{komboe_login_passkeys, komboe_passkey_challenges},
    },
    util::get_uuid,
};

const MAX_CREDENTIALS: usize = 5;
const STATE_TTL: Duration = Duration::from_mins(5);

pub fn routes() -> Vec<Route> {
    routes![list, attestation_options, assertion_options, create, update_keys, delete]
}

static WEBAUTHN: LazyLock<Webauthn> = LazyLock::new(|| {
    let domain = CONFIG.domain();
    let rp_id = Url::parse(&domain).map(|u| u.domain().map(str::to_owned)).ok().flatten().unwrap_or_default();
    let rp_origin = Url::parse(&CONFIG.domain_origin()).unwrap();
    WebauthnBuilder::new(&rp_id, &rp_origin)
        .expect("Creating WebauthnBuilder failed")
        .rp_name("Komboe")
        .timeout(Duration::from_mins(3))
        .build()
        .expect("Building Webauthn failed")
});

#[derive(Serialize, Deserialize)]
enum Pending {
    Register(UserId, PasskeyRegistration),
    Assert(UserId, PasskeyAuthentication),
    Login(DiscoverableAuthentication),
}

// Challenge state lives in the database (not process memory) so any server node
// behind a load balancer can finish a ceremony another node started. Rows hold
// only WebAuthn ceremony state (challenge + allowed credential ids), never keys
// or vault data. Each token is single-use: the DELETE that claims it must hit
// exactly one row, so two nodes racing on the same token cannot both succeed.
#[derive(Insertable, Queryable)]
#[diesel(table_name = komboe_passkey_challenges)]
struct ChallengeRow {
    token: String,
    state: String,
    created_at: i64,
}

fn now_secs() -> i64 {
    chrono::Utc::now().timestamp()
}

async fn stash(p: Pending, conn: &DbConn) -> crate::api::ApiResult<String> {
    let token = crypto::encode_random_bytes::<32>(&data_encoding::BASE64URL_NOPAD);
    let row = ChallengeRow {
        token: token.clone(),
        state: serde_json::to_string(&p)?,
        created_at: now_secs(),
    };
    let cutoff = now_secs() - STATE_TTL.as_secs() as i64;
    if let Err(e) = conn
        .run(move |c| {
            diesel::delete(komboe_passkey_challenges::table.filter(komboe_passkey_challenges::created_at.lt(cutoff)))
                .execute(c)?;
            diesel::insert_into(komboe_passkey_challenges::table).values(&row).execute(c)
        })
        .await
    {
        err!(format!("Error saving passkey challenge: {e}"));
    }
    Ok(token)
}

async fn take(token: &str, conn: &DbConn) -> Option<Pending> {
    let token = token.to_string();
    let cutoff = now_secs() - STATE_TTL.as_secs() as i64;
    let row: ChallengeRow = conn
        .run(move |c| {
            let row = komboe_passkey_challenges::table
                .filter(komboe_passkey_challenges::token.eq(&token))
                .first::<ChallengeRow>(c)
                .ok()?;
            let n = diesel::delete(komboe_passkey_challenges::table.filter(komboe_passkey_challenges::token.eq(&token)))
                .execute(c)
                .ok()?;
            (n == 1).then_some(row)
        })
        .await?;
    if row.created_at < cutoff {
        return None;
    }
    serde_json::from_str(&row.state).ok()
}

#[derive(Queryable, Insertable, Clone)]
#[diesel(table_name = komboe_login_passkeys)]
pub struct PasskeyRow {
    pub uuid: String,
    pub user_uuid: String,
    pub name: String,
    pub cred_id: String,
    pub credential: String,
    pub supports_prf: bool,
    pub encrypted_user_key: Option<String>,
    pub encrypted_public_key: Option<String>,
    pub encrypted_private_key: Option<String>,
}

impl PasskeyRow {
    fn passkey(&self) -> Option<Passkey> {
        serde_json::from_str(&self.credential).ok()
    }

    fn prf_status(&self) -> i32 {
        match (self.supports_prf, self.encrypted_user_key.is_some()) {
            (true, true) => 0,
            (true, false) => 1,
            _ => 2,
        }
    }

    /// Bitwarden `WebAuthnPrfDecryptionOption`, only when a wrapped key set exists.
    pub fn prf_option(&self) -> Option<Value> {
        match (&self.encrypted_user_key, &self.encrypted_private_key) {
            (Some(uk), Some(pk)) if self.supports_prf => Some(json!({
                "EncryptedPrivateKey": pk,
                "EncryptedUserKey": uk,
                "CredentialId": self.cred_id,
                "Transports": [],
            })),
            _ => None,
        }
    }
}

pub(crate) async fn has_prf_unlock(user: &UserId, conn: &DbConn) -> bool {
    for_user(user, conn).await.iter().any(|p| p.encrypted_user_key.is_some())
}

async fn for_user(user: &UserId, conn: &DbConn) -> Vec<PasskeyRow> {
    let user = user.to_string();
    conn.run(move |c| {
        komboe_login_passkeys::table
            .filter(komboe_login_passkeys::user_uuid.eq(user))
            .load::<PasskeyRow>(c)
            .unwrap_or_default()
    })
    .await
}

async fn by_cred_id(cred_id: String, conn: &DbConn) -> Option<PasskeyRow> {
    conn.run(move |c| {
        komboe_login_passkeys::table.filter(komboe_login_passkeys::cred_id.eq(cred_id)).first::<PasskeyRow>(c).ok()
    })
    .await
}

async fn store(row: PasskeyRow, conn: &DbConn) -> EmptyResult {
    if let Err(e) = conn
        .run(move |c| {
            diesel::delete(komboe_login_passkeys::table.filter(komboe_login_passkeys::uuid.eq(&row.uuid)))
                .execute(c)?;
            diesel::insert_into(komboe_login_passkeys::table).values(&row).execute(c)
        })
        .await
    {
        err!(format!("Error saving passkey: {e}"));
    }
    Ok(())
}

fn ciphertext(v: Option<&String>) -> EmptyResult {
    if let Some(v) = v
        && (v.len() < 8 || v.len() > 20_000 || !v.contains('.'))
    {
        err!("Passkey key material must be client ciphertext")
    }
    Ok(())
}

/// Bitwarden clients send `clientDataJson`; webauthn-rs expects `clientDataJSON`.
/// Client extension results are dropped: PRF output must never reach the server.
fn normalize(mut v: Value) -> Value {
    if let Some(r) = v.get_mut("response").and_then(Value::as_object_mut)
        && let Some(cd) = r.remove("clientDataJson")
    {
        r.insert("clientDataJSON".into(), cd);
    }
    if let Some(o) = v.as_object_mut() {
        o.insert("extensions".into(), json!({}));
    }
    v
}

fn options_json(mut v: Value) -> Value {
    // Only the publicKey part goes to the browser; drop conditional mediation.
    let mut pk = v.get_mut("publicKey").map(Value::take).unwrap_or(v);
    if let Some(o) = pk.as_object_mut() {
        // Creation options: the web client maps excludeCredentials unconditionally.
        if o.contains_key("rp") && o.get("excludeCredentials").is_none_or(Value::is_null) {
            o.insert("excludeCredentials".into(), json!([]));
        }
        o.remove("hints");
    }
    pk
}

#[get("/webauthn")]
async fn list(headers: Headers, conn: DbConn) -> Json<Value> {
    let data: Vec<Value> = for_user(&headers.user.uuid, &conn)
        .await
        .iter()
        .map(|r| {
            json!({
                "id": r.uuid,
                "name": r.name,
                "prfStatus": r.prf_status(),
                "encryptedPublicKey": r.encrypted_public_key,
                "encryptedUserKey": r.encrypted_user_key,
                "object": "webauthnCredential",
            })
        })
        .collect();
    Json(json!({"object": "list", "data": data, "continuationToken": null}))
}

#[post("/webauthn/attestation-options", data = "<data>")]
async fn attestation_options(data: Json<PasswordOrOtpData>, headers: Headers, conn: DbConn) -> JsonResult {
    let user = headers.user;
    data.into_inner().validate(&user, false, &conn).await?;
    let existing = for_user(&user.uuid, &conn).await;
    if existing.len() >= MAX_CREDENTIALS {
        err!("Maximum number of passkeys reached")
    }
    let exclude = existing.iter().filter_map(PasskeyRow::passkey).map(|p| p.cred_id().clone()).collect::<Vec<_>>();
    let Ok(user_uuid) = uuid::Uuid::parse_str(&user.uuid.to_string()) else {
        err!("Invalid user id")
    };
    let (mut challenge, state) = WEBAUTHN.start_passkey_registration(
        user_uuid,
        &user.email,
        &user.name,
        (!exclude.is_empty()).then_some(exclude),
    )?;
    // Discoverable credential so the user can sign in without typing an email.
    if let Some(sel) = challenge.public_key.authenticator_selection.as_mut() {
        sel.resident_key = Some(ResidentKeyRequirement::Required);
        sel.require_resident_key = true;
        sel.user_verification = UserVerificationPolicy::Required;
    }
    let token = stash(Pending::Register(user.uuid.clone(), state), &conn).await?;
    Ok(Json(json!({
        "options": options_json(serde_json::to_value(challenge)?),
        "token": token,
        "object": "webauthnCredentialCreateOptions",
    })))
}

#[post("/webauthn/assertion-options", data = "<data>")]
async fn assertion_options(data: Json<PasswordOrOtpData>, headers: Headers, conn: DbConn) -> JsonResult {
    let user = headers.user;
    data.into_inner().validate(&user, false, &conn).await?;
    let keys = for_user(&user.uuid, &conn).await.iter().filter_map(PasskeyRow::passkey).collect::<Vec<_>>();
    if keys.is_empty() {
        err!("No passkeys registered")
    }
    let (challenge, state) = WEBAUTHN.start_passkey_authentication(&keys)?;
    let token = stash(Pending::Assert(user.uuid.clone(), state), &conn).await?;
    Ok(Json(json!({
        "options": options_json(serde_json::to_value(challenge)?),
        "token": token,
        "object": "webAuthnLoginAssertionOptions",
    })))
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateData {
    device_response: Value,
    name: String,
    token: String,
    #[serde(default)]
    supports_prf: bool,
    encrypted_user_key: Option<String>,
    encrypted_public_key: Option<String>,
    encrypted_private_key: Option<String>,
}

#[post("/webauthn", data = "<data>")]
async fn create(data: Json<CreateData>, headers: Headers, conn: DbConn) -> EmptyResult {
    let data = data.into_inner();
    let Some(Pending::Register(uid, state)) = take(&data.token, &conn).await else {
        err!("Passkey challenge expired, try again")
    };
    if uid != headers.user.uuid {
        err!("Passkey challenge does not belong to this user")
    }
    if for_user(&uid, &conn).await.len() >= MAX_CREDENTIALS {
        err!("Maximum number of passkeys reached")
    }
    for v in [&data.encrypted_user_key, &data.encrypted_public_key, &data.encrypted_private_key] {
        ciphertext(v.as_ref())?;
    }
    let reg: RegisterPublicKeyCredential = serde_json::from_value(normalize(data.device_response))?;
    let passkey = WEBAUTHN.finish_passkey_registration(&reg, &state)?;
    let name = data.name.trim().chars().take(50).collect::<String>();
    let has_keys = data.encrypted_user_key.is_some() && data.encrypted_private_key.is_some();
    store(
        PasskeyRow {
            uuid: get_uuid(),
            user_uuid: uid.to_string(),
            name: if name.is_empty() {
                "Passkey".into()
            } else {
                name
            },
            cred_id: data_encoding::BASE64URL_NOPAD.encode(passkey.cred_id().as_ref()),
            credential: serde_json::to_string(&passkey)?,
            supports_prf: data.supports_prf,
            encrypted_user_key: has_keys.then(|| data.encrypted_user_key.clone()).flatten(),
            encrypted_public_key: has_keys.then(|| data.encrypted_public_key.clone()).flatten(),
            encrypted_private_key: has_keys.then(|| data.encrypted_private_key.clone()).flatten(),
        },
        &conn,
    )
    .await
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateData {
    device_response: Value,
    token: String,
    encrypted_user_key: String,
    encrypted_public_key: String,
    encrypted_private_key: String,
}

/// Turn on vault encryption for an existing passkey (proves possession first).
#[put("/webauthn", data = "<data>")]
async fn update_keys(data: Json<UpdateData>, headers: Headers, conn: DbConn) -> EmptyResult {
    let data = data.into_inner();
    let Some(Pending::Assert(uid, state)) = take(&data.token, &conn).await else {
        err!("Passkey challenge expired, try again")
    };
    if uid != headers.user.uuid {
        err!("Passkey challenge does not belong to this user")
    }
    for v in [&data.encrypted_user_key, &data.encrypted_public_key, &data.encrypted_private_key] {
        ciphertext(Some(v))?;
    }
    let cred: PublicKeyCredential = serde_json::from_value(normalize(data.device_response))?;
    let result = WEBAUTHN.finish_passkey_authentication(&cred, &state)?;
    let Some(mut row) = by_cred_id(data_encoding::BASE64URL_NOPAD.encode(result.cred_id().as_ref()), &conn).await
    else {
        err!("Passkey not found")
    };
    if row.user_uuid != uid.to_string() || !row.supports_prf {
        err!("Passkey cannot be used for vault encryption")
    }
    if let Some(mut pk) = row.passkey() {
        pk.update_credential(&result);
        row.credential = serde_json::to_string(&pk)?;
    }
    row.encrypted_user_key = Some(data.encrypted_user_key);
    row.encrypted_public_key = Some(data.encrypted_public_key);
    row.encrypted_private_key = Some(data.encrypted_private_key);
    store(row, &conn).await
}

#[post("/webauthn/<id>/delete", data = "<data>")]
async fn delete(id: &str, data: Json<PasswordOrOtpData>, headers: Headers, conn: DbConn) -> EmptyResult {
    data.into_inner().validate(&headers.user, true, &conn).await?;
    let (id, user) = (id.to_string(), headers.user.uuid.to_string());
    let n = conn
        .run(move |c| {
            diesel::delete(
                komboe_login_passkeys::table
                    .filter(komboe_login_passkeys::uuid.eq(id))
                    .filter(komboe_login_passkeys::user_uuid.eq(user)),
            )
            .execute(c)
        })
        .await
        .unwrap_or(0);
    if n == 0 {
        err!("Passkey not found")
    }
    Ok(())
}

/// `GET /identity/accounts/webauthn/assertion-options` (unauthenticated).
pub async fn login_options(conn: &DbConn) -> JsonResult {
    let (challenge, state) = WEBAUTHN.start_discoverable_authentication()?;
    let token = stash(Pending::Login(state), conn).await?;
    Ok(Json(json!({
        "options": options_json(serde_json::to_value(challenge)?),
        "token": token,
        "object": "webAuthnLoginAssertionOptions",
    })))
}

/// Verify a `grant_type=webauthn` assertion. Returns the user and the passkey used.
pub async fn verify_login(token: &str, device_response: &str, conn: &DbConn) -> ApiResultUser {
    let Some(Pending::Login(state)) = take(token, conn).await else {
        err!("Passkey challenge expired, try again")
    };
    let cred: PublicKeyCredential = serde_json::from_value(normalize(serde_json::from_str(device_response)?))?;
    let (user_uuid, cred_id) = WEBAUTHN.identify_discoverable_authentication(&cred)?;
    let cred_id = data_encoding::BASE64URL_NOPAD.encode(cred_id);
    let Some(mut row) = by_cred_id(cred_id, conn).await else {
        err!("Passkey not recognized")
    };
    if row.user_uuid != user_uuid.to_string() {
        err!("Passkey not recognized")
    }
    let Some(mut pk) = row.passkey() else {
        err!("Passkey not recognized")
    };
    let result = WEBAUTHN.finish_discoverable_authentication(&cred, state, &[DiscoverableKey::from(&pk)])?;
    if !result.user_verified() {
        err!("Passkey user verification is required")
    }
    if pk.update_credential(&result).is_some() {
        row.credential = serde_json::to_string(&pk)?;
        store(row.clone(), conn).await?;
    }
    let Some(user) = User::find_by_uuid(&UserId::from(row.user_uuid.clone()), conn).await else {
        err!("Passkey not recognized")
    };
    Ok((user, row))
}

type ApiResultUser = crate::api::ApiResult<(User, PasskeyRow)>;
