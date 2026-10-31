// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.organizations

enum class MemberDecryptionType {
    KEY_CONNECTOR,
    MASTER_PASSWORD,
    TRUSTED_DEVICE_ENCRYPTION,
}

enum class OrganizationUserStatusType {
    ACCEPTED,
    CONFIRMED,
    INVITED,
    REVOKED,
    STAGED,
}

enum class OrganizationUserType {
    ADMIN,
    CUSTOM,
    OWNER,
    USER,
}

enum class ProductTierType {
    ENTERPRISE,
    FAMILIES,
    FREE,
    TEAMS,
    TEAMS_STARTER,
}

enum class ProviderType {
    BUSINESS_UNIT,
    MSP,
    RESELLER,
}

data class Permissions(
    val accessEventLogs: Any? = null,
    val accessImportExport: Any? = null,
    val accessReports: Any? = null,
    val createNewCollections: Any? = null,
    val editAnyCollection: Any? = null,
    val deleteAnyCollection: Any? = null,
    val manageGroups: Any? = null,
    val manageSso: Any? = null,
    val managePolicies: Any? = null,
    val manageUsers: Any? = null,
    val manageResetPassword: Any? = null,
    val manageScim: Any? = null
)

data class ProfileOrganization(
    val id: Any? = null,
    val name: Any? = null,
    val status: Any? = null,
    val type: Any? = null,
    val enabled: Any? = null,
    val usePolicies: Any? = null,
    val useGroups: Any? = null,
    val useDirectory: Any? = null,
    val useEvents: Any? = null,
    val useTotp: Any? = null,
    val use2fa: Any? = null,
    val useApi: Any? = null,
    val useSso: Any? = null,
    val useOrganizationDomains: Any? = null,
    val useKeyConnector: Any? = null,
    val useScim: Any? = null,
    val useCustomPermissions: Any? = null,
    val useResetPassword: Any? = null,
    val useSecretsManager: Any? = null,
    val usePasswordManager: Any? = null,
    val useActivateAutofillPolicy: Any? = null,
    val useAutomaticUserConfirmation: Any? = null,
    val selfHost: Any? = null,
    val usersGetPremium: Any? = null,
    val seats: Any? = null,
    val maxCollections: Any? = null,
    val maxStorageGb: Any? = null,
    val ssoBound: Any? = null,
    val identifier: Any? = null,
    val permissions: Any? = null,
    val resetPasswordEnrolled: Any? = null,
    val userId: Any? = null,
    val organizationUserId: Any? = null,
    val hasPublicAndPrivateKeys: Any? = null,
    val providerId: Any? = null,
    val providerName: Any? = null,
    val providerType: Any? = null,
    val isProviderUser: Any? = null,
    val isMember: Any? = null,
    val familySponsorshipFriendlyName: Any? = null,
    val familySponsorshipAvailable: Any? = null,
    val productTierType: Any? = null,
    val keyConnectorEnabled: Any? = null,
    val keyConnectorUrl: Any? = null,
    val familySponsorshipLastSyncDate: Any? = null,
    val familySponsorshipValidUntil: Any? = null,
    val familySponsorshipToDelete: Any? = null,
    val accessSecretsManager: Any? = null,
    val limitCollectionCreation: Any? = null,
    val limitCollectionDeletion: Any? = null,
    val limitItemDeletion: Any? = null,
    val allowAdminAccessToAllCollectionItems: Any? = null,
    val userIsManagedByOrganization: Any? = null,
    val useAccessIntelligence: Any? = null,
    val useAdminSponsoredFamilies: Any? = null,
    val useDisableSmAdsForUsers: Any? = null,
    val isAdminInitiated: Any? = null,
    val ssoEnabled: Any? = null,
    val ssoMemberDecryptionType: Any? = null,
    val usePhishingBlocker: Any? = null,
    val useMyItems: Any? = null
)
