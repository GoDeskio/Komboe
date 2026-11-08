/**
 * Device PIN and pattern unlock.
 * The secret never leaves this browser. The stored record holds only a wrapped user key.
 * This is not a server login and it does not replace the master password.
 */

export const STORAGE_PREFIX = "komboe.deviceUnlock.v1.";
export const MAX_FAILURES = 5;
export const UNLOCK_TTL_MS = 12 * 60 * 60 * 1000;
const ITERATIONS = 600000;

const REJECTED_PINS = new Set(["000000", "111111", "123456", "654321", "121212"]);

export function storageKey(userId) {
  return `${STORAGE_PREFIX}${userId}`;
}

export function validatePin(pin) {
  if (!/^[0-9]{6,12}$/.test(pin)) {
    return "Use 6 to 12 digits.";
  }
  if (REJECTED_PINS.has(pin)) {
    return "That PIN is too easy to guess.";
  }
  return null;
}

export function validatePattern(pattern) {
  if (!/^[0-8]{4,9}$/.test(pattern)) {
    return "Connect at least 4 dots.";
  }
  if (new Set(pattern).size !== pattern.length) {
    return "Each dot can be used once.";
  }
  return null;
}

export function biometricCapability(nav = globalThis.navigator) {
  const credentials = nav && nav.credentials;
  if (!credentials || typeof credentials.create !== "function" || !globalThis.PublicKeyCredential) {
    return {
      supported: false,
      reason:
        "This browser cannot use a device authenticator. Komboe does not collect fingerprints or face data. Use your master password.",
    };
  }
  return {
    supported: true,
    reason:
      "On the web, biometrics stay inside the device authenticator (Touch ID, Windows Hello, or a security key) via a passkey with the PRF extension. Komboe never receives a biometric sample. The passkey control on the lock screen is the unlock. It stays unavailable until a PRF passkey is enrolled on this device.",
  };
}

function bytesToB64(bytes) {
  let text = "";
  for (const byte of bytes) {
    text += String.fromCharCode(byte);
  }
  return btoa(text);
}

function b64ToBytes(value) {
  const text = atob(value);
  const bytes = new Uint8Array(text.length);
  for (let i = 0; i < text.length; i += 1) {
    bytes[i] = text.charCodeAt(i);
  }
  return bytes;
}

async function wrappingKey(secret, salt) {
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), "PBKDF2", false, [
    "deriveKey",
  ]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: ITERATIONS, hash: "SHA-256" },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

/** A vault user key is 32 or 64 bytes. A session token or a short secret is refused. */
export function assertVaultUserKey(userKey) {
  if (!(userKey instanceof Uint8Array) || (userKey.byteLength !== 32 && userKey.byteLength !== 64)) {
    throw new Error("Refusing to wrap anything except a vault user key.");
  }
}

export async function enrollDeviceUnlock(userKey, secret, kind) {
  const problem = kind === "pin" ? validatePin(secret) : validatePattern(secret);
  if (problem) {
    throw new Error(problem);
  }
  assertVaultUserKey(userKey);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await wrappingKey(`${kind}:${secret}`, salt);
  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, userKey),
  );
  return {
    v: 1,
    kind,
    kdf: "PBKDF2-SHA256",
    iterations: ITERATIONS,
    salt: bytesToB64(salt),
    iv: bytesToB64(iv),
    ciphertext: bytesToB64(ciphertext),
    failures: 0,
    lastSuccess: Date.now(),
  };
}

export async function unlockDevice(record, secret) {
  if (!record || record.failures >= MAX_FAILURES) {
    return { wiped: true, record: null, userKey: null, expired: false, error: "Device unlock was removed." };
  }
  if (Date.now() - record.lastSuccess > UNLOCK_TTL_MS) {
    return {
      wiped: false,
      expired: true,
      record,
      userKey: null,
      error: "This device unlock expired. Use your master password, then enroll again.",
    };
  }
  try {
    const key = await wrappingKey(`${record.kind}:${secret}`, b64ToBytes(record.salt));
    const plain = new Uint8Array(
      await crypto.subtle.decrypt(
        { name: "AES-GCM", iv: b64ToBytes(record.iv) },
        key,
        b64ToBytes(record.ciphertext),
      ),
    );
    return {
      wiped: false,
      expired: false,
      userKey: plain,
      error: null,
      record: { ...record, failures: 0, lastSuccess: Date.now() },
    };
  } catch {
    const failures = record.failures + 1;
    if (failures >= MAX_FAILURES) {
      return { wiped: true, record: null, userKey: null, expired: false, error: "Too many attempts. Device unlock was removed." };
    }
    return {
      wiped: false,
      expired: false,
      userKey: null,
      error: "That PIN or pattern did not match.",
      record: { ...record, failures },
    };
  }
}

export function recordHoldsPlaintext(record, secret, userKey) {
  const text = JSON.stringify(record);
  if (secret && text.includes(secret)) {
    return true;
  }
  if (userKey && text.includes(bytesToB64(userKey))) {
    return true;
  }
  return false;
}
