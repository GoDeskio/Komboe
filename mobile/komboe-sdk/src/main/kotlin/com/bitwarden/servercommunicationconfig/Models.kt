// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.servercommunicationconfig

sealed class BootstrapConfig {
    data class SsoCookieVendor(
        val v1: SsoCookieVendorConfig,
    ) : BootstrapConfig()
    object Direct : BootstrapConfig()
}

data class AcquiredCookie(
    val name: String = "",
    val value: String = "",
)

data class ServerCommunicationConfig(
    val bootstrap: BootstrapConfig
)

data class SsoCookieVendorConfig(
    val idpLoginUrl: String? = null,
    val vaultUrl: String? = null,
    val cookieName: String? = null,
    val cookieDomain: String? = null,
    val cookieValue: List<AcquiredCookie>? = null,
)

interface ServerCommunicationConfigPlatformApi {
    suspend fun acquireCookies(hostname: String): List<AcquiredCookie>?
}
