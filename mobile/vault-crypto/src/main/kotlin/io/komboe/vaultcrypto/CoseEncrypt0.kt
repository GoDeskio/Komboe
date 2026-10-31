// COSE_Encrypt0 (RFC 9052) for vault EncString type 7.
// Untagged CBOR array of three items, which is the layout Komboe stores.
package io.komboe.vaultcrypto

internal object CoseEncrypt0 {
    data class Envelope(
        val algorithm: Int,
        val nonce: ByteArray,
        val ciphertext: ByteArray,
        val protectedHeader: ByteArray,
    )

    fun encode(algorithm: Int, nonce: ByteArray, ciphertext: ByteArray, keyId: ByteArray? = null): ByteArray {
        val pairs = mutableListOf(Cbor.int(1) to Cbor.int(algorithm.toLong()))
        if (keyId != null) pairs += Cbor.int(4) to Cbor.bstr(keyId)
        val protected = Cbor.bstr(Cbor.map(pairs))
        val unprotected = Cbor.map(listOf(Cbor.int(5) to Cbor.bstr(nonce)))
        return byteArrayOf(0x83.toByte()) + protected + unprotected + Cbor.bstr(ciphertext)
    }

    /** RFC 9052 Enc_structure. The AEAD uses this as additional data. */
    fun encStructure(protectedHeader: ByteArray): ByteArray =
        byteArrayOf(0x83.toByte()) + Cbor.tstr("Encrypt0") + Cbor.bstr(protectedHeader) + Cbor.bstr(ByteArray(0))

    fun decode(bytes: ByteArray): Envelope {
        val reader = Cbor.Reader(bytes)
        require(reader.u8() == 0x83) { "COSE_Encrypt0 must be a 3-element array" }
        val protected = reader.bstr()
        val header = Cbor.Reader(protected).intKeyMap()
        val algorithm = (header[1L] as? Long)?.toInt() ?: error("protected header is missing alg")
        val unprotected = reader.intKeyMap()
        val nonce = unprotected[5L] as? ByteArray ?: error("unprotected header is missing the nonce")
        val ciphertext = reader.bstr()
        require(reader.done())
        return Envelope(algorithm, nonce, ciphertext, protected)
    }
}
