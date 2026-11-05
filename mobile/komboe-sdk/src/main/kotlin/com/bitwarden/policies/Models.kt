// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.policies

enum class PolicyType {
    ACTIVATE_AUTOFILL,
    AUTOMATIC_APP_LOG_IN,
    AUTOMATIC_USER_CONFIRMATION,
    AUTOTYPE_DEFAULT_SETTING,
    BLOCK_CLAIMED_DOMAIN_ACCOUNT_CREATION,
    DISABLE_PERSONAL_VAULT_EXPORT,
    DISABLE_SEND,
    FILL_ASSIST,
    FREE_FAMILIES_SPONSORSHIP,
    MASTER_PASSWORD,
    MAXIMUM_VAULT_TIMEOUT,
    ORGANIZATION_DATA_OWNERSHIP,
    ORGANIZATION_USER_NOTIFICATION,
    PASSWORD_GENERATOR,
    REMOVE_UNLOCK_WITH_PIN,
    REQUIRE_SSO,
    RESET_PASSWORD,
    RESTRICTED_ITEM_TYPES,
    SEND_CONTROLS,
    SEND_OPTIONS,
    SINGLE_ORG,
    TWO_FACTOR_AUTHENTICATION,
    URI_MATCH_DEFAULTS,
}

data class OrganizationUserPolicyContext(
    val id: Any? = null,
    val status: Any? = null,
    val role: Any? = null,
    val enabled: Any? = null,
    val usePolicies: Any? = null,
    val isProviderUser: Any? = null
)

data class Policy(
    val organizationId: String = "",
    val id: String? = null,
    val type: PolicyType = PolicyType.MASTER_PASSWORD,
    val enabled: Boolean = false,
    val data: String? = null,
    val revisionDate: java.time.Instant? = null,
)
