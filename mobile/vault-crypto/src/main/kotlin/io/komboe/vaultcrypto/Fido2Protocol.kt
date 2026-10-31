// CTAP2 / WebAuthn authenticator (W3C WebAuthn level 3, FIDO CTAP2).
// ES256, attestation format "none", and the Bitwarden authenticator AAGUID so a
// passkey created here verifies in the web vault and the extension, which use
// the same authenticator data layout.
package io.komboe.vaultcrypto

import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.Signature
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.PKCS8EncodedKeySpec
import java.util.Base64

object Fido2Protocol {
    /** Bitwarden authenticator AAGUID: d548826e-79b4-db40-a3d8-11116f7e8349. */
    val AAGUID: ByteArray = byteArrayOf(
        0xd5.toByte(), 0x48, 0x82.toByte(), 0x6e, 0x79, 0xb4.toByte(), 0xdb.toByte(), 0x40,
        0xa3.toByte(), 0xd8.toByte(), 0x11, 0x11, 0x6f, 0x7e, 0x83.toByte(), 0x49,
    )

    data class Created(
        val credentialId: String,
        val privateKeyPkcs8: ByteArray,
        val publicKeySpki: ByteArray,
        val authenticatorData: ByteArray,
        val attestationObject: ByteArray,
        val clientDataJson: ByteArray,
        val signatureCounter: Int,
    )

    data class Asserted(
        val credentialId: String,
        val authenticatorData: ByteArray,
        val signature: ByteArray,
        val clientDataJson: ByteArray,
        val userHandle: ByteArray,
    )

    fun clientDataJson(type: String, challenge: String, origin: String, androidPackageName: String? = null): ByteArray {
        val json = buildString {
            append("""{"type":${json(type)},"challenge":${json(challenge)},"origin":${json(origin)}""")
            if (androidPackageName != null) append(""","androidPackageName":${json(androidPackageName)}""")
            append("}")
        }
        return json.toByteArray(Charsets.UTF_8)
    }

