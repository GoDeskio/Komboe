# Komboe Roadmap

Every one of the 106 features in [FEATURES.md](FEATURES.md) is mapped to a milestone and a code base below.

## M0 — Scaffolding (repo, docs, import/rebrand scripts, RailYard checks)

_No features from the list; infrastructure work only._

## M1 — Import & rebrand (pinned upstream, strip branding, builds green)

_No features from the list; infrastructure work only._

## M2 — Core vault: web vault + server, E2E crypto, items, auth, health, import/export, self-host

| # | Feature | Sources | Code base |
|---|---|---|---|
| 1 | Unlimited logins/passwords | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 2 | Multiple personal vaults / folders | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 3 | Collections / shared vaults with per-vault permissions | PP, BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 4 | Tags | KP, PB, PD, PS | New code (ideas from KP) |
| 5 | Favorites, search, filters | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 6 | Item/secret history (versions) and trash/restore | PP, BW, VW, KP, PB | Bitwarden clients / Vaultwarden fork |
| 7 | Custom fields (text, hidden, boolean, linked) | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 8 | File attachments | PP, BW, VW, KP, PS | Bitwarden clients / Vaultwarden fork |
| 9 | Offline access / cached vault | PP, BW, VW, KP, PB, PS | Bitwarden clients / Vaultwarden fork |
| 10 | Login item | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 11 | Secure note | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 12 | Credit card | PP, BW, VW, PD, PS | Bitwarden clients / Vaultwarden fork |
| 13 | Identity | PP, BW, VW, PD | Bitwarden clients / Vaultwarden fork |
| 14 | SSH key item + SSH agent | BW, VW, KP, PS | Bitwarden clients / Vaultwarden fork |
| 15 | Wi-Fi, passport, license, bank and other custom templates | PP, PD, PS | New code (ideas from PP) |
| 16 | Environment variables / API secrets | PS | New code (ideas from PS) |
| 17 | GPG keys | PS | New code (ideas from PS) |
| 18 | Bookmarks | PS | New code (ideas from PS) |
| 46 | Master password + KDF (PBKDF2/Argon2id) | PP, BW, VW, KP, PD, PS | Bitwarden clients / Vaultwarden fork |
| 47 | Account 2FA: TOTP | PP, BW, VW, PB, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 48 | Account 2FA: WebAuthn/FIDO2 security keys | PP, BW, VW, PB, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 49 | Account 2FA: Duo / YubiKey OTP / email | BW, VW, PB, PS | Bitwarden clients / Vaultwarden fork |
| 50 | Login with passkey (passwordless account) | BW | Bitwarden clients / Vaultwarden fork |
| 51 | Login with device approval | BW, VW | Bitwarden clients / Vaultwarden fork |
| 52 | Biometric / PIN unlock | PP, BW, VW, KP, PB, PD | Bitwarden clients / Vaultwarden fork |
| 53 | Hardware key / key file vault unlock (YubiKey challenge-response) | KP | New code (ideas from KP) |
| 54 | PGP key-based auth with passphrase (3-step) | PB | New code (ideas from PB) |
| 56 | Built-in TOTP authenticator for stored items | PP, BW, VW, KP, PB, PS | Bitwarden clients / Vaultwarden fork |
| 57 | Passkey storage + autofill | PP, BW, VW, KP, PB | Bitwarden clients / Vaultwarden fork |
| 58 | Passkey import/export (FIDO CXP) | PP, BW, KP | Bitwarden clients / Vaultwarden fork |
| 67 | Emergency access (view/takeover after wait period) | PP, BW, VW | Bitwarden clients / Vaultwarden fork |
| 68 | Weak / reused password report | PP, BW, VW, KP, PB, PS | Bitwarden clients / Vaultwarden fork |
| 69 | Breach (HIBP) / dark-web monitoring | PP, BW, VW, KP, PS | Bitwarden clients / Vaultwarden fork |
| 70 | Exposed-password check (k-anonymity) | BW, VW, KP, PS | Bitwarden clients / Vaultwarden fork |
| 71 | Inactive 2FA report / missing 2FA | PP, BW, VW | Bitwarden clients / Vaultwarden fork |
| 72 | Unsecured (http) website report | BW, VW | Bitwarden clients / Vaultwarden fork |
| 73 | Org access-intelligence / risk insights | BW | Clean-room |
| 74 | Password + passphrase generator | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 75 | Username generator | BW, VW | Bitwarden clients / Vaultwarden fork |
| 76 | Import CSV / JSON from all major managers | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 77 | Import/export KDBX | KP, PB | New code (ideas from KP) |
| 78 | Encrypted export (password-protected JSON) | PP, BW, VW, KP | Bitwarden clients / Vaultwarden fork |
| 79 | Org-level import/export | BW, VW, PB, PS | Bitwarden clients / Vaultwarden fork |
| 80 | Web vault | PP, BW, VW, PB, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 93 | Docker self-host | VW, BW, PB, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 94 | Lightweight single-binary/SQLite server | VW | Bitwarden clients / Vaultwarden fork |
| 97 | End-to-end, zero-knowledge vault encryption | PP, BW, VW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 98 | Per-vault keys wrapped with user public keys | PP, BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 99 | OpenPGP-based encryption | PP, PB | New code (ideas from PP) |
| 100 | AES-256 / XChaCha20 / Argon2id | BW, KP, PS | Bitwarden clients / Vaultwarden fork |
| 101 | Local-only file database (no server) | KP | New code (ideas from KP) |

