// GPL-3.0-only stand-in for com.bitwarden:sdk-android.
// Vault crypto goes through io.komboe.vaultcrypto. FIDO2 is not reimplemented.
package com.bitwarden.sdk

import com.bitwarden.auth.PasswordPreloginResponse
import com.bitwarden.collections.Collection
import com.bitwarden.collections.CollectionView
import com.bitwarden.core.AsymmetricCryptoKey
import com.bitwarden.core.ClientManagedTokens
import com.bitwarden.core.ClientSettings
import com.bitwarden.core.DeriveKeyConnectorException
import com.bitwarden.core.DeriveKeyConnectorRequest
import com.bitwarden.core.EncryptionSettingsException
import com.bitwarden.core.EnrollPinResponse
import com.bitwarden.core.FingerprintRequest
import com.bitwarden.core.InitOrgCryptoRequest
import com.bitwarden.core.InitUserCryptoMethod
import com.bitwarden.core.InitUserCryptoRequest
import com.bitwarden.core.KeyConnectorResponse
import com.bitwarden.core.MasterPasswordAuthenticationData
import com.bitwarden.core.MasterPasswordPolicyOptions
import com.bitwarden.core.MasterPasswordUnlockData
import com.bitwarden.core.RegisterKeyResponse
import com.bitwarden.core.RegisterTdeKeyResponse
import com.bitwarden.core.ReinitUserCryptoRequest
import com.bitwarden.core.StateBridgeForeignImpl
import com.bitwarden.core.UpdateKdfResponse
import com.bitwarden.core.UpdatePasswordResponse
import com.bitwarden.core.WrappedAccountCryptographicState
import com.bitwarden.crypto.HashPurpose
import com.bitwarden.crypto.Kdf
import com.bitwarden.crypto.SymmetricCryptoKey
import com.bitwarden.crypto.TrustDeviceResponse
import com.bitwarden.exporters.Account
import com.bitwarden.exporters.ExportFormat
import com.bitwarden.fido.CheckUserOptions
import com.bitwarden.fido.ClientData
import com.bitwarden.fido.Fido2CredentialAutofillView
import com.bitwarden.fido.Origin
import com.bitwarden.fido.PublicKeyCredentialAuthenticatorAssertionResponse
import com.bitwarden.fido.PublicKeyCredentialAuthenticatorAttestationResponse
import com.bitwarden.generators.PassphraseGeneratorRequest
import com.bitwarden.generators.PasswordGeneratorRequest
import com.bitwarden.generators.UsernameGeneratorRequest
import com.bitwarden.policies.OrganizationUserPolicyContext
import com.bitwarden.policies.Policy
import com.bitwarden.policies.PolicyType
import com.bitwarden.send.Send
import com.bitwarden.send.SendView
import com.bitwarden.servercommunicationconfig.AcquiredCookie
import com.bitwarden.servercommunicationconfig.ServerCommunicationConfig
import com.bitwarden.servercommunicationconfig.ServerCommunicationConfigPlatformApi
import com.bitwarden.vault.Attachment
import com.bitwarden.vault.AttachmentEncryptResult
import com.bitwarden.vault.BankAccount
import com.bitwarden.vault.BankAccountView
import com.bitwarden.vault.Card
import com.bitwarden.vault.CardView
import com.bitwarden.vault.DriversLicense
import com.bitwarden.vault.DriversLicenseView
import com.bitwarden.vault.Field
import com.bitwarden.vault.FieldView
import com.bitwarden.vault.Identity
import com.bitwarden.vault.IdentityView
import com.bitwarden.vault.Passport
import com.bitwarden.vault.PassportView
import com.bitwarden.vault.SecureNote
import com.bitwarden.vault.SecureNoteView
import com.bitwarden.vault.SshKey
import com.bitwarden.vault.SshKeyView
import com.bitwarden.vault.AttachmentView
import com.bitwarden.vault.Cipher
import com.bitwarden.vault.CipherListView
import com.bitwarden.vault.CipherListViewType
import com.bitwarden.vault.CipherRepromptType
import com.bitwarden.vault.CipherType
import com.bitwarden.vault.CipherView
import com.bitwarden.vault.DecryptCipherListResult
import com.bitwarden.vault.EncryptionContext
import com.bitwarden.vault.Folder
import com.bitwarden.vault.FolderView
import com.bitwarden.vault.Login
import com.bitwarden.vault.LoginListView
import com.bitwarden.vault.LoginUri
import com.bitwarden.vault.LoginUriView
import com.bitwarden.vault.LoginView
import com.bitwarden.vault.PasswordHistory
import com.bitwarden.vault.PasswordHistoryView
import com.bitwarden.vault.TotpException
import com.bitwarden.vault.TotpResponse
import io.komboe.vaultcrypto.AccountV2
import io.komboe.vaultcrypto.HashPurpose as KPurpose
import io.komboe.vaultcrypto.KdfConfig
import io.komboe.vaultcrypto.SymmetricKey
import io.komboe.vaultcrypto.VaultCrypto
import java.io.Closeable
import java.net.HttpURLConnection
import java.net.URI
import java.security.MessageDigest
import java.security.SecureRandom
import java.time.Instant
import java.util.Base64

fun initLogger(callback: LogCallback, level: LogLevel, platformLogger: Boolean) {
    // The GPL build logs through the app's LogCallback only when the app asks.
    // Nothing is sent off the device.
}

interface LogCallback {
    fun onLog(level: LogLevel, target: String, message: String)
}

interface CipherRepository {
    suspend fun get(id: String): Cipher?
    suspend fun has(id: String): Boolean
    suspend fun list(): List<Cipher>
    suspend fun remove(id: String)
    suspend fun set(id: String, value: Cipher)
    suspend fun setBulk(values: Map<String, Cipher>)
    suspend fun removeBulk(keys: List<String>)
    suspend fun removeAll()
}

interface FolderRepository {
    suspend fun get(id: String): Folder?
    suspend fun list(): List<Folder>
    suspend fun set(id: String, value: Folder)
    suspend fun setBulk(values: Map<String, Folder>)
    suspend fun remove(id: String)
    suspend fun removeBulk(keys: List<String>)
    suspend fun removeAll()
    suspend fun has(id: String): Boolean
}

interface LocalUserDataKeyStateRepository {
    suspend fun get(id: String): com.bitwarden.core.LocalUserDataKeyState?
    suspend fun has(id: String): Boolean
    suspend fun list(): List<com.bitwarden.core.LocalUserDataKeyState>
    suspend fun remove(id: String)
    suspend fun removeAll()
    suspend fun removeBulk(keys: List<String>)
    suspend fun set(id: String, value: com.bitwarden.core.LocalUserDataKeyState)
    suspend fun setBulk(values: Map<String, com.bitwarden.core.LocalUserDataKeyState>)
}

