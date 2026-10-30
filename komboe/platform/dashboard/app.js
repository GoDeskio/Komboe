const C = globalThis.KomboeCrypto;
const app = document.querySelector("#app");
const state = {
  email: "",
  token: "",
  userKey: null,
  items: [],
  selected: null,
  query: "",
  error: "",
  busy: false,
  mode: "vault",
};

function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("komboe-theme", next);
  const logo = document.querySelector("[data-testid=logo]");
  if (logo) {
    logo.src = next === "dark" ? "/brand/komboe-dark-transparent.png" : "/brand/komboe-light-transparent.png";
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = "Bearer " + state.token;
  const res = await fetch(path, {
    method: opts.method || (opts.body ? "POST" : "GET"),
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || "request failed");
  return data;
}

function brand(large) {
  const theme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  const src = theme === "dark" ? "/brand/komboe-dark-transparent.png" : "/brand/komboe-light-transparent.png";
  return `<div class="brand-row">
    <img data-testid="logo" src="${src}" alt="" height="${large ? 44 : 36}">
    <div class="wordmark" data-testid="wordmark" style="font-size:${large ? 28 : 22}px">Komboe</div>
  </div>`;
}

function renderAuth() {
  app.innerHTML = `<main class="auth"><section class="auth-card">
    ${brand(true)}
    <p class="lede">A private vault with a calm, three-pane layout. Your master password is used only on this device.</p>
    <form id="authForm">
      <label>Email <input data-testid="email" type="email" autocomplete="username" required></label>
      <label>Master password <input data-testid="password" type="password" autocomplete="current-password" required minlength="12"></label>
      <div class="row">
        <button class="primary" type="submit" data-testid="create-account">Create account</button>
        <button class="ghost" type="button" data-testid="unlock">Unlock</button>
      </div>
      <p class="err" data-testid="auth-error">${esc(state.error)}</p>
      <p class="fine">End-to-end encrypted. The server stores ciphertext and a one-way password hash, never the master password or vault keys.</p>
    </form>
  </section></main>`;
  const form = document.querySelector("#authForm");
  form.email = form.querySelector("[data-testid=email]");
  form.addEventListener("submit", (ev) => { ev.preventDefault(); unlock(true); });
  form.querySelector("[data-testid=unlock]").addEventListener("click", () => unlock(false));
  const email = form.querySelector("[data-testid=email]");
  const password = form.querySelector("[data-testid=password]");
  email.value = state.email || "";
  form.querySelector("[data-testid=create-account]").disabled = state.busy;
}

async function derive(email, password) {
  const master = await C.pbkdf2(password, C.utf8(email), 600000, 32);
  const hash = await C.passwordHash(master, password);
  const stretched = await C.stretch(master);
  return { master, hash, stretched };
}

async function unlock(create) {
  const email = document.querySelector("[data-testid=email]").value.trim().toLowerCase();
  const password = document.querySelector("[data-testid=password]").value;
  state.busy = true; state.error = ""; state.email = email; renderAuth();
  try {
    const { hash, stretched } = await derive(email, password);
    if (create) {
      const userKey = crypto.getRandomValues(new Uint8Array(64));
      const protectedKey = await C.enc(userKey, stretched);
      await api("/api/accounts/register", { body: {
        email, name: email.split("@")[0], masterPasswordHash: hash,
        kdfIterations: 600000, userSymmetricKey: protectedKey,
      } });
      state.userKey = userKey;
    }
    const session = await api("/identity/login", { body: { email, masterPasswordHash: hash } });
    if (session.vaultKeyIncluded !== false) throw new Error("server returned a vault key");
    state.token = session.accessToken;
    if (!state.userKey) state.userKey = await C.dec(session.userSymmetricKey, stretched);
    sessionStorage.setItem("komboe-session", JSON.stringify({
      email, token: state.token, userKey: C.b64(state.userKey),
    }));
    await refresh();
    state.mode = "vault";
    render();
  } catch (err) {
    state.error = err.message;
    state.busy = false;
    renderAuth();
  }
}

async function refresh() {
  const sync = await api("/api/sync");
  const items = [];
  for (const row of sync.ciphers) {
    const name = await C.decText(row.name, state.userKey);
    const data = row.data ? JSON.parse(await C.decText(row.data, state.userKey)) : {};
    items.push({ id: row.id, type: row.type, name, data });
  }
  state.items = items;
  if (state.selected) state.selected = items.find((i) => i.id === state.selected.id) || null;
}

function filtered() {
  const q = state.query.trim().toLowerCase();
  if (!q) return state.items;
  return state.items.filter((i) => i.name.toLowerCase().includes(q) || (i.data.username || "").toLowerCase().includes(q));
}

function renderVault() {
  const rows = filtered().map((item) => `<button class="item" data-id="${esc(item.id)}" aria-selected="${state.selected && state.selected.id === item.id}">
      <span class="avatar">${esc(item.name.slice(0, 1).toUpperCase())}</span>
      <span><b>${esc(item.name)}</b><span>${esc(item.data.username || "Login")}</span></span>
    </button>`).join("");
  const detail = state.mode === "edit" ? editor() : viewer();
  app.innerHTML = `<div class="shell">
    <aside class="sidebar" data-testid="sidebar">
      ${brand(false)}
      <button class="nav-btn" aria-current="page" type="button">Vault</button>
      <div class="side-foot">
        <div class="who" data-testid="who">${esc(state.email)}</div>
        <button class="ghost" type="button" data-testid="theme-toggle">Light / dark</button>
        <button class="ghost" type="button" data-testid="lock">Lock</button>
      </div>
    </aside>
    <section class="list" data-testid="list">
      <div class="list-head">
        <input data-testid="search" type="text" placeholder="Search vault" value="${esc(state.query)}">
        <button class="icon-btn" type="button" data-testid="new-item" aria-label="New item">+</button>
      </div>
      <div class="items" data-testid="items">${rows || `<div class="empty">${state.query ? "Nothing matches" : "No items yet. Create one with the plus button."}</div>`}</div>
    </section>
    <section class="detail" data-testid="detail">${detail}</section>
  </div>`;
  document.querySelector("[data-testid=theme-toggle]").addEventListener("click", () => {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });
  document.querySelector("[data-testid=lock]").addEventListener("click", () => {
    sessionStorage.removeItem("komboe-session");
    state.token = ""; state.userKey = null; state.items = []; state.selected = null; state.mode = "vault";
    renderAuth();
  });
  document.querySelector("[data-testid=new-item]").addEventListener("click", () => {
    state.mode = "edit"; state.selected = { id: null, name: "", data: { username: "", password: "", uri: "" } };
    renderVault();
  });
  const search = document.querySelector("[data-testid=search]");
  search.addEventListener("input", () => { state.query = search.value; renderVault(); document.querySelector("[data-testid=search]").focus(); });
  document.querySelectorAll(".item").forEach((btn) => btn.addEventListener("click", () => {
    state.selected = state.items.find((i) => i.id === btn.dataset.id) || null;
    state.mode = "vault";
    renderVault();
  }));
  bindDetail();
}

function viewer() {
  if (!state.selected) return `<div class="detail-inner"><h2>Your vault</h2><p class="fine">Select an item, or create one. Nothing in this pane is sent to the server as plaintext.</p></div>`;
  const item = state.selected;
  return `<div class="detail-inner">
    <h2 data-testid="detail-name">${esc(item.name)}</h2>
    <div class="secret"><div><span>Username</span><b data-testid="detail-username">${esc(item.data.username || "")}</b></div></div>
    <div class="secret"><div><span>Password</span><b data-testid="detail-password">${esc(item.data.password || "")}</b></div></div>
    <div class="secret"><div><span>Website</span><b>${esc(item.data.uri || "")}</b></div></div>
    <div class="actions"><button class="danger" type="button" data-testid="delete-item">Delete</button></div>
  </div>`;
}

function editor() {
  const item = state.selected;
  return `<div class="detail-inner"><h2>New login</h2>
    <label>Name <input data-testid="item-name" type="text" value="${esc(item.name)}"></label>
    <label>Username <input data-testid="item-username" type="text" value="${esc(item.data.username || "")}"></label>
    <label>Password <input data-testid="item-password" type="text" value="${esc(item.data.password || "")}"></label>
    <label>Website <input data-testid="item-uri" type="url" value="${esc(item.data.uri || "")}"></label>
    <p class="err">${esc(state.error)}</p>
    <div class="actions">
      <button class="primary" type="button" data-testid="save-item">Save</button>
      <button class="ghost" type="button" data-testid="cancel-item">Cancel</button>
    </div>
  </div>`;
}

function bindDetail() {
  const save = document.querySelector("[data-testid=save-item]");
  if (save) {
    save.addEventListener("click", saveItem);
    document.querySelector("[data-testid=cancel-item]").addEventListener("click", () => {
      state.mode = "vault"; state.selected = null; state.error = ""; renderVault();
    });
  }
  const del = document.querySelector("[data-testid=delete-item]");
  if (del) del.addEventListener("click", async () => {
    await api("/api/ciphers/" + state.selected.id, { method: "DELETE" });
    state.selected = null;
    await refresh();
    renderVault();
  });
}

async function saveItem() {
  const name = document.querySelector("[data-testid=item-name]").value.trim();
  const data = {
    username: document.querySelector("[data-testid=item-username]").value,
    password: document.querySelector("[data-testid=item-password]").value,
    uri: document.querySelector("[data-testid=item-uri]").value,
  };
  if (!name) { state.error = "Name is required"; renderVault(); return; }
  const body = {
    type: 1,
    name: await C.enc(name, state.userKey),
    data: await C.enc(JSON.stringify(data), state.userKey),
    passwordChangedAt: new Date().toISOString(),
  };
  await api("/api/ciphers", { body });
  state.mode = "vault"; state.error = "";
  await refresh();
  state.selected = state.items.find((i) => i.name === name) || null;
  renderVault();
}

function render() {
  if (state.token && state.userKey) renderVault();
  else renderAuth();
}

applyTheme(localStorage.getItem("komboe-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
try {
  const saved = JSON.parse(sessionStorage.getItem("komboe-session") || "null");
  if (saved && saved.token && saved.userKey) {
    state.email = saved.email; state.token = saved.token; state.userKey = C.ub64(saved.userKey);
    refresh().then(render).catch(() => { sessionStorage.removeItem("komboe-session"); renderAuth(); });
  } else renderAuth();
} catch { renderAuth(); }
