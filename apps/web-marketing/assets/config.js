// Komboe sign-in (shared account identity provider, themed padlock-K + Sora, at auth.komboe.com). OIDC public client + PKCE; no secrets.
window.KOMBOE_AUTH = {
  issuer: "https://auth.komboe.com/application/o/komboe/", // PLACEHOLDER
  clientId: "KOMBOE_WEB_CLIENT_ID",                        // PLACEHOLDER (public client)
  redirectUri: location.origin + "/auth/callback.html",
  scope: "openid email profile",
  // Optional: enrollment flow URL (e.g. https://auth.komboe.com/if/flow/<enrollment-slug>/) for Sign up (else prompt=create is sent)
  enrollmentUrl: ""
};
