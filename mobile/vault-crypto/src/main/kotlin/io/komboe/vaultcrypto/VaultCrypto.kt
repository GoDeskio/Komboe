// Komboe vault crypto. Written from the public Bitwarden protocol
// (security white paper, EncString layout, HKDF-Expand "enc"/"mac").
// GPL-3.0-only. Not derived from the Bitwarden SDK or sdk-internal.
package io.komboe.vaultcrypto

import org.bouncycastle.crypto.modes.ChaCha20Poly1305
import org.bouncycastle.crypto.params.KeyParameter
import org.bouncycastle.crypto.params.ParametersWithIV
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.spec.MGF1ParameterSpec
import java.security.spec.PKCS8EncodedKeySpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.OAEPParameterSpec
import javax.crypto.spec.PSource
import javax.crypto.spec.SecretKeySpec

enum class HashPurpose(val iterations: Int) {
    /** Sent to the server as the master password verifier. */
    SERVER_AUTHORIZATION(1),
    /** Stored on the device to check the master password offline. */
    LOCAL_AUTHORIZATION(2),
}

sealed class KdfConfig {
    data class Pbkdf2(val iterations: Int) : KdfConfig()
    /** [memoryMiB] is mebibytes, matching the Bitwarden account KDF parameter. */
    data class Argon2id(val iterations: Int, val memoryMiB: Int, val parallelism: Int) : KdfConfig()
}

/** 32-byte AES key, or 64-byte AES key followed by an HMAC-SHA256 key. */
class SymmetricKey(val bytes: ByteArray) {
    init {
        require(bytes.size == 32 || bytes.size == 64) { "symmetric key must be 32 or 64 bytes" }
    }

    val encryptionKey: ByteArray get() = if (bytes.size == 64) bytes.copyOfRange(0, 32) else bytes.copyOf()
    val macKey: ByteArray? get() = if (bytes.size == 64) bytes.copyOfRange(32, 64) else null

    fun toBase64(): String = b64(bytes)

    companion object {
        fun fromBase64(value: String): SymmetricKey = SymmetricKey(b64d(value))
        fun random(size: Int = 64, random: SecureRandom = SecureRandom()): SymmetricKey =
            SymmetricKey(ByteArray(size).also { random.nextBytes(it) })
    }
}

data class RsaMaterial(val publicSpki: ByteArray, val privatePkcs8: ByteArray) {
    val publicBase64: String get() = b64(publicSpki)
    val privateBase64: String get() = b64(privatePkcs8)
}

data class TotpCode(val code: String, val periodSeconds: Int)

enum class CoseAead(val algorithmId: Int) {
    /** COSE private-use algorithm id used for XChaCha20-Poly1305 vault envelopes. */
    XCHACHA20_POLY1305(-70000),
    /** COSE private-use algorithm id for XAES-256-GCM (C2SP). */
    XAES_256_GCM(-70010),
}

object VaultCrypto {
    private val random = SecureRandom()

    fun masterKey(password: String, email: String, kdf: KdfConfig): ByteArray {
        val salt = email.trim().lowercase().toByteArray(Charsets.UTF_8)
        val secret = password.toByteArray(Charsets.UTF_8)
        return when (kdf) {
            is KdfConfig.Pbkdf2 -> pbkdf2(secret, salt, kdf.iterations, 32)
            is KdfConfig.Argon2id -> argon2id(secret, salt, kdf.iterations, kdf.memoryMiB, kdf.parallelism)
        }
    }

    /** HKDF-Expand the 32-byte master key into a 64-byte enc||mac key. */
    fun stretch(masterKey: ByteArray): SymmetricKey {
        require(masterKey.size == 32) { "only a 256-bit master key is stretched" }
        val enc = hkdfExpand(masterKey, "enc".toByteArray(Charsets.UTF_8), 32)
        val mac = hkdfExpand(masterKey, "mac".toByteArray(Charsets.UTF_8), 32)
        return SymmetricKey(enc + mac)
    }

