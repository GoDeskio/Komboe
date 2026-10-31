// Komboe: native KeePass (KDBX 4) export. Runs entirely on the client: the vault is decrypted
// locally, re-encrypted into the KDBX container with the export password, and only written to disk.
import { argon2d, argon2id } from "hash-wasm";
import * as kdbxweb from "kdbxweb";

type ExportField = { name?: string; value?: string; type?: number };
type ExportItem = {
  type: number;
  name?: string;
  notes?: string;
  folderId?: string | null;
  favorite?: boolean;
  login?: {
    username?: string;
    password?: string;
    totp?: string;
    uris?: { uri?: string }[];
  };
  card?: Record<string, string | null>;
  identity?: Record<string, string | null>;
  sshKey?: Record<string, string | null>;
  fields?: ExportField[];
};
type ExportJson = { folders?: { id: string; name: string }[]; items?: ExportItem[] };

const HIDDEN_FIELD = 1;
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

function setField(
  entry: kdbxweb.KdbxEntry,
  name: string,
  value: string | null | undefined,
  secret = false,
) {
  if (value == null || value === "") {
    return;
  }
  let key = name;
  for (let i = 2; entry.fields.has(key); i++) {
    key = `${name} (${i})`;
  }
  entry.fields.set(key, secret ? kdbxweb.ProtectedValue.fromString(value) : value);
}

function addSection(
  entry: kdbxweb.KdbxEntry,
  prefix: string,
  data: Record<string, string | null> | undefined,
  secretKeys: string[],
) {
  for (const [k, v] of Object.entries(data ?? {})) {
    if (typeof v === "string") {
      setField(entry, `${prefix}${k}`, v, secretKeys.includes(k));
    }
  }
}

/** Converts a decrypted Komboe JSON export into a password-protected KDBX 4 file. */
export async function buildKdbx(exportJson: string, password: string): Promise<Uint8Array> {
  if (!password) {
    throw new Error("A password is required for a KeePass (kdbx) export.");
  }
  ensureArgon2();
  const data = JSON.parse(exportJson) as ExportJson;
  const creds = new kdbxweb.Credentials(kdbxweb.ProtectedValue.fromString(password));
  const db = kdbxweb.Kdbx.create(creds, "Komboe export");
  const root = db.getDefaultGroup();
  const groups = new Map<string, kdbxweb.KdbxGroup>();
  for (const f of data.folders ?? []) {
    // Nested folder names ("a/b") become nested KeePass groups.
    let parent = root;
    let path = "";
    for (const part of f.name.split("/")) {
      path = path ? `${path}/${part}` : part;
      let g = groups.get(`path:${path}`);
      if (!g) {
        g = db.createGroup(parent, part);
        groups.set(`path:${path}`, g);
      }
      parent = g;
    }
    groups.set(f.id, parent);
  }

  for (const item of data.items ?? []) {
    const entry = db.createEntry(groups.get(item.folderId ?? "") ?? root);
    entry.fields.set("Title", item.name ?? "");
    entry.fields.set("Notes", item.notes ?? "");
    if (item.login) {
      entry.fields.set("UserName", item.login.username ?? "");
      entry.fields.set("Password", kdbxweb.ProtectedValue.fromString(item.login.password ?? ""));
      const uris = (item.login.uris ?? []).map((u) => u.uri).filter((u): u is string => !!u);
      entry.fields.set("URL", uris[0] ?? "");
      uris.slice(1).forEach((u, i) => setField(entry, `KP2A_URL_${i + 1}`, u));
      setField(entry, "otp", item.login.totp, true);
    }
    addSection(entry, "Card ", item.card, ["number", "code"]);
    addSection(entry, "Identity ", item.identity, ["ssn", "passportNumber", "licenseNumber"]);
    addSection(entry, "SSH ", item.sshKey, ["privateKey"]);
    for (const field of item.fields ?? []) {
      setField(entry, field.name || "Field", field.value, field.type === HIDDEN_FIELD);
    }
    if (item.favorite) {
      entry.tags.push("favorite");
    }
  }
  return new Uint8Array(await db.save());
}
