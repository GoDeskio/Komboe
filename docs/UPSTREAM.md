# Upstream sources

| Upstream | Repo | Pinned tag | License | Prefix |
|---|---|---|---|---|
| Bitwarden clients | bitwarden/clients | `web-v2026.10.0` (verify latest before import) | GPL-3.0; `bitwarden_license/` excluded | `clients/upstream` |
| Vaultwarden | dani-garcia/vaultwarden | `1.34.3` (verify latest before import) | AGPL-3.0 | `server/upstream` |
| SimpleLogin | simple-login/app | TBD | AGPL-3.0 | `aliases/upstream` |

Import (not yet run, to keep this PR reviewable):
```
BW_TAG=<tag> VW_TAG=<tag> scripts/import-upstream.sh all
```
License notes: GPL-3.0 client code is compatible for combination in an AGPL-3.0 project (GPLv3 §13). Never import `bitwarden_license/`. Keep upstream copyright headers. Server must offer source to network users (AGPL §13).
