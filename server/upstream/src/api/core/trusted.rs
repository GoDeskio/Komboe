//! Trusted-device unlock. The server stores ciphertext the client already wrapped
//! to a device key. It never unwraps a user key and never accepts an organization
//! reset-password enrollment as a substitute.

use diesel::prelude::*;
use rocket::{
    Route,
    http::Status,
    request::{FromRequest, Outcome, Request},
    serde::json::{Json, Value, json},
};
use serde::Deserialize;

use crate::{
    api::{EmptyResult, JsonResult},
    auth::Headers,
    db::{
        DbConn,
        models::{Device, DeviceId, UserId},
        schema::{devices, komboe_device_trust},
    },
};

pub fn routes() -> Vec<Route> {
    routes![put_keys, retrieve_keys, update_trust, lost_trust, untrust, deactivate]
}

#[derive(Queryable, Insertable, Clone)]
#[diesel(table_name = komboe_device_trust)]
struct TrustRow {
    device_uuid: String,
    user_uuid: String,
    encrypted_user_key: String,
    encrypted_public_key: String,
    encrypted_private_key: String,
}

fn encstring(value: &str) -> EmptyResult {
    if value.len() < 8 || value.len() > 20_000 || !value.contains('.') {
        err!("Trusted device material must be client ciphertext")
    }
    Ok(())
}

async fn load(device: &str, user: &str, conn: &DbConn) -> Option<TrustRow> {
    let (device, user) = (device.to_string(), user.to_string());
    conn.run(move |c| {
        komboe_device_trust::table
            .filter(komboe_device_trust::device_uuid.eq(device))
            .filter(komboe_device_trust::user_uuid.eq(user))
            .first::<TrustRow>(c)
            .ok()
    })
    .await
}

async fn save(row: TrustRow, conn: &DbConn) -> EmptyResult {
    if let Err(e) = conn
        .run(move |c| {
            diesel::delete(
                komboe_device_trust::table
                    .filter(komboe_device_trust::device_uuid.eq(&row.device_uuid))
                    .filter(komboe_device_trust::user_uuid.eq(&row.user_uuid)),
            )
            .execute(c)?;
            diesel::insert_into(komboe_device_trust::table).values(&row).execute(c)
        })
        .await
    {
        err!(format!("Error saving trusted device: {e}"));
    }
    Ok(())
}

async fn clear(device: &str, user: &str, conn: &DbConn) -> EmptyResult {
    let (device, user) = (device.to_string(), user.to_string());
    if let Err(e) = conn
        .run(move |c| {
            diesel::delete(
                komboe_device_trust::table
                    .filter(komboe_device_trust::device_uuid.eq(device))
                    .filter(komboe_device_trust::user_uuid.eq(user)),
            )
            .execute(c)
        })
        .await
    {
        err!(format!("Error clearing trusted device: {e}"));
    }
    Ok(())
}

pub async fn any_trusted(user: &UserId, conn: &DbConn) -> bool {
    let user = user.to_string();
    conn.run(move |c| {
        komboe_device_trust::table
            .filter(komboe_device_trust::user_uuid.eq(user))
            .count()
            .get_result::<i64>(c)
            .unwrap_or(0)
            > 0
    })
    .await
}

/// Device types that can approve a login request (Bitwarden's LoginApprovingDeviceTypes:
/// mobile and desktop apps).
const APPROVING_TYPES: [i32; 7] = [0, 1, 15, 6, 7, 8, 16];

/// True only when the user has *another* trusted device of an approving type that still
/// exists for this user, so "approve from your other device" is an option that can work.
pub async fn has_login_approving_device(current: &DeviceId, user: &UserId, conn: &DbConn) -> bool {
    let (current, user) = (current.to_string(), user.to_string());
    conn.run(move |c| {
        let trusted: Vec<String> = komboe_device_trust::table
            .filter(komboe_device_trust::user_uuid.eq(&user))
            .filter(komboe_device_trust::device_uuid.ne(&current))
            .select(komboe_device_trust::device_uuid)
            .load(c)
            .unwrap_or_default();
        !trusted.is_empty()
            && devices::table
                .filter(devices::user_uuid.eq(&user))
                .filter(devices::uuid.eq_any(trusted))
                .filter(devices::atype.eq_any(APPROVING_TYPES))
                .count()
                .get_result::<i64>(c)
                .unwrap_or(0)
                > 0
    })
    .await
}

/// Login payload for this device.
///
/// Accounts with no master password always receive the option, so the web vault
/// can trust this browser instead of demanding a password. Key Connector is never set.
pub async fn decryption_option(
    device: &DeviceId,
    user: &UserId,
    has_master_password: bool,
    conn: &DbConn,
) -> Option<Value> {
    let current = load(&device.to_string(), &user.to_string(), conn).await;
    let approving = current.is_some() || any_trusted(user, conn).await;
    if has_master_password && !approving {
        return None;
    }
    let mut option = json!({
        "HasAdminApproval": false,
        "HasLoginApprovingDevice": has_login_approving_device(device, user, conn).await,
        "HasManageResetPasswordPermission": false,
        "IsTdeOffboarding": false,
    });
    if let Some(row) = current {
        option["EncryptedPrivateKey"] = json!(row.encrypted_private_key);
        option["EncryptedUserKey"] = json!(row.encrypted_user_key);
    }
    Some(option)
}