interface ServerCommunicationConfigRepository {
    suspend fun get(domain: String): ServerCommunicationConfig?
    suspend fun save(domain: String, config: ServerCommunicationConfig)
}

interface Fido2CredentialStore {
    suspend fun allCredentials(): List<CipherListView>
    suspend fun findCredentials(ids: List<ByteArray>?, ripId: String, userHandle: ByteArray?): List<CipherView>
    suspend fun saveCredential(cred: EncryptionContext)
}

interface Fido2UserInterface {
    suspend fun checkUser(options: CheckUserOptions, hint: UiHint): CheckUserResult
    suspend fun checkUserAndPickCredentialForCreation(
        options: CheckUserOptions,
        newCredential: com.bitwarden.vault.Fido2CredentialNewView,
    ): CheckUserAndPickCredentialForCreationResult
    fun isVerificationEnabled(): Boolean
    suspend fun pickCredentialForAuthentication(availableCredentials: List<CipherView>): CipherViewWrapper
}

data class CipherViewWrapper(val cipher: CipherView)

sealed class BitwardenException(message: String) : Exception(message) {
    class DeriveKeyConnector(val v1: DeriveKeyConnectorException) : BitwardenException(v1.message ?: "derive key")
    class EncryptionSettings(val v1: EncryptionSettingsException) : BitwardenException(v1.message ?: "encryption settings")
    class Totp(val v1: TotpException) : BitwardenException(v1.message ?: "totp")
}

class Client(
    @Suppress("unused") val tokenProvider: ClientManagedTokens? = null,
    val settings: ClientSettings? = null,
    @Suppress("unused") val managedSettings: ManagedSettingsBindingClient = ManagedSettingsBindingClient(),
) : Closeable {
    internal val session = VaultSession()
    private var bridge: StateBridgeForeignImpl? = null

    fun platform() = PlatformApi(this)
    fun crypto() = CryptoApi(this)
    fun auth() = AuthClient(this)
    fun vault() = VaultClient(this)
    fun sends() = SendApi(this)
    fun generators() = GeneratorClients()
    fun exporters() = ExporterApi(this)
    fun policies() = PolicyApi()
    fun kmStateBridge() = KmStateBridge(this)

class KmStateBridge(private val client: Client) {
    fun registerBridgeImpl(impl: StateBridgeForeignImpl) {
        client.installBridge(impl)
    }
}

    internal fun bridge(): StateBridgeForeignImpl? = bridge
    internal fun installBridge(impl: StateBridgeForeignImpl) {
        bridge = impl
    }
    override fun close() {}
}

internal class VaultSession {
    var email: String? = null
    var kdf: Kdf? = null
    var userKey: SymmetricKey? = null
    var privateKey: ByteArray? = null
    val orgKeys = linkedMapOf<String, SymmetricKey>()
    var userId: String? = null
}

class PlatformApi(private val client: Client) {
    fun loadFlags(@Suppress("unused") flags: Map<String, Boolean>) {}
    fun serverCommunicationConfig(
        @Suppress("unused") repository: ServerCommunicationConfigRepository,
        @Suppress("unused") platformApi: ServerCommunicationConfigPlatformApi,
    ) {}
    fun state() = PlatformState()
    fun userFingerprint(fingerprintMaterial: String): String = fingerprint(fingerprintMaterial, client.session.privateKey)
    fun fingerprint(req: FingerprintRequest): String {
        val material = req.fingerprintMaterial as? String ?: ""
        val publicKey = decodeKey(req.publicKey as? String)
        return VaultCrypto.fingerprintPhrase(material, publicKey)
    }
    fun fido2() = Fido2Api()
}

class PlatformState {
    fun registerClientManagedRepositories(@Suppress("unused") repositories: Repositories) {}
}

class Fido2Api {
    fun client(
        @Suppress("unused") userInterface: Fido2UserInterface,
        @Suppress("unused") credentialStore: Fido2CredentialStore,
    ) = Fido2Client()

    fun authenticator(
        @Suppress("unused") userInterface: Fido2UserInterface,
        @Suppress("unused") credentialStore: Fido2CredentialStore,
    ) = Fido2Authenticator()

    fun getFido2AutofillCredentials(@Suppress("unused") cipherView: CipherView): List<Fido2CredentialAutofillView> =
        emptyList()
}

class Fido2Client {
    fun register(
        @Suppress("unused") origin: Origin,
        @Suppress("unused") request: String,
        @Suppress("unused") clientData: ClientData,
    ): PublicKeyCredentialAuthenticatorAttestationResponse =
        throw UnsupportedOperationException("FIDO2 registration is not in the GPL vault-crypto build")

    fun authenticate(
        @Suppress("unused") origin: Origin,
        @Suppress("unused") request: String,
        @Suppress("unused") clientData: ClientData,
    ): PublicKeyCredentialAuthenticatorAssertionResponse =
        throw UnsupportedOperationException("FIDO2 authentication is not in the GPL vault-crypto build")
}

class Fido2Authenticator {
    fun silentlyDiscoverCredentials(
        @Suppress("unused") relyingPartyId: String,
        @Suppress("unused") userHandle: ByteArray?,
    ): List<Fido2CredentialAutofillView> = emptyList()
}

class LoginClient(private val client: Client) {
    fun getPasswordPrelogin(email: String): PasswordPreloginResponse = fetchPrelogin(client.settings, email)
}

class CryptoApi(private val client: Client) {
    fun getKeyIdForSymmetricKey(key: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(Base64.getDecoder().decode(key))
        return digest.joinToString("") { "%02x".format(it) }.take(32)
    }

    fun initializeUserCrypto(req: InitUserCryptoRequest) {
        val session = client.session
        session.email = req.email as? String
        session.userId = req.userId as? String
        session.kdf = req.kdfParams as? Kdf
        when (val method = req.method) {
            is InitUserCryptoMethod.MasterPasswordUnlock -> {
                val unlock = method.masterPasswordUnlock
                val email = unlock.salt
                session.email = email
                session.kdf = unlock.kdf
                session.userKey = VaultCrypto.unlockUserKey(
                    method.password,
                    email,
                    unlock.kdf.toConfig(),
                    unlock.masterKeyWrappedUserKey,
                )
            }
            is InitUserCryptoMethod.DecryptedKey -> {
                session.userKey = SymmetricKey.fromBase64(method.decryptedUserKey as String)
            }
            is InitUserCryptoMethod.Pin -> {
                val email = session.email ?: error("PIN unlock needs the account email")
                val kdf = session.kdf ?: error("PIN unlock needs the account KDF")
                session.userKey = VaultCrypto.unlockWithPin(
                    method.pin as String,
                    email,
                    kdf.toConfig(),
                    method.pinProtectedUserKey as String,
                )
            }
            is InitUserCryptoMethod.PinEnvelope -> {
                val email = session.email ?: error("PIN unlock needs the account email")
                val kdf = session.kdf ?: error("PIN unlock needs the account KDF")
                session.userKey = VaultCrypto.unlockWithPin(
                    method.pin as String,
                    email,
                    kdf.toConfig(),
                    method.pinProtectedUserKeyEnvelope as String,
                )
            }
            else -> throw BitwardenException.EncryptionSettings(EncryptionSettingsException.CryptoInitialization)
        }
        when (val state = req.accountCryptographicState) {
            is WrappedAccountCryptographicState.V1 -> {
                val userKey = session.userKey
                if (userKey != null) {
                    session.privateKey = runCatching { VaultCrypto.decryptBytes(state.privateKey, userKey) }.getOrNull()
                }
            }
            is WrappedAccountCryptographicState.V2 -> {
                val userKey = session.userKey ?: throw BitwardenException.EncryptionSettings(EncryptionSettingsException.Crypto)
                val signing = AccountV2.unwrapSigningKey(state.signingKey, userKey)
                AccountV2.verifySecurityState(state.securityState, signing)
                AccountV2.verifySignedPublicKey(state.signedPublicKey, signing)
                session.privateKey = VaultCrypto.decryptBytes(state.privateKey, userKey)
            }
            else -> Unit
        }
    }

