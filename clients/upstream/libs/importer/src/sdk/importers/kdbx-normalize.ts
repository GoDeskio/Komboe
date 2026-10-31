// Komboe: KeePass writers (KeePass 2.x, pykeepass, KeePassXC) may emit an entry's <String>
// elements after <AutoType>/<History>; the SDK's strict KDBX reader rejects that order. This
// re-serializes the database client-side with kdbxweb (same credentials, same KDBX version) so the
// SDK can parse it. Nothing leaves the device; the decrypted XML never reaches the server.
import { argon2d, argon2id } from "hash-wasm";
import * as kdbxweb from "kdbxweb";

let argon2Ready = false;

function ensureArgon2() {
  if (argon2Ready) {
    return;
  }
  kdbxweb.CryptoEngine.setArgon2Impl(
    async (password, salt, memory, iterations, length, parallelism, type) => {
      const fn = type === kdbxweb.CryptoEngine.Argon2TypeArgon2id ? argon2id : argon2d;
      const out = await fn({
        password: new Uint8Array(password),
        salt: new Uint8Array(salt),
        memorySize: memory,
        iterations,
        hashLength: length,
        parallelism,
        outputType: "binary",
      });
      return out.buffer.slice(out.byteOffset, out.byteOffset + out.byteLength) as ArrayBuffer;
    },
  );
  argon2Ready = true;
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

/** Returns a canonically ordered copy of the KDBX file, or null if kdbxweb cannot open it. */
export async function normalizeKdbx(
  file: Uint8Array,
  password: string,
  keyFile?: Uint8Array | null,
): Promise<Uint8Array | null> {
  ensureArgon2();
  try {
    const credentials = new kdbxweb.Credentials(
      kdbxweb.ProtectedValue.fromString(password ?? ""),
      keyFile ? toArrayBuffer(keyFile) : null,
    );
    await credentials.ready;
    const db = await kdbxweb.Kdbx.load(toArrayBuffer(file), credentials);
    return new Uint8Array(await db.save());
  } catch {
    return null;
  }
}