pub async fn apply_trust(mut value: Value, device: &DeviceId, user: &UserId, conn: &DbConn) -> Value {
    if let Some(row) = load(&device.to_string(), &user.to_string(), conn).await {
        value["isTrusted"] = json!(true);
        value["encryptedUserKey"] = json!(row.encrypted_user_key);
        value["encryptedPublicKey"] = json!(row.encrypted_public_key);
    }
    value
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct KeysBody {
    encrypted_user_key: String,
    encrypted_public_key: String,
    encrypted_private_key: String,
}

#[put("/devices/<device_id>/keys", data = "<body>")]
async fn put_keys(device_id: DeviceId, body: Json<KeysBody>, headers: Headers, conn: DbConn) -> JsonResult {
    let Some(device) = Device::find_by_uuid_and_user(&device_id, &headers.user.uuid, &conn).await else {
        err!("No device found");
    };
    let body = body.into_inner();
    encstring(&body.encrypted_user_key)?;
    encstring(&body.encrypted_public_key)?;
    encstring(&body.encrypted_private_key)?;
    save(
        TrustRow {
            device_uuid: device.uuid.to_string(),
            user_uuid: headers.user.uuid.to_string(),
            encrypted_user_key: body.encrypted_user_key,
            encrypted_public_key: body.encrypted_public_key,
            encrypted_private_key: body.encrypted_private_key,
        },
        &conn,
    )
    .await?;
    Ok(Json(apply_trust(device.to_json(), &device.uuid, &headers.user.uuid, &conn).await))
}

#[post("/devices/<device_id>/retrieve-keys")]
async fn retrieve_keys(device_id: DeviceId, headers: Headers, conn: DbConn) -> JsonResult {
    let Some(device) = Device::find_by_uuid_and_user(&device_id, &headers.user.uuid, &conn).await else {
        err!("No device found");
    };
    let Some(row) = load(&device.uuid.to_string(), &headers.user.uuid.to_string(), &conn).await else {
        err!("This device is not trusted");
    };
    Ok(Json(json!({
        "id": device.uuid,
        "name": device.name,
        "identifier": device.uuid,
        "type": device.atype,
        "creationDate": crate::util::format_date(&device.created_at),
        "encryptedUserKey": row.encrypted_user_key,
        "encryptedPublicKey": row.encrypted_public_key,
    })))
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct KeyUpdate {
    encrypted_public_key: Option<String>,
    encrypted_user_key: Option<String>,
    device_id: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateTrustBody {
    current_device: Option<KeyUpdate>,
    other_devices: Option<Vec<KeyUpdate>>,
}

async fn rotate(device: &str, user: &str, update: &KeyUpdate, conn: &DbConn) -> EmptyResult {
    let Some(mut row) = load(device, user, conn).await else {
        return Ok(());
    };
    if let Some(key) = update.encrypted_user_key.as_deref() {
        encstring(key)?;
        row.encrypted_user_key = key.to_string();
    }
    if let Some(key) = update.encrypted_public_key.as_deref() {
        encstring(key)?;
        row.encrypted_public_key = key.to_string();
    }
    save(row, conn).await
}

#[post("/devices/update-trust", data = "<body>")]
async fn update_trust(body: Json<UpdateTrustBody>, headers: Headers, conn: DbConn) -> EmptyResult {
    let body = body.into_inner();
    let user_id = headers.user.uuid.to_string();
    if let Some(current) = body.current_device {
        rotate(&headers.device.uuid.to_string(), &user_id, &current, &conn).await?;
    }
    for other in body.other_devices.unwrap_or_default() {
        let Some(id) = other.device_id.clone() else {
            continue;
        };
        if Device::find_by_uuid_and_user(&DeviceId::from(id.clone()), &headers.user.uuid, &conn).await.is_some() {
            rotate(&id, &user_id, &other, &conn).await?;
        }
    }
    Ok(())
}

struct DeviceHeader(String);

#[rocket::async_trait]
impl<'r> FromRequest<'r> for DeviceHeader {
    type Error = &'static str;

    async fn from_request(req: &'r Request<'_>) -> Outcome<Self, Self::Error> {
        match req.headers().get_one("Device-Identifier") {
            Some(id) if !id.is_empty() => Outcome::Success(DeviceHeader(id.to_string())),
            _ => Outcome::Error((Status::BadRequest, "Device-Identifier is required")),
        }
    }
}

#[post("/devices/lost-trust")]
async fn lost_trust(header: DeviceHeader, headers: Headers, conn: DbConn) -> EmptyResult {
    if Device::find_by_uuid_and_user(&DeviceId::from(header.0.clone()), &headers.user.uuid, &conn).await.is_none() {
        err!("No device found");
    }
    clear(&header.0, &headers.user.uuid.to_string(), &conn).await
}

#[derive(Deserialize)]
struct UntrustBody {
    devices: Vec<String>,
}

#[post("/devices/untrust", data = "<body>")]
async fn untrust(body: Json<UntrustBody>, headers: Headers, conn: DbConn) -> EmptyResult {
    for id in &body.devices {
        if Device::find_by_uuid_and_user(&DeviceId::from(id.clone()), &headers.user.uuid, &conn).await.is_some() {
            clear(id, &headers.user.uuid.to_string(), &conn).await?;
        }
    }
    Ok(())
}

#[post("/devices/<device_id>/deactivate")]
async fn deactivate(device_id: DeviceId, headers: Headers, conn: DbConn) -> EmptyResult {
    if Device::find_by_uuid_and_user(&device_id, &headers.user.uuid, &conn).await.is_none() {
        err!("No device found");
    }
    clear(&device_id.to_string(), &headers.user.uuid.to_string(), &conn).await
}
