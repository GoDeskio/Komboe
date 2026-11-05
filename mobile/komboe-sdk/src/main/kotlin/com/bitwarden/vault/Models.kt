// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.vault

enum class CipherRepromptType {
    NONE,
    PASSWORD,
}

enum class CipherType {
    BANK_ACCOUNT,
    CARD,
    DRIVERS_LICENSE,
    IDENTITY,
    LOGIN,
    PASSPORT,
    SECURE_NOTE,
    SSH_KEY,
}

enum class CopyableCipherFields {
    BANK_ACCOUNT_ACCOUNT_NUMBER,
    BANK_ACCOUNT_ROUTING_NUMBER,
    CARD_NUMBER,
    CARD_SECURITY_CODE,
    DRIVERS_LICENSE_LICENSE_NUMBER,
    LOGIN_PASSWORD,
    LOGIN_TOTP,
    LOGIN_USERNAME,
    PASSPORT_PASSPORT_NUMBER,
    SECURE_NOTES,
}

enum class FieldType {
    BOOLEAN,
    HIDDEN,
    LINKED,
    TEXT,
}

enum class SecureNoteType {
    GENERIC,
}

enum class UriMatchType {
    DOMAIN,
    EXACT,
    HOST,
    NEVER,
    REGULAR_EXPRESSION,
    STARTS_WITH,
}

sealed class CipherListViewType {
    data class BankAccount(
        val v1: BankAccountListView
    ) : CipherListViewType()
    data class Card(
        val v1: CardListView
    ) : CipherListViewType()
    object DriversLicense : CipherListViewType()
    object Identity : CipherListViewType()
    data class Login(
        val v1: LoginListView
    ) : CipherListViewType()
    object Passport : CipherListViewType()
    object SecureNote : CipherListViewType()
    object SshKey : CipherListViewType()
}

sealed class TotpException(message: String = "totp") : Exception(message) {
    object MissingSecret : TotpException()
}

data class Attachment(
    val id: String? = null,
    val url: String? = null,
    val size: String? = null,
    val sizeName: String? = null,
    val fileName: String? = null,
    val key: String? = null
)

data class AttachmentView(
    val id: String? = null,
    val url: String? = null,
    val size: String? = null,
    val sizeName: String? = null,
    val fileName: String? = null,
    val key: String? = null
)

data class BankAccount(
    val bankName: String? = null,
    val nameOnAccount: String? = null,
    val accountType: String? = null,
    val accountNumber: String? = null,
    val routingNumber: String? = null,
    val branchNumber: String? = null,
    val pin: String? = null,
    val swiftCode: String? = null,
    val iban: String? = null,
    val bankContactPhone: String? = null
)

data class BankAccountListView(
    val accountNumber: String? = null,
    val accountType: String? = null
)

data class BankAccountView(
    val bankName: String? = null,
    val nameOnAccount: String? = null,
    val accountType: String? = null,
    val accountNumber: String? = null,
    val routingNumber: String? = null,
    val branchNumber: String? = null,
    val pin: String? = null,
    val swiftCode: String? = null,
    val iban: String? = null,
    val bankContactPhone: String? = null
)

data class Card(
    val cardholderName: String? = null,
    val expMonth: String? = null,
    val expYear: String? = null,
    val code: String? = null,
    val brand: String? = null,
    val number: String? = null
)

data class CardListView(
    val brand: String? = null
)

data class CardView(
    val cardholderName: String? = null,
    val expMonth: String? = null,
    val expYear: String? = null,
    val code: String? = null,
    val brand: String? = null,
    val number: String? = null
)

data class Cipher(
    val id: String? = null,
    val organizationId: String? = null,
    val folderId: String? = null,
    val collectionIds: List<String> = emptyList(),
    val key: String? = null,
    val name: String? = null,
    val notes: String? = null,
    val type: CipherType = CipherType.LOGIN,
    val login: Login? = null,
    val identity: Identity? = null,
    val sshKey: SshKey? = null,
    val card: Card? = null,
    val bankAccount: BankAccount? = null,
    val driversLicense: DriversLicense? = null,
    val passport: Passport? = null,
    val secureNote: SecureNote? = null,
    val favorite: Boolean = false,
    val reprompt: CipherRepromptType = CipherRepromptType.NONE,
    val organizationUseTotp: Boolean = false,
    val edit: Boolean = false,
    val viewPassword: Boolean = false,
    val localData: String? = null,
    val attachments: List<Attachment>? = null,
    val fields: List<Field>? = null,
    val passwordHistory: List<PasswordHistory>? = null,
    val permissions: CipherPermissions? = null,
    val creationDate: java.time.Instant = java.time.Instant.EPOCH,
    val deletedDate: java.time.Instant? = null,
    val revisionDate: java.time.Instant = java.time.Instant.EPOCH,
    val archivedDate: java.time.Instant? = null,
    val data: String? = null,
    val partialData: String? = null
)