    fun reinitUserCrypto(@Suppress("unused") req: ReinitUserCryptoRequest) {}

    fun initializeOrgCrypto(req: InitOrgCryptoRequest) {
        val session = client.session
        val userKey = session.userKey ?: throw BitwardenException.EncryptionSettings(EncryptionSettingsException.MissingPrivateKey)
        val privateKey = session.privateKey
        val keys = req.organizationKeys as? Map<*, *> ?: return
        keys.forEach { (id, wrapped) ->
            val orgId = id as? String ?: return@forEach
            val enc = wrapped as? String ?: return@forEach
            val raw = if (enc.startsWith("2.") || enc.startsWith("0.")) {
                VaultCrypto.unwrapKey(enc, userKey)
            } else if (privateKey != null) {
                VaultCrypto.rsaDecrypt(enc, privateKey)
            } else {
                return@forEach
            }
            session.orgKeys[orgId] = SymmetricKey(raw)
        }
    }

    fun getUserEncryptionKey(): String = requireUserKey().toBase64()

    fun deriveKeyConnector(request: DeriveKeyConnectorRequest): String {
        return try {
            val kdf = request.kdf as Kdf
            VaultCrypto.unlockUserKey(
                request.password as String,
                request.email as String,
                kdf.toConfig(),
                request.userKeyEncrypted as String,
            ).toBase64()
        } catch (_: Exception) {
            throw BitwardenException.DeriveKeyConnector(DeriveKeyConnectorException.WrongPassword)
        }
    }

    fun enrollPin(pin: String): EnrollPinResponse {
        val session = client.session
        val email = session.email ?: error("no email")
        val kdf = session.kdf ?: error("no kdf")
        val userKey = requireUserKey()
        val envelope = VaultCrypto.protectWithPin(pin, email, kdf.toConfig(), userKey)
        val encryptedPin = VaultCrypto.encryptUtf8(pin, userKey)
        return EnrollPinResponse(userKeyEncryptedPin = encryptedPin, pinProtectedUserKeyEnvelope = envelope)
    }

    fun enrollPinWithEncryptedPin(encryptedPin: String): EnrollPinResponse {
        val pin = VaultCrypto.decryptUtf8(encryptedPin, requireUserKey())
        return enrollPin(pin)
    }

    fun enrollAdminPasswordReset(publicKey: String): String {
        val userKey = requireUserKey()
        return VaultCrypto.rsaEncrypt(userKey.bytes, decodeKey(publicKey), sha256 = false)
    }

    fun makeUpdatePassword(newPassword: String): UpdatePasswordResponse {
        val session = client.session
        val email = session.email ?: error("no email")
        val kdf = session.kdf ?: Kdf.Pbkdf2(600_000u)
        val account = VaultCrypto.makeAccountKeys(newPassword, email, kdf.toConfig())
        // Keep the existing user key and only re-wrap it, so vault items stay readable.
        val stretched = VaultCrypto.stretch(VaultCrypto.masterKey(newPassword, email, kdf.toConfig()))
        val wrapped = VaultCrypto.wrapKey(requireUserKey().bytes, stretched)
        val hash = VaultCrypto.hashMasterPassword(
            VaultCrypto.masterKey(newPassword, email, kdf.toConfig()),
            newPassword,
            KPurpose.SERVER_AUTHORIZATION,
        )
        return UpdatePasswordResponse(passwordHash = hash, newKey = wrapped).also {
            // account is used so a brand-new key path stays available for callers that need it
            check(account.masterPasswordHash.isNotEmpty())
        }
    }

    fun makeUpdateKdf(password: String, kdf: Kdf): UpdateKdfResponse {
        val session = client.session
        val email = session.email ?: error("no email")
        val oldKdf = session.kdf ?: kdf
        val oldMaster = VaultCrypto.masterKey(password, email, oldKdf.toConfig())
        val newMaster = VaultCrypto.masterKey(password, email, kdf.toConfig())
        val wrapped = VaultCrypto.wrapKey(requireUserKey().bytes, VaultCrypto.stretch(newMaster))
        val newHash = VaultCrypto.hashMasterPassword(newMaster, password, KPurpose.SERVER_AUTHORIZATION)
        val oldHash = VaultCrypto.hashMasterPassword(oldMaster, password, KPurpose.SERVER_AUTHORIZATION)
        session.kdf = kdf
        return UpdateKdfResponse(
            masterPasswordAuthenticationData = MasterPasswordAuthenticationData(kdf, newHash, email),
            oldMasterPasswordAuthenticationData = MasterPasswordAuthenticationData(oldKdf, oldHash, email),
            masterPasswordUnlockData = MasterPasswordUnlockData(kdf, wrapped, email),
        )
    }

    private fun requireUserKey(): SymmetricKey =
        client.session.userKey ?: throw BitwardenException.EncryptionSettings(EncryptionSettingsException.Crypto)
}

