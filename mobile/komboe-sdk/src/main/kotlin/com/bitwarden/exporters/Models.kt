// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.exporters

sealed class ExportFormat {
    object Json : ExportFormat()
    object Csv : ExportFormat()
    data class EncryptedJson(val password: String) : ExportFormat()
}

data class Account(
    val id: Any? = null,
    val email: Any? = null,
    val name: Any? = null
)