data class CipherListView(
    val id: String? = null,
    val organizationId: String? = null,
    val folderId: String? = null,
    val collectionIds: List<String> = emptyList(),
    val name: String = "",
    val subtitle: String,
    val type: CipherListViewType = CipherListViewType.SecureNote,
    val favorite: Boolean = false,
    val reprompt: CipherRepromptType = CipherRepromptType.NONE,
    val organizationUseTotp: Boolean = false,
    val edit: Boolean = false,
    val permissions: CipherPermissions? = null,
    val viewPassword: Boolean = false,
    val attachments: UInt,
    val hasOldAttachments: Boolean,
    val localData: String? = null,
    val creationDate: java.time.Instant = java.time.Instant.EPOCH,
    val deletedDate: java.time.Instant? = null,
    val revisionDate: java.time.Instant = java.time.Instant.EPOCH,
    val copyableFields: List<CopyableCipherFields> = emptyList(),
    val archivedDate: java.time.Instant? = null,
    val partial: Boolean
)

data class CipherPermissions(
    val delete: Boolean = false,
    val restore: Boolean = false,
)

data class CipherView(
    val id: String? = null,
    val collectionIds: List<String> = emptyList(),
    val key: String? = null,
    val edit: Boolean = false,
    val viewPassword: Boolean = false,
    val localData: String? = null,
    val attachments: List<AttachmentView>? = null,
    val organizationUseTotp: Boolean = false,
    val passwordHistory: List<PasswordHistoryView>? = null,
    val permissions: CipherPermissions? = null,
    val creationDate: java.time.Instant,
    val deletedDate: java.time.Instant? = null,
    val revisionDate: java.time.Instant,
    val archivedDate: java.time.Instant? = null,
    val attachmentDecryptionFailures: String? = null,
    val partial: Boolean,
    val type: CipherType = CipherType.LOGIN,
    val identity: IdentityView? = null,
    val secureNote: SecureNoteView? = null,
    val login: LoginView? = null,
    val card: CardView? = null,
    val sshKey: SshKeyView? = null,
    val bankAccount: BankAccountView? = null,
    val driversLicense: DriversLicenseView? = null,
    val passport: PassportView? = null,
    val name: String = "",
    val notes: String? = null,
    val favorite: Boolean = false,
    val folderId: String? = null,
    val organizationId: String? = null,
    val reprompt: CipherRepromptType = CipherRepromptType.NONE,
    val fields: List<FieldView>? = null
)

data class DecryptCipherListResult(
    val successes: List<CipherListView> = emptyList(),
    val failures: List<Cipher> = emptyList()
)

data class DriversLicense(
    val firstName: String? = null,
    val middleName: String? = null,
    val lastName: String? = null,
    val licenseNumber: String? = null,
    val issuingCountry: String? = null,
    val issuingState: String? = null,
    val issuingAuthority: String? = null,
    val expirationDate: String? = null,
    val dateOfBirth: String? = null,
    val issueDate: String? = null,
    val licenseClass: String? = null
)

data class DriversLicenseView(
    val firstName: String? = null,
    val middleName: String? = null,
    val lastName: String? = null,
    val dateOfBirth: java.time.LocalDate? = null,
    val licenseNumber: String? = null,
    val issuingCountry: String? = null,
    val issuingState: String? = null,
    val issueDate: java.time.LocalDate? = null,
    val issuingAuthority: String? = null,
    val expirationDate: java.time.LocalDate? = null,
    val licenseClass: String? = null
)

data class Fido2Credential(
    val credentialId: String = "",
    val keyType: String = "",
    val keyAlgorithm: String = "",
    val keyCurve: String = "",
    val keyValue: String = "",
    val rpId: String = "",
    val rpName: String? = null,
    val userHandle: String? = null,
    val userName: String? = null,
    val userDisplayName: String? = null,
    val counter: String = "",
    val discoverable: String = "",
    val creationDate: java.time.Instant = java.time.Instant.EPOCH,
)

data class Field(
    val name: String? = null,
    val value: String? = null,
    val type: FieldType = FieldType.TEXT,
    val linkedId: UInt? = null
)

data class FieldView(
    val name: String? = null,
    val value: String? = null,
    val type: FieldType,
    val linkedId: UInt? = null
)

data class Folder(
    val id: String? = null,
    val name: String? = null,
    val revisionDate: java.time.Instant = java.time.Instant.EPOCH,
)

data class FolderView(
    val name: String = "",
    val id: String? = null,
    val revisionDate: java.time.Instant
)

