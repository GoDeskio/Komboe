# Rebrand checklist (upstream → Komboe)
- [ ] Run `scripts/rebrand.sh` and review report
- [ ] Replace logos, icons, favicons, splash screens, store art with `branding/` assets
- [ ] App names/titles/manifest names (extensions, desktop, mobile, CLI binary `komboe`)
- [ ] URLs: bitwarden.com / vault.bitwarden.com / vaultwarden links → Komboe URLs (domain TBD)
- [ ] Remove upstream telemetry/analytics endpoints and update/notification servers
- [ ] Bundle IDs / extension IDs / package names
- [ ] Email templates and server web-vault strings
- [ ] Keep copyright & license headers intact; keep credits in README/NOTICE
- [ ] Confirm `scripts/check-licenses.sh` passes; no `bitwarden_license/`
- [ ] Do not imply endorsement anywhere

## For Marcus (legal review before anything commercial)
- The web vault / anon-layout footer still reads "© {year} Bitwarden Inc." — kept deliberately (copyright notices are never
  altered by `scripts/rebrand_apply.py`). A separate "Komboe" product line is shown beside it. Decide the final footer wording.
- Android: built from bitwarden/android (GPL-3.0) with the Bitwarden SDK (`com.bitwarden:sdk-android`, from sdk-internal,
  GPL-3.0 per the npm package of the same source). Confirm before distribution.

## Phase C branding gaps (closed)
- Server picker (extension/desktop): Bitwarden cloud regions (bitwarden.com/.eu) are no longer offered; label reads "Choose your Komboe server" until a self-hosted URL is saved. Web vault on self-host already hides its region selector.
- Autofill inline menu / notification icons: upstream blue #175DDC -> Komboe violet #6D4AFF.
- Android debug build label: "Komboe" (was "Komboe Dev").
- Still open: the inline-menu button glyph is the upstream shield *shape* (now violet); replace with the padlock-K glyph (shape locked) in a follow-up.