    fun sha256(data: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(data)

    fun makeCredential(
        rpId: String,
        userHandle: ByteArray,
        userVerified: Boolean,
        clientDataHash: ByteArray,
        credentialId: ByteArray = randomUuid(),
    ): Created {
        val generator = KeyPairGenerator.getInstance("EC")
        generator.initialize(ECGenParameterSpec("secp256r1"))
        val pair = generator.generateKeyPair()
        val authData = authenticatorData(
            rpId = rpId,
            userPresent = true,
            userVerified = userVerified,
            counter = 0,
            credentialId = credentialId,
            publicKey = pair.public as ECPublicKey,
        )
        val attestation = coseMap(
            listOf(
                Cbor.tstr("fmt") to Cbor.tstr("none"),
                Cbor.tstr("attStmt") to byteArrayOf(0xa0.toByte()),
                Cbor.tstr("authData") to Cbor.bstr(authData),
            ),
        )
        return Created(
            credentialId = uuidString(credentialId),
            privateKeyPkcs8 = pair.private.encoded,
            publicKeySpki = pair.public.encoded,
            authenticatorData = authData,
            attestationObject = attestation,
            clientDataJson = ByteArray(0),
            signatureCounter = 0,
        ).also {
            // The attestation signature is inside authenticatorData's credential public key;
            // the RP verifies that key later. Touch clientDataHash so a caller cannot omit it.
            require(clientDataHash.size == 32)
        }
    }

    fun getAssertion(
        rpId: String,
        credentialId: ByteArray,
        privateKeyPkcs8: ByteArray,
        userHandle: ByteArray,
        userVerified: Boolean,
        clientDataHash: ByteArray,
        counter: Int = 0,
    ): Asserted {
        val authData = authenticatorData(
            rpId = rpId,
            userPresent = true,
            userVerified = userVerified,
            counter = counter,
            credentialId = null,
            publicKey = null,
        )
        val signature = sign(privateKeyPkcs8, authData + clientDataHash)
        return Asserted(uuidString(credentialId), authData, signature, ByteArray(0), userHandle)
    }

    fun verifyAssertion(publicKeySpki: ByteArray, authenticatorData: ByteArray, clientDataHash: ByteArray, signature: ByteArray): Boolean {
        val verifier = Signature.getInstance("SHA256withECDSA")
        val key = KeyFactory.getInstance("EC").generatePublic(java.security.spec.X509EncodedKeySpec(publicKeySpki))
        verifier.initVerify(key)
        verifier.update(authenticatorData + clientDataHash)
        return verifier.verify(signature)
    }

    fun authenticatorData(
        rpId: String,
        userPresent: Boolean,
        userVerified: Boolean,
        counter: Int,
        credentialId: ByteArray?,
        publicKey: ECPublicKey?,
    ): ByteArray {
        var flags = 0
        if (userPresent) flags = flags or 0x01
        if (userVerified) flags = flags or 0x04
        flags = flags or 0x08 // backup eligibility
        flags = flags or 0x10 // backup state: synced passkey
        val out = ArrayList<Byte>()
        sha256(rpId.toByteArray(Charsets.UTF_8)).forEach { out += it }
        out += flags.toByte()
        out += ((counter ushr 24) and 0xff).toByte()
        out += ((counter ushr 16) and 0xff).toByte()
        out += ((counter ushr 8) and 0xff).toByte()
        out += (counter and 0xff).toByte()
        if (credentialId != null && publicKey != null) {
            out[32] = (out[32].toInt() or 0x40).toByte()
            AAGUID.forEach { out += it }
            out += ((credentialId.size ushr 8) and 0xff).toByte()
            out += (credentialId.size and 0xff).toByte()
            credentialId.forEach { out += it }
            coseEs256(publicKey).forEach { out += it }
        }
        return out.toByteArray()
    }

    /** Uncompressed P-256 COSE_Key, the 77-byte form authenticators put in authData. */
    fun coseEs256(publicKey: ECPublicKey): ByteArray {
        val point = publicKey.w
        val x = unsignedCoordinate(point.affineX.toByteArray())
        val y = unsignedCoordinate(point.affineY.toByteArray())
        val out = ByteArray(77)
        byteArrayOf(0xa5.toByte(), 0x01, 0x02, 0x03, 0x26, 0x20, 0x01, 0x21, 0x58, 0x20).copyInto(out)
        x.copyInto(out, 10)
        byteArrayOf(0x22, 0x58, 0x20).copyInto(out, 42)
        y.copyInto(out, 45)
        return out
    }

    fun sign(privateKeyPkcs8: ByteArray, message: ByteArray): ByteArray {
        val key = KeyFactory.getInstance("EC").generatePrivate(PKCS8EncodedKeySpec(privateKeyPkcs8))
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(key)
        signer.update(message)
        return signer.sign()
    }

    fun base64Url(data: ByteArray): String =
        Base64.getUrlEncoder().withoutPadding().encodeToString(data)

    fun base64UrlDecode(text: String): ByteArray = Base64.getUrlDecoder().decode(text)

    fun uuidString(raw: ByteArray): String {
        require(raw.size == 16)
        val hex = raw.joinToString("") { "%02x".format(it) }
        return "${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}"
    }

    fun randomUuid(): ByteArray = ByteArray(16).also { java.security.SecureRandom().nextBytes(it) }

    private fun unsignedCoordinate(twosComplement: ByteArray): ByteArray {
        val stripped = if (twosComplement.size > 32 && twosComplement[0] == 0.toByte()) {
            twosComplement.copyOfRange(twosComplement.size - 32, twosComplement.size)
        } else {
            twosComplement
        }
        val out = ByteArray(32)
        stripped.copyInto(out, destinationOffset = 32 - stripped.size)
        return out
    }

    private fun coseMap(pairs: List<Pair<ByteArray, ByteArray>>): ByteArray = Cbor.map(pairs)

    private fun json(value: String): String =
        "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
}
