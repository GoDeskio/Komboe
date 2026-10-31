#!/usr/bin/env bash
# Build a rebranded Komboe Android debug APK from the pinned upstream bitwarden/android (GPL-3.0).
# Portable toolchain, no apt: TOOLS=/workspace/tools with jdk-21*/ and android-sdk/cmdline-tools/latest.
set -euo pipefail
PIN=$(cat "$(dirname "$0")/ANDROID_UPSTREAM_PIN")
SRC=${SRC:-/workspace/up/bw-android}; TOOLS=${TOOLS:-/workspace/tools}
[ -d "$SRC" ] || git clone -q --depth 1 -b "$PIN" https://github.com/bitwarden/android.git "$SRC"
export JAVA_HOME=$(ls -d "$TOOLS"/jdk-21*) ANDROID_HOME=$TOOLS/android-sdk; export PATH=$JAVA_HOME/bin:$PATH
yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses >/dev/null || true
python3 "$(dirname "$0")/android_rebrand.py" "$SRC"
# GPL-3.0: the debug APK must contain the license text and the source offer.
for f in LICENSE.txt komboe-source.txt THIRD-PARTY-NOTICES.md; do
  [ -f "$SRC/app/src/main/assets/$f" ] || { echo "missing GPL asset $f"; exit 1; }
done
grep -q "GNU GENERAL PUBLIC LICENSE" "$SRC/app/src/main/assets/LICENSE.txt"
grep -q "v2026.10.1-bwpm" "$SRC/app/src/main/assets/komboe-source.txt"
cd "$SRC" && ./gradlew --no-daemon -Dorg.gradle.jvmargs=-Xmx3g :app:assembleFdroidDebug
ls app/build/outputs/apk/fdroid/debug/*.apk
