/**
 * The vault-key salt is the email, including its case.
 * A login name is not a salt. The email is recovered from an AES-GCM envelope
 * that was wrapped with the account's own KDF.
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

/** Padded plaintext inside the login-name envelope. The ciphertext length does not reveal the email. */
export const LOGIN_NAME_ENVELOPE_PLAINTEXT = 128;

export function randomEnvelopeSalt(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let salt = "";
  for (const byte of bytes) {
    salt += byte.toString(16).padStart(2, "0");
  }
  return salt;
}

export function envelopeKeyBytes(encodedKey: Uint8Array): Uint8Array {
  if (encodedKey.length < 32) {
    throw new Error("The wrapping key is too short.");
  }
  return encodedKey.slice(0, 32);
}

function bytesToB64(bytes: Uint8Array): string {
  let text = "";
  for (const byte of bytes) {
    text += String.fromCharCode(byte);
  }
  return btoa(text);
}

function b64ToBytes(value: string): Uint8Array {
  const text = atob(value);
  const bytes = new Uint8Array(text.length);
  for (let i = 0; i < text.length; i += 1) {
    bytes[i] = text.charCodeAt(i);
  }
  return bytes;
}

function asBuffer(bytes: Uint8Array): Uint8Array<ArrayBuffer> {
  // WebCrypto's BufferSource typing excludes SharedArrayBuffer. These copies are not shared.
  return bytes as Uint8Array<ArrayBuffer>;
}

function paddedEmail(kdfEmail: string): Uint8Array {
  const raw = new TextEncoder().encode(kdfEmail);
  if (raw.length === 0 || raw.length >= LOGIN_NAME_ENVELOPE_PLAINTEXT || !kdfEmail.includes("@")) {
    throw new Error("The vault email cannot be sealed.");
  }
  const padded = new Uint8Array(LOGIN_NAME_ENVELOPE_PLAINTEXT);
  padded.set(raw);
  return padded;
}

/** AES-GCM under the first 32 bytes of an account-KDF key. The salt for that KDF is not the login name. */
export async function sealKdfEmail(rawKey: Uint8Array, kdfEmail: string): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await crypto.subtle.importKey("raw", asBuffer(rawKey), "AES-GCM", false, ["encrypt"]);
  const cipher = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, asBuffer(paddedEmail(kdfEmail))),
  );
  const out = new Uint8Array(iv.length + cipher.length);
  out.set(iv, 0);
  out.set(cipher, iv.length);
  return bytesToB64(out);
}

/** Decrypts the vault-key email. A wrong password or a decoy envelope throws. */
export async function openKdfEmail(rawKey: Uint8Array, envelope: string): Promise<string> {
  const bytes = b64ToBytes(envelope);
  if (bytes.length !== 12 + LOGIN_NAME_ENVELOPE_PLAINTEXT + 16) {
    throw new Error("That login name was not accepted.");
  }
  const key = await crypto.subtle.importKey("raw", asBuffer(rawKey), "AES-GCM", false, ["decrypt"]);
  let plain: ArrayBuffer;
  try {
    plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: asBuffer(bytes.slice(0, 12)) },
      key,
      asBuffer(bytes.slice(12)),
    );
  } catch {
    throw new Error("That login name was not accepted.");
  }
  const text = new TextDecoder().decode(plain).replace(/\0+$/g, "");
  if (!text.includes("@")) {
    throw new Error("That login name was not accepted.");
  }
  return text;
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