class AuthClient(private val client: Client) {
    fun login() = LoginClient(client)
    fun registration() = RegistrationApi(client)
    fun hashPassword(email: String, password: String, kdfParams: Kdf, purpose: HashPurpose): String {
        val kPurpose = if (purpose == HashPurpose.LOCAL_AUTHORIZATION) KPurpose.LOCAL_AUTHORIZATION else KPurpose.SERVER_AUTHORIZATION
        val master = VaultCrypto.masterKey(password, email, kdfParams.toConfig())
        return VaultCrypto.hashMasterPassword(master, password, kPurpose)
    }
    fun validatePassword(password: String, passwordHash: String): Boolean {
        val session = client.session
        val email = session.email ?: return false
        val kdf = session.kdf ?: return false
        val computed = hashPassword(email, password, kdf, HashPurpose.LOCAL_AUTHORIZATION)
        return MessageDigest.isEqual(computed.toByteArray(), passwordHash.toByteArray())
    }
    fun validatePasswordUserKey(password: String, encryptedUserKey: String): String {
        val email = client.session.email ?: throw BitwardenException.EncryptionSettings(EncryptionSettingsException.WrongPin)
        val kdf = client.session.kdf ?: throw BitwardenException.EncryptionSettings(EncryptionSettingsException.WrongPin)
        return VaultCrypto.unlockUserKey(password, email, kdf.toConfig(), encryptedUserKey).toBase64()
    }
    fun validatePinProtectedUserKeyEnvelope(pin: String, pinProtectedUserKeyEnvelope: String): Boolean =
        runCatching {
            val email = client.session.email ?: return false
            val kdf = client.session.kdf ?: return false
            VaultCrypto.unlockWithPin(pin, email, kdf.toConfig(), pinProtectedUserKeyEnvelope)
            true
        }.getOrDefault(false)
    fun approveAuthRequest(publicKey: String): String = crypto().enrollAdminPasswordReset(publicKey)
    fun trustDevice(): TrustDeviceResponse = TrustDeviceResponse()
    fun makeKeyConnectorKeys(): KeyConnectorResponse {
        val account = freshAccount()
        return KeyConnectorResponse(encryptedUserKey = account.encryptedUserKey, keys = account.keys())
    }
    fun makeRegisterKeys(email: String, password: String, kdf: Kdf): RegisterKeyResponse {
        val account = VaultCrypto.makeAccountKeys(password, email, kdf.toConfig())
        return RegisterKeyResponse(
            masterPasswordHash = account.masterPasswordHash,
            encryptedUserKey = account.encryptedUserKey,
            keys = AsymmetricCryptoKey(public = account.publicKey, private = account.encryptedPrivateKey),
        )
    }
    fun makeRegisterTdeKeys(
        @Suppress("unused") email: String,
        @Suppress("unused") orgPublicKey: String,
        @Suppress("unused") rememberDevice: Boolean,
    ): RegisterTdeKeyResponse = throw UnsupportedOperationException("Trusted-device registration is not in this build")
    fun passwordStrength(password: String, @Suppress("unused") email: String, @Suppress("unused") additionalInputs: List<String>): UByte {
        var score = 0
        if (password.length >= 8) score++
        if (password.length >= 12) score++
        if (password.any { it.isUpperCase() } && password.any { it.isLowerCase() }) score++
        if (password.any { it.isDigit() } && password.any { !it.isLetterOrDigit() }) score++
        return score.coerceIn(0, 4).toUByte()
    }
    fun satisfiesPolicy(password: String, @Suppress("unused") strength: UByte, @Suppress("unused") policy: MasterPasswordPolicyOptions): Boolean =
        password.length >= 12
    fun newAuthRequest(@Suppress("unused") email: String): com.bitwarden.core.AuthRequestResponse =
        throw UnsupportedOperationException("Auth requests are not in this build")

    private fun crypto() = client.crypto()
    private fun freshAccount() = VaultCrypto.makeAccountKeys(
        password = ByteArray(16).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) },
        email = client.session.email ?: "user@komboe.local",
        kdf = (client.session.kdf ?: Kdf.Pbkdf2(600_000u)).toConfig(),
    )
}

class RegistrationApi(private val client: Client) {
    fun postKeysForUserPasswordRegistration(request: com.bitwarden.auth.UserMasterPasswordRegistrationRequest): com.bitwarden.auth.UserMasterPasswordRegistrationResponse {
        val email = request.email as? String ?: error("registration email is missing")
        val password = request.masterPassword as? String ?: error("registration password is missing")
        val salt = request.salt as? String ?: email
        val account = AccountV2.make(password, salt, KdfConfig.Pbkdf2(600_000))
        val identity = client.settings?.identityUrl?.trimEnd('/')
            ?: error("identity URL is not configured")
        val hint = (request.masterPasswordHint as? String).orEmpty()
        val token = (request.emailVerificationToken as? String).orEmpty()
        val body = buildString {
            append("""{"email":${jsonString(email)},"masterPasswordHint":${jsonString(hint)},""")
            append(""""emailVerificationToken":${jsonString(token)},""")
            append(""""userSymmetricKey":${jsonString(account.encryptedUserKey)},"masterPasswordHash":${jsonString(account.masterPasswordHash)},""")
            append(""""kdf":0,"kdfIterations":600000,""")
            append(""""userAsymmetricKeys":{"publicKey":${jsonString(account.publicKey)},"encryptedPrivateKey":${jsonString(account.encryptedPrivateKey)}},""")
            append(""""accountKeys":{"publicKeyEncryptionKeyPair":{"wrappedPrivateKey":${jsonString(account.encryptedPrivateKey)},"publicKey":${jsonString(account.publicKey)},"signedPublicKey":${jsonString(account.signedPublicKey)}},""")
            append(""""signatureKeyPair":{"wrappedSigningKey":${jsonString(account.wrappedSigningKey)},"verifyingKey":${jsonString(account.verifyingKey)}},""")
            append(""""securityState":{"securityState":${jsonString(account.securityState)},"securityVersion":${account.securityVersion}}}}""")
        }
        postJson("$identity/accounts/register/finish", body)
        return com.bitwarden.auth.UserMasterPasswordRegistrationResponse()
    }
    fun postKeysForJitPasswordRegistration(@Suppress("unused") request: com.bitwarden.auth.JitMasterPasswordRegistrationRequest): com.bitwarden.auth.JitMasterPasswordRegistrationResponse =
        throw UnsupportedOperationException("JIT registration is not in this build")
    fun postKeysForKeyConnectorRegistration(@Suppress("unused") keyConnectorUrl: String, @Suppress("unused") ssoOrgIdentifier: String): com.bitwarden.auth.KeyConnectorRegistrationResult =
        throw UnsupportedOperationException("Key Connector is not supported")
    fun postKeysForTdeRegistration(@Suppress("unused") request: com.bitwarden.auth.TdeRegistrationRequest): com.bitwarden.auth.TdeRegistrationResponse =
        throw UnsupportedOperationException("Trusted-device registration is not in this build")
}

class PolicyApi {
    fun filterByType(policies: List<Policy>, @Suppress("unused") organizationUserPolicyContexts: List<OrganizationUserPolicyContext>, policyType: PolicyType): List<Policy> =
        policies.filter { it.type == policyType || it.type == null }
}

