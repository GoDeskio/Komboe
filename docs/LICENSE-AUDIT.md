# License audit: Bitwarden-licensed code and SDK in Komboe builds

Date: 2026-10-30 (updated after the desktop OSS-SDK change). Scope: `clients/upstream` (web vault, browser extension, desktop, CLI) and the builds we
actually ship/run (`/workspace/run/web-vault`, `/workspace/run/ext`, desktop `app.asar`). Nothing has been removed
by this audit; it reports what is there and whether it can be replaced with GPL code. Pending legal review.

## Summary

| Item | Present in source? | Present in shipped build? | License | Action proposed |
|---|---|---|---|---|
| `bitwarden_license/` directory (bit-web, bit-browser, bit-desktop, bit-common, bit-cli) | **No** (directory absent) | No | Bitwarden License Agreement | None needed; clean leftover config references (below) |
| `@bitwarden/sdk-internal` 0.2.0-main.1126 | Yes (npm dep) | Yes: web vault, extension, desktop (WASM) | GPL-3.0 | Keep; it is the GPL SDK. Corresponding source: bitwarden/sdk-internal at that version |
| `@bitwarden/commercial-sdk-internal` 0.2.0-main.1126 | Yes (npm dep in root `package.json`, used only by upstream `build:bit*` targets) | **No.** Desktop builds use the OSS (`build:oss*`) webpack configs, which import only `@bitwarden/sdk-internal`; `electron-builder.json` now excludes `node_modules/@bitwarden/commercial-sdk-internal` and `**/bitwarden_license/**`, and the installed desktop `app.asar`/`app.asar.unpacked` were repacked without it | "BITWARDEN SOFTWARE DEVELOPMENT KIT LICENSE AGREEMENT Version 2, 7 October 2025" (proprietary) | Done for shipped builds; verified by `tests/features/desktop_oss_sdk.py`. Remaining: the root `package.json` dependency and `scripts/sdk-internal-versions.ts` (dev install only) |
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
- The shipped web vault string `bitwarden_license.json` (license upload hint) is now `komboe_license.json`.
- Also still present (build tooling only, never shipped): `tsconfig.base.json` path alias `@bitwarden/bit-common`,
  root `jest.config.js` projects, `angular.json` `bit-web` project, `apps/browser/project.json` commercial
  configurations, `build:bit*` scripts. Removing them is a tooling clean-up, not a licensing requirement.
- Package metadata `repository` in desktop and CLI `package.json` now points at GoDeskio/Komboe.

## Bitwarden-licensed features

The features Bitwarden implements under `bitwarden_license/` (organization SSO config UI, SCIM, Secrets Manager,
provider portal, event-log integrations, access intelligence, etc.) are **not present**. Komboe's equivalents
(LDAP directory, SCIM, OIDC SSO, upcoming SAML SSO) are new code in this repository under GPL-3.0 (clients) /
AGPL-3.0 (server).

## Can it be swapped for GPL code?

- `commercial-sdk-internal`: done for shipped builds (see table). The dependency itself can be removed from the
  root `package.json` together with the upstream `bit` build targets.
- Config references: yes, delete.

## Licenses bundled per package

`LICENSE.txt` (AGPL-3.0, repo root), `LICENSE_GPL.txt` (GPL-3.0, clients) and `THIRD-PARTY-NOTICES.md` are copied
into the web vault root, the extension root, and the desktop `app.asar` by each client's webpack config, and into
the desktop installer `resources/` via `electron-builder.json` `extraResources`. The CLI copies the same three files into `apps/cli/build`, which `pkg` embeds and npm publishes.
Upstream copyright and license headers in source files are untouched.

## In-app notice

Exact approved text, with **View license** (`/blob/<tag>/LICENSE`) and **Source code** (`/tree/<tag>`) links,
`<tag>` = `KOMBOE_SOURCE_REF` env, else `git describe --tags --exact-match`, else the commit SHA:
web login footer (anon layout) and public pages footer, web `#/about` (linked from Settings → About Komboe),
extension Settings → About dialog, desktop Help/App menu → About dialog (buttons open both links).
Verified by `tests/features/legal_web.py`.

## Android (GPL-3.0)

The Android app is Bitwarden Android tag `v2026.10.1-bwpm` (commit `1470154cf3d3d0511cdbe5bfc6493971b6478edf`), GPL-3.0-only, plus the Komboe rebrand in `mobile/`. It is not vendored in this tree; `mobile/android-build.sh` clones that tag.

GPL-3.0 obligations for a binary:

- License text: `mobile/android_rebrand.py` copies the upstream `LICENSE.txt` (GNU GPL v3) into `app/src/main/assets/LICENSE.txt`, so it is inside the APK.
- Corresponding source: `app/src/main/assets/komboe-source.txt` (from `mobile/ANDROID-SOURCE.txt`) names the upstream tag, the commit, and the Komboe files that modify it (`mobile/android_rebrand.py`, `mobile/android-build.sh`, `mobile/ANDROID_UPSTREAM_PIN`). Both repositories are public.
- Copyright headers in the upstream Kotlin/Java sources are not rewritten. The rebrand script skips lines that mention copyright or license.
- `THIRD-PARTY-NOTICES.md` is copied into the same assets directory.

The fdroid build also links `com.bitwarden:sdk-android` `4.0.0-9318-3b2c8fc3` from `bitwarden/sdk`. That library is under the Bitwarden Software Development Kit License Agreement, not the GPL, and is used unmodified. It is listed separately in `THIRD-PARTY-NOTICES.md`. Distributing an APK that combines the GPL app with that SDK needs a review against both licenses before a store or public binary release.

## Still open

- macOS `extendInfo.BitwardenAppGroupIdentifier` / `com.bitwarden.desktop` app-group ID in `electron-builder.json`
  (needs a Komboe Apple team ID before any macOS build).
- Windows Store AppxManifest identity is a placeholder until Partner Center reserves the Komboe name.
- Upstream workflow files under `clients/upstream/.github` still reference `bw` binaries and Bitwarden secrets; they
  are not run by this repository.
- The GPL attribution notice wording awaits legal review.
