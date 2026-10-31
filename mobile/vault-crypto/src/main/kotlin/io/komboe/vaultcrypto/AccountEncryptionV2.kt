// Account encryption v2.
//
// The user key is a 32-byte XAES-256-GCM COSE key (COSE alg -70010). The stretched
// master key, which stays AES-256-CBC-HMAC, wraps that COSE key as an EncString type 2.
// The RSA private key and the Ed25519 signing key are wrapped by the user key as
// EncString type 7. The encryption public key and the security state ({"version": 2})
// are COSE_Sign1 objects (RFC 9052) under signing namespaces 1 and 2, header label
// -80000. The server stores these strings and checks only their shape.
package io.komboe.vaultcrypto

import org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import java.util.Base64

data class AccountEncryptionV2(
    val userKey: SymmetricKey,
    val keyId: ByteArray,
    val encryptedUserKey: String,
    val publicKey: String,
    val encryptedPrivateKey: String,
    val verifyingKey: String,
    val wrappedSigningKey: String,
    val signedPublicKey: String,
    val securityState: String,
    val securityVersion: Long,
    val masterPasswordHash: String,
)

object AccountV2 {
    const val SECURITY_VERSION: Long = 2
    const val NAMESPACE_HEADER: Long = -80000
    const val NAMESPACE_SIGNED_PUBLIC_KEY: Long = 1
    const val NAMESPACE_SECURITY_STATE: Long = 2
    private const val COSE_EDDSA: Long = -8
    private const val CONTENT_CBOR: Long = 60
    private const val KTY_OKP: Long = 1
    private const val KTY_SYMMETRIC: Long = 4
    private const val CRV_ED25519: Long = 6

    fun make(password: String, email: String, kdf: KdfConfig): AccountEncryptionV2 {
        val master = VaultCrypto.masterKey(password, email, kdf)
        val stretched = VaultCrypto.stretch(master)
        val userKeyBytes = ByteArray(32).also { VaultCryptoBytes.random(it) }
        val keyId = ByteArray(16).also { VaultCryptoBytes.random(it) }
        val userKey = SymmetricKey(userKeyBytes)
        val coseUserKey = symmetricCoseKey(userKeyBytes, keyId)
        val rsa = VaultCrypto.generateRsa()
        val signingSeed = ByteArray(32).also { VaultCryptoBytes.random(it) }
        val signing = ed25519(signingSeed)
        val signingKeyId = ByteArray(16).also { VaultCryptoBytes.random(it) }
        val wrappedSigning = VaultCrypto.encryptCose(
            coseOkpKey(signing.publicKey, signingSeed, signingKeyId, includePrivate = true),
            userKeyBytes,
            CoseAead.XAES_256_GCM,
            keyId = keyId,
        )
        val signedPublic = sign(
            payload = signedPublicKeyMessage(rsa.publicSpki),
            seed = signingSeed,
            keyId = signingKeyId,
            namespace = NAMESPACE_SIGNED_PUBLIC_KEY,
        )
        val security = sign(
            payload = securityStateMessage(SECURITY_VERSION),
            seed = signingSeed,
            keyId = signingKeyId,
            namespace = NAMESPACE_SECURITY_STATE,
        )
        return AccountEncryptionV2(
            userKey = userKey,
            keyId = keyId,
            encryptedUserKey = VaultCrypto.wrapKey(coseUserKey, stretched),
            publicKey = rsa.publicBase64,
            encryptedPrivateKey = VaultCrypto.encryptCose(rsa.privatePkcs8, userKeyBytes, CoseAead.XAES_256_GCM, keyId = keyId),
            verifyingKey = b64(coseOkpKey(signing.publicKey, signingSeed, signingKeyId, includePrivate = false)),
            wrappedSigningKey = wrappedSigning,
            signedPublicKey = b64(signedPublic),
            securityState = b64(security),
            securityVersion = SECURITY_VERSION,
            masterPasswordHash = VaultCrypto.hashMasterPassword(master, password, HashPurpose.SERVER_AUTHORIZATION),
        )
    }

