# fdroid runtime classpath

Generated from the rebranded Bitwarden Android tree (`mobile/ANDROID_UPSTREAM_PIN` = `v2026.10.1-bwpm`) after `mobile/android_rebrand.py` swaps `implementation(libs.bitwarden.sdk)` for `implementation(project(":komboe-sdk"))`.

Command:

```sh
./gradlew :app:dependencies --configuration fdroidDebugRuntimeClasspath
```

Result: **426** external artifacts. `com.bitwarden:sdk-android` does not appear. No `com.bitwarden` Maven coordinate, Firebase, or Play services artifact is on this classpath.

The vault-crypto edge is:

```
+--- project :komboe-sdk
|    \--- org.bouncycastle:bcprov-jdk18on:1.79
```

`bcprov-jdk18on` 1.79 is MIT (Bouncy Castle), which the GPL permits in a combined work distributed under the GPL. The other artifacts are the upstream fdroid set: AndroidX, Kotlin, OkHttp, Retrofit, Dagger/Hilt, Glide, Tink, ZXing, Timber, and Guava, under Apache-2.0 or other permissive licenses. They are not the Bitwarden SDK.

Debug APK: `io.komboe.android-fdroid.apk`, package `io.komboe.android`, label Komboe.

sha256: `3c0b5d12b8d674e74b4d9d4c7f16514e5a0d88ba6e64648f73d70d2fc2ea646d`

The APK contains no `libbitwarden_uniffi` (or other Bitwarden SDK native library).
