# License audit: Bitwarden-licensed code and SDK in Komboe builds

Date: 2026-10-30. Scope: `clients/upstream` (web vault, browser extension, desktop, CLI) and the builds we
actually ship/run (`/workspace/run/web-vault`, `/workspace/run/ext`, desktop `app.asar`). Nothing has been removed
by this audit; it reports what is there and whether it can be replaced with GPL code. Pending legal review.

## Summary

| Item | Present in source? | Present in shipped build? | License | Action proposed |
|---|---|---|---|---|
| `bitwarden_license/` directory (bit-web, bit-browser, bit-desktop, bit-common, bit-cli) | **No** (directory absent) | No | Bitwarden License Agreement | None needed; clean leftover config references (below) |
| `@bitwarden/sdk-internal` 0.2.0-main.1126 | Yes (npm dep) | Yes: web vault, extension, desktop (WASM) | GPL-3.0 | Keep; it is the GPL SDK. Corresponding source: bitwarden/sdk-internal at that version |
| `@bitwarden/commercial-sdk-internal` 0.2.0-main.1126 | Yes (npm dep in root `package.json`) | **Desktop only**: `app.asar` and `app.asar.unpacked` contain `node_modules/@bitwarden/commercial-sdk-internal` (both `.wasm` files) | "BITWARDEN SOFTWARE DEVELOPMENT KIT LICENSE AGREEMENT Version 2, 7 October 2025" (proprietary) | **Gap.** Not referenced by any app JS; can be dropped with an electron-builder `files` exclusion (`!node_modules/@bitwarden/commercial-sdk-internal`) and by removing the dependency. Not stripped yet, per instructions |
| Web vault / extension WASM | — | Byte-identical to the OSS `sdk-internal` WASM | GPL-3.0 | OK |

## Leftover `bitwarden_license` references (config only, no code)

These point at paths that do not exist; they compile nothing in, but should be removed for clarity:

- `clients/upstream/tsconfig.json` `include`: `bitwarden_license/bit-desktop`, `bit-web`, `bit-common`, `bit-browser`.
- `clients/upstream/tsconfig.eslint.json` (same paths).
- `apps/web/tailwind.config.js` line 9 (content glob into `bitwarden_license/`).
- `apps/desktop/package.json`: `build:bit:*` and `test:bit` scripts.
- `apps/desktop/project.json`: "commercial" build configurations.
- `apps/cli/package.json`: `build:bit`.
- Comment in `apps/web/src/app/app.module.ts`.
- Shipped web vault chunk (`405.js`) contains only the string `bitwarden_license.json` (file name in the
  self-host license upload UI). No Bitwarden-licensed code.

## Bitwarden-licensed features

The features Bitwarden implements under `bitwarden_license/` (organization SSO config UI, SCIM, Secrets Manager,
provider portal, event-log integrations, access intelligence, etc.) are **not present**. Komboe's equivalents
(LDAP directory, SCIM, OIDC SSO, upcoming SAML SSO) are new code in this repository under GPL-3.0 (clients) /
AGPL-3.0 (server).

## Can it be swapped for GPL code?

- `commercial-sdk-internal`: yes. The OSS `sdk-internal` is already what every client loads; the commercial
  package is only an unused copy in the desktop package. Fix = exclude + remove dependency + rebuild, then re-run
  `tests/features/legal_web.py` and a `grep -c commercial app.asar` = 0 check.
- Config references: yes, delete.

## Licenses bundled per package

`LICENSE.txt` (AGPL-3.0, repo root), `LICENSE_GPL.txt` (GPL-3.0, clients) and `THIRD-PARTY-NOTICES.md` are copied
into the web vault root, the extension root, and the desktop `app.asar` by each client's webpack config, and into
the desktop installer `resources/` via `electron-builder.json` `extraResources`. The CLI is not packaged yet.
Upstream copyright and license headers in source files are untouched.

## In-app notice

Exact approved text, with **View license** (`/blob/<tag>/LICENSE`) and **Source code** (`/tree/<tag>`) links,
`<tag>` = `KOMBOE_SOURCE_REF` env, else `git describe --tags --exact-match`, else the commit SHA:
web login footer (anon layout) and public pages footer, web `#/about` (linked from Settings → About Komboe),
extension Settings → About dialog, desktop Help/App menu → About dialog (buttons open both links).
Verified by `tests/features/legal_web.py`.
