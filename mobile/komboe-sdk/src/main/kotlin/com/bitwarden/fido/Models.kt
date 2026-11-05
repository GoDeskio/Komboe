// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.fido

sealed class ClientData {
    data class DefaultWithCustomHash(
        val hash: ByteArray? = null,
    ) : ClientData()
    data class DefaultWithExtraData(
        val androidPackageName: String? = null,
    ) : ClientData()
}

sealed class Origin {
    data class Android(val asset: UnverifiedAssetLink) : Origin()
    data class Web(val origin: String) : Origin()
}

data class UnverifiedAssetLink(
    val packageName: String? = null,
    val sha256CertFingerprint: String? = null,
    val host: String? = null,
    val assetLinkUrl: String? = null,
)

open class CheckUserOptions

data class Fido2CredentialAutofillView(
    val credentialId: ByteArray = byteArrayOf(),
    val userNameForUi: String? = null,
    val cipherId: String = "",
)

data class AuthenticatorAssertionInner(
    val clientDataJson: ByteArray = byteArrayOf(),
    val authenticatorData: ByteArray = byteArrayOf(),
    val signature: ByteArray = byteArrayOf(),
    val userHandle: ByteArray = byteArrayOf(),
)

data class CredProps(val rk: Boolean? = null)

data class ClientExtensionResults(val credProps: CredProps? = null)

data class PublicKeyCredentialAuthenticatorAssertionResponse(
    val id: String = "",
    val rawId: ByteArray = byteArrayOf(),
    val ty: String = "public-key",
    val authenticatorAttachment: String? = null,
    val response: AuthenticatorAssertionInner = AuthenticatorAssertionInner(),
    val clientExtensionResults: ClientExtensionResults = ClientExtensionResults(),
)

data class AuthenticatorAttestationInner(
    val clientDataJson: ByteArray = byteArrayOf(),
    val attestationObject: ByteArray = byteArrayOf(),
    val transports: List<String>? = null,
    val publicKeyAlgorithm: Long = 0,
    val publicKey: ByteArray? = null,
    val authenticatorData: ByteArray = byteArrayOf(),
)

data class PublicKeyCredentialAuthenticatorAttestationResponse(
    val id: String = "",
    val rawId: ByteArray = byteArrayOf(),
    val ty: String = "public-key",
    val authenticatorAttachment: String? = null,
    val response: AuthenticatorAttestationInner = AuthenticatorAttestationInner(),
    val clientExtensionResults: ClientExtensionResults = ClientExtensionResults(),
)
