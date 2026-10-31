// Komboe: account encryption v2 (XChaCha20-Poly1305, EncString type 7 / COSE) key material.
//
// Zero-knowledge: every field here is produced and consumed by the client SDK.
// The server stores the values as opaque strings, checks only shape and size,
// and never sees a user key, a signing key or any plaintext. The only server-side
// logic is downgrade protection on the plaintext `security_version` counter.
use diesel::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};

use crate::{
    api::EmptyResult,
    db::{DbConn, schema::komboe_account_keys_v2},
    error::MapResult,
};

use super::User;

/// Upper bound for any single opaque key blob (COSE strings are ~1.3x the v1 size).
const MAX_BLOB: usize = 16 * 1024;

#[derive(Clone, Debug, Insertable, Queryable, AsChangeset)]
#[diesel(table_name = komboe_account_keys_v2)]
#[diesel(treat_none_as_null = true)]
pub struct AccountKeysV2 {
    pub user_uuid: String,
    pub wrapped_signing_key: String,
    pub verifying_key: String,
    pub signed_public_key: Option<String>,
    pub security_state: String,
    pub security_version: i64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SignatureKeyPairData {
    #[serde(alias = "WrappedSigningKey")]
    pub wrapped_signing_key: String,
    #[serde(alias = "VerifyingKey")]
    pub verifying_key: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SecurityStateData {
    #[serde(alias = "SecurityState")]
    pub security_state: String,
    #[serde(alias = "SecurityVersion")]
    pub security_version: i64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicKeyEncryptionKeyPairData {
    #[serde(alias = "WrappedPrivateKey")]
    pub wrapped_private_key: String,
    #[serde(alias = "PublicKey")]
    pub public_key: String,
    #[serde(alias = "SignedPublicKey")]
    pub signed_public_key: Option<String>,
}

/// The `accountKeys` request object (upstream `AccountKeysRequestModel`).
/// v1 clients send only the deprecated flat fields; v2 clients add the signature
/// key pair and the signed security state.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountKeysData {
    #[serde(alias = "UserKeyEncryptedAccountPrivateKey")]
    pub user_key_encrypted_account_private_key: Option<String>,
    #[serde(alias = "AccountPublicKey")]
    pub account_public_key: Option<String>,
    #[serde(alias = "PublicKeyEncryptionKeyPair")]
    pub public_key_encryption_key_pair: Option<PublicKeyEncryptionKeyPairData>,
    #[serde(alias = "SignatureKeyPair")]
    pub signature_key_pair: Option<SignatureKeyPairData>,
    #[serde(alias = "SecurityState")]
    pub security_state: Option<SecurityStateData>,
}

fn blob_ok(s: &str) -> bool {
    !s.is_empty() && s.len() <= MAX_BLOB && s.bytes().all(|b| b.is_ascii_graphic())
}

pub fn aead_v2_enabled() -> bool {
    matches!(std::env::var("KOMBOE_AEAD_V2").as_deref(), Ok("true" | "1"))
}

impl AccountKeysData {
    pub fn private_key(&self) -> Option<&String> {
        self.public_key_encryption_key_pair
            .as_ref()
            .map(|p| &p.wrapped_private_key)
            .or(self.user_key_encrypted_account_private_key.as_ref())
    }

    pub fn public_key(&self) -> Option<&String> {
        self.public_key_encryption_key_pair.as_ref().map(|p| &p.public_key).or(self.account_public_key.as_ref())
    }

    pub fn is_v2(&self) -> bool {
        self.signature_key_pair.is_some() || self.security_state.is_some()
    }

    /// Shape/size validation only. Returns the v2 row to store, if this is a v2 request.
    pub fn to_v2(&self, user_uuid: &str) -> Result<Option<AccountKeysV2>, &'static str> {
        if !self.is_v2() {
            return Ok(None);
        }
        if !aead_v2_enabled() {
            return Err("Account encryption v2 is not enabled on this server (KOMBOE_AEAD_V2)");
        }
        let (Some(sig), Some(state)) = (&self.signature_key_pair, &self.security_state) else {
            return Err("signatureKeyPair and securityState must be sent together");
        };
        let signed_public_key = self.public_key_encryption_key_pair.as_ref().and_then(|p| p.signed_public_key.clone());
        let Some(spk) = signed_public_key.as_ref() else {
            return Err("v2 account keys need publicKeyEncryptionKeyPair.signedPublicKey");
        };
        if !(blob_ok(&sig.wrapped_signing_key)
            && blob_ok(&sig.verifying_key)
            && blob_ok(&state.security_state)
            && blob_ok(spk))
        {
            return Err("Invalid or oversized v2 key material");
        }
        // A v2 signing key must be wrapped by the v2 (COSE/XChaCha20-Poly1305) user key: EncString type 7.
        if !sig.wrapped_signing_key.starts_with("7.") {
            return Err("wrappedSigningKey must be an EncString type 7");
        }
        if let Some(pk) = self.private_key()
            && !pk.starts_with("7.")
        {
            return Err("v2 private key must be an EncString type 7");
        }
        if state.security_version < 2 {
            return Err("securityVersion must be >= 2 for v2 accounts");
        }
        Ok(Some(AccountKeysV2 {
            user_uuid: user_uuid.to_owned(),
            wrapped_signing_key: sig.wrapped_signing_key.clone(),
            verifying_key: sig.verifying_key.clone(),
            signed_public_key,
            security_state: state.security_state.clone(),
            security_version: state.security_version,
        }))
    }
}

impl AccountKeysV2 {
    pub async fn find_by_user(user_uuid: &str, conn: &DbConn) -> Option<Self> {
        let user_uuid = user_uuid.to_owned();
        conn.run(move |c| {
            komboe_account_keys_v2::table
                .filter(komboe_account_keys_v2::user_uuid.eq(user_uuid))
                .first::<Self>(c)
                .ok()
        })
        .await
    }