## M3 — Sharing, orgs and admin: family/company orgs, seats, personal-vault isolation, split-off, clean-room SSO/SCIM

| # | Feature | Sources | Code base |
|---|---|---|---|
| 20 | Share single item with user | PP, BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 21 | Share whole vault with user/group | PP, BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 22 | Group-based sharing / RBAC | BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 23 | Secure link sharing (one-time/expiring) | PP, PS | New code (ideas from PP) |
| 24 | Send: ephemeral encrypted text/file share with expiry, max views, password | BW, VW | Bitwarden clients / Vaultwarden fork |
| 25 | Accept-invite share flow with key exchange (public-key) | PP, BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 26 | Organization owns shared data | BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 27 | Family plan (up to 6) | PP, BW, VW, PD | Bitwarden clients / Vaultwarden fork |
| 28 | Per-seat business plans, add/remove seats | PP, BW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 29 | Member keeps personal vault separate from org | PP, BW, VW, PD | Bitwarden clients / Vaultwarden fork |
| 30 | Admin cannot read personal vaults | PP, BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 31 | Move member to new org (family split-off) | GoDesk-original | Komboe original |
| 32 | Per-member family pricing | GoDesk-original | Komboe original |
| 33 | Admin console / dashboard | PP, BW, VW, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 34 | Event / activity logs, audit | PP, BW, VW, PB, PS | Bitwarden clients / Vaultwarden fork |
| 35 | SIEM / syslog export | PP, BW, PB | Bitwarden clients / Vaultwarden fork |
| 36 | Enterprise policies (master password rules, 2FA required, disable export etc.) | PP, BW, VW, PB, PS | Bitwarden clients / Vaultwarden fork |
| 37 | Password expiry / rotation policy | PB | New code (ideas from PB) |
| 38 | Public org management API | BW, PB, PS | Bitwarden clients / Vaultwarden fork |
| 39 | Directory connector LDAP/AD | BW, PB, PS | Bitwarden clients / Vaultwarden fork |
| 40 | SSO SAML/OIDC login | PP, BW, PB, PS | Clean-room |
| 41 | SCIM provisioning | PP, BW, PB, PS | Clean-room |
| 42 | Trusted devices (SSO without master password) | BW | Clean-room |
| 45 | Self-hosted instance admin page (/admin) | VW, PB, PS | Bitwarden clients / Vaultwarden fork |

## M4 — All clients: desktop, mobile, every browser extension, CLI, autofill

