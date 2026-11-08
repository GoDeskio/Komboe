/**
 * The vault-key salt is the email, including its case.
 * A login name is not a salt. The client learns the email only after
 * `loginNameVerifier` is accepted by `/identity/accounts/login-name/resolve`.
 */
export function kdfIdentity(typed: string, _canonicalEmail?: string | null): string {
  const value = typed.trim();
  if (!value.includes("@")) {
    throw new Error(
      "Sign in with the email for this vault. Komboe will not derive a vault key from a login name.",
    );
  }
  return value;
}

/** Public KDF for the login-name proof. This is not the vault key. */
export const LOGIN_NAME_VERIFIER_ITERATIONS = 100_000;

export async function loginNameVerifier(name: string, password: string): Promise<string> {
  const salt = new TextEncoder().encode(name.trim().toLowerCase());
  const material = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt, iterations: LOGIN_NAME_VERIFIER_ITERATIONS, hash: "SHA-256" },
    material,
    256,
  );
  const bytes = new Uint8Array(bits);
  let text = "";
  for (const byte of bytes) {
    text += String.fromCharCode(byte);
  }
  return btoa(text);
}

/** True when the login form can submit this identifier. */
export function loginIdentifierAccepted(typed: string): boolean {
  const value = typed.trim();
  if (!value) {
    return false;
  }
  if (value.includes("@")) {
    return value.includes(".") && !value.startsWith("@") && !value.endsWith("@");
  }
  return /^[a-z0-9._-]{3,32}$/i.test(value);
}
