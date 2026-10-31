// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.collections

enum class CollectionType {
    DEFAULT_USER_COLLECTION,
    SHARED_COLLECTION,
}

data class Collection(
    val id: Any? = null,
    val organizationId: Any? = null,
    val name: Any? = null,
    val externalId: Any? = null,
    val hidePasswords: Any? = null,
    val readOnly: Any? = null,
    val manage: Any? = null,
    val defaultUserCollectionEmail: Any? = null,
    val type: Any? = null
)

typealias CollectionId = String

data class CollectionView(
    val id: String? = null,
    val organizationId: String? = null,
    val name: String = "",
    val externalId: String? = null,
    val hidePasswords: Boolean = false,
    val readOnly: Boolean = false,
    val manage: Boolean = false,
    val defaultUserCollectionEmail: String? = null,
    val type: CollectionType? = null,
)