    fun hashMasterPassword(masterKey: ByteArray, password: String, purpose: HashPurpose): String {
        val hash = pbkdf2Raw(masterKey, password.toByteArray(Charsets.UTF_8), purpose.iterations, 32)
        return b64(hash)
    }

    fun encryptUtf8(plain: String, key: SymmetricKey, iv: ByteArray? = null): String =
        encryptBytes(plain.toByteArray(Charsets.UTF_8), key, iv)

    fun decryptUtf8(enc: String, key: SymmetricKey): String =
        decryptBytes(enc, key).toString(Charsets.UTF_8)

    fun encryptBytes(plain: ByteArray, key: SymmetricKey, iv: ByteArray? = null): String {
        val usedIv = iv ?: ByteArray(16).also { random.nextBytes(it) }
        require(usedIv.size == 16) { "AES-CBC IV must be 16 bytes" }
        val ciphertext = aesCbc(key.encryptionKey, usedIv, plain, encrypt = true)
        val macKey = key.macKey
        return if (macKey != null) {
            val mac = hmacSha256(macKey, usedIv + ciphertext)
            "2.${b64(usedIv)}|${b64(ciphertext)}|${b64(mac)}"
        } else {
            "0.${b64(usedIv)}|${b64(ciphertext)}"
        }
    }

    fun decryptBytes(enc: String, key: SymmetricKey): ByteArray {
        val parsed = parseEncString(enc)
        return when (parsed.type) {
            0 -> {
                require(key.bytes.size == 32 || key.bytes.size == 64)
                aesCbc(key.encryptionKey, parsed.iv!!, parsed.data, encrypt = false)
            }
            2 -> {
                val macKey = key.macKey ?: error("type 2 EncString needs a 64-byte key")
                val expected = hmacSha256(macKey, parsed.iv!! + parsed.data)
                if (!MessageDigest.isEqual(expected, parsed.mac)) error("EncString MAC failed")
                aesCbc(key.encryptionKey, parsed.iv, parsed.data, encrypt = false)
            }
            7 -> decryptCose(enc, rawAeadKey(key))
            else -> error("unsupported symmetric EncString type ${parsed.type}")
        }
    }

    fun randomSymmetricKey(bytes: Int = 64): SymmetricKey = SymmetricKey.random(bytes, random)

    fun wrapKey(inner: ByteArray, wrapping: SymmetricKey): String = encryptBytes(inner, wrapping)

    fun unwrapKey(enc: String, wrapping: SymmetricKey): ByteArray = decryptBytes(enc, wrapping)

    fun generateRsa(bits: Int = 2048): RsaMaterial {
        val generator = KeyPairGenerator.getInstance("RSA")
        generator.initialize(bits, random)
        val pair = generator.generateKeyPair()
        return RsaMaterial(pair.public.encoded, pair.private.encoded)
    }

    /** RSA-OAEP. [sha256] selects EncString type 3; otherwise type 4 (SHA-1), the org-key default. */
    fun rsaEncrypt(plain: ByteArray, publicSpki: ByteArray, sha256: Boolean): String {
        val cipher = rsaCipher(encrypt = true, publicSpki = publicSpki, privatePkcs8 = null, sha256 = sha256)
        val encrypted = cipher.doFinal(plain)
        return if (sha256) "3.${b64(encrypted)}" else "4.${b64(encrypted)}"
    }

    fun rsaDecrypt(enc: String, privatePkcs8: ByteArray): ByteArray {
        val parsed = parseEncString(enc)
        val sha256 = when (parsed.type) {
            3 -> true
            4 -> false
            else -> error("not an RSA EncString: type ${parsed.type}")
        }
        val cipher = rsaCipher(encrypt = false, publicSpki = null, privatePkcs8 = privatePkcs8, sha256 = sha256)
        return cipher.doFinal(parsed.data)
    }

