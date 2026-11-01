// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.sdk

enum class LogLevel {
    DEBUG,
    ERROR,
    INFO,
    TRACE,
    WARN,
}


data class CheckUserAndPickCredentialForCreationResult(
    val cipher: CipherViewWrapper,
    val checkUserResult: CheckUserResult
)

data class CheckUserResult(
    val userPresent: Boolean,
    val userVerified: Boolean
)


data class Repositories(
    val cipher: Any? = null,
    val folder: Any? = null,
    val localUserDataKeyState: Any? = null,
    val organizationSharedKey: Any? = null,
    val policy: Any? = null,
    val send: Any? = null
)










open class ManagedSettingsBindingClient


open class UiHint

