# Third-party notices

Komboe © 2026. Komboe is based on Vaultwarden (© Vaultwarden contributors, AGPL-3.0) and
Bitwarden clients (© Bitwarden Inc., GPL-3.0). Komboe is not affiliated with or endorsed by Bitwarden Inc. or
the Vaultwarden project. This program comes with ABSOLUTELY NO WARRANTY. It is free software: you may
redistribute and modify it under the GNU GPL v3 / AGPL v3.

Corresponding source: https://github.com/GoDeskio/Komboe (each build links to the exact tag it was built from).

The Android debug APK also carries this file, the GPL-3.0 text (`LICENSE.txt`), and `komboe-source.txt` in its assets. Corresponding source for the Android app is the Bitwarden Android tag above plus the Komboe rebrand in `mobile/` of this repository. See `mobile/ANDROID-SOURCE.txt`.

This file ships with every Komboe package (web vault, browser extension, desktop app, Android APK) next to `LICENSE.txt`
(GNU AGPL v3, the license of this repository and the server) and `LICENSE_GPL.txt` (GNU GPL v3, the license of the
Bitwarden-derived clients). All upstream copyright and license headers in source files are kept unchanged.

## Components

| Component | Upstream | Copyright | License |
|---|---|---|---|
| Server (`server/upstream`) | https://github.com/dani-garcia/vaultwarden | © Vaultwarden contributors | AGPL-3.0-only |
| Web vault, browser extension, desktop, CLI (`clients/upstream`) | https://github.com/bitwarden/clients | © Bitwarden Inc. | GPL-3.0 (code outside `bitwarden_license/`) |
| `@bitwarden/sdk-internal` (WASM SDK used by the clients) | https://github.com/bitwarden/sdk-internal | © Bitwarden Inc. | GPL-3.0 |
| Email aliases (`aliases/upstream`) | https://github.com/simple-login/app tag `v4.83.2` | © SimpleLogin | AGPL-3.0-only |
| Android app (fdroid flavor) | https://github.com/bitwarden/android tag `v2026.10.1-bwpm`, commit `1470154cf3d3d0511cdbe5bfc6493971b6478edf` | © Bitwarden Inc. and contributors | GPL-3.0-only |
| Vault crypto (`mobile/vault-crypto`, `mobile/komboe-sdk`) | Written for Komboe from the public Bitwarden protocol | © 2026 GODESK IO LLC | GPL-3.0-only |
| Bouncy Castle (`org.bouncycastle:bcprov-jdk18on` 1.79) | https://www.bouncycastle.org | © The Legion of the Bouncy Castle | MIT |
| Sora typeface (`branding/fonts/sora`) | https://github.com/sora-xor/sora-font | © 2019 The Sora Project Authors | SIL Open Font License 1.1 |

The Android fdroid build does not link `com.bitwarden:sdk-android` `4.0.0-9318-3b2c8fc3`. That artifact is published under the
Bitwarden Software Development Kit License Agreement, which is not the GPL, and it is not a dependency of the fdroid APK.
Vault encryption (KDF, EncString, account and organization keys, TOTP, Send) is the GPL-3.0-only code in
`mobile/vault-crypto`, called through `mobile/komboe-sdk`. Bouncy Castle is MIT, which is compatible with
the GPL when the combined work is distributed under the GPL. Other AndroidX, Kotlin, and Google libraries
linked by the upstream fdroid flavor stay under their own Apache-2.0 or similar permissive licenses.

Code under Bitwarden's `bitwarden_license/` directory (Bitwarden License Agreement) is not included in this
repository. See `docs/LICENSE-AUDIT.md` for the current audit, including one known gap in the desktop package.

Each package also bundles many npm / Cargo dependencies under their own permissive or copyleft licenses
(MIT, Apache-2.0, BSD, ISC and others). Their license texts are in the respective packages, e.g.
`node_modules/*/LICENSE` in the desktop app and `cargo about`-style listings from `server/upstream/Cargo.lock`.

"Bitwarden" and "Vaultwarden" are trademarks of their respective owners and are used here only to describe origin.
