# Komboe marketing site (komboe.com) — STAGING ONLY

Static site (no build step required; `python3 build.py` regenerates the HTML from one template). Serve with any static host: `python3 -m http.server`.

Pages: Home, Features, Security, Pricing (placeholder prices), Downloads (placeholder builds/versions/SHA-256, platform auto-detect), Log in, Sign up.

Branding: padlock-K logo from `branding/logo` (shape untouched, color variant only), Sora font (OFL), every password field has a show/hide toggle.

## Accounts: one Komboe sign-in (shared account identity, OIDC)
Users never see "GoDesk" in the sign-in flow. There are no email/password fields anywhere on the site: Log in / Sign up buttons go straight to the Komboe sign-in at `auth.komboe.com` (OIDC authorization code + PKCE S256). Sign up sends `prompt=create`, or redirects to `enrollmentUrl` if set. `login_hint` is passed only if present in the page URL.

Wiring (Jonathan), in `assets/config.js` (no secrets, public client):
- Identity provider (Authentik) served at `https://auth.komboe.com`, themed Komboe: padlock-K logo (shape unchanged), Sora font, no GoDesk branding; offers email+password, Google and passkey.
- `issuer`: `https://auth.komboe.com/application/o/<slug>/`, `clientId`: public client id.
- Redirect URIs: `https://komboe.com/auth/callback.html` (+ staging origin).
- Optional `enrollmentUrl` for the enrollment flow.
- `auth/callback.html` checks `state`; token exchange (PKCE verifier in sessionStorage) is a TODO.

## SEO
Per-page title/description/canonical/OG/Twitter, JSON-LD (Organization, SoftwareApplication with Free offer only, FAQPage, BreadcrumbList), sitemap.xml, robots.txt, 404.html, hreflang en + x-default.
Build for staging (default): `python3 build.py` → noindex + robots `Disallow: /`. Production: `KOMBOE_ENV=production python3 build.py`.

Not deployed. No DNS changes.
