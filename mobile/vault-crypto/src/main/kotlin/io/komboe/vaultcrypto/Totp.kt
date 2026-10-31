// RFC 6238 TOTP, plus the Steam Guard alphabet used by vault authenticators.
package io.komboe.vaultcrypto

import java.nio.ByteBuffer
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

internal object Totp {
    private const val STEAM = "23456789BCDFGHJKMNPQRTVWXY"

    fun generate(secretOrUri: String, timeSeconds: Long): TotpCode {
        val parsed = parse(secretOrUri.trim())
        val code = if (parsed.steam) {
            steam(parsed.secret, timeSeconds, parsed.period)
        } else {
            hotp(parsed.secret, timeSeconds / parsed.period, parsed.digits, parsed.algorithm)
        }
        return TotpCode(code, parsed.period)
    }

    fun hotp(secret: ByteArray, counter: Long, digits: Int, algorithm: String): String {
        val mac = Mac.getInstance(macName(algorithm))
        mac.init(SecretKeySpec(secret, macName(algorithm)))
        val counterBytes = ByteBuffer.allocate(8).putLong(counter).array()
        val hash = mac.doFinal(counterBytes)
        val offset = hash.last().toInt() and 0x0f
        val binary = ((hash[offset].toInt() and 0x7f) shl 24) or
            ((hash[offset + 1].toInt() and 0xff) shl 16) or
            ((hash[offset + 2].toInt() and 0xff) shl 8) or
            (hash[offset + 3].toInt() and 0xff)
        val mod = pow10(digits)
        return (binary % mod).toString().padStart(digits, '0')
    }

    private fun steam(secret: ByteArray, timeSeconds: Long, period: Int): String {
        val mac = Mac.getInstance("HmacSHA1")
        mac.init(SecretKeySpec(secret, "HmacSHA1"))
        val hash = mac.doFinal(ByteBuffer.allocate(8).putLong(timeSeconds / period).array())
        val offset = hash.last().toInt() and 0x0f
        var full = ((hash[offset].toInt() and 0x7f) shl 24) or
            ((hash[offset + 1].toInt() and 0xff) shl 16) or
            ((hash[offset + 2].toInt() and 0xff) shl 8) or
            (hash[offset + 3].toInt() and 0xff)
        val out = CharArray(5)
        for (i in 0 until 5) {
            out[i] = STEAM[full % STEAM.length]
            full /= STEAM.length
        }
        return String(out)
    }

    private data class Params(val secret: ByteArray, val period: Int, val digits: Int, val algorithm: String, val steam: Boolean)

    private fun parse(value: String): Params {
        if (value.startsWith("otpauth://", ignoreCase = true) || value.startsWith("steam://", ignoreCase = true)) {
            val query = value.substringAfter('?', "")
            val parts = query.split('&').mapNotNull {
                val key = it.substringBefore('=').lowercase()
                val raw = it.substringAfter('=', "")
                if (raw.isEmpty()) null else key to java.net.URLDecoder.decode(raw, Charsets.UTF_8)
            }.toMap()
            val secret = decodeBase32(parts["secret"] ?: error("otpauth URI has no secret"))
            val algorithm = (parts["algorithm"] ?: "SHA1").uppercase()
            val steam = value.startsWith("steam://", ignoreCase = true) || algorithm == "STEAM" ||
                (parts["issuer"] ?: "").equals("Steam", ignoreCase = true)
            return Params(
                secret = secret,
                period = parts["period"]?.toIntOrNull() ?: 30,
                digits = parts["digits"]?.toIntOrNull() ?: if (steam) 5 else 6,
                algorithm = if (algorithm == "STEAM") "SHA1" else algorithm,
                steam = steam,
            )
        }
        return Params(decodeBase32(value), 30, 6, "SHA1", false)
    }

    private fun macName(algorithm: String): String = when (algorithm.uppercase()) {
        "SHA1", "SHA-1" -> "HmacSHA1"
        "SHA256", "SHA-256" -> "HmacSHA256"
        "SHA512", "SHA-512" -> "HmacSHA512"
        else -> error("unsupported TOTP algorithm $algorithm")
    }

    private fun pow10(digits: Int): Int {
        var n = 1
        repeat(digits) { n *= 10 }
        return n
    }

    internal fun decodeBase32(value: String): ByteArray {
        val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        val cleaned = value.uppercase().filter { it != ' ' && it != '=' && it != '-' }
        var buffer = 0
        var bits = 0
        val out = ArrayList<Byte>(cleaned.length * 5 / 8)
        for (char in cleaned) {
            val index = alphabet.indexOf(char)
            require(index >= 0) { "invalid base32" }
            buffer = (buffer shl 5) or index
            bits += 5
            if (bits >= 8) {
                bits -= 8
                out.add((buffer shr bits).toByte())
                buffer = buffer and ((1 shl bits) - 1)
            }
        }
        return out.toByteArray()
    }
}
