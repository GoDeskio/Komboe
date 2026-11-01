package io.komboe.vaultcrypto

import org.junit.jupiter.api.Assertions.assertArrayEquals
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.util.Base64

class VaultCryptoTest {
    private val vectors = json()

    @Test
    fun pbkdf2MasterKeyMatchesWebCryptoVectors() {
        val v = vectors.obj("pbkdf2")
        val master = VaultCrypto.masterKey(v.str("password"), v.str("email"), KdfConfig.Pbkdf2(v.int("iterations")))
        assertArrayEquals(b64(v.str("masterKey")), master)
        val stretched = VaultCrypto.stretch(master)
        assertArrayEquals(b64(v.str("encKey")), stretched.encryptionKey)
        assertArrayEquals(b64(v.str("macKey")), stretched.macKey)
        assertEquals(
            v.str("serverPasswordHash"),
            VaultCrypto.hashMasterPassword(master, v.str("password"), HashPurpose.SERVER_AUTHORIZATION),
        )
        assertEquals(
            v.str("localPasswordHash"),
            VaultCrypto.hashMasterPassword(master, v.str("password"), HashPurpose.LOCAL_AUTHORIZATION),
        )
    }

    @Test
    fun encStringRoundTripsAgainstPythonAes() {
        val account = vectors.obj("pbkdf2")
        val item = vectors.obj("encString")
        val key = SymmetricKey(b64(account.str("encKey")) + b64(account.str("macKey")))
        val produced = VaultCrypto.encryptUtf8(item.str("plaintext"), key, b64(item.str("iv")))
        assertEquals(item.str("ciphertext"), produced)
        assertEquals(item.str("plaintext"), VaultCrypto.decryptUtf8(produced, key))
        assertTrue(produced.startsWith("2."))
    }

    @Test
    fun cipherFieldsRoundTripUnderItemKey() {
        val item = vectors.obj("item")
        val key = SymmetricKey.fromBase64(item.str("key"))
        val encrypted = VaultCrypto.encryptUtf8(item.str("plaintext"), key, b64(item.str("iv")))
        assertEquals(item.str("ciphertext"), encrypted)
        val name = VaultCrypto.encryptUtf8("Bank", key)
        val fields = VaultCrypto.decryptFields(
            mapOf("name" to name, "password" to encrypted, "notes" to null),
            key,
        )
        assertEquals("Bank", fields["name"])
        assertEquals(item.str("plaintext"), fields["password"])
        assertEquals(null, fields["notes"])
    }

    @Test
    fun argon2idMatchesIndependentImplementation() {
        val v = vectors.obj("argon2id")
        val master = VaultCrypto.masterKey(
            v.str("password"),
            v.str("email"),
            KdfConfig.Argon2id(v.int("iterations"), v.int("memoryMiB"), v.int("parallelism")),
        )
        assertArrayEquals(b64(v.str("masterKey")), master)
    }

    @Test
    fun rsaOaepOrgKeyMatchesPython() {
        val v = vectors.obj("rsa")
        val pkcs8 = pemBody(v.str("pkcs8Pem"))
        assertArrayEquals(b64(v.str("orgKey")), VaultCrypto.rsaDecrypt(v.str("type4"), pkcs8))
        assertArrayEquals(b64(v.str("orgKey")), VaultCrypto.rsaDecrypt(v.str("type3"), pkcs8))
        val account = VaultCrypto.makeAccountKeys("correct horse battery staple", "ada@komboe.test", KdfConfig.Pbkdf2(1000))
        val unlocked = VaultCrypto.unlockUserKey(
            "correct horse battery staple",
            "ada@komboe.test",
            KdfConfig.Pbkdf2(1000),
            account.encryptedUserKey,
        )
        assertArrayEquals(account.userKey.bytes, unlocked.bytes)
        val privateKey = VaultCrypto.decryptBytes(account.encryptedPrivateKey, unlocked)
        val org = SymmetricKey.random(64)
        val wrapped = VaultCrypto.shareOrgKey(org, Base64.getDecoder().decode(account.publicKey))
        assertTrue(wrapped.startsWith("4."))
        assertArrayEquals(org.bytes, VaultCrypto.receiveOrgKey(wrapped, privateKey).bytes)
    }

    @Test
    fun sendKeyAndPasswordHashMatchVectors() {
        val v = vectors.obj("send")
        val material = b64(v.str("material"))
        val derived = VaultCrypto.sendKey(material)
        assertArrayEquals(b64(v.str("derivedKey")), derived.bytes)
        val name = VaultCrypto.encryptUtf8(v.str("name"), derived, b64(v.str("iv")))
        assertEquals(v.str("nameEnc"), name)
        assertEquals(v.str("name"), VaultCrypto.decryptUtf8(name, derived))
        assertEquals(v.str("passwordHash"), VaultCrypto.hashSendPassword(v.str("password"), material))
    }

    @Test
    fun totpMatchesRfc6238() {
        val v = vectors.obj("totp")
        val code = Totp.hotp(v.str("secretAscii").toByteArray(Charsets.US_ASCII), v.int("time").toLong() / 30, 8, "SHA1")
        assertEquals(v.str("code"), code)
        val uri = "otpauth://totp/Komboe:ada?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&issuer=Komboe&digits=8&period=30"
        assertEquals("94287082", VaultCrypto.totp(uri, 59).code)
    }