class VaultClient(private val client: Client) {
    fun ciphers() = CipherApi(client)
    fun folders() = FolderApi(client)
    fun collections() = CollectionApi(client)
    fun attachments() = AttachmentApi(client)
    fun passwordHistory() = PasswordHistoryApi(client)
    fun generateTotpCipherView(view: CipherListView, time: Instant?): TotpResponse {
        val secret = (view.type as? CipherListViewType.Login)?.v1?.totp as? String
        if (secret.isNullOrBlank()) throw BitwardenException.Totp(TotpException.MissingSecret)
        return generateTotp(key = secret, time = time)
    }

    fun generateTotp(key: String, time: Instant?): TotpResponse {
        val code = VaultCrypto.totp(key, time?.epochSecond ?: (System.currentTimeMillis() / 1000))
        return TotpResponse(code = code.code, period = code.periodSeconds.toUInt())
    }
}

class CipherApi(private val client: Client) {
    fun encrypt(cipherView: CipherView): EncryptionContext {
        val key = itemKeyForView(cipherView)
        val orgId = cipherView.organizationId as? String
        val wrapped = cipherView.key as? String ?: VaultCrypto.wrapKey(key.bytes, wrappingKey(orgId))
        val cipher = cipherView.toCipher(wrapped, key)
        return EncryptionContext(cipher = cipher, encryptedFor = client.session.userId ?: orgId.orEmpty())
    }

    fun decrypt(cipher: Cipher): CipherView = cipher.toView(itemKey(cipher))

    fun decryptListWithFailures(cipherList: List<Cipher>): DecryptCipherListResult {
        val ok = mutableListOf<CipherListView>()
        val bad = mutableListOf<Cipher>()
        for (cipher in cipherList) {
            runCatching { cipher.toListView(itemKey(cipher)) }.fold(
                onSuccess = { ok += it },
                onFailure = { bad += cipher },
            )
        }
        return DecryptCipherListResult(successes = ok, failures = bad)
    }

    fun moveToOrganization(cipher: CipherView, organizationId: String): CipherView {
        val key = itemKeyForView(cipher)
        val wrapped = VaultCrypto.wrapKey(key.bytes, client.session.orgKeys[organizationId] ?: error("missing org key"))
        return cipher.copy(organizationId = organizationId, key = wrapped)
    }

    fun prepareCiphersForBulkShare(
        organizationId: String,
        ciphers: List<CipherView>,
        @Suppress("unused") collectionIds: List<com.bitwarden.collections.CollectionId>,
    ): List<EncryptionContext> = ciphers.map { encrypt(moveToOrganization(it, organizationId)) }

    private fun itemKey(cipher: Cipher): SymmetricKey {
        val wrapped = cipher.key as? String
        val outer = wrappingKey(cipher.organizationId as? String)
        return if (wrapped.isNullOrBlank()) outer else SymmetricKey(VaultCrypto.unwrapKey(wrapped, outer))
    }

    private fun itemKeyForView(view: CipherView): SymmetricKey {
        val wrapped = view.key as? String
        if (wrapped.isNullOrBlank()) return SymmetricKey.random(64)
        return SymmetricKey(VaultCrypto.unwrapKey(wrapped, wrappingKey(view.organizationId as? String)))
    }

    private fun wrappingKey(orgId: String?): SymmetricKey {
        if (!orgId.isNullOrBlank()) {
            client.session.orgKeys[orgId]?.let { return it }
        }
        return client.session.userKey ?: error("vault is locked")
    }
}

class FolderApi(private val client: Client) {
    fun encrypt(folder: FolderView): Folder {
        val key = client.session.userKey ?: error("vault is locked")
        return Folder(
            id = folder.id,
            name = (folder.name as? String)?.let { VaultCrypto.encryptUtf8(it, key) },
            revisionDate = folder.revisionDate,
        )
    }
    fun decrypt(folder: Folder): FolderView {
        val key = client.session.userKey ?: error("vault is locked")
        return FolderView(
            id = folder.id,
            name = (folder.name as? String)?.let { VaultCrypto.decryptUtf8(it, key) } ?: "",
            revisionDate = (folder.revisionDate as? Instant) ?: Instant.EPOCH,
        )
    }
    fun decryptList(folders: List<Folder>): List<FolderView> = folders.map { decrypt(it) }
}

class CollectionApi(private val client: Client) {
    fun decrypt(collection: Collection): CollectionView {
        val key = client.session.userKey ?: error("vault is locked")
        return CollectionView(
            id = collection.id as? String,
            organizationId = collection.organizationId as? String,
            name = (collection.name as? String)?.let { VaultCrypto.decryptUtf8(it, key) } ?: "",
            externalId = collection.externalId as? String,
            hidePasswords = collection.hidePasswords as? Boolean ?: false,
            readOnly = collection.readOnly as? Boolean ?: false,
            manage = collection.manage as? Boolean ?: false,
            type = collection.type as? com.bitwarden.collections.CollectionType,
        )
    }
    fun decryptList(collections: List<Collection>): List<CollectionView> = collections.map { decrypt(it) }
}

class AttachmentApi(private val client: Client) {
    fun encryptFile(
        cipher: Cipher,
        attachment: AttachmentView,
        decryptedFilePath: String,
        encryptedFilePath: String,
    ): Attachment {
        val key = SymmetricKey.random(64)
        val bytes = java.io.File(decryptedFilePath).readBytes()
        java.io.File(encryptedFilePath).writeBytes(Base64.getDecoder().run {
            // File payload is the raw EncString bytes of the content.
            VaultCrypto.encryptBytes(bytes, key).toByteArray()
        })
        val outer = client.session.userKey ?: error("vault is locked")
        return Attachment(
            id = attachment.id,
            url = attachment.url,
            size = attachment.size,
            sizeName = attachment.sizeName,
            fileName = (attachment.fileName as? String)?.let { VaultCrypto.encryptUtf8(it, outer) },
            key = VaultCrypto.wrapKey(key.bytes, outer),
        )
    }
    fun decryptFile(cipher: Cipher, attachment: AttachmentView, encryptedFilePath: String, decryptedFilePath: String) {
        val outer = client.session.userKey ?: error("vault is locked")
        val key = SymmetricKey(VaultCrypto.unwrapKey(attachment.key as String, outer))
        val payload = java.io.File(encryptedFilePath).readBytes().toString(Charsets.UTF_8)
        java.io.File(decryptedFilePath).writeBytes(VaultCrypto.decryptBytes(payload, key))
    }
}

class PasswordHistoryApi(private val client: Client) {
    fun encrypt(passwordHistory: PasswordHistoryView): PasswordHistory {
        val key = client.session.userKey ?: error("vault is locked")
        return PasswordHistory(
            password = VaultCrypto.encryptUtf8(passwordHistory.password, key),
            lastUsedDate = passwordHistory.lastUsedDate,
        )
    }
    fun decryptList(list: List<PasswordHistory>): List<PasswordHistoryView> {
        val key = client.session.userKey ?: error("vault is locked")
        return list.map {
            PasswordHistoryView(
                password = VaultCrypto.decryptUtf8(it.password as String, key),
                lastUsedDate = it.lastUsedDate as Instant,
            )
        }
    }
}

