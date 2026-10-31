// Shared GoDesk account via self-hosted Authentik (OIDC). Fill at deploy time; no secrets here (public client + PKCE).
window.KOMBOE_AUTH = {
  issuer: "https://AUTHENTIK_HOST/application/o/komboe/", // PLACEHOLDER
  clientId: "KOMBOE_WEB_CLIENT_ID",                        // PLACEHOLDER (public client)
  redirectUri: location.origin + "/auth/callback.html",
  scope: "openid email profile"
};
