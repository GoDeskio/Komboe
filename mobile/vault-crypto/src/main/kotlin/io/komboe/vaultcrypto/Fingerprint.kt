// Account fingerprint phrase. SHA-256 of the public key, HKDF-Expand with the
// material (email or user id) as info, then the public EFF long wordlist.
package io.komboe.vaultcrypto

import java.math.BigInteger
import java.security.MessageDigest
import kotlin.math.ceil
import kotlin.math.ln

internal object Fingerprint {
    private val words: List<String> by lazy {
        val stream = Fingerprint::class.java.classLoader.getResourceAsStream("eff_long_wordlist.txt")
            ?: error("EFF long wordlist is missing from the jar")
        stream.bufferedReader().readLines().filter { it.isNotBlank() }
    }

    fun phrase(material: String, publicKey: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(publicKey)
        val expanded = hkdfExpand(digest, material.toByteArray(Charsets.UTF_8), 32)
        return hashPhrase(expanded).joinToString("-")
    }

    private fun hashPhrase(hash: ByteArray, minimumEntropy: Int = 64): List<String> {
        val list = words
        val entropyPerWord = ln(list.size.toDouble()) / ln(2.0)
        var remaining = ceil(minimumEntropy / entropyPerWord).toInt()
        var number = BigInteger(1, hash)
        val modulus = BigInteger.valueOf(list.size.toLong())
        val phrase = ArrayList<String>(remaining)
        while (remaining-- > 0) {
            val div = number.divideAndRemainder(modulus)
            phrase.add(list[div[1].toInt()])
            number = div[0]
        }
        return phrase
    }
}