    /// Insert or replace. Refuses to lower `security_version` (server-side downgrade guard).
    pub async fn save(self, conn: &DbConn) -> EmptyResult {
        if let Some(existing) = Self::find_by_user(&self.user_uuid, conn).await {
            if self.security_version < existing.security_version {
                err!("Refusing to downgrade the account security version")
            }
            return conn
                .run(move |c| {
                    diesel::update(
                        komboe_account_keys_v2::table.filter(komboe_account_keys_v2::user_uuid.eq(&self.user_uuid)),
                    )
                    .set(&self)
                    .execute(c)
                    .map_res("Error saving v2 account keys")
                })
                .await;
        }
        conn.run(move |c| {
            diesel::insert_into(komboe_account_keys_v2::table)
                .values(&self)
                .execute(c)
                .map_res("Error saving v2 account keys")
        })
        .await
    }

    pub async fn delete_all_by_user(user_uuid: &str, conn: &DbConn) -> EmptyResult {
        let user_uuid = user_uuid.to_owned();
        conn.run(move |c| {
            diesel::delete(komboe_account_keys_v2::table.filter(komboe_account_keys_v2::user_uuid.eq(user_uuid)))
                .execute(c)
                .map_res("Error deleting v2 account keys")
        })
        .await
    }
}

/// The full `accountKeys` object (upstream `PrivateKeysResponseModel`), v1 or v2.
pub async fn account_keys_json(user: &User, conn: &DbConn) -> Value {
    if user.private_key.is_none() {
        return Value::Null;
    }
    let v2 = AccountKeysV2::find_by_user(&user.uuid.to_string(), conn).await;
    let (sig, state, spk) = match &v2 {
        Some(k) => (
            json!({
                "wrappedSigningKey": k.wrapped_signing_key,
                "verifyingKey": k.verifying_key,
                "object": "signatureKeyPair",
            }),
            json!({
                "securityState": k.security_state,
                "securityVersion": k.security_version,
                "object": "securityState",
            }),
            json!(k.signed_public_key),
        ),
        None => (Value::Null, Value::Null, Value::Null),
    };
    json!({
        "publicKeyEncryptionKeyPair": {
            "wrappedPrivateKey": user.private_key,
            "publicKey": user.public_key,
            "signedPublicKey": spk,
            "object": "publicKeyEncryptionKeyPair",
        },
        "signatureKeyPair": sig,
        "securityState": state,
        "object": "privateKeys"
    })
}
