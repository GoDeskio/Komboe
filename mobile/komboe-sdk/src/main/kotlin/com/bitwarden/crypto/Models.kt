// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.crypto

enum class HashPurpose {
    LOCAL_AUTHORIZATION,
    SERVER_AUTHORIZATION,
}

sealed class Kdf {
    data class Argon2id(
        val iterations: UInt = 0u,
        val memory: UInt = 0u,
        val parallelism: UInt = 0u
    ) : Kdf()
    data class Pbkdf2(
        val iterations: UInt = 0u
    ) : Kdf()
}

typealias EncString = String

typealias PasswordProtectedKeyEnvelope = String

open class SymmetricCryptoKey

data class TrustDeviceResponse(
    val protectedDevicePrivateKey: String = "",
    val protectedDevicePublicKey: String = "",
    val protectedUserKey: String = "",
    val deviceKey: String = "",
)