data class Identity(
    val title: String? = null,
    val middleName: String? = null,
    val firstName: String? = null,
    val lastName: String? = null,
    val address1: String? = null,
    val address2: String? = null,
    val address3: String? = null,
    val city: String? = null,
    val state: String? = null,
    val postalCode: String? = null,
    val country: String? = null,
    val company: String? = null,
    val email: String? = null,
    val phone: String? = null,
    val ssn: String? = null,
    val username: String? = null,
    val passportNumber: String? = null,
    val licenseNumber: String? = null
)

data class IdentityView(
    val title: String? = null,
    val firstName: String? = null,
    val lastName: String? = null,
    val middleName: String? = null,
    val address1: String? = null,
    val address2: String? = null,
    val address3: String? = null,
    val city: String? = null,
    val state: String? = null,
    val postalCode: String? = null,
    val country: String? = null,
    val company: String? = null,
    val email: String? = null,
    val phone: String? = null,
    val ssn: String? = null,
    val username: String? = null,
    val passportNumber: String? = null,
    val licenseNumber: String? = null
)

data class Login(
    val username: String? = null,
    val password: String? = null,
    val passwordRevisionDate: java.time.Instant? = null,
    val uris: List<LoginUri>? = null,
    val totp: String? = null,
    val autofillOnPageLoad: Boolean? = null,
    val fido2Credentials: List<Fido2Credential>? = null
)

data class LoginListView(
    val fido2Credentials: List<Fido2Credential>? = null,
    val hasFido2: Boolean,
    val username: String? = null,
    val totp: String? = null,
    val uris: List<LoginUriView>? = null
)

data class LoginUri(
    val uri: String? = null,
    val match: UriMatchType? = null,
    val uriChecksum: String? = null
)

data class LoginUriView(
    val uri: String? = null,
    val match: UriMatchType? = null,
    val uriChecksum: String? = null
)

data class LoginView(
    val username: String? = null,
    val password: String? = null,
    val passwordRevisionDate: java.time.Instant? = null,
    val uris: List<LoginUriView>? = null,
    val totp: String? = null,
    val autofillOnPageLoad: Boolean? = null,
    val fido2Credentials: List<Fido2CredentialView>? = null,
)

data class Passport(
    val surname: String? = null,
    val givenName: String? = null,
    val dateOfBirth: String? = null,
    val birthPlace: String? = null,
    val sex: String? = null,
    val nationality: String? = null,
    val passportNumber: String? = null,
    val passportType: String? = null,
    val nationalIdentificationNumber: String? = null,
    val issuingCountry: String? = null,
    val issuingAuthority: String? = null,
    val issueDate: String? = null,
    val expirationDate: String? = null,
)

data class PassportView(
    val surname: String? = null,
    val givenName: String? = null,
    val dateOfBirth: java.time.LocalDate? = null,
    val birthPlace: String? = null,
    val sex: String? = null,
    val nationality: String? = null,
    val passportNumber: String? = null,
    val passportType: String? = null,
    val issuingCountry: String? = null,
    val issuingAuthority: String? = null,
    val issueDate: java.time.LocalDate? = null,
    val expirationDate: java.time.LocalDate? = null,
    val nationalIdentificationNumber: String? = null
)

data class PasswordHistory(
    val password: String = "",
    val lastUsedDate: java.time.Instant = java.time.Instant.EPOCH,
)

data class PasswordHistoryView(
    val password: String,
    val lastUsedDate: java.time.Instant
)

data class SecureNote(
    val type: SecureNoteType = SecureNoteType.GENERIC
)

data class SecureNoteView(
    val type: SecureNoteType
)

data class SshKey(
    val publicKey: String? = null,
    val privateKey: String = "",
    val fingerprint: String? = null,
)

data class SshKeyView(
    val publicKey: String = "",
    val privateKey: String = "",
    val fingerprint: String = "",
)

data class AttachmentEncryptResult(val attachment: Attachment)
data class EncryptionContext(
    val cipher: Cipher,
    val encryptedFor: String,
    val encryptedByKeyId: String? = null,
)
open class Fido2CredentialNewView
data class Fido2CredentialView(
    val credentialId: String = "",
    val keyType: String = "public-key",
    val keyAlgorithm: String = "ECDSA",
    val keyCurve: String = "P-256",
    val keyValue: String = "",
    val rpId: String = "",
    val userHandle: String? = null,
    val userName: String? = null,
    val counter: String = "0",
    val rpName: String? = null,
    val userDisplayName: String? = null,
    val discoverable: String = "true",
    val creationDate: java.time.Instant = java.time.Instant.EPOCH,
)
data class TotpResponse(val code: String, val period: UInt)