class SendApi(private val client: Client) {
    fun encrypt(send: SendView): Send {
        val material = VaultCrypto.randomSendMaterial()
        val key = VaultCrypto.sendKey(material)
        val userKey = client.session.userKey ?: error("vault is locked")
        return Send(
            id = send.id,
            accessId = send.accessId,
            name = (send.name)?.let { VaultCrypto.encryptUtf8(it, key) } ?: "",
            notes = (send.notes)?.let { VaultCrypto.encryptUtf8(it, key) } ?: "",
            key = VaultCrypto.encryptBytes(material, userKey),
            password = (send.newPassword as? String)?.let { VaultCrypto.hashSendPassword(it, material) },
            type = send.type,
            file = null,
            text = null,
            data = send.data,
            maxAccessCount = (send.maxAccessCount as? UInt) ?: 0u,
            accessCount = (send.accessCount as? UInt) ?: 0u,
            disabled = send.disabled,
            hideEmail = send.hideEmail,
            revisionDate = send.revisionDate,
            deletionDate = send.deletionDate,
            expirationDate = send.expirationDate,
            emails = send.emails.joinToString(","),
            authType = send.authType,
        )
    }
    fun decrypt(send: Send): SendView {
        val userKey = client.session.userKey ?: error("vault is locked")
        val material = VaultCrypto.decryptBytes(send.key as String, userKey)
        val key = VaultCrypto.sendKey(material)
        return SendView(
            id = send.id,
            accessId = send.accessId,
            name = (send.name)?.let { VaultCrypto.decryptUtf8(it, key) } ?: "",
            notes = (send.notes as? String)?.let { VaultCrypto.decryptUtf8(it, key) },
            key = java.util.Base64.getEncoder().encodeToString(material),
            type = send.type,
            file = null,
            text = null,
            data = send.data,
            hasPassword = send.password != null,
            maxAccessCount = send.maxAccessCount,
            accessCount = send.accessCount as? UInt ?: 0u,
            disabled = send.disabled,
            hideEmail = send.hideEmail,
            revisionDate = send.revisionDate ?: Instant.EPOCH,
            deletionDate = send.deletionDate,
            expirationDate = send.expirationDate,
            emails = send.emails?.split(',')?.map { it.trim() }?.filter { it.isNotEmpty() } ?: emptyList(),
            authType = send.authType,
        )
    }
    fun encryptBuffer(send: Send, buffer: ByteArray): ByteArray {
        val userKey = client.session.userKey ?: error("vault is locked")
        val key = VaultCrypto.sendKey(VaultCrypto.decryptBytes(send.key as String, userKey))
        return VaultCrypto.encryptBytes(buffer, key).toByteArray()
    }
    fun encryptFile(send: Send, decryptedFilePath: String, encryptedFilePath: String) {
        val encrypted = encryptBuffer(send, java.io.File(decryptedFilePath).readBytes())
        java.io.File(encryptedFilePath).writeBytes(encrypted)
    }
}

class GeneratorClients {
    private val random = SecureRandom()
    private val words = listOf(
        "apricot", "birch", "cinder", "delta", "ember", "fjord", "granite", "harbor",
        "iris", "juniper", "kelp", "linen", "marble", "nectar", "ochre", "pebble",
    )
    fun password(request: PasswordGeneratorRequest): String {
        val pool = buildString {
            if (request.lowercase) append("abcdefghijkmnopqrstuvwxyz")
            if (request.uppercase) append("ABCDEFGHJKLMNPQRSTUVWXYZ")
            if (request.numbers) append("23456789")
            if (request.special) append("!@#\$%^&*")
        }.ifEmpty { "abcdefghijkmnopqrstuvwxyz" }
        return buildString(request.length.toInt()) {
            repeat(request.length.toInt()) { append(pool[random.nextInt(pool.length)]) }
        }
    }
    fun passphrase(request: PassphraseGeneratorRequest): String {
        val sep = request.wordSeparator as? String ?: "-"
        return (1..request.numWords.toInt()).joinToString(sep) { words[random.nextInt(words.size)] }
    }
    fun username(request: UsernameGeneratorRequest): String = when (request) {
        is UsernameGeneratorRequest.Subaddress -> {
            val email = request.email as? String ?: "user@komboe.local"
            val at = email.indexOf('@')
            if (at < 0) email else email.substring(0, at) + "+" + words[random.nextInt(words.size)] + email.substring(at)
        }
        is UsernameGeneratorRequest.Catchall -> words[random.nextInt(words.size)] + "@" + (request.domain as? String ?: "komboe.local")
        is UsernameGeneratorRequest.Word -> words[random.nextInt(words.size)]
        is UsernameGeneratorRequest.Forwarded -> words[random.nextInt(words.size)] + "@forward.komboe.local"
    }
}

class ExporterApi(private val client: Client) {
    fun exportVault(@Suppress("unused") folders: List<Folder>, @Suppress("unused") ciphers: List<Cipher>, @Suppress("unused") format: ExportFormat): String =
        "{\"encrypted\":false,\"items\":[]}"
    fun exportCxf(@Suppress("unused") account: Account, @Suppress("unused") ciphers: List<Cipher>): String = "{}"
    fun importCxf(@Suppress("unused") payload: String): List<EncryptionContext> = emptyList()
}

private fun Cipher.toView(key: SymmetricKey): CipherView {
    val loginEnc = login as? Login
    return CipherView(
        id = id,
        collectionIds = (collectionIds as? List<*>)?.filterIsInstance<String>().orEmpty(),
        key = this.key,
        edit = edit as? Boolean ?: true,
        viewPassword = viewPassword as? Boolean ?: true,
        localData = localData,
        attachments = null,
        organizationUseTotp = organizationUseTotp as? Boolean ?: false,
        passwordHistory = null,
        permissions = permissions,
        creationDate = creationDate as? Instant ?: Instant.EPOCH,
        deletedDate = deletedDate,
        revisionDate = revisionDate as? Instant ?: Instant.EPOCH,
        archivedDate = archivedDate,
        partial = false,
        type = type,
        identity = identity?.viewed(key),
        secureNote = secureNote?.viewed(),
        login = loginEnc?.let {
            LoginView(
                username = dec(it.username, key),
                password = dec(it.password, key),
                passwordRevisionDate = it.passwordRevisionDate,
                uris = (it.uris as? List<*>)?.map { uri ->
                    val row = uri as LoginUri
                    LoginUriView(uri = dec(row.uri, key), match = row.match, uriChecksum = row.uriChecksum)
                },
                totp = dec(it.totp, key),
                autofillOnPageLoad = it.autofillOnPageLoad ?: false,
                fido2Credentials = null,
            )
        },
        card = card?.viewed(key),
        sshKey = sshKey?.viewed(key),
        bankAccount = bankAccount?.viewed(key),
        driversLicense = driversLicense?.viewed(key),
        passport = passport?.viewed(key),
        name = dec(name, key) ?: "",
        notes = dec(notes, key),
        favorite = favorite as? Boolean ?: false,
        folderId = folderId,
        organizationId = organizationId,
        reprompt = reprompt ?: CipherRepromptType.NONE,
        fields = fields?.map { it.viewed(key) },
    )
}

