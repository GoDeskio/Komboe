// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.core

enum class DeviceType {
    ANDROID,
}

sealed class AuthRequestMethod {
    data class MasterKey(
        val protectedMasterKey: Any? = null,
        val authRequestKey: Any? = null
    ) : AuthRequestMethod()
    data class UserKey(
        val protectedUserKey: Any? = null
    ) : AuthRequestMethod()
}

sealed class DeriveKeyConnectorException(message: String = "derive key connector") : Exception(message) {
    object Crypto : DeriveKeyConnectorException()
    object WrongPassword : DeriveKeyConnectorException()
}

sealed class EncryptionSettingsException(message: String = "encryption settings") : Exception(message) {
    object Crypto : EncryptionSettingsException()
    object CryptoInitialization : EncryptionSettingsException()
    object InvalidUpgradeToken : EncryptionSettingsException()
    object KeyConnectorRetrievalFailed : EncryptionSettingsException()
    object LocalUserDataKeyInitFailed : EncryptionSettingsException()
    object LocalUserDataKeyLoadFailed : EncryptionSettingsException()
    object LocalUserDataMigrationFailed : EncryptionSettingsException()
    object MissingPrivateKey : EncryptionSettingsException()
    object PinUnlockNotAvailable : EncryptionSettingsException()
    object UserIdAlreadySet : EncryptionSettingsException()
    object UserKeyStateRetrievalFailed : EncryptionSettingsException()
    object UserKeyStateUpdateFailed : EncryptionSettingsException()
    object WrongPin : EncryptionSettingsException()
}

sealed class InitUserCryptoMethod {
    data class AuthRequest(
        val requestPrivateKey: Any? = null,
        val method: AuthRequestMethod
    ) : InitUserCryptoMethod()
    data class DecryptedKey(
        val decryptedUserKey: Any? = null
    ) : InitUserCryptoMethod()
    data class DeviceKey(
        val deviceKey: Any? = null,
        val protectedDevicePrivateKey: Any? = null,
        val deviceProtectedUserKey: Any? = null
    ) : InitUserCryptoMethod()
    data class KeyConnector(
        val masterKey: Any? = null,
        val userKey: Any? = null
    ) : InitUserCryptoMethod()
    data class KeyConnectorUrl(
        val url: Any? = null,
        val keyConnectorKeyWrappedUserKey: Any? = null
    ) : InitUserCryptoMethod()
    data class MasterPasswordUnlock(
        val password: String,
        val masterPasswordUnlock: MasterPasswordUnlockData,
    ) : InitUserCryptoMethod()
    data class Pin(
        val pin: Any? = null,
        val pinProtectedUserKey: Any? = null
    ) : InitUserCryptoMethod()
    data class PinEnvelope(
        val pin: Any? = null,
        val pinProtectedUserKeyEnvelope: Any? = null
    ) : InitUserCryptoMethod()
    data class PinState(
        val pin: Any? = null
    ) : InitUserCryptoMethod()
}

sealed class WrappedAccountCryptographicState {
    data class V1(
        val privateKey: String,
    ) : WrappedAccountCryptographicState()
    data class V2(
        val privateKey: String,
        val securityState: String,
        val signingKey: String,
        val signedPublicKey: String,
    ) : WrappedAccountCryptographicState()
}

data class ClientSettings(
    val identityUrl: String? = null,
    val apiUrl: String? = null,
    val userAgent: String? = null,
    val deviceType: DeviceType,
    val deviceIdentifier: Any? = null,
    val bitwardenClientVersion: Any? = null,
    val bitwardenPackageType: Any? = null
)

data class DeriveKeyConnectorRequest(
    val userKeyEncrypted: Any? = null,
    val password: Any? = null,
    val kdf: Any? = null,
    val email: Any? = null
)

data class FingerprintRequest(
    val fingerprintMaterial: Any? = null,
    val publicKey: Any? = null
)

data class InitOrgCryptoRequest(
    val organizationKeys: Any? = null
)

data class InitUserCryptoRequest(
    val accountCryptographicState: Any? = null,
    val userId: Any? = null,
    val kdfParams: Any? = null,
    val email: Any? = null,
    val method: InitUserCryptoMethod,
    val upgradeToken: Any? = null
)

data class LocalUserDataKeyState(
    val wrappedKey: String? = null,
)

data class MasterPasswordUnlockData(
    val kdf: com.bitwarden.crypto.Kdf,
    val masterKeyWrappedUserKey: String,
    val salt: String,
    val containedKeyId: String? = null,
)

data class ReinitUserCryptoRequest(
    val accountCryptographicState: Any? = null,
    val upgradeToken: Any? = null
)

data class V2UpgradeToken(
    val wrappedUserKey1: String = "",
    val wrappedUserKey2: String = "",
)

data class AuthRequestResponse(
    val publicKey: String = "",
    val privateKey: String = "",
    val accessCode: String = "",
    val fingerprint: String = "",
)

open class MasterPasswordPolicyOptions

data class RegisterTdeKeyResponse(
    val publicKey: String = "",
    val privateKey: String = "",
    val adminReset: String = "",
    val deviceKey: com.bitwarden.crypto.TrustDeviceResponse? = null,
)

typealias Uuid = String

open class WebAuthnPrfUnlockData
