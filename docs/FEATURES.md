# Komboe feature list (106)

Source: GoDesk password manager research, 2026-10-29. Abbreviations: PP=Proton Pass, BW=Bitwarden, VW=Vaultwarden, KP=KeePassXC, PB=Passbolt, PD=Padloc, PS=Psono, SL=SimpleLogin.

Status: **Excluded** = conflicts with the no-escrow/no-recovery rules; **Review** = allowed only under the stated constraint.

| # | Category | Feature | Sources | Status | Note |
|---|---|---|---|---|---|
| 1 | Vault | Unlimited logins/passwords | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 2 | Vault | Multiple personal vaults / folders | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 3 | Vault | Collections / shared vaults with per-vault permissions | PP, BW, VW, PB, PD, PS | In scope |  |
| 4 | Vault | Tags | KP, PB, PD, PS | In scope |  |
| 5 | Vault | Favorites, search, filters | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 6 | Vault | Item/secret history (versions) and trash/restore | PP, BW, VW, KP, PB | In scope |  |
| 7 | Vault | Custom fields (text, hidden, boolean, linked) | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 8 | Vault | File attachments | PP, BW, VW, KP, PS | In scope |  |
| 9 | Vault | Offline access / cached vault | PP, BW, VW, KP, PB, PS | In scope |  |
| 10 | Items | Login item | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 11 | Items | Secure note | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 12 | Items | Credit card | PP, BW, VW, PD, PS | In scope |  |
| 13 | Items | Identity | PP, BW, VW, PD | In scope |  |
| 14 | Items | SSH key item + SSH agent | BW, VW, KP, PS | In scope |  |
| 15 | Items | Wi-Fi, passport, license, bank and other custom templates | PP, PD, PS | In scope |  |
| 16 | Items | Environment variables / API secrets | PS | In scope |  |
| 17 | Items | GPG keys | PS | In scope |  |
| 18 | Items | Bookmarks | PS | In scope |  |
| 19 | Items | Email alias item linked to a login | PP, SL | In scope |  |
| 20 | Sharing | Share single item with user | PP, BW, VW, PB, PD, PS | In scope |  |
| 21 | Sharing | Share whole vault with user/group | PP, BW, VW, PB, PD, PS | In scope |  |
| 22 | Sharing | Group-based sharing / RBAC | BW, VW, PB, PD, PS | In scope |  |
| 23 | Sharing | Secure link sharing (one-time/expiring) | PP, PS | In scope |  |
| 24 | Sharing | Send: ephemeral encrypted text/file share with expiry, max views, password | BW, VW | In scope |  |
| 25 | Sharing | Accept-invite share flow with key exchange (public-key) | PP, BW, VW, PB, PD, PS | In scope |  |
| 26 | Orgs | Organization owns shared data | BW, VW, PB, PD, PS | In scope |  |
| 27 | Orgs | Family plan (up to 6) | PP, BW, VW, PD | In scope |  |
| 28 | Orgs | Per-seat business plans, add/remove seats | PP, BW, PB, PD, PS | In scope |  |
| 29 | Orgs | Member keeps personal vault separate from org | PP, BW, VW, PD | In scope |  |
| 30 | Orgs | Admin cannot read personal vaults | PP, BW, VW, PB, PD, PS | In scope |  |
| 31 | Orgs | Move member to new org (family split-off) | GoDesk-original | In scope | GAP: no source has admin-approved family split-off; GoDesk-original |
| 32 | Orgs | Per-member family pricing | GoDesk-original | In scope | GAP: sources use flat 6-seat family; GoDesk-original |
| 33 | Admin | Admin console / dashboard | PP, BW, VW, PB, PD, PS | In scope |  |
| 34 | Admin | Event / activity logs, audit | PP, BW, VW, PB, PS | In scope |  |
| 35 | Admin | SIEM / syslog export | PP, BW, PB | Review | BW event export is enterprise-tier — clean-room on Vaultwarden side |
| 36 | Admin | Enterprise policies (master password rules, 2FA required, disable export etc.) | PP, BW, VW, PB, PS | In scope |  |
| 37 | Admin | Password expiry / rotation policy | PB | In scope |  |
| 38 | Admin | Public org management API | BW, PB, PS | In scope |  |
| 39 | Admin | Directory connector LDAP/AD | BW, PB, PS | Review | BW Directory Connector is separate repo; verify license before reuse |
| 40 | Admin | SSO SAML/OIDC login | PP, BW, PB, PS | Review | SSO for identity only; never key release. BW SSO is bitwarden_license/ — clean-room build |
| 41 | Admin | SCIM provisioning | PP, BW, PB, PS | Review | BW SCIM is bitwarden_license/ — clean-room build |
| 42 | Admin | Trusted devices (SSO without master password) | BW | Review | Allowed only if admin/server can never decrypt; BW trusted-device code under bitwarden_license/ must not be copied |
| 43 | Admin | Admin password reset / account recovery | BW, PB | Excluded | Escrow/admin recovery — violates no-recovery rule |
| 44 | Admin | Key Connector (org-held decryption key) | BW | Excluded | Org-held decryption key — violates no-escrow rule |
| 45 | Admin | Self-hosted instance admin page (/admin) | VW, PB, PS | In scope |  |
| 46 | Auth | Master password + KDF (PBKDF2/Argon2id) | PP, BW, VW, KP, PD, PS | In scope |  |
| 47 | Auth | Account 2FA: TOTP | PP, BW, VW, PB, PD, PS, SL | In scope |  |
| 48 | Auth | Account 2FA: WebAuthn/FIDO2 security keys | PP, BW, VW, PB, PD, PS, SL | In scope |  |
| 49 | Auth | Account 2FA: Duo / YubiKey OTP / email | BW, VW, PB, PS | In scope |  |
| 50 | Auth | Login with passkey (passwordless account) | BW | In scope |  |
| 51 | Auth | Login with device approval | BW, VW | In scope |  |
| 52 | Auth | Biometric / PIN unlock | PP, BW, VW, KP, PB, PD | In scope |  |
| 53 | Auth | Hardware key / key file vault unlock (YubiKey challenge-response) | KP | In scope |  |
| 54 | Auth | PGP key-based auth with passphrase (3-step) | PB | In scope |  |
| 55 | Auth | Advanced account protection (Sentinel-style anomaly detection) | PP | Review | Server-side metadata only; keep minimal |
| 56 | TOTP | Built-in TOTP authenticator for stored items | PP, BW, VW, KP, PB, PS | In scope |  |
| 57 | TOTP | Passkey storage + autofill | PP, BW, VW, KP, PB | In scope |  |
| 58 | TOTP | Passkey import/export (FIDO CXP) | PP, BW, KP | In scope |  |
| 59 | Aliases | Hide-my-email aliases | PP, SL | In scope | BW integrates via 3rd-party alias APIs |
| 60 | Aliases | Alias generation integrations (SimpleLogin/addy/Firefox Relay/Fastmail/DuckDuckGo) | BW, VW | In scope |  |
| 61 | Aliases | Custom domains for aliases, catch-all | PP, SL | In scope |  |
| 62 | Aliases | Multiple mailboxes per alias | PP, SL | In scope |  |
| 63 | Aliases | Reply/send from alias (reverse alias) | PP, SL | In scope |  |
| 64 | Aliases | PGP encryption of forwarded mail | SL | In scope |  |
| 65 | Aliases | Alias enable/disable, block sender, stats | PP, SL | In scope |  |
| 66 | Aliases | Subdomain / directory aliases | SL | In scope |  |
| 67 | Emergency | Emergency access (view/takeover after wait period) | PP, BW, VW | Review | Must be E2E key sharing to grantee, user-initiated, never escrow |
| 68 | Health | Weak / reused password report | PP, BW, VW, KP, PB, PS | In scope |  |
| 69 | Health | Breach (HIBP) / dark-web monitoring | PP, BW, VW, KP, PS | In scope |  |
| 70 | Health | Exposed-password check (k-anonymity) | BW, VW, KP, PS | In scope |  |
| 71 | Health | Inactive 2FA report / missing 2FA | PP, BW, VW | In scope |  |
| 72 | Health | Unsecured (http) website report | BW, VW | In scope |  |
| 73 | Health | Org access-intelligence / risk insights | BW | Review | BW access intelligence is enterprise (bitwarden_license/) — clean-room |
| 74 | Generator | Password + passphrase generator | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 75 | Generator | Username generator | BW, VW | In scope |  |
| 76 | Import | Import CSV / JSON from all major managers | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 77 | Import | Import/export KDBX | KP, PB | In scope |  |
| 78 | Import | Encrypted export (password-protected JSON) | PP, BW, VW, KP | In scope |  |
| 79 | Import | Org-level import/export | BW, VW, PB, PS | In scope |  |
| 80 | Platform | Web vault | PP, BW, VW, PB, PD, PS, SL | In scope |  |
| 81 | Platform | Desktop Windows/macOS/Linux | PP, BW, KP, PD | In scope |  |
| 82 | Platform | Desktop app Windows only | PB | In scope |  |
| 83 | Platform | Mobile iOS + Android | PP, BW, PB, PD, PS, SL | In scope |  |
| 84 | Platform | Browser ext Chrome/Edge/Brave/Opera | PP, BW, KP, PB, PD, PS, SL | In scope |  |
| 85 | Platform | Browser ext Firefox | PP, BW, KP, PB, PD, PS, SL | In scope |  |
| 86 | Platform | Browser ext Safari | PP, BW, KP, SL | In scope |  |
| 87 | Platform | Browser ext Vivaldi/Tor | BW | In scope |  |
| 88 | Platform | CLI | PP, BW, KP, PB, PS | In scope |  |
| 89 | Platform | Autofill: inline in-form menu + keyboard shortcuts | PP, BW, KP, PB, PD, PS | In scope |  |
| 90 | Platform | Auto-type (desktop global) | KP | In scope |  |
| 91 | Platform | Secret Service / FreeDesktop integration | KP | In scope |  |
| 92 | Platform | Apple Watch / Wear OS | PP, BW | In scope |  |
| 93 | Self-host | Docker self-host | VW, BW, PB, PD, PS, SL | In scope |  |
| 94 | Self-host | Lightweight single-binary/SQLite server | VW | In scope |  |
| 95 | Self-host | HA / clustering | BW, PB, PS | In scope |  |
| 96 | Self-host | External storage backends (S3/GCS) for attachments | PS | In scope |  |
| 97 | Crypto | End-to-end, zero-knowledge vault encryption | PP, BW, VW, KP, PB, PD, PS | In scope |  |
| 98 | Crypto | Per-vault keys wrapped with user public keys | PP, BW, VW, PB, PD, PS | In scope |  |
| 99 | Crypto | OpenPGP-based encryption | PP, PB | In scope | Proton uses PGP-based keys; Passbolt OpenPGP |
| 100 | Crypto | AES-256 / XChaCha20 / Argon2id | BW, KP, PS | In scope |  |
| 101 | Crypto | Local-only file database (no server) | KP | In scope |  |
| 102 | Crypto | Third-party audits published | PP, BW, KP, PB, PS, SL | In scope |  |
| 103 | Billing | Hosted SaaS monthly or annual | PP, BW, PB, PD, PS, SL | In scope |  |
| 104 | Billing | Free tier | PP, BW, PD, PS, SL | In scope |  |
| 105 | UI | Proton-style dashboard UI (Dustin preference) | PP | Review | Re-implement look; no Proton branding/assets |
| 106 | Secrets | Machine secrets manager (projects, service accounts) | BW | Excluded (upstream code) — reimplement | Bitwarden Secrets Manager is Bitwarden License — upstream code excluded; clean-room reimplementation only (M8) |

## Exclusions also applied
- Passbolt-style account recovery (part of #43) — excluded.
- Any file under `bitwarden_license/` — never imported (see scripts/check-licenses.sh).