    /**
     * New account material: a random 64-byte user key wrapped by the stretched master key,
     * an RSA key pair whose private half is wrapped by the user key, and the server password hash.
     */
    fun makeAccountKeys(password: String, email: String, kdf: KdfConfig): AccountKeys {
        val master = masterKey(password, email, kdf)
        val stretched = stretch(master)
        val userKey = randomSymmetricKey(64)
        val rsa = generateRsa()
        return AccountKeys(
            userKey = userKey,
            encryptedUserKey = wrapKey(userKey.bytes, stretched),
            publicKey = rsa.publicBase64,
            encryptedPrivateKey = encryptBytes(rsa.privatePkcs8, userKey),
            masterPasswordHash = hashMasterPassword(master, password, HashPurpose.SERVER_AUTHORIZATION),
        )
    }

    fun unlockUserKey(password: String, email: String, kdf: KdfConfig, encryptedUserKey: String): SymmetricKey {
        val master = masterKey(password, email, kdf)
        return AccountV2.materialToUserKey(unwrapKey(encryptedUserKey, stretch(master)))
    }

    /** Org symmetric key, wrapped to a member with RSA-OAEP SHA-1 (EncString type 4). */
    fun shareOrgKey(orgKey: SymmetricKey, memberPublicSpki: ByteArray): String =
        rsaEncrypt(orgKey.bytes, memberPublicSpki, sha256 = false)

    fun receiveOrgKey(encryptedOrgKey: String, memberPrivatePkcs8: ByteArray): SymmetricKey =
        SymmetricKey(rsaDecrypt(encryptedOrgKey, memberPrivatePkcs8))

    /**
     * PIN unlock. The PIN is run through the account KDF with the email as salt, stretched,
     * and used to unwrap the stored user key. This is the legacy pin-protected user key.
     */
    fun unlockWithPin(pin: String, email: String, kdf: KdfConfig, pinProtectedUserKey: String): SymmetricKey {
        val pinKey = stretch(masterKey(pin, email, kdf))
        return SymmetricKey(unwrapKey(pinProtectedUserKey, pinKey))
    }

    fun protectWithPin(pin: String, email: String, kdf: KdfConfig, userKey: SymmetricKey): String {
        val pinKey = stretch(masterKey(pin, email, kdf))
        return wrapKey(userKey.bytes, pinKey)
    }

    fun totp(secretOrUri: String, timeSeconds: Long): TotpCode = Totp.generate(secretOrUri, timeSeconds)

    /** 16-byte send seed → 64-byte key via HKDF-SHA256(salt="bitwarden-send", info="send"). */
    fun sendKey(material: ByteArray): SymmetricKey {
        val prk = hmacSha256("bitwarden-send".toByteArray(Charsets.UTF_8), material)
        return SymmetricKey(hkdfExpand(prk, "send".toByteArray(Charsets.UTF_8), 64))
    }

    fun randomSendMaterial(): ByteArray = ByteArray(16).also { random.nextBytes(it) }

    /** Password gate stored on the server. PBKDF2(material, password, 100000). */
    fun hashSendPassword(password: String, material: ByteArray): String =
        b64(pbkdf2(material, password.toByteArray(Charsets.UTF_8), 100_000, 32))

    fun fingerprintPhrase(material: String, publicKey: ByteArray): String =
        Fingerprint.phrase(material, publicKey)

    fun encryptCose(
        plain: ByteArray,
        key32: ByteArray,
        algorithm: CoseAead,
        nonce: ByteArray? = null,
        keyId: ByteArray? = null,
    ): String {
        require(key32.size == 32)
        val used = nonce ?: ByteArray(24).also { random.nextBytes(it) }
        require(used.size == 24)
        val protected = coseProtected(algorithm.algorithmId, keyId)
        val aad = if (keyId == null) ByteArray(0) else CoseEncrypt0.encStructure(protected)
        val ciphertext = when (algorithm) {
            CoseAead.XCHACHA20_POLY1305 -> xchacha(key32, used, plain, encrypt = true)
            CoseAead.XAES_256_GCM -> xaes(key32, used, plain, encrypt = true, aad = aad)
        }
        return "7." + b64(CoseEncrypt0.encode(algorithm.algorithmId, used, ciphertext, keyId))
    }

    private fun coseProtected(algorithm: Int, keyId: ByteArray?): ByteArray {
        val pairs = mutableListOf(Cbor.int(1) to Cbor.int(algorithm.toLong()))
        if (keyId != null) pairs += Cbor.int(4) to Cbor.bstr(keyId)
        return Cbor.map(pairs)
    }

