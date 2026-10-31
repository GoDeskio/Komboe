# Komboe marketing site (komboe.com) — STAGING ONLY

Static site (no build step required; `python3 build.py` regenerates the HTML from one template). Serve with any static host: `python3 -m http.server`.

Pages: Home, Features, Security, Pricing (placeholder prices), Downloads (placeholder builds/versions/SHA-256, platform auto-detect), Log in, Sign up.

Branding: padlock-K logo from `branding/logo` (shape untouched, color variant only), Sora font (OFL), every password field has a show/hide toggle.

## Accounts — shared GoDesk account via Authentik (OIDC)
No Komboe-only login. Log in / Sign up collect email (`login_hint`) and redirect to Authentik with authorization code + PKCE (S256). Sign up adds `prompt=create`.
Configure `assets/config.js` (no secrets — public client):
- `issuer`: `https://<authentik-host>/application/o/<slug>/`
- `clientId`: Authentik public OAuth2/OIDC provider client id
- Redirect URI to register: `https://komboe.com/auth/callback.html` (+ staging origin)
- `auth/callback.html` validates `state`; token exchange is a TODO for the Komboe app/backend.

Not deployed. No DNS changes.
