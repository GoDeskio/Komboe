# Komboe marketing site (komboe.com) — STAGING ONLY

Static site (no build step required; `python3 build.py` regenerates the HTML from one template). Serve with any static host: `python3 -m http.server`.

Pages: Home, Features, Security, Pricing (placeholder prices), Downloads (placeholder builds/versions/SHA-256, platform auto-detect), Log in, Sign up.

Branding: padlock-K logo from `branding/logo` (shape untouched, color variant only), Sora font (OFL), every password field has a show/hide toggle.

## Accounts: one Komboe account
One Komboe account (email + master password, optional passkey + 2FA) across Komboe's own tools: web vault, extensions, Android, desktop, CLI, MCP. Not shared with other apps. This site collects no passwords and has no auth code: `login.html` / `signup.html` are explainers linking to the web vault at `/vault` and `/vault/signup` (PLACEHOLDERS in `build.py`: `VAULT_LOGIN`, `VAULT_SIGNUP`; alternative `https://app.komboe.com`). Self-hosters: local accounts by default, optional enterprise SSO (OIDC/SAML).

## SEO
Per-page title/description/canonical/OG/Twitter, JSON-LD (Organization, SoftwareApplication with Free offer only, FAQPage, BreadcrumbList), sitemap.xml, robots.txt, 404.html, hreflang en + x-default.
Build for staging (default): `python3 build.py` → noindex + robots `Disallow: /`. Production: `KOMBOE_ENV=production python3 build.py`.

Not deployed. No DNS changes.
