/* Vault crypto for the Komboe dashboard. Runs in the browser only.
   Matches komboe/platform/crypto.py: PBKDF2-SHA256, HKDF-Expand, AES-256-CBC + HMAC. */
function komboeUtf8(s) { return new TextEncoder().encode(s); }
function komboeB64(bytes) {
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = "";
  for (let i = 0; i < view.length; i++) bin += String.fromCharCode(view[i]);
  return btoa(bin);
}
function komboeUb64(s) {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
function komboeConcat(a, b) {
  const left = a instanceof Uint8Array ? a : new Uint8Array(a);
  const right = b instanceof Uint8Array ? b : new Uint8Array(b);
  const out = new Uint8Array(left.length + right.length);
  out.set(left, 0);
  out.set(right, left.length);
  return out;
}
async function komboeHmac(key, data) {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, data));
}
async function komboeHkdfExpand(prk, info) {
  const infoBytes = typeof info === "string" ? komboeUtf8(info) : info;
  const block = await komboeHmac(prk, komboeConcat(infoBytes, new Uint8Array([1])));
  return block.slice(0, 32);
}
async function komboeStretch(masterKey) {
  return komboeConcat(await komboeHkdfExpand(masterKey, "enc"), await komboeHkdfExpand(masterKey, "mac"));
}
async function komboePbkdf2(password, salt, iterations, length) {
  const pw = password instanceof Uint8Array ? password : komboeUtf8(password);
  const sa = salt instanceof Uint8Array ? salt : komboeUtf8(salt);
  const base = await crypto.subtle.importKey("raw", pw, "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: sa, iterations, hash: "SHA-256" },
    base,
    length * 8,
  );
  return new Uint8Array(bits);
}
async function komboeEnc(plain, key64) {
  const bytes = plain instanceof Uint8Array ? plain : komboeUtf8(plain);
  const ek = key64.slice(0, 32);
  const mk = key64.slice(32, 64);
  const iv = crypto.getRandomValues(new Uint8Array(16));
  const aes = await crypto.subtle.importKey("raw", ek, "AES-CBC", false, ["encrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-CBC", iv }, aes, bytes));
  const mac = await komboeHmac(mk, komboeConcat(iv, ct));
  return `2.${komboeB64(iv)}|${komboeB64(ct)}|${komboeB64(mac)}`;
}
async function komboeDec(token, key64) {
  if (!token.startsWith("2.")) throw new Error("unsupported ciphertext");
  const [ivB, ctB, macB] = token.slice(2).split("|");
  const iv = komboeUb64(ivB);
  const ct = komboeUb64(ctB);
  const mac = komboeUb64(macB);
  const expect = await komboeHmac(key64.slice(32, 64), komboeConcat(iv, ct));
  if (komboeB64(expect) !== komboeB64(mac)) throw new Error("MAC mismatch");
  const aes = await crypto.subtle.importKey("raw", key64.slice(0, 32), "AES-CBC", false, ["decrypt"]);
  return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-CBC", iv }, aes, ct));
}
async function komboeDecText(token, key64) {
  return new TextDecoder().decode(await komboeDec(token, key64));
}
async function komboePasswordHash(masterKey, password) {
  return komboeB64(await komboePbkdf2(masterKey, komboeUtf8(password), 1, 32));
}
globalThis.KomboeCrypto = {
  utf8: komboeUtf8, b64: komboeB64, ub64: komboeUb64, stretch: komboeStretch,
  pbkdf2: komboePbkdf2, enc: komboeEnc, dec: komboeDec, decText: komboeDecText,
  passwordHash: komboePasswordHash,
};