    @Test
    fun pinUnlockRoundTrips() {
        val kdf = KdfConfig.Pbkdf2(1000)
        val account = VaultCrypto.makeAccountKeys("horse", "ada@komboe.test", kdf)
        val envelope = VaultCrypto.protectWithPin("1234", "ada@komboe.test", kdf, account.userKey)
        val unlocked = VaultCrypto.unlockWithPin("1234", "ada@komboe.test", kdf, envelope)
        assertArrayEquals(account.userKey.bytes, unlocked.bytes)
    }

    @Test
    fun coseXChaChaAndXaesRoundTrip() {
        val key = ByteArray(32) { (it + 3).toByte() }
        val nonce = ByteArray(24) { (it + 9).toByte() }
        val plain = "vault-row".toByteArray()
        for (alg in CoseAead.entries) {
            val enc = VaultCrypto.encryptCose(plain, key, alg, nonce)
            assertTrue(enc.startsWith("7."))
            assertArrayEquals(plain, VaultCrypto.decryptCose(enc, key))
        }
    }

    @Test
    fun xaesMatchesC2spVectors() {
        val key = ByteArray(32) { 0x01 }
        val nonce = "ABCDEFGHIJKLMNOPQRSTUVWX".toByteArray(Charsets.US_ASCII)
        val (derived, n) = xaesDerive(key, nonce)
        assertEquals(
            "c8612c9ed53fe43e8e005b828a1631a0bbcb6ab2f46514ec4f439fcfd0fa969b",
            derived.toHex(),
        )
        assertEquals("4d4e4f505152535455565758", n.toHex())
        val ct = xaes(key, nonce, "XAES-256-GCM".toByteArray(Charsets.US_ASCII), encrypt = true, aad = ByteArray(0))
        assertEquals("ce546ef63c9cc60765923609b33a9a1974e96e52daf2fcf7075e2271", ct.toHex())

        val key2 = ByteArray(32) { 0x03 }
        val ct2 = xaes(
            key2,
            nonce,
            "XAES-256-GCM".toByteArray(Charsets.US_ASCII),
            encrypt = true,
            aad = "c2sp.org/XAES-256-GCM".toByteArray(Charsets.US_ASCII),
        )
        assertEquals("986ec1832593df5443a179437fd083bf3fdb41abd740a21f71eb769d", ct2.toHex())
    }

    @Test
    fun fingerprintUsesEffWordlist() {
        val phrase = VaultCrypto.fingerprintPhrase("ada@komboe.test", "komboe-public-key".toByteArray())
        assertEquals(5, phrase.split("-").size)
        assertTrue(phrase.all { it.isLetter() || it == '-' })
    }

    private fun json(): Json = Json.parse(
        VaultCryptoTest::class.java.classLoader.getResource("vectors.json")!!.readText(),
    )

    private fun b64(value: String): ByteArray = Base64.getDecoder().decode(value)

    private fun pemBody(pem: String): ByteArray {
        val body = pem.lineSequence().filter { !it.startsWith("-----") }.joinToString("")
        return Base64.getDecoder().decode(body)
    }

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }
}

/** Tiny JSON reader so the tests do not take a parser dependency. */
private class Json private constructor(private val value: Any?) {
    fun obj(name: String): Json = Json((value as Map<*, *>)[name]!!)
    fun str(name: String): String = (value as Map<*, *>)[name] as String
    fun int(name: String): Int = (value as Map<*, *>)[name] as Int

    companion object {
        fun parse(text: String): Json = Json(Parser(text).parse())
    }

    private class Parser(private val text: String) {
        private var i = 0
        fun parse(): Any? {
            skip()
            return when (val c = text[i]) {
                '{' -> parseObject()
                '"' -> parseString()
                else -> if (c == '-' || c.isDigit()) parseNumber() else error("bad json at $i")
            }
        }

        private fun parseObject(): Map<String, Any?> {
            expect('{')
            val map = linkedMapOf<String, Any?>()
            skip()
            if (peek('}')) return map
            while (true) {
                skip()
                val key = parseString()
                skip()
                expect(':')
                map[key] = parse()
                skip()
                if (peek('}')) return map
                expect(',')
            }
        }

        private fun parseString(): String {
            expect('"')
            val out = StringBuilder()
            while (true) {
                val c = text[i++]
                if (c == '"') return out.toString()
                if (c == '\\') {
                    when (val escaped = text[i++]) {
                        'n' -> out.append('\n')
                        'r' -> out.append('\r')
                        't' -> out.append('\t')
                        else -> out.append(escaped)
                    }
                } else {
                    out.append(c)
                }
            }
        }

        private fun parseNumber(): Int {
            val start = i
            if (text[i] == '-') i++
            while (i < text.length && text[i].isDigit()) i++
            return text.substring(start, i).toInt()
        }

        private fun skip() {
            while (i < text.length && text[i].isWhitespace()) i++
        }

        private fun expect(c: Char) {
            skip()
            require(text[i] == c)
            i++
        }

        private fun peek(c: Char): Boolean {
            skip()
            if (text[i] != c) return false
            i++
            return true
        }
    }
}
