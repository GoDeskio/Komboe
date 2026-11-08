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

/**
 * Unauthenticated login-name responses always use this PBKDF2 count.
 * The account's own KDF is inside the envelope. A custom account KDF is not
 * returned in the clear, because a miss cannot imitate it.
 */
export const LOGIN_NAME_WRAP_KDF_TYPE = 0;
export const LOGIN_NAME_WRAP_ITERATIONS = 600_000;

export type LoginNamePayload = {
  kdfEmail: string;
  kdfType: number;
  kdfIterations: number;
  kdfMemory: number | null;
  kdfParallelism: number | null;
};

export function loginNamePlaintext(payload: LoginNamePayload): string {
  const memory = payload.kdfMemory == null ? "" : String(payload.kdfMemory);
  const parallelism = payload.kdfParallelism == null ? "" : String(payload.kdfParallelism);
  return [
    "v2",
    payload.kdfEmail,
    String(payload.kdfType),
    String(payload.kdfIterations),
    memory,
    parallelism,
  ].join("\n");
}

export function parseLoginNamePlaintext(plain: string): LoginNamePayload {
  const text = plain.replace(/\0+$/g, "");
  if (!text.startsWith("v2\n")) {
    if (!text.includes("@")) {
      throw new Error("That login name was not accepted.");
    }
    return {
      kdfEmail: text,
      kdfType: LOGIN_NAME_WRAP_KDF_TYPE,
      kdfIterations: LOGIN_NAME_WRAP_ITERATIONS,
      kdfMemory: null,
      kdfParallelism: null,
    };
  }
  const parts = text.split("\n");
  const kdfEmail = parts[1] || "";
  const kdfIterations = Number(parts[3]);
  if (!kdfEmail.includes("@") || !Number.isFinite(kdfIterations) || kdfIterations < 100000) {
    throw new Error("That login name was not accepted.");
  }
  const memory = parts[4] ? Number(parts[4]) : null;
  const parallelism = parts[5] ? Number(parts[5]) : null;
  return {
    kdfEmail,
    kdfType: Number(parts[2]),
    kdfIterations,
    kdfMemory: Number.isFinite(memory) ? memory : null,
    kdfParallelism: Number.isFinite(parallelism) ? parallelism : null,
  };
}

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

function paddedPlaintext(text: string): Uint8Array {
  const raw = new TextEncoder().encode(text);
  if (raw.length === 0 || raw.length >= LOGIN_NAME_ENVELOPE_PLAINTEXT || !text.includes("@")) {
    throw new Error("The vault email cannot be sealed.");
  }
  const padded = new Uint8Array(LOGIN_NAME_ENVELOPE_PLAINTEXT);
  padded.set(raw);
  return padded;
}

/** AES-GCM under the first 32 bytes of the public login-name wrap key. The salt is not the login name. */
export async function sealKdfEmail(rawKey: Uint8Array, kdfEmail: string): Promise<string> {
  return sealLoginNamePlaintext(rawKey, kdfEmail);
}

export async function sealLoginNamePlaintext(rawKey: Uint8Array, plaintext: string): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await crypto.subtle.importKey("raw", asBuffer(rawKey), "AES-GCM", false, ["encrypt"]);
  const cipher = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, asBuffer(paddedPlaintext(plaintext))),
  );
  const out = new Uint8Array(iv.length + cipher.length);
  out.set(iv, 0);
  out.set(cipher, iv.length);
  return bytesToB64(out);
}

async function decryptEnvelope(rawKey: Uint8Array, envelope: string): Promise<string> {
  const bytes = b64ToBytes(envelope);
  if (bytes.length !== 12 + LOGIN_NAME_ENVELOPE_PLAINTEXT + 16) {
    throw new Error("That login name was not accepted.");
  }
  const key = await crypto.subtle.importKey("raw", asBuffer(rawKey), "AES-GCM", false, ["decrypt"]);
  try {
    const plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: asBuffer(bytes.slice(0, 12)) },
      key,
      asBuffer(bytes.slice(12)),
    );
    return new TextDecoder().decode(plain).replace(/\0+$/g, "");
  } catch {
    throw new Error("That login name was not accepted.");
  }
}

/** Decrypts the vault-key email. A wrong password or a decoy envelope throws. */
export async function openKdfEmail(rawKey: Uint8Array, envelope: string): Promise<string> {
  return (await openLoginNamePayload(rawKey, envelope)).kdfEmail;
}

export async function openLoginNamePayload(rawKey: Uint8Array, envelope: string): Promise<LoginNamePayload> {
  return parseLoginNamePlaintext(await decryptEnvelope(rawKey, envelope));
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
