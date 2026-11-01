// Minimal COSE_Encrypt0 (RFC 9052) for vault EncString type 7.
// Untagged CBOR array of three items, which is the layout Komboe stores.
package io.komboe.vaultcrypto

internal object CoseEncrypt0 {
    data class Envelope(val algorithm: Int, val nonce: ByteArray, val ciphertext: ByteArray)

    fun encode(algorithm: Int, nonce: ByteArray, ciphertext: ByteArray): ByteArray {
        val protectedMap = cborMap(1 to cborInt(algorithm))
        val protected = cborBstr(protectedMap)
        val unprotected = cborMap(5 to cborBstr(nonce))
        return byteArrayOf(0x83.toByte()) + protected + unprotected + cborBstr(ciphertext)
    }

    fun decode(bytes: ByteArray): Envelope {
        val reader = Reader(bytes)
        require(reader.u8() == 0x83) { "COSE_Encrypt0 must be a 3-element array" }
        val protected = reader.bstr()
        val header = Reader(protected)
        require(header.u8() == 0xa1) { "protected header must be a one-entry map" }
        require(header.unsigned() == 1) { "protected header is missing alg" }
        val algorithm = header.signed()
        require(reader.u8() == 0xa1)
        require(reader.unsigned() == 5) { "unprotected header is missing the nonce" }
        val nonce = reader.bstr()
        val ciphertext = reader.bstr()
        require(reader.done())
        return Envelope(algorithm, nonce, ciphertext)
    }

    private fun cborInt(value: Int): ByteArray {
        if (value >= 0) return cborUnsigned(0, value)
        return cborUnsigned(1, -1 - value)
    }

    private fun cborUnsigned(major: Int, value: Int): ByteArray {
        val head = major shl 5
        return when {
            value < 24 -> byteArrayOf((head or value).toByte())
            value < 256 -> byteArrayOf((head or 24).toByte(), value.toByte())
            value < 65536 -> byteArrayOf(
                (head or 25).toByte(),
                (value shr 8).toByte(),
                value.toByte(),
            )
            else -> byteArrayOf(
                (head or 26).toByte(),
                (value ushr 24).toByte(),
                (value ushr 16).toByte(),
                (value ushr 8).toByte(),
                value.toByte(),
            )
        }
    }

    private fun cborBstr(data: ByteArray): ByteArray = cborUnsigned(2, data.size) + data

    private fun cborMap(vararg pairs: Pair<Int, ByteArray>): ByteArray {
        require(pairs.size < 24)
        var out = byteArrayOf((0xa0 or pairs.size).toByte())
        for ((key, value) in pairs) out += cborInt(key) + value
        return out
    }

    private class Reader(private val bytes: ByteArray) {
        private var i = 0
        fun u8(): Int = bytes[i++].toInt() and 0xff
        fun done(): Boolean = i == bytes.size

        fun unsigned(): Int {
            val initial = u8()
            require(initial shr 5 == 0) { "expected unsigned" }
            return argument(initial and 0x1f)
        }

        fun signed(): Int {
            val initial = u8()
            val major = initial shr 5
            val argument = argument(initial and 0x1f)
            return if (major == 0) argument else -1 - argument
        }

        fun bstr(): ByteArray {
            val initial = u8()
            require(initial shr 5 == 2) { "expected bstr" }
            val len = argument(initial and 0x1f)
            val out = bytes.copyOfRange(i, i + len)
            i += len
            return out
        }

        private fun argument(ai: Int): Int = when (ai) {
            in 0..23 -> ai
            24 -> u8()
            25 -> (u8() shl 8) or u8()
            26 -> (u8() shl 24) or (u8() shl 16) or (u8() shl 8) or u8()
            else -> error("unsupported CBOR additional info $ai")
        }
    }
}