    /**
     * Unwrap a master-key-wrapped user key. A v1 key is 32 or 64 raw bytes. A v2 key is a
     * COSE symmetric key whose `k` parameter is the 32-byte XAES key.
     */
    fun unlockUserKey(password: String, email: String, kdf: KdfConfig, encryptedUserKey: String): SymmetricKey {
        val master = VaultCrypto.masterKey(password, email, kdf)
        val unwrapped = VaultCrypto.unwrapKey(encryptedUserKey, VaultCrypto.stretch(master))
        return materialToUserKey(unwrapped)
    }

    fun materialToUserKey(unwrapped: ByteArray): SymmetricKey {
        if (unwrapped.size == 32 || unwrapped.size == 64) return SymmetricKey(unwrapped)
        val fields = Cbor.Reader(unwrapped).intKeyMap()
        val key = fields[-1L] as? ByteArray ?: error("v2 user key is missing the COSE k parameter")
        require(key.size == 32) { "v2 user key must be 32 bytes" }
        return SymmetricKey(key)
    }

    fun unwrapSigningKey(wrapped: String, userKey: SymmetricKey): Ed25519Material {
        val cose = VaultCrypto.decryptCose(wrapped, userKey.bytes.copyOf(32))
        val fields = Cbor.Reader(cose).intKeyMap()
        val seed = fields[-4L] as? ByteArray ?: error("signing key is missing d")
        val keyId = fields[2L] as? ByteArray ?: ByteArray(0)
        return ed25519(seed).copy(keyId = keyId)
    }

    fun verifySecurityState(securityStateB64: String, verifying: Ed25519Material): Long {
        val payload = verify(b64d(securityStateB64), verifying.publicKey, NAMESPACE_SECURITY_STATE)
        val version = Cbor.Reader(payload).textKeyMap()["version"] as? Long
            ?: error("security state is missing version")
        require(version >= SECURITY_VERSION) { "security version $version is below v2" }
        return version
    }

    fun verifySignedPublicKey(signedPublicKeyB64: String, verifying: Ed25519Material): ByteArray {
        val payload = verify(b64d(signedPublicKeyB64), verifying.publicKey, NAMESPACE_SIGNED_PUBLIC_KEY)
        val fields = Cbor.Reader(payload).textKeyMap()
        val algorithm = fields["algorithm"] as? Long ?: error("signed public key is missing algorithm")
        val format = fields["contentFormat"] as? Long ?: error("signed public key is missing contentFormat")
        require(algorithm == 0L && format == 0L) { "unsupported signed public key" }
        return fields["publicKey"] as? ByteArray ?: error("signed public key is missing publicKey")
    }

    /** Verify the published detached COSE_Sign1 test vector (namespace -1). */
    fun verifyDetached(coseSign1: ByteArray, payload: ByteArray, publicKey: ByteArray, namespace: Long): Boolean {
        val parsed = parseSign1(coseSign1)
        val signed = Cbor.sigStructure(parsed.protectedHeader, payload)
        return ed25519Verify(publicKey, signed, parsed.signature) && parsed.namespace == namespace
    }

    private fun sign(payload: ByteArray, seed: ByteArray, keyId: ByteArray, namespace: Long): ByteArray {
        val protectedHeader = protectedHeader(keyId, namespace)
        val signature = ed25519Sign(seed, Cbor.sigStructure(protectedHeader, payload))
        return byteArrayOf(0x84.toByte()) +
            Cbor.bstr(protectedHeader) +
            byteArrayOf(0xa0.toByte()) +
            Cbor.bstr(payload) +
            Cbor.bstr(signature)
    }

    private fun verify(coseSign1: ByteArray, publicKey: ByteArray, namespace: Long): ByteArray {
        val parsed = parseSign1(coseSign1)
        require(parsed.namespace == namespace) { "signing namespace ${parsed.namespace} is not $namespace" }
        val payload = parsed.payload ?: error("COSE_Sign1 payload is missing")
        val signed = Cbor.sigStructure(parsed.protectedHeader, payload)
        require(ed25519Verify(publicKey, signed, parsed.signature)) { "COSE_Sign1 signature failed" }
        return payload
    }

