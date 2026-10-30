<p align="center"><img alt="Komboe" src="../branding/wordmark/komboe-wordmark-light.svg" width="300"></p>

# Upstream sources (verified 2026-10-29 via GitHub API + git ls-remote)

| Upstream | Repo | Pinned tag | Commit SHA | Released (MST) | License | Prefix |
|---|---|---|---|---|---|---|
| Bitwarden web vault | bitwarden/clients | `web-v2026.10.1` | `91214c3b978edb5496a32a946451960fe7d44531` | 2026-10-27 17:52 | GPL-3.0 (excl. `bitwarden_license/`) | `clients/upstream` |
| Bitwarden browser ext | bitwarden/clients | `browser-v2026.10.1` | same commit | 2026-10-29 05:54 | GPL-3.0 | `clients/upstream` |
| Bitwarden desktop | bitwarden/clients | `desktop-v2026.10.2` | same commit | 2026-10-29 06:53 | GPL-3.0 | `clients/upstream` |
| Bitwarden CLI | bitwarden/clients | `cli-v2026.10.1` | same commit | 2026-10-29 05:21 | GPL-3.0 | `clients/upstream` |
| Vaultwarden server | dani-garcia/vaultwarden | `1.37.4` | `7c188967e7a467b19b2757bc3326f9cf3ccae327` | 2026-10-05 16:40 | AGPL-3.0 | `server/upstream` |
| Vaultwarden web-vault build | dani-garcia/bw_web_builds | `v2026.7.0` | `fac81a4f35ede45965b220daa3255994abbf0eb1` | 2026-08-05 12:27 | GPL-3.0 (patches on BW web) | reference only |
| SimpleLogin | simple-login/app | `v4.83.2` | `dc4130adc75e975cce74db4c1acbd9417105f60d` | 2026-10-26 04:14 | AGPL-3.0 | `aliases/upstream` |

All four Bitwarden client tags point to one monorepo commit, so a single subtree import covers web, browser, desktop and CLI.
Mobile apps are not in bitwarden/clients (separate `bitwarden/android` and `bitwarden/ios` repos), so they still need pins.
bw_web_builds lags (web v2026.7.0 vs clients web-v2026.10.1). Komboe builds the web vault from `clients/` and uses bw_web_builds only as a reference for Vaultwarden-compatibility patches.

Import (not yet run, to keep this PR reviewable):
```
scripts/import-upstream.sh all      # verifies each tag's SHA before importing
```
License notes: combining GPL-3.0 client code into an AGPL-3.0 project is allowed (GPLv3 §13). Never import `bitwarden_license/`. Keep upstream copyright headers. The server must offer its source to network users (AGPL §13).
