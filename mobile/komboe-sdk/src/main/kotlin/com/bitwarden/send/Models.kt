// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.send

enum class AuthType {
    EMAIL,
    NONE,
    PASSWORD,
}

enum class SendType {
    FILE,
    ITEM,
    TEXT,
}

data class Send(
    val id: String? = null,
    val accessId: String? = null,
    val name: String = "",
    val notes: String? = null,
    val key: String = "",
    val password: String? = null,
    val type: SendType = SendType.TEXT,
    val file: SendFile? = null,
    val text: SendText? = null,
    val data: String? = null,
    val maxAccessCount: UInt? = null,
    val accessCount: UInt = 0u,
    val disabled: Boolean = false,
    val hideEmail: Boolean = false,
    val revisionDate: java.time.Instant? = null,
    val deletionDate: java.time.Instant = java.time.Instant.EPOCH,
    val expirationDate: java.time.Instant? = null,
    val emails: String? = null,
    val authType: AuthType = AuthType.NONE
)

data class SendFile(
    val id: String? = null,
    val fileName: String = "",
    val size: String? = null,
    val sizeName: String? = null
)

data class SendFileView(
    val id: String? = null,
    val fileName: String = "",
    val size: String? = null,
    val sizeName: String? = null
)

data class SendText(
    val text: String? = null,
    val hidden: Boolean = false
)

data class SendTextView(
    val text: String? = null,
    val hidden: Boolean = false
)

data class SendView(
    val id: String? = null,
    val accessId: String? = null,
    val name: String = "",
    val notes: String? = null,
    val key: String? = null,
    val newPassword: String? = null,
    val hasPassword: Boolean,
    val type: SendType = SendType.TEXT,
    val file: SendFileView? = null,
    val text: SendTextView? = null,
    val data: String? = null,
    val maxAccessCount: UInt? = null,
    val accessCount: UInt = 0u,
    val disabled: Boolean = false,
    val hideEmail: Boolean = false,
    val revisionDate: java.time.Instant,
    val deletionDate: java.time.Instant = java.time.Instant.EPOCH,
    val expirationDate: java.time.Instant? = null,
    val emails: List<String> = emptyList(),
    val authType: AuthType = AuthType.NONE
)