    fun decryptCose(enc: String, key32: ByteArray): ByteArray {
        require(key32.size == 32)
        val parsed = parseEncString(enc)
        require(parsed.type == 7)
        val envelope = CoseEncrypt0.decode(parsed.data)
        val aads = listOf(CoseEncrypt0.encStructure(envelope.protectedHeader), ByteArray(0))
        var last: Exception? = null
        for (aad in aads) {
            try {
                return when (envelope.algorithm) {
                    CoseAead.XCHACHA20_POLY1305.algorithmId ->
                        xchacha(key32, envelope.nonce, envelope.ciphertext, encrypt = false)
                    CoseAead.XAES_256_GCM.algorithmId ->
                        xaes(key32, envelope.nonce, envelope.ciphertext, encrypt = false, aad = aad)
                    else -> error("unsupported COSE algorithm ${envelope.algorithm}")
                }
            } catch (error: Exception) {
                last = error
            }
        }
        throw last ?: error("COSE decrypt failed")
    }

    /** Encrypt each non-null string. Used for cipher, folder, collection and send fields. */
    fun encryptFields(fields: Map<String, String?>, key: SymmetricKey): Map<String, String?> =
        fields.mapValues { (_, value) -> value?.let { encryptUtf8(it, key) } }

    fun decryptFields(fields: Map<String, String?>, key: SymmetricKey): Map<String, String?> =
        fields.mapValues { (_, value) -> value?.let { decryptUtf8(it, key) } }

    private fun rawAeadKey(key: SymmetricKey): ByteArray {
        require(key.bytes.size == 32) { "COSE AEAD key must be 32 bytes" }
        return key.bytes
    }
}

data class AccountKeys(
    val userKey: SymmetricKey,
    val encryptedUserKey: String,
    val publicKey: String,
    val encryptedPrivateKey: String,
    val masterPasswordHash: String,
)

internal data class ParsedEncString(
    val type: Int,
    val iv: ByteArray?,
    val data: ByteArray,
    val mac: ByteArray?,
)

internal fun parseEncString(value: String): ParsedEncString {
    val header = value.split('.', limit = 2)
    val (type, body) = if (header.size == 2 && header[0].toIntOrNull() != null) {
        header[0].toInt() to header[1]
    } else {
        0 to value
    }
    val parts = body.split('|')
    return when (type) {
        0, 2 -> {
            require(parts.size >= 2)
            ParsedEncString(
                type = type,
                iv = b64d(parts[0]),
                data = b64d(parts[1]),
                mac = parts.getOrNull(2)?.let { b64d(it) },
            )
        }
        3, 4, 7 -> ParsedEncString(type, null, b64d(parts[0]), parts.getOrNull(1)?.let { b64d(it) })
        else -> error("unknown EncString type $type")
    }
}

internal fun pbkdf2(password: ByteArray, salt: ByteArray, iterations: Int, length: Int): ByteArray =
    pbkdf2Raw(password, salt, iterations, length)

/** PBKDF2-HMAC-SHA256 over raw bytes. Text passwords are UTF-8, not Java chars. */
internal fun pbkdf2Raw(password: ByteArray, salt: ByteArray, iterations: Int, length: Int): ByteArray {
    val generator = org.bouncycastle.crypto.generators.PKCS5S2ParametersGenerator(
        org.bouncycastle.crypto.digests.SHA256Digest(),
    )
    generator.init(password, salt, iterations)
    return (generator.generateDerivedParameters(length * 8) as KeyParameter).key
}

internal fun hkdfExpand(prk: ByteArray, info: ByteArray, length: Int): ByteArray {
    val hashLen = 32
    require(prk.size >= hashLen)
    val n = (length + hashLen - 1) / hashLen
    val okm = ByteArray(n * hashLen)
    var previous = ByteArray(0)
    var offset = 0
    for (i in 1..n) {
        previous = hmacSha256(prk, previous + info + byteArrayOf(i.toByte()))
        previous.copyInto(okm, offset)
        offset += previous.size
    }
    return okm.copyOf(length)
}

