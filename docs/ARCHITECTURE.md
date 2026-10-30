<p align="center"><img alt="Komboe" src="../branding/wordmark/komboe-wordmark-light.svg" width="300"></p>

# Komboe Architecture

## Components
| Layer | Base | Path | License |
|---|---|---|---|
| Clients (web, desktop, browser extensions, CLI) | Fork of `bitwarden/clients` (GPL-3.0 parts only) | `clients/` | GPL-3.0 → distributed within AGPL-3.0 project |
| Mobile (iOS/Android) | Fork of Bitwarden mobile (GPL-3.0) | `clients/mobile/` | GPL-3.0 |
| Server / API | Fork of `dani-garcia/vaultwarden` (Rust) | `server/` | AGPL-3.0 |
| Email aliases | SimpleLogin | `aliases/` | AGPL-3.0 |
| Branding | Komboe assets, themes | `branding/` | AGPL-3.0 / project trademark |

Clients speak the Bitwarden-compatible API to the Komboe server; the alias service is reached via its API from clients and the dashboard.

## Zero-knowledge E2E model
- Master password → KDF (Argon2id default, PBKDF2 compatibility) → master key, derived **only on device**.
- Master key unwraps a per-user symmetric key; vault items are encrypted client-side (AES-256 + HMAC).
- The server stores only ciphertext, encrypted keys, KDF params and an authentication hash.
- Org sharing uses per-org keys wrapped with each member's public key.

### Hard rules — no exceptions
- **No backdoor, no key escrow, no server-held master key, no recovery copy** of any user key.
- Lost master password = lost vault (only user-held options like an exported emergency kit or user-initiated emergency access to a trusted contact, which is E2E and approved by the user).
- **Explicitly excluded:**
  - Admin password reset / account recovery by org admins
  - Key Connector (server-held keys)
  - Passbolt-style account recovery
  - Any code from `bitwarden_license/` (Bitwarden License, non-OSS)

## Organizations
- **Family** and **company** organizations with admin seats.
- Billing: per-member family fee; company per-seat.
- Every member has a **personal vault the admin cannot read** — admins manage membership and shared collections only.
- **Admin-approved split-off:** a member can request to leave; on admin approval the member keeps their personal vault and becomes admin of their own new family org. Shared org items stay with the original org.

## Billing data
Only minimal billing metadata is stored: account id, plan, seat count, status, renewal date, and the payment processor's customer/subscription ids. No card data, no vault data, no usage telemetry beyond what billing needs.

## Platforms
Web vault, desktop (Windows/macOS/Linux), mobile (iOS/Android), browser extensions (Chrome, Firefox, Edge, Safari, Brave, Opera, Vivaldi), CLI.

## UX
Dashboard styled after Proton Pass's clean look (left nav, item list, detail pane, light/dark). Komboe branding only.

## Business model
Fully open source (AGPL-3.0). Revenue from the hosted Komboe dashboard subscription; self-hosting is free.
