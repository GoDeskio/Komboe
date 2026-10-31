#!/usr/bin/env bash
# Build the Komboe Electron desktop app for Linux (AppImage + deb) on a box without root/apt.
# Native deps (pkg-config, dbus, libsecret, glib) come from a micromamba env.
set -euo pipefail
MAMBA=${MAMBA:-/workspace/tools/mamba/bin/micromamba}; ENV=${MAMBA_ENV:-/workspace/tools/mamba/env}
SRC=${SRC:-$(cd "$(dirname "$0")/../clients/upstream" && pwd)}   # rebranded clients tree in this repo
[ -x "$ENV/bin/pkg-config" ] || "$MAMBA" create -y -p "$ENV" -c conda-forge pkg-config dbus libsecret glib
export PKG_CONFIG_PATH=$ENV/lib/pkgconfig:$ENV/share/pkgconfig LIBRARY_PATH=$ENV/lib LD_LIBRARY_PATH=$ENV/lib
export CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-/workspace/up/dn-target}
cd "$SRC/apps/desktop/desktop_native"; mkdir -p "$CARGO_TARGET_DIR"; [ -e target ] || ln -s "$CARGO_TARGET_DIR" target
export CARGO_TARGET_DIR=$(readlink -f target)   # build.js copies from ./target
node build.js --release
cd ..; npm run build
npx electron-builder --linux AppImage deb --x64 -p never
ls -l dist/*.AppImage dist/*.deb