    private fun protectedHeader(keyId: ByteArray, namespace: Long): ByteArray = Cbor.map(
        listOf(
            Cbor.int(1) to Cbor.int(COSE_EDDSA),
            Cbor.int(3) to Cbor.int(CONTENT_CBOR),
            Cbor.int(4) to Cbor.bstr(keyId),
            Cbor.int(NAMESPACE_HEADER) to Cbor.int(namespace),
        ),
    )

    private fun parseSign1(bytes: ByteArray): Sign1 {
        val reader = Cbor.Reader(bytes)
        require(reader.u8() == 0x84) { "COSE_Sign1 must be a 4-element array" }
        val protected = reader.bstr()
        reader.intKeyMap()
        val payload = reader.optionalBstr()
        val signature = reader.bstr()
        val header = Cbor.Reader(protected).intKeyMap()
        val namespace = header[NAMESPACE_HEADER] as? Long ?: error("signature is missing its namespace")
        return Sign1(protected, payload, signature, namespace)
    }

    private fun signedPublicKeyMessage(spki: ByteArray): ByteArray = Cbor.map(
        listOf(
            Cbor.tstr("algorithm") to Cbor.int(0),
            Cbor.tstr("contentFormat") to Cbor.int(0),
            Cbor.tstr("publicKey") to Cbor.bstr(spki),
        ),
    )

    private fun securityStateMessage(version: Long): ByteArray = Cbor.map(
        listOf(Cbor.tstr("version") to Cbor.int(version)),
    )

    private fun symmetricCoseKey(key: ByteArray, keyId: ByteArray): ByteArray = Cbor.map(
        listOf(
            Cbor.int(1) to Cbor.int(KTY_SYMMETRIC),
            Cbor.int(2) to Cbor.bstr(keyId),
            Cbor.int(3) to Cbor.int(CoseAead.XAES_256_GCM.algorithmId.toLong()),
            Cbor.int(-1) to Cbor.bstr(key),
        ),
    )

    private fun coseOkpKey(publicKey: ByteArray, seed: ByteArray, keyId: ByteArray, includePrivate: Boolean): ByteArray {
        val pairs = mutableListOf(
            Cbor.int(1) to Cbor.int(KTY_OKP),
            Cbor.int(2) to Cbor.bstr(keyId),
            Cbor.int(3) to Cbor.int(COSE_EDDSA),
            Cbor.int(-1) to Cbor.int(CRV_ED25519),
            Cbor.int(-2) to Cbor.bstr(publicKey),
        )
        if (includePrivate) pairs += Cbor.int(-4) to Cbor.bstr(seed)
        return Cbor.map(pairs)
    }

    private fun ed25519(seed: ByteArray): Ed25519Material {
        val private = Ed25519PrivateKeyParameters(seed, 0)
        val public = private.generatePublicKey().encoded
        return Ed25519Material(seed, public, ByteArray(0))
    }

    private fun ed25519Sign(seed: ByteArray, message: ByteArray): ByteArray {
        val signer = Ed25519Signer()
        signer.init(true, Ed25519PrivateKeyParameters(seed, 0))
        signer.update(message, 0, message.size)
        return signer.generateSignature()
    }

    private fun ed25519Verify(publicKey: ByteArray, message: ByteArray, signature: ByteArray): Boolean {
        val verifier = Ed25519Signer()
        verifier.init(false, Ed25519PublicKeyParameters(publicKey, 0))
        verifier.update(message, 0, message.size)
        return verifier.verifySignature(signature)
    }

    private fun b64(data: ByteArray): String = Base64.getEncoder().encodeToString(data)
    private fun b64d(text: String): ByteArray = Base64.getDecoder().decode(text)

    private data class Sign1(
        val protectedHeader: ByteArray,
        val payload: ByteArray?,
        val signature: ByteArray,
        val namespace: Long,
    )
}

data class Ed25519Material(val seed: ByteArray, val publicKey: ByteArray, val keyId: ByteArray)

/** Random bytes without exposing VaultCrypto's private generator. */
internal object VaultCryptoBytes {
    fun random(into: ByteArray) {
        java.security.SecureRandom().nextBytes(into)
    }
}
