import com.android.build.api.dsl.LibraryExtension
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.android.library)
}

configure<LibraryExtension> {
    namespace = "io.komboe.vaultcrypto"
    compileSdk {
        version = release(libs.versions.compileSdk.get().toInt())
    }
    defaultConfig {
        minSdk {
            version = release(libs.versions.minSdk.get().toInt())
        }
    }
    compileOptions {
        sourceCompatibility(libs.versions.jvmTarget.get())
        targetCompatibility(libs.versions.jvmTarget.get())
    }
    sourceSets.getByName("main").apply {
        kotlin.srcDir(file("src/main/kotlin"))
        kotlin.srcDir(file("../vault-crypto/src/main/kotlin"))
        resources.srcDir(file("../vault-crypto/src/main/resources"))
    }
}

dependencies {
    implementation("org.bouncycastle:bcprov-jdk18on:1.79")
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.fromTarget(libs.versions.jvmTarget.get()))
    }
}