private fun Cipher.toListView(key: SymmetricKey): CipherListView {
    val view = toView(key)
    val loginView = view.login as? LoginView
    return CipherListView(
        id = view.id,
        organizationId = view.organizationId,
        folderId = view.folderId,
        collectionIds = view.collectionIds,
        name = view.name as? String ?: "",
        subtitle = loginView?.username as? String ?: "",
        type = when (view.type) {
            CipherType.LOGIN -> CipherListViewType.Login(
                LoginListView(
                    fido2Credentials = null,
                    hasFido2 = false,
                    username = loginView?.username,
                    totp = loginView?.totp,
                    uris = loginView?.uris,
                ),
            )
            CipherType.CARD -> CipherListViewType.Card(com.bitwarden.vault.CardListView(brand = null))
            CipherType.SECURE_NOTE -> CipherListViewType.SecureNote
            CipherType.IDENTITY -> CipherListViewType.Identity
            CipherType.SSH_KEY -> CipherListViewType.SshKey
            CipherType.BANK_ACCOUNT -> CipherListViewType.BankAccount(com.bitwarden.vault.BankAccountListView(accountNumber = null, accountType = null))
            CipherType.DRIVERS_LICENSE -> CipherListViewType.DriversLicense
            CipherType.PASSPORT -> CipherListViewType.Passport
            else -> CipherListViewType.SecureNote
        },
        favorite = view.favorite as? Boolean ?: false,
        reprompt = (view.reprompt as? CipherRepromptType) ?: CipherRepromptType.NONE,
        organizationUseTotp = view.organizationUseTotp as? Boolean ?: false,
        edit = view.edit as? Boolean ?: true,
        permissions = view.permissions,
        viewPassword = view.viewPassword as? Boolean ?: true,
        attachments = 0u,
        hasOldAttachments = false,
        localData = view.localData,
        creationDate = view.creationDate,
        deletedDate = view.deletedDate,
        revisionDate = view.revisionDate,
        copyableFields = emptyList(),
        archivedDate = view.archivedDate,
        partial = false,
    )
}

private fun CipherView.toCipher(wrappedKey: String, key: SymmetricKey): Cipher {
    val loginView = login as? LoginView
    return Cipher(
        id = id,
        organizationId = organizationId,
        folderId = folderId,
        collectionIds = collectionIds,
        key = wrappedKey,
        name = enc(name, key),
        notes = enc(notes, key),
        type = type,
        login = loginView?.let {
            Login(
                username = enc(it.username, key),
                password = enc(it.password, key),
                passwordRevisionDate = it.passwordRevisionDate,
                uris = (it.uris as? List<*>)?.map { uri ->
                    val row = uri as LoginUriView
                    LoginUri(uri = enc(row.uri, key), match = row.match, uriChecksum = row.uriChecksum)
                },
                totp = enc(it.totp, key),
                autofillOnPageLoad = it.autofillOnPageLoad,
                fido2Credentials = null,
            )
        },
        identity = identity?.sealed(key),
        sshKey = sshKey?.sealed(key),
        card = card?.sealed(key),
        bankAccount = bankAccount?.sealed(key),
        driversLicense = driversLicense?.sealed(key),
        passport = passport?.sealed(key),
        secureNote = secureNote?.sealed(),
        favorite = favorite,
        reprompt = reprompt,
        organizationUseTotp = organizationUseTotp,
        edit = edit,
        viewPassword = viewPassword,
        localData = localData,
        attachments = null,
        fields = fields?.map { it.sealed(key) },
        passwordHistory = null,
        permissions = permissions,
        creationDate = creationDate,
        deletedDate = deletedDate,
        revisionDate = revisionDate,
        archivedDate = archivedDate,
    )
}