internal fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray {
    val mac = Mac.getInstance("HmacSHA256")
    mac.init(SecretKeySpec(key, "HmacSHA256"))
    return mac.doFinal(data)
}

internal fun aesCbc(key: ByteArray, iv: ByteArray, data: ByteArray, encrypt: Boolean): ByteArray {
    val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
    val mode = if (encrypt) Cipher.ENCRYPT_MODE else Cipher.DECRYPT_MODE
    cipher.init(mode, SecretKeySpec(key, "AES"), IvParameterSpec(iv))
    return cipher.doFinal(data)
}

internal fun argon2id(password: ByteArray, salt: ByteArray, iterations: Int, memoryMiB: Int, parallelism: Int): ByteArray {
    val builder = org.bouncycastle.crypto.params.Argon2Parameters.Builder(
        org.bouncycastle.crypto.params.Argon2Parameters.ARGON2_id,
    )
        .withVersion(org.bouncycastle.crypto.params.Argon2Parameters.ARGON2_VERSION_13)
        .withIterations(iterations)
        .withMemoryAsKB(memoryMiB * 1024)
        .withParallelism(parallelism)
        .withSalt(salt)
    val generator = org.bouncycastle.crypto.generators.Argon2BytesGenerator()
    generator.init(builder.build())
    val out = ByteArray(32)
    generator.generateBytes(password, out)
    return out
}

private fun rsaCipher(encrypt: Boolean, publicSpki: ByteArray?, privatePkcs8: ByteArray?, sha256: Boolean): Cipher {
    val hash = if (sha256) "SHA-256" else "SHA-1"
    val mgf = if (sha256) MGF1ParameterSpec.SHA256 else MGF1ParameterSpec.SHA1
    val cipher = Cipher.getInstance("RSA/ECB/OAEPPadding")
    val spec = OAEPParameterSpec(hash, "MGF1", mgf, PSource.PSpecified.DEFAULT)
    if (encrypt) {
        val key = KeyFactory.getInstance("RSA").generatePublic(X509EncodedKeySpec(publicSpki))
        cipher.init(Cipher.ENCRYPT_MODE, key, spec)
    } else {
        val key = KeyFactory.getInstance("RSA").generatePrivate(PKCS8EncodedKeySpec(privatePkcs8))
        cipher.init(Cipher.DECRYPT_MODE, key, spec)
    }
    return cipher
}

internal fun b64(data: ByteArray): String = Base64.getEncoder().encodeToString(data)

internal fun b64d(value: String): ByteArray {
    val padded = value.replace('-', '+').replace('_', '/')
    val withPad = padded + "=".repeat((4 - padded.length % 4) % 4)
    return Base64.getDecoder().decode(withPad)
}

/** XChaCha20-Poly1305: HChaCha20(key, nonce[0:16]) then ChaCha20-Poly1305 with a 12-byte nonce. */
internal fun xchacha(key: ByteArray, nonce24: ByteArray, data: ByteArray, encrypt: Boolean): ByteArray {
    require(key.size == 32 && nonce24.size == 24)
    val subkey = hchacha20(key, nonce24.copyOfRange(0, 16))
    val iv = ByteArray(12)
    nonce24.copyInto(iv, destinationOffset = 4, startIndex = 16, endIndex = 24)
    val cipher = ChaCha20Poly1305()
    cipher.init(encrypt, ParametersWithIV(KeyParameter(subkey), iv))
    val out = ByteArray(cipher.getOutputSize(data.size))
    var n = cipher.processBytes(data, 0, data.size, out, 0)
    n += cipher.doFinal(out, n)
    return out.copyOf(n)
}

