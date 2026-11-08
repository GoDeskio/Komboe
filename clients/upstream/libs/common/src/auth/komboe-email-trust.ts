/**
 * Revoke the timed-email bearer token.
 * The local copy is removed only after the server accepts the revocation, so a
 * failed request can be retried. The token is not device-bound.
 */
export async function revokeKomboeEmailTrust(accessToken: string | null | undefined): Promise<boolean> {
  const storage = globalThis.sessionStorage;
  if (!storage) {
    return true;
  }
  const trust = storage.getItem("komboe.deviceTrust");
  if (!trust) {
    return true;
  }
  if (!accessToken) {
    return false;
  }
  const apiBase = storage.getItem("komboe.apiBase") || "";
  const trimmed = apiBase.replace(/\/$/, "");
  const url = trimmed
    ? (trimmed.endsWith("/api") ? trimmed : trimmed + "/api") + "/komboe/email-login-trust/clear"
    : "/api/komboe/email-login-trust/clear";
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + accessToken,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ token: trust }),
    });
    if (!response.ok) {
      return false;
    }
    storage.removeItem("komboe.deviceTrust");
    storage.removeItem("komboe.loginChallenge");
    return true;
  } catch {
    return false;
  }
}