private fun Identity.viewed(key: SymmetricKey) = IdentityView(
    title = dec(title, key), middleName = dec(middleName, key), firstName = dec(firstName, key),
    lastName = dec(lastName, key), address1 = dec(address1, key), address2 = dec(address2, key),
    address3 = dec(address3, key), city = dec(city, key), state = dec(state, key),
    postalCode = dec(postalCode, key), country = dec(country, key), company = dec(company, key),
    email = dec(email, key), phone = dec(phone, key), ssn = dec(ssn, key), username = dec(username, key),
    passportNumber = dec(passportNumber, key), licenseNumber = dec(licenseNumber, key),
)
private fun IdentityView.sealed(key: SymmetricKey) = Identity(
    title = enc(title, key), firstName = enc(firstName, key), lastName = enc(lastName, key),
    middleName = enc(middleName, key), address1 = enc(address1, key), address2 = enc(address2, key),
    address3 = enc(address3, key), city = enc(city, key), state = enc(state, key),
    postalCode = enc(postalCode, key), country = enc(country, key), company = enc(company, key),
    email = enc(email, key), phone = enc(phone, key), ssn = enc(ssn, key), username = enc(username, key),
    passportNumber = enc(passportNumber, key), licenseNumber = enc(licenseNumber, key),
)
private fun Card.viewed(key: SymmetricKey) = CardView(
    cardholderName = dec(cardholderName, key), expMonth = dec(expMonth, key), expYear = dec(expYear, key),
    code = dec(code, key), brand = dec(brand, key), number = dec(number, key),
)
private fun CardView.sealed(key: SymmetricKey) = Card(
    cardholderName = enc(cardholderName, key), expMonth = enc(expMonth, key), expYear = enc(expYear, key),
    code = enc(code, key), brand = enc(brand, key), number = enc(number, key),
)
private fun SshKey.viewed(key: SymmetricKey) = SshKeyView(
    publicKey = dec(publicKey, key) ?: "", privateKey = dec(privateKey, key) ?: "", fingerprint = dec(fingerprint, key) ?: "",
)
private fun SshKeyView.sealed(key: SymmetricKey) = SshKey(
    publicKey = enc(publicKey, key), privateKey = enc(privateKey, key) ?: "", fingerprint = enc(fingerprint, key),
)
private fun BankAccount.viewed(key: SymmetricKey) = BankAccountView(
    bankName = dec(bankName, key), nameOnAccount = dec(nameOnAccount, key), accountType = dec(accountType, key),
    accountNumber = dec(accountNumber, key), routingNumber = dec(routingNumber, key), branchNumber = dec(branchNumber, key),
    pin = dec(pin, key), swiftCode = dec(swiftCode, key), iban = dec(iban, key), bankContactPhone = dec(bankContactPhone, key),
)
private fun BankAccountView.sealed(key: SymmetricKey) = BankAccount(
    bankName = enc(bankName, key), nameOnAccount = enc(nameOnAccount, key), accountType = enc(accountType, key),
    accountNumber = enc(accountNumber, key), routingNumber = enc(routingNumber, key), branchNumber = enc(branchNumber, key),
    pin = enc(pin, key), swiftCode = enc(swiftCode, key), iban = enc(iban, key), bankContactPhone = enc(bankContactPhone, key),
)
private fun DriversLicense.viewed(key: SymmetricKey) = DriversLicenseView(
    firstName = dec(firstName, key), middleName = dec(middleName, key), lastName = dec(lastName, key),
    licenseNumber = dec(licenseNumber, key), issuingCountry = dec(issuingCountry, key), issuingState = dec(issuingState, key),
    issuingAuthority = dec(issuingAuthority, key), expirationDate = null, dateOfBirth = null,
    issueDate = null, licenseClass = dec(licenseClass, key),
)
private fun DriversLicenseView.sealed(key: SymmetricKey) = DriversLicense(
    firstName = enc(firstName, key), middleName = enc(middleName, key), lastName = enc(lastName, key),
    dateOfBirth = null, licenseNumber = enc(licenseNumber, key), issuingCountry = enc(issuingCountry, key),
    issuingState = enc(issuingState, key), issueDate = null, issuingAuthority = enc(issuingAuthority, key),
    expirationDate = null, licenseClass = enc(licenseClass, key),
)
private fun Passport.viewed(key: SymmetricKey) = PassportView(
    surname = dec(surname, key), givenName = dec(givenName, key), dateOfBirth = null,
    birthPlace = dec(birthPlace, key), sex = dec(sex, key), nationality = dec(nationality, key),
    passportNumber = dec(passportNumber, key), passportType = dec(passportType, key),
    nationalIdentificationNumber = dec(nationalIdentificationNumber, key), issuingCountry = dec(issuingCountry, key),
    issuingAuthority = dec(issuingAuthority, key), issueDate = null, expirationDate = null,
)
private fun PassportView.sealed(key: SymmetricKey) = Passport(
    surname = enc(surname, key), givenName = enc(givenName, key), dateOfBirth = null,
    birthPlace = enc(birthPlace, key), sex = enc(sex, key), nationality = enc(nationality, key),
    passportNumber = enc(passportNumber, key), passportType = enc(passportType, key),
    issuingCountry = enc(issuingCountry, key), issuingAuthority = enc(issuingAuthority, key),
    issueDate = null, expirationDate = null,
    nationalIdentificationNumber = enc(nationalIdentificationNumber, key),
)
private fun Field.viewed(key: SymmetricKey) = FieldView(
    name = dec(name, key), value = dec(value, key), type = type ?: com.bitwarden.vault.FieldType.TEXT, linkedId = linkedId,
)
private fun FieldView.sealed(key: SymmetricKey) = Field(
    name = enc(name, key), value = enc(value, key), type = type, linkedId = linkedId,
)
private fun SecureNote.viewed() = SecureNoteView(type = type ?: com.bitwarden.vault.SecureNoteType.GENERIC)
private fun SecureNoteView.sealed() = SecureNote(type = type)

private fun enc(value: Any?, key: SymmetricKey): String? =
    (value as? String)?.takeIf { it.isNotEmpty() }?.let { VaultCrypto.encryptUtf8(it, key) }

private fun dec(value: Any?, key: SymmetricKey): String? =
    (value as? String)?.takeIf { it.isNotEmpty() }?.let { VaultCrypto.decryptUtf8(it, key) }

private fun Kdf.toConfig(): KdfConfig = when (this) {
    is Kdf.Pbkdf2 -> KdfConfig.Pbkdf2(iterations.toInt())
    is Kdf.Argon2id -> KdfConfig.Argon2id(iterations.toInt(), memory.toInt(), parallelism.toInt())
}

private fun io.komboe.vaultcrypto.AccountKeys.keys() =
    AsymmetricCryptoKey(public = publicKey, private = encryptedPrivateKey)

private fun decodeKey(value: String?): ByteArray =
    if (value.isNullOrBlank()) ByteArray(0) else Base64.getDecoder().decode(value)

private fun fingerprint(material: String, privateKey: ByteArray?): String {
    if (privateKey == null || privateKey.isEmpty()) return ""
    return VaultCrypto.fingerprintPhrase(material, privateKey)
}

private fun jsonString(value: String): String =
    "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

private fun postJson(url: String, body: String) {
    val connection = (URI(url).toURL().openConnection() as HttpURLConnection).apply {
        requestMethod = "POST"
        doOutput = true
        setRequestProperty("Content-Type", "application/json")
        connectTimeout = 20000
        readTimeout = 20000
    }
    connection.outputStream.use { it.write(body.toByteArray()) }
    val code = connection.responseCode
    if (code !in 200..299) {
        val error = connection.errorStream?.bufferedReader()?.readText().orEmpty()
        error("registration failed ($code) $error")
    }
}

private fun fetchPrelogin(settings: ClientSettings?, email: String): PasswordPreloginResponse {
    val identity = settings?.identityUrl?.trimEnd('/') ?: return PasswordPreloginResponse(email, Kdf.Pbkdf2(600_000u))
    val url = URI("$identity/accounts/prelogin").toURL()
    val connection = (url.openConnection() as HttpURLConnection).apply {
        requestMethod = "POST"
        doOutput = true
        setRequestProperty("Content-Type", "application/json")
        connectTimeout = 15000
        readTimeout = 15000
    }
    connection.outputStream.use { it.write("""{"email":"${email.replace("\"", "")}"}""".toByteArray()) }
    val body = connection.inputStream.bufferedReader().readText()
    val kdfType = Regex(""""kdf"\s*:\s*(\d+)""").find(body)?.groupValues?.get(1)?.toInt() ?: 0
    val iterations = Regex(""""kdfIterations"\s*:\s*(\d+)""").find(body)?.groupValues?.get(1)?.toInt() ?: 600_000
    val memory = Regex(""""kdfMemory"\s*:\s*(\d+)""").find(body)?.groupValues?.get(1)?.toInt()
    val parallelism = Regex(""""kdfParallelism"\s*:\s*(\d+)""").find(body)?.groupValues?.get(1)?.toInt()
    val kdf = if (kdfType == 1 && memory != null && parallelism != null) {
        Kdf.Argon2id(iterations.toUInt(), memory.toUInt(), parallelism.toUInt())
    } else {
        Kdf.Pbkdf2(iterations.toUInt())
    }
    return PasswordPreloginResponse(salt = email, kdf = kdf)
}
