// Small CBOR (RFC 8949) reader and writer for COSE envelopes.
// Integer map keys are encoded in the order the caller supplies.
package io.komboe.vaultcrypto

internal object Cbor {
    fun unsigned(major: Int, value: Long): ByteArray {
        val head = major shl 5
        return when {
            value < 24 -> byteArrayOf((head or value.toInt()).toByte())
            value < 256 -> byteArrayOf((head or 24).toByte(), value.toByte())
            value < 65536 -> byteArrayOf((head or 25).toByte(), (value ushr 8).toByte(), value.toByte())
            value < 4294967296L -> byteArrayOf(
                (head or 26).toByte(),
                (value ushr 24).toByte(),
                (value ushr 16).toByte(),
                (value ushr 8).toByte(),
                value.toByte(),
            )
            else -> error("CBOR integer too large")
        }
    }

    fun int(value: Long): ByteArray =
        if (value >= 0) unsigned(0, value) else unsigned(1, -1 - value)

    fun bstr(data: ByteArray): ByteArray = unsigned(2, data.size.toLong()) + data

    fun tstr(text: String): ByteArray = unsigned(3, text.length.toLong()) + text.toByteArray(Charsets.UTF_8)

    fun map(pairs: List<Pair<ByteArray, ByteArray>>): ByteArray {
        var out = unsigned(5, pairs.size.toLong())
        for ((key, value) in pairs) out += key + value
        return out
    }

    /** RFC 9052 Sig_structure, context "Signature1", empty external AAD. */
    fun sigStructure(protected: ByteArray, payload: ByteArray): ByteArray =
        byteArrayOf(0x84.toByte()) + tstr("Signature1") + bstr(protected) + bstr(ByteArray(0)) + bstr(payload)

    class Reader(private val bytes: ByteArray) {
        private var i = 0
        fun done(): Boolean = i == bytes.size
        fun u8(): Int = bytes[i++].toInt() and 0xff

        fun bstr(): ByteArray {
            val (major, len) = head()
            require(major == 2) { "expected bstr" }
            val out = bytes.copyOfRange(i, i + len)
            i += len
            return out
        }

        fun long(): Long {
            val (major, arg) = headLong()
            return if (major == 0) arg else -1 - arg
        }

        /** Map of integer labels to a byte string or an integer. Other values are skipped. */
        fun optionalBstr(): ByteArray? {
            if ((bytes[i].toInt() and 0xff) == 0xf6) {
                i++
                return null
            }
            return bstr()
        }

        fun textKeyMap(): Map<String, Any> {
            val (major, count) = head()
            require(major == 5) { "expected map" }
            val out = linkedMapOf<String, Any>()
            repeat(count) {
                val key = text()
                val value = valueOrSkip() ?: error("unsupported CBOR map value")
                out[key] = value
            }
            return out
        }

        fun text(): String {
            val (major, len) = head()
            require(major == 3) { "expected text" }
            val out = bytes.copyOfRange(i, i + len).toString(Charsets.UTF_8)
            i += len
            return out
        }

        fun intKeyMap(): Map<Long, Any> {
            val (major, count) = head()
            require(major == 5) { "expected map" }
            val out = linkedMapOf<Long, Any>()
            repeat(count) {
                val key = long()
                val mark = i
                val value = valueOrSkip()
                if (value != null) out[key] = value
                if (i == mark) error("CBOR value was not consumed")
            }
            return out
        }

        private fun valueOrSkip(): Any? {
            val peek = bytes[i].toInt() and 0xff
            val major = peek shr 5
            return when (major) {
                0, 1 -> long()
                2 -> bstr()
                3 -> skipSimple(3)
                4 -> skipContainer(4)
                5 -> skipContainer(5)
                6 -> { head(); valueOrSkip(); null }
                7 -> { head(); null }
                else -> error("bad major")
            }
        }

        private fun skipSimple(expected: Int): Any? {
            val (major, len) = head()
            require(major == expected)
            i += len
            return null
        }

        private fun skipContainer(expected: Int): Any? {
            val (major, count) = head()
            require(major == expected)
            val items = if (expected == 5) count * 2 else count
            repeat(items) { valueOrSkip() }
            return null
        }

        private fun head(): Pair<Int, Int> {
            val (major, arg) = headLong()
            return major to arg.toInt()
        }

        private fun headLong(): Pair<Int, Long> {
            val initial = u8()
            val major = initial shr 5
            val ai = initial and 0x1f
            val arg = when (ai) {
                in 0..23 -> ai.toLong()
                24 -> u8().toLong()
                25 -> ((u8().toLong() shl 8) or u8().toLong())
                26 -> ((u8().toLong() shl 24) or (u8().toLong() shl 16) or (u8().toLong() shl 8) or u8().toLong())
                else -> error("unsupported CBOR additional info $ai")
            }
            return major to arg
        }
    }
}
