// Generated from GPL Android call sites by mobile/gen_sdk_surface.py.
// GPL-3.0-only. These types stand in for com.bitwarden:sdk-android.
package com.bitwarden.generators

sealed class ForwarderServiceType {
    data class AddyIo(
        val apiToken: Any? = null,
        val domain: Any? = null,
        val baseUrl: Any? = null
    ) : ForwarderServiceType()
    data class DuckDuckGo(
        val token: Any? = null
    ) : ForwarderServiceType()
    data class Fastmail(
        val apiToken: Any? = null
    ) : ForwarderServiceType()
    data class Firefox(
        val apiToken: Any? = null
    ) : ForwarderServiceType()
    data class ForwardEmail(
        val apiToken: String = "",
        val domain: String = "",
    ) : ForwarderServiceType()
    data class SimpleLogin(
        val apiKey: Any? = null,
        val baseUrl: Any? = null
    ) : ForwarderServiceType()
}

sealed class UsernameGeneratorRequest {
    data class Catchall(
        val type: AppendType,
        val domain: Any? = null
    ) : UsernameGeneratorRequest()
    data class Forwarded(
        val service: ForwarderServiceType,
        val website: Any? = null
    ) : UsernameGeneratorRequest()
    data class Subaddress(
        val type: AppendType,
        val email: Any? = null
    ) : UsernameGeneratorRequest()
    data class Word(
        val capitalize: Any? = null,
        val includeNumber: Any? = null
    ) : UsernameGeneratorRequest()
}

data class PassphraseGeneratorRequest(
    val numWords: UByte,
    val wordSeparator: Any? = null,
    val capitalize: Any? = null,
    val includeNumber: Any? = null
)

data class PasswordGeneratorRequest(
    val lowercase: Boolean,
    val uppercase: Boolean,
    val numbers: Boolean,
    val special: Boolean,
    val length: UByte,
    val avoidAmbiguous: Boolean,
    val minLowercase: Any? = null,
    val minUppercase: Any? = null,
    val minNumber: UByte? = null,
    val minSpecial: UByte? = null
)

enum class AppendType { Random, Website }
