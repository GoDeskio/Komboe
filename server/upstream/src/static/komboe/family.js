"use strict";
// Komboe Family & Company console. All key material is generated/wrapped in this browser.
const $ = (id) => document.getElementById(id);
const te = new TextEncoder();
const b64 = (u8) => btoa(String.fromCharCode(...new Uint8Array(u8)));
let S = { at: null, me: null, orgs: [], cur: null };
const ROLE = ["Owner", "Admin", "User", "Manager", "Custom"], STATUS = { "-1": "Revoked", 0: "Invited", 1: "Accepted", 2: "Confirmed" };

async function api(method, path, body) {
  const h = { "Content-Type": "application/json", Accept: "application/json", "Device-Type": "9", "Bitwarden-Client-Name": "web", "Bitwarden-Client-Version": "2026.10.1" };
  if (S.at) h.Authorization = "Bearer " + S.at;
  const r = await fetch(path, { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body) });
  const t = await r.text(); let j = null; try { j = t ? JSON.parse(t) : null; } catch (e) { j = { message: t }; }
  if (!r.ok) throw new Error((j && (j.message || (j.errorModel && j.errorModel.message))) || r.status);
  return j;
}
async function pbkdf2(pw, salt, it) {
  const k = await crypto.subtle.importKey("raw", typeof pw === "string" ? te.encode(pw) : pw, "PBKDF2", false, ["deriveBits"]);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: te.encode(salt), iterations: it }, k, 256));
}
async function login(email, pw) {
  const pre = await api("POST", "/identity/accounts/prelogin", { email });
  const kdf = pre.kdf ?? pre.Kdf, it = pre.kdfIterations ?? pre.KdfIterations;
  if (kdf !== 0) throw new Error("This console supports PBKDF2 accounts; use the main web vault for Argon2id accounts.");
  const mk = await pbkdf2(pw, email.toLowerCase().trim(), it);
  const hash = b64(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: te.encode(pw), iterations: 1 },
    await crypto.subtle.importKey("raw", mk, "PBKDF2", false, ["deriveBits"]), 256));
  const dev = localStorage.getItem("komboeConsoleDevice") || crypto.randomUUID(); localStorage.setItem("komboeConsoleDevice", dev);
  const form = new URLSearchParams({ grant_type: "password", username: email, password: hash, scope: "api offline_access", client_id: "web", deviceType: "9", deviceIdentifier: dev, deviceName: "Komboe Family console" });
  const r = await fetch("/identity/connect/token", { method: "POST", body: form, headers: { "Device-Type": "9", "Bitwarden-Client-Name": "web", "Bitwarden-Client-Version": "2026.10.1" } });
  const j = await r.json(); if (!r.ok) throw new Error(j.error_description || j.message || "Login failed");
  if (!j.access_token) throw new Error("Two-step login is not supported in this console yet; use the main web vault.");
  S.at = j.access_token; S.me = JSON.parse(atob(S.at.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
}
// Bitwarden type-2 EncString: AES-256-CBC + HMAC-SHA256 with a 64-byte key (enc||mac).
async function encString(data, key64) {
  const iv = crypto.getRandomValues(new Uint8Array(16));
  const ek = await crypto.subtle.importKey("raw", key64.slice(0, 32), "AES-CBC", false, ["encrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-CBC", iv }, ek, data));
  const mk = await crypto.subtle.importKey("raw", key64.slice(32), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", mk, new Uint8Array([...iv, ...ct]));
  return "2." + b64(iv) + "|" + b64(ct) + "|" + b64(mac);
}
async function createOrg(name) {
  // Org symmetric key and org RSA keypair are generated here; the server only sees wrapped values.
  const pub = await api("GET", `/api/users/${S.me.sub}/public-key`);
  const userPub = await crypto.subtle.importKey("spki", Uint8Array.from(atob(pub.publicKey), (c) => c.charCodeAt(0)), { name: "RSA-OAEP", hash: "SHA-1" }, false, ["encrypt"]);
  const ok = crypto.getRandomValues(new Uint8Array(64));
  const kp = await crypto.subtle.generateKey({ name: "RSA-OAEP", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-1" }, true, ["encrypt", "decrypt"]);
  const r = await api("POST", "/api/organizations", {
    name, billingEmail: S.me.email, planType: 0,
    key: "4." + b64(await crypto.subtle.encrypt({ name: "RSA-OAEP" }, userPub, ok)),
    collectionName: await encString(te.encode("Default collection"), ok),
    keys: { publicKey: b64(await crypto.subtle.exportKey("spki", kp.publicKey)), encryptedPrivateKey: await encString(new Uint8Array(await crypto.subtle.exportKey("pkcs8", kp.privateKey)), ok) },
  });
  return r.id;
}
function td(tr, v) { const c = document.createElement("td"); c.textContent = v; tr.appendChild(c); return c; }
function btn(cell, label, fn, alt) { const b = document.createElement("button"); b.textContent = label; if (alt) b.className = "alt"; b.onclick = () => fn().catch(showErr); cell.appendChild(b); cell.append(" "); }
function showErr(e) { $("orgMsg").textContent = e.message || String(e); }

async function loadOrgs() {
  const p = await api("GET", "/api/accounts/profile"); S.orgs = p.organizations || [];
  const box = $("orgs"); box.textContent = "";
  if (!S.orgs.length) box.textContent = "You are not in any organization yet.";
  for (const o of S.orgs) {
    const d = document.createElement("div"); d.className = "org";
    const n = document.createElement("strong"); n.textContent = o.name; d.appendChild(n);
    const r = document.createElement("span"); r.className = "pill"; r.textContent = ROLE[o.type] || o.type; d.appendChild(r);
    btn(d, "Open", () => openOrg(o)); box.appendChild(d);
  }
  await loadMine();
}
async function openOrg(o) {
  S.cur = o; $("orgView").hidden = false; $("orgTitle").textContent = o.name; $("orgMsg").textContent = "";
  const admin = o.type === 0 || o.type === 1;
  const plan = await api("GET", `/api/komboe/organizations/${o.id}/plan`);
  $("planKind").value = plan.kind; $("planSeats").value = plan.seats; $("planPrice").value = plan.pricePerMemberCents;
  $("planForm").querySelectorAll("input,select,button").forEach((e) => (e.disabled = o.type !== 0));
  $("planInfo").textContent = `${plan.seatsUsed} of ${plan.seats} seats used` + (plan.parentOrganizationId ? " · split off from another family" : "");
  try { const q = await api("GET", `/api/komboe/organizations/${o.id}/billing/quote`);
    $("quote").textContent = `Monthly estimate: ${q.seatsUsed} × $${(q.pricePerMemberCents / 100).toFixed(2)} = $${(q.monthlyTotalCents / 100).toFixed(2)} · billing: ${q.providerStatus}`;
  } catch (e) { $("quote").textContent = ""; }
  const mb = $("members").querySelector("tbody"); mb.textContent = "";
  const sb = $("splits").querySelector("tbody"); sb.textContent = "";
  $("members").hidden = $("splits").hidden = !admin; $("splitForm").hidden = o.type === 0;
  if (!admin) return;
  for (const m of (await api("GET", `/api/komboe/organizations/${o.id}/members`)).data) {
    const tr = document.createElement("tr"); [m.email, m.name || "", ROLE[m.type] || m.type, STATUS[m.status] ?? m.status, m.twoFactorEnabled ? "On" : "Off", m.personalItemCount, m.vaultReadable ? "yes" : "No (encrypted)"].forEach((v) => td(tr, v)); mb.appendChild(tr);
  }
  for (const s of (await api("GET", `/api/komboe/organizations/${o.id}/split-requests`)).data) {
    const tr = document.createElement("tr"); [s.email, s.note || "", s.status].forEach((v) => td(tr, v)); const c = td(tr, "");
    if (s.status === "pending" && s.userId !== S.me.sub) {
      btn(c, "Approve", async () => { await api("POST", `/api/komboe/split-requests/${s.id}/approve`); await openOrg(o); });
      btn(c, "Deny", async () => { await api("POST", `/api/komboe/split-requests/${s.id}/deny`); await openOrg(o); }, true);
    }
    sb.appendChild(tr);
  }
}
async function loadMine() {
  const rows = []; for (const o of S.orgs) if (o.type !== 0) {
    try { for (const s of (await api("GET", `/api/komboe/organizations/${o.id}/split-requests`)).data) if (s.userId === S.me.sub) rows.push([o, s]); } catch (e) {}
  }
  $("mine").hidden = !rows.length; const tb = $("mySplits").querySelector("tbody"); tb.textContent = "";
  for (const [o, s] of rows) {
    const tr = document.createElement("tr"); td(tr, o.name); td(tr, s.status); const c = td(tr, "");
    if (s.status === "approved") btn(c, "Create my family and move", async () => {
      const name = prompt("Name for your new family", "My family"); if (!name) return;
      const nid = await createOrg(name);
      await api("POST", `/api/komboe/split-requests/${s.id}/complete`, { newOrganizationId: nid });
      await loadOrgs(); await openOrg(S.orgs.find((x) => x.id === nid));
    });
    tb.appendChild(tr);
  }
}
$("loginForm").onsubmit = async (e) => { e.preventDefault(); $("loginErr").textContent = "";
  try { await login($("email").value, $("password").value); $("password").value = ""; $("login").hidden = true; $("app").hidden = false; await loadOrgs(); }
  catch (er) { $("loginErr").textContent = er.message; } };
$("newOrgForm").onsubmit = async (e) => { e.preventDefault();
  try { const id = await createOrg($("newOrgName").value); await api("PUT", `/api/komboe/organizations/${id}/plan`, { kind: $("newOrgKind").value });
    $("newOrgName").value = ""; await loadOrgs(); await openOrg(S.orgs.find((x) => x.id === id)); } catch (er) { showErr(er); } };
$("planForm").onsubmit = async (e) => { e.preventDefault();
  try { await api("PUT", `/api/komboe/organizations/${S.cur.id}/plan`, { kind: $("planKind").value, seats: +$("planSeats").value, pricePerMemberCents: +$("planPrice").value }); await openOrg(S.cur); } catch (er) { showErr(er); } };
$("splitForm").onsubmit = async (e) => { e.preventDefault();
  try { await api("POST", `/api/komboe/organizations/${S.cur.id}/split-requests`, { note: $("splitNote").value }); $("splitNote").value = ""; $("orgMsg").textContent = "Request sent to your family admin."; await loadMine(); } catch (er) { showErr(er); } };