| # | Feature | Sources | Code base |
|---|---|---|---|
| 81 | Desktop Windows/macOS/Linux | PP, BW, KP, PD | Bitwarden clients / Vaultwarden fork |
| 82 | Desktop app Windows only | PB | New code (ideas from PB) |
| 83 | Mobile iOS + Android | PP, BW, PB, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 84 | Browser ext Chrome/Edge/Brave/Opera | PP, BW, KP, PB, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 85 | Browser ext Firefox | PP, BW, KP, PB, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 86 | Browser ext Safari | PP, BW, KP, SL | Bitwarden clients / Vaultwarden fork |
| 87 | Browser ext Vivaldi/Tor | BW | Bitwarden clients / Vaultwarden fork |
| 88 | CLI | PP, BW, KP, PB, PS | Bitwarden clients / Vaultwarden fork |
| 89 | Autofill: inline in-form menu + keyboard shortcuts | PP, BW, KP, PB, PD, PS | Bitwarden clients / Vaultwarden fork |
| 90 | Auto-type (desktop global) | KP | New code (ideas from KP) |
| 91 | Secret Service / FreeDesktop integration | KP | New code (ideas from KP) |
| 92 | Apple Watch / Wear OS | PP, BW | Bitwarden clients / Vaultwarden fork |

## M5 — Aliases (SimpleLogin)

| # | Feature | Sources | Code base |
|---|---|---|---|
| 19 | Email alias item linked to a login | PP, SL | SimpleLogin fork |
| 59 | Hide-my-email aliases | PP, SL | SimpleLogin fork |
| 60 | Alias generation integrations (SimpleLogin/addy/Firefox Relay/Fastmail/DuckDuckGo) | BW, VW | Bitwarden clients / Vaultwarden fork |
| 61 | Custom domains for aliases, catch-all | PP, SL | SimpleLogin fork |
| 62 | Multiple mailboxes per alias | PP, SL | SimpleLogin fork |
| 63 | Reply/send from alias (reverse alias) | PP, SL | SimpleLogin fork |
| 64 | PGP encryption of forwarded mail | SL | SimpleLogin fork |
| 65 | Alias enable/disable, block sender, stats | PP, SL | SimpleLogin fork |
| 66 | Subdomain / directory aliases | SL | SimpleLogin fork |

## M6 — Hosted dashboard (Proton Pass-style) + subscription billing — owner approval for billing

| # | Feature | Sources | Code base |
|---|---|---|---|
| 103 | Hosted SaaS monthly or annual | PP, BW, PB, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 104 | Free tier | PP, BW, PD, PS, SL | Bitwarden clients / Vaultwarden fork |
| 105 | Proton-style dashboard UI (Dustin preference) | PP | Komboe original (Proton Pass look) |

## M7 — Hardening: audit, HA, storage backends, legal review (Marcus) before commercial

| # | Feature | Sources | Code base |
|---|---|---|---|
| 55 | Advanced account protection (Sentinel-style anomaly detection) | PP | New code (ideas from PP) |
| 95 | HA / clustering | BW, PB, PS | Bitwarden clients / Vaultwarden fork |
| 96 | External storage backends (S3/GCS) for attachments | PS | New code (ideas from PS) |
| 102 | Third-party audits published | PP, BW, KP, PB, PS, SL | Bitwarden clients / Vaultwarden fork |

## M8 — Post-1.0: clean-room machine secrets manager

| # | Feature | Sources | Code base |
|---|---|---|---|
| 106 | Machine secrets manager (projects, service accounts) | BW | — |

## Excluded (not built)

| # | Feature | Reason |
|---|---|---|
| 43 | Admin password reset / account recovery | Escrow/admin recovery — violates no-recovery rule |
| 44 | Key Connector (org-held decryption key) | Org-held decryption key — violates no-escrow rule |
| — | Passbolt-style account recovery | Escrow — violates no-recovery rule |
| — | Any `bitwarden_license/` code | Not open source |

Counts: M0 0, M1 0, M2 51, M3 24, M4 12, M5 9, M6 3, M7 4, M8 1, Excluded 2 (total 106).