internal fun hchacha20(key: ByteArray, nonce16: ByteArray): ByteArray {
    require(key.size == 32 && nonce16.size == 16)
    val state = IntArray(16)
    val constants = "expand 32-byte k".toByteArray(Charsets.US_ASCII)
    for (i in 0 until 4) state[i] = load32(constants, i * 4)
    for (i in 0 until 8) state[4 + i] = load32(key, i * 4)
    for (i in 0 until 4) state[12 + i] = load32(nonce16, i * 4)
    val working = state.clone()
    repeat(10) {
        quarter(working, 0, 4, 8, 12)
        quarter(working, 1, 5, 9, 13)
        quarter(working, 2, 6, 10, 14)
        quarter(working, 3, 7, 11, 15)
        quarter(working, 0, 5, 10, 15)
        quarter(working, 1, 6, 11, 12)
        quarter(working, 2, 7, 8, 13)
        quarter(working, 3, 4, 9, 14)
    }
    val out = ByteArray(32)
    for (i in 0 until 4) store32(out, i * 4, working[i])
    for (i in 0 until 4) store32(out, 16 + i * 4, working[12 + i])
    return out
}

private fun quarter(s: IntArray, a: Int, b: Int, c: Int, d: Int) {
    s[a] += s[b]; s[d] = (s[d] xor s[a]).rotateLeft(16)
    s[c] += s[d]; s[b] = (s[b] xor s[c]).rotateLeft(12)
    s[a] += s[b]; s[d] = (s[d] xor s[a]).rotateLeft(8)
    s[c] += s[d]; s[b] = (s[b] xor s[c]).rotateLeft(7)
}

private fun load32(b: ByteArray, offset: Int): Int =
    (b[offset].toInt() and 0xff) or
        ((b[offset + 1].toInt() and 0xff) shl 8) or
        ((b[offset + 2].toInt() and 0xff) shl 16) or
        ((b[offset + 3].toInt() and 0xff) shl 24)

private fun store32(b: ByteArray, offset: Int, value: Int) {
    b[offset] = value.toByte()
    b[offset + 1] = (value ushr 8).toByte()
    b[offset + 2] = (value ushr 16).toByte()
    b[offset + 3] = (value ushr 24).toByte()
}

/**
 * XAES-256-GCM (https://c2sp.org/XAES-256-GCM): a 32-byte key and a 24-byte nonce
 * derive an AES-256-GCM subkey. AAD is empty for vault envelopes.
 */
internal fun xaes(key: ByteArray, nonce24: ByteArray, data: ByteArray, encrypt: Boolean, aad: ByteArray): ByteArray {
    require(key.size == 32 && nonce24.size == 24)
    val (derived, nonce12) = xaesDerive(key, nonce24)
    val cipher = Cipher.getInstance("AES/GCM/NoPadding")
    val spec = javax.crypto.spec.GCMParameterSpec(128, nonce12)
    cipher.init(if (encrypt) Cipher.ENCRYPT_MODE else Cipher.DECRYPT_MODE, SecretKeySpec(derived, "AES"), spec)
    if (aad.isNotEmpty()) cipher.updateAAD(aad)
    return cipher.doFinal(data)
}

internal fun xaesDerive(key: ByteArray, nonce24: ByteArray): Pair<ByteArray, ByteArray> {
    val block = Cipher.getInstance("AES/ECB/NoPadding")
    block.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"))
    val zero = ByteArray(16)
    val l = block.doFinal(zero)
    val k1 = shiftLeftOne(l)
    if ((l[0].toInt() and 0x80) != 0) k1[15] = (k1[15].toInt() xor 0x87).toByte()
    val prefix = nonce24.copyOfRange(0, 12)
    fun message(counter: Int): ByteArray {
        val m = ByteArray(16)
        m[0] = 0
        m[1] = counter.toByte()
        m[2] = 0x58
        m[3] = 0
        prefix.copyInto(m, 4)
        for (i in m.indices) m[i] = (m[i].toInt() xor k1[i].toInt()).toByte()
        return block.doFinal(m)
    }
    return message(1) + message(2) to nonce24.copyOfRange(12, 24)
}

private fun shiftLeftOne(block: ByteArray): ByteArray {
    val out = ByteArray(16)
    var carry = 0
    for (i in 15 downTo 0) {
        val value = block[i].toInt() and 0xff
        out[i] = ((value shl 1) or carry).toByte()
        carry = value ushr 7
    }
    return out
}
