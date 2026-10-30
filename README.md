# Komboe

**Komboe is an open-source, zero-knowledge password manager — all the best password-manager features under one roof.**

- End-to-end encrypted: your master password and vault keys never leave your devices.
- No backdoors, no key escrow, no master/recovery key held by us — ever.
- Family and company organizations with admin seats, while every member keeps a **personal vault the admin cannot read**.
- Every platform: web vault, desktop (Windows/macOS/Linux), mobile (iOS/Android), browser extensions (Chrome, Firefox, Edge, Safari, Brave, Opera, Vivaldi), and a CLI.
- Built-in email aliases to hide your real address.
- Self-host free under AGPL-3.0, or subscribe to the hosted Komboe dashboard.

Status: **pre-alpha scaffolding.** See [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Credits — all features under one roof

| Project | License | What Komboe uses / learns from |
|---|---|---|
| [Bitwarden clients](https://github.com/bitwarden/clients) | GPL-3.0 (excluding `bitwarden_license/`) | Forked base for web, desktop, browser extension and CLI clients |
| [Vaultwarden](https://github.com/dani-garcia/vaultwarden) | AGPL-3.0 | Forked base for the Komboe server |
| [SimpleLogin](https://github.com/simple-login/app) | AGPL-3.0 | Email alias service |
| [Proton Pass](https://github.com/protonpass) | GPL-3.0 | Dashboard look-and-feel inspiration, alias UX |
| [KeePassXC](https://github.com/keepassxreboot/keepassxc) | GPL-2.0/3.0 | Offline vault and KDBX import/export ideas |
| [Passbolt](https://github.com/passbolt) | AGPL-3.0 | Team sharing ideas (its account recovery model is deliberately **not** adopted) |
| [Padloc](https://github.com/padloc/padloc) | AGPL-3.0 | Org/sharing UX ideas |
| [Psono](https://gitlab.com/psono) | Apache-2.0 | Self-hosted feature ideas |

**No endorsement.** Komboe is an independent project, not affiliated with, sponsored by, or endorsed by Bitwarden Inc., the Vaultwarden contributors, Proton AG, KeePassXC, Passbolt SA, Padloc, Psono, SimpleLogin, or any other listed project. All product names, logos and trademarks belong to their owners and appear here only to give credit. Upstream branding is removed from Komboe builds.

## License

[GNU AGPL-3.0](LICENSE). Third-party notices: [NOTICE](NOTICE).
