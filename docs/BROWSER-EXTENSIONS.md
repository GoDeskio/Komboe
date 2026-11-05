# Komboe browser extensions

Phase B client matrix for loading the password-manager extension across Chromium-family browsers (including **Cerebro Browser**), Firefox/Tor, and Safari.

Machine-readable source of truth: [`clients/SUPPORTED-BROWSERS.json`](../clients/SUPPORTED-BROWSERS.json).  
Headless smoke (no browser UI): `node scripts/extension-smoke.mjs`

Updated 2026-11-05 Arizona MST.

## Builds

| Build | Artifact (under `KOMBOE_ARTIFACTS`, default `/workspace/artifacts`) | How to produce |
|---|---|---|
| Chromium MV3 | `komboe-chrome-mv3.zip` | In `clients/upstream`: `npm run dist:chrome --workspace @bitwarden/browser` (then rebrand/copy into artifacts as today) |
| Firefox | `komboe-firefox.zip` | `npm run dist:firefox --workspace @bitwarden/browser` |
| Safari | (macOS only) | `npm run dist:safari --workspace @bitwarden/browser` — needs Xcode |

Edge/Opera webpack targets also exist (`dist:edge`, `dist:opera`); the Chromium MV3 zip is what we ship and load everywhere Chromium-compatible.

## Supported browsers

| Browser | Family | Build to load | Status |
|---|---|---|---|
| Google Chrome | Chromium | Chromium MV3 | Supported (tested) |
| Microsoft Edge | Chromium | Chromium MV3 | Supported (tested) |
| Brave | Chromium | Chromium MV3 | Supported (tested) |
| Opera | Chromium | Chromium MV3 | Supported |
| **Vivaldi** | Chromium | Chromium MV3 | Supported — **not yet E2E'd** (Phase B #87) |
| **Cerebro Browser** (GoDesk Chromium) | Chromium | Chromium MV3 | Supported — treat as Chrome for load + autofill; **keep on the bar** |
| Firefox | Gecko | Firefox zip | Supported (tested) |
| **Tor Browser** | Gecko | Firefox zip | Supported — **not yet E2E'd** (Phase B #87) |
| Safari | Safari | Safari package | Blocked without macOS/Xcode (Phase B #86) |

## Load checklist (Chromium family, including Cerebro / Vivaldi / Brave / Edge)

1. Unzip `komboe-chrome-mv3.zip` to a folder (or use the unpacked `dist/apps/browser/chrome` build).
2. Open the browser's extensions page:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
   - Brave: `brave://extensions`
   - Vivaldi: `vivaldi://extensions`
   - Opera: `opera://extensions`
   - **Cerebro Browser**: use the Chromium extensions page (same MV3 load-unpacked flow as Chrome).
3. Enable **Developer mode** → **Load unpacked** → select the unzipped folder.
4. Confirm the toolbar icon name is **Komboe** (not upstream Bitwarden branding).
5. Point the extension at your self-host / hosted vault and sign in.
6. Autofill smoke: open a login form on a test site; confirm the inline menu / popup can fill username + password.

## Load checklist (Firefox / Tor Browser)

1. Unzip or keep `komboe-firefox.zip`.
2. Firefox: `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on** → pick `manifest.json` inside the unzipped tree (or the zip where allowed).
3. Tor Browser: same Firefox temporary-add-on flow; expect stricter first-party isolation — re-test autofill after confirming the temporary add-on loaded.
4. Confirm branding and vault URL.

## What this smoke does **not** claim

- It does **not** launch Chrome/Vivaldi/Tor/Cerebro or run Playwright autofill.
- Device / OS biometric prompts are out of scope here (see desktop PIN/biometric notes in `docs/PHASE-B-LOCAL.md`).
- Safari remains blocked on Linux CI.

## CI / local command

```sh
node scripts/extension-smoke.mjs
# with built zips:
KOMBOE_ARTIFACTS=/workspace/artifacts node scripts/extension-smoke.mjs
```

## Cerebro Browser load contract (tied to real MV3 manifest)

Cerebro Browser is GoDesk Chromium. It loads the **same** Chromium MV3 build as Chrome (`komboe-chrome-mv3.zip` / unpacked `dist`). There is no separate Cerebro artifact.

The headless smoke (`scripts/extension-smoke.mjs`) asserts these fields from `clients/upstream/apps/browser/src/manifest.v3.json`:

| Manifest field | Why Cerebro needs it |
|---|---|
| `manifest_version: 3` | Cerebro is Chromium MV3 |
| `permissions` includes `storage`, `tabs`, `scripting`, `alarms`, `notifications` | Vault state, tab autofill injection, unlock reminders |
| `host_permissions` covers `https://*/*` (or equivalent) | Autofill on HTTPS login forms |
| `action.default_popup` | Toolbar unlock / vault popup |
| `content_scripts[].matches` cover web pages (`*://*/*` / http(s) / `<all_urls>`) | Inline in-form menu |

Load steps: same Chromium checklist above (`cerebro://extensions` or the Chromium extensions page → Developer mode → Load unpacked). Confirm toolbar name **Komboe**, set self-host URL, smoke autofill.

UI E2E inside Cerebro is still **manual** until a Cerebro binary is on the box (Phase B #87 partial).

## Vivaldi load contract (Chromium MV3)

Vivaldi loads the **same** Chromium MV3 build as Chrome (`komboe-chrome-mv3.zip`). There is no separate Vivaldi artifact.

`scripts/extension-smoke.mjs` reads `load_contract` for `vivaldi` from [`clients/SUPPORTED-BROWSERS.json`](../clients/SUPPORTED-BROWSERS.json) and asserts it against `manifest.v3.json` (same fields as Cerebro: permissions, host_permissions, `action.default_popup`, content_scripts).

Load: `vivaldi://extensions` → Developer mode → Load unpacked. UI E2E inside Vivaldi is still **manual** (Phase B #87 partial).

## Tor Browser load contract (Firefox MV2)

Tor Browser loads the **Firefox** zip (`komboe-firefox.zip`) via the temporary-add-on flow. There is no separate Tor artifact.

`scripts/extension-smoke.mjs` reads `load_contract` for `tor` from the matrix and asserts it against `clients/upstream/apps/browser/src/manifest.json`:

| Manifest field | Why Tor/Firefox needs it |
|---|---|
| `manifest_version: 2` | Tor Browser is Firefox-based (MV2 temporary add-on) |
| `permissions` includes `storage`, `tabs`, `alarms`, `notifications` | Vault state + unlock reminders |
| host permission / `<all_urls>` / `*://*/*` | Autofill on pages (Tor first-party isolation still needs manual re-test) |
| `browser_action.default_popup` | Toolbar unlock / vault popup |
| `content_scripts[].matches` cover web pages | Inline in-form menu |

Load: Tor Browser → `about:debugging#/runtime/this-firefox` → Load Temporary Add-on. UI E2E inside Tor is still **manual** (Phase B #87 partial).

