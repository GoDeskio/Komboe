/**
 * Choose the string mixed into the master-password KDF.
 * An email is returned unchanged, including its case, so existing vault keys stay valid.
 * A login name is accepted only with the email the server stored for that account.
 */
export function kdfIdentity(typed: string, canonicalEmail: string | null | undefined): string {
  const value = typed.trim();
  if (value.includes("@")) {
    return value;
  }
  const email = (canonicalEmail ?? "").trim();
  if (!email.includes("@")) {
    throw new Error(
      "This login name is not an account. Komboe will not derive a vault key from a login name.",
    );
  }
  return email;
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
