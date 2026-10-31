// Response and bridge types the GPL Android app implements or reads.
package com.bitwarden.core

import com.bitwarden.crypto.EncString
import com.bitwarden.crypto.Kdf
import com.bitwarden.crypto.PasswordProtectedKeyEnvelope
import com.bitwarden.crypto.SymmetricCryptoKey
import java.time.Instant

data class AsymmetricCryptoKey(
    val public: String,
    val `private`: String,
)

data class RegisterKeyResponse(
    val masterPasswordHash: String,
    val encryptedUserKey: String,
    val keys: AsymmetricCryptoKey,
)

data class KeyConnectorResponse(
    val encryptedUserKey: String,
    val keys: AsymmetricCryptoKey,
    val masterKey: String = "",
)

data class EnrollPinResponse(
    val userKeyEncryptedPin: String,
    val pinProtectedUserKeyEnvelope: String,
)

data class UpdatePasswordResponse(
    val passwordHash: String,
    val newKey: String,
)

data class MasterPasswordAuthenticationData(
    val kdf: Kdf,
    val masterPasswordAuthenticationHash: String,
    val salt: String,
)

data class UpdateKdfResponse(
    val masterPasswordAuthenticationData: MasterPasswordAuthenticationData,
    val oldMasterPasswordAuthenticationData: MasterPasswordAuthenticationData,
    val masterPasswordUnlockData: MasterPasswordUnlockData,
)

interface ClientManagedTokens {
    suspend fun getAccessToken(): String?
}

interface StateBridgeForeignImpl {
    suspend fun setUserKey(value: SymmetricCryptoKey)
    suspend fun getUserKey(): SymmetricCryptoKey?
    suspend fun clearUserKey()
    suspend fun setUserKeyId(value: String)
    suspend fun getUserKeyId(): String?
    suspend fun clearUserKeyId()
    suspend fun setPersistentPinEnvelope(value: PasswordProtectedKeyEnvelope)
    suspend fun getPersistentPinEnvelope(): PasswordProtectedKeyEnvelope?
    suspend fun clearPersistentPinEnvelope()
    suspend fun setEphemeralPinEnvelope(value: PasswordProtectedKeyEnvelope)
    suspend fun getEphemeralPinEnvelope(): PasswordProtectedKeyEnvelope?
    suspend fun clearEphemeralPinEnvelope()
    suspend fun setEncryptedPin(value: EncString)
    suspend fun getEncryptedPin(): EncString?
    suspend fun clearEncryptedPin()
    suspend fun setV2UpgradeToken(value: V2UpgradeToken)
    suspend fun getV2UpgradeToken(): V2UpgradeToken?
    suspend fun clearV2UpgradeToken()
    suspend fun setAccountCryptographicState(value: WrappedAccountCryptographicState)
    suspend fun getAccountCryptographicState(): WrappedAccountCryptographicState?
    suspend fun clearAccountCryptographicState()
    suspend fun setMasterpasswordUnlockData(value: MasterPasswordUnlockData)
    suspend fun getMasterpasswordUnlockData(): MasterPasswordUnlockData?
    suspend fun clearMasterpasswordUnlockData()
    suspend fun getKdfConfig(): Kdf?
    suspend fun setKdfConfig(value: Kdf)
    suspend fun clearKdfConfig()
    suspend fun setV2EncryptedMigrationsGracePeriodStart(value: Instant)
    suspend fun getV2EncryptedMigrationsGracePeriodStart(): Instant?
    suspend fun clearV2EncryptedMigrationsGracePeriodStart()
    suspend fun getWebauthnPrfUnlockData(): WebAuthnPrfUnlockData?
    suspend fun setWebauthnPrfUnlockData(value: WebAuthnPrfUnlockData)
    suspend fun clearWebauthnPrfUnlockData()
}
