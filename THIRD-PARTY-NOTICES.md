# Third-party notices

Komboe © 2026 GODESK IO LLC. Komboe is based on Vaultwarden (© Vaultwarden contributors, AGPL-3.0) and
Bitwarden clients (© Bitwarden Inc., GPL-3.0). Komboe is not affiliated with or endorsed by Bitwarden Inc. or
the Vaultwarden project. This program comes with ABSOLUTELY NO WARRANTY. It is free software: you may
redistribute and modify it under the GNU GPL v3 / AGPL v3.

Corresponding source: https://github.com/GoDeskio/Komboe (each build links to the exact tag it was built from).

This file ships with every Komboe package (web vault, browser extension, desktop app) next to `LICENSE.txt`
(GNU AGPL v3, the license of this repository and the server) and `LICENSE_GPL.txt` (GNU GPL v3, the license of the
Bitwarden-derived clients). All upstream copyright and license headers in source files are kept unchanged.

## Components

| Component | Upstream | Copyright | License |
|---|---|---|---|
| Server (`server/upstream`) | https://github.com/dani-garcia/vaultwarden | © Vaultwarden contributors | AGPL-3.0-only |
| Web vault, browser extension, desktop, CLI (`clients/upstream`) | https://github.com/bitwarden/clients | © Bitwarden Inc. | GPL-3.0 (code outside `bitwarden_license/`) |
| `@bitwarden/sdk-internal` (WASM SDK used by the clients) | https://github.com/bitwarden/sdk-internal | © Bitwarden Inc. | GPL-3.0 |
| Android app (`mobile/`, pin `mobile/ANDROID_UPSTREAM_PIN`: v2026.10.1-bwpm) | https://github.com/bitwarden/android | © Bitwarden Inc. | GPL-3.0 |
| Email aliases (`aliases/upstream`) | https://github.com/simple-login/app | © SimpleLogin | AGPL-3.0 |

Code under Bitwarden's `bitwarden_license/` directory (Bitwarden License Agreement) is not included in this
repository. See `docs/LICENSE-AUDIT.md` for the current audit, including one known gap in the desktop package.

Each package also bundles many npm / Cargo dependencies under their own permissive or copyleft licenses
(MIT, Apache-2.0, BSD, ISC and others). Their license texts are in the respective packages, e.g.
`node_modules/*/LICENSE` in the desktop app and `cargo about`-style listings from `server/upstream/Cargo.lock`.

"Bitwarden" and "Vaultwarden" are trademarks of their respective owners and are used here only to describe origin.
