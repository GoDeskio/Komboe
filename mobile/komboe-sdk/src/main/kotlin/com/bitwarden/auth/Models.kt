// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.auth

data class JitMasterPasswordRegistrationRequest(
    val orgId: Any? = null,
    val orgPublicKey: Any? = null,
    val userId: Any? = null,
    val organizationSsoIdentifier: Any? = null,
    val salt: Any? = null,
    val masterPassword: Any? = null,
    val masterPasswordHint: Any? = null,
    val resetPasswordEnroll: Any? = null
)

data class PasswordPreloginResponse(
    val salt: String,
    val kdf: com.bitwarden.crypto.Kdf,
)

data class TdeRegistrationRequest(
    val orgId: Any? = null,
    val orgPublicKey: Any? = null,
    val userId: Any? = null,
    val deviceIdentifier: Any? = null,
    val trustDevice: Any? = null
)

data class UserMasterPasswordRegistrationRequest(
    val email: Any? = null,
    val salt: Any? = null,
    val masterPassword: Any? = null,
    val masterPasswordHint: Any? = null,
    val emailVerificationToken: Any? = null,
    val organizationUserId: Any? = null,
    val orgInviteToken: Any? = null,
    val orgSponsoredFreeFamilyPlanToken: Any? = null,
    val acceptEmergencyAccessInviteToken: Any? = null,
    val acceptEmergencyAccessId: Any? = null,
    val providerInviteToken: Any? = null,
    val providerUserId: Any? = null,
    val salesAssistedToken: Any? = null,
    val openOrgInvite: Any? = null
)

data class JitMasterPasswordRegistrationResponse(
    val accountCryptographicState: com.bitwarden.core.WrappedAccountCryptographicState? = null,
    val masterPasswordUnlock: com.bitwarden.core.MasterPasswordUnlockData? = null,
)

data class KeyConnectorRegistrationResult(
    val keyConnectorKey: String = "",
    val keyConnectorKeyWrappedUserKey: String = "",
    val accountCryptographicState: com.bitwarden.core.WrappedAccountCryptographicState =
        com.bitwarden.core.WrappedAccountCryptographicState.V1(privateKey = ""),
)

data class TdeRegistrationResponse(
    val accountCryptographicState: com.bitwarden.core.WrappedAccountCryptographicState =
        com.bitwarden.core.WrappedAccountCryptographicState.V1(privateKey = ""),
    val userKey: String = "",
    val deviceKey: String = "",
)

open class UserMasterPasswordRegistrationResponse
