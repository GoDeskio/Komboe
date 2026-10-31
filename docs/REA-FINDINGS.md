# REA findings + features to adopt (Komboe)

Scan date: 2026-10-31 (Asia/Taipei). Tool: REA `rea-agents@6.5.0`, static only.
- Box: `analyze-javascript-application` on public OSS/SDK sources, plus `inspect-web-page` and `analyze-web-bundle` on public pages with no login.
- Dad's computer: `analyze-javascript-application` on Electron `app.asar` extracted, never run, from official Linux `.deb` downloads (Bitwarden, 1Password, Proton Pass).
- Raw evidence lives in `/workspace/rea-scans/komboe/reports` (box). Large files are gzipped.

No logins, no paid-account bypass, no DRM circumvention. Code under GPL, AGPL, BUSL or proprietary licenses was used only to learn behavior; nothing was copied.

## What REA showed

| Competitor | REA evidence | Notable capability |
|---|---|---|
| Dashlane (dashlane-cli, Apache-2.0) | 560 JS modules, 140 endpoints; `modules/auth/opaque`, `auth/confidential-sso`, `tunnel-api-connect/steps` | OPAQUE PAKE login (server never sees a password-equivalent); "confidential SSO" brokered inside an attested enclave over an attested tunnel |
| Proton Pass (WebClients, GPL-3.0) | `packages/pass/lib/{alias,secure-links,monitor,ssh-agent,spotlight,b2b,passkeys}` | Hide-my-email aliases, expiring secure links, Pass Monitor (breach, 2FA and reuse), SSH agent, spotlight quick search |
| 1Password SDK (MIT) | 105 modules; `client`, `client_builder`, `configuration` | Service-account SDK with secret references (`op://vault/item/field`) |
| Keeper Commander (MIT) | repo inventory | Compliance and audit reports, event export to SIEM, record types |
| KeePassXC (GPL) | site and repo | KDBX4, SSH agent, key-file and YubiKey challenge-response unlock |
| NordPass, LastPass, RoboForm, Enpass, Bitwarden | public page and bundle inventories (`*.web-page.json`) | Marketing feature lists only. Pages are mostly policy-filtered, and no app code was reachable without a login |

## Features to adopt (ranked)

1. **SIEM audit-event export, hash-chained JSONL** (Keeper, 1Password Events API). Closes STATUS #35. **Implemented in this PR.**
2. **Secret references and `komboe run` env injection** (1Password `op://`, Dashlane CLI). CLI only.
3. **Pass Monitor-style health dashboard** (Proton): reuse, weak passwords and missing 2FA, computed client-side. Partly in the upstream reports.
4. **Hide-my-email aliases** (Proton): self-hosted alias service. The `aliases/` dir exists, so wire it into the generator.
5. **OPAQUE login** (Dashlane): a PAKE in place of the hashed master password. Large, and goes through the Encryptoglyph roadmap.
6. **SSH agent** (Proton, KeePassXC). Desktop Phase B.
7. **Expiring secure links** (Proton). Close to Send; add view-count UX.
8. **YubiKey challenge-response unlock** (KeePassXC). STATUS #53.

### Desktop clients (official Linux .deb → `app.asar`, parsed inertly on the lab PC, never executed)
- **Proton Pass desktop**: IPC channels `sshAgent:start/clear/destroy/getStatus/setSshKeyItems/setSettingEnabled` → a built-in SSH agent that serves vault SSH-key items, toggled per device. Confirms feature #6 (SSH agent) as a desktop-side IPC service; also biometric unlock hooks.
- **1Password desktop**: passkey modules and quick-access snippets; graph capacity-limited (2.8k modules) so mostly UI chunks.
- **Bitwarden desktop** (our upstream): scanned for baseline only; REA hit its result-capacity limit at 13,241/16,432 sources.
Summaries: `GoDeskio/rea-scans` → `komboe/reports/*.asar.summary.json`.
