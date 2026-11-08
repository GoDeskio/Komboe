const TOKEN_KEY = "komboe.accessToken";
const TRUST_KEY = "komboe.deviceTrust";
const DEVICE_KEY = "komboe.deviceId";

function bytes(text) {
  return new TextEncoder().encode(text);
}

function b64(data) {
  let text = "";
  data.forEach((value) => { text += String.fromCharCode(value); });
  return btoa(text);
}

async function pbkdf2(password, salt, iterations) {
  const key = await crypto.subtle.importKey("raw", password, "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({
    name: "PBKDF2",
    hash: "SHA-256",
    salt,
    iterations,
  }, key, 256);
  return new Uint8Array(bits);
}

async function masterKey(email, password, pre) {
  if (pre.kdf === 1) {
    const salt = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes(email)));
    const hash = await globalThis.hashwasm.argon2id({
      password,
      salt,
      iterations: pre.kdfIterations,
      parallelism: pre.kdfParallelism || 4,
      memorySize: (pre.kdfMemory || 64) * 1024,
      hashLength: 32,
      outputType: "binary",
    });
    return new Uint8Array(hash);
  }
  return pbkdf2(bytes(password), bytes(email), pre.kdfIterations || 600000);
}

export async function passwordHash(email, password, pre) {
  const key = await masterKey(email, password, pre);
  return b64(await pbkdf2(key, bytes(password), 1));
}

async function openKdfEmail(rawKey, envelope) {
  const text = atob(envelope);
  const packed = new Uint8Array(text.length);
  for (let i = 0; i < text.length; i += 1) packed[i] = text.charCodeAt(i);
  if (packed.length !== 12 + 128 + 16) throw new Error("That login name was not accepted.");
  const key = await crypto.subtle.importKey("raw", rawKey, "AES-GCM", false, ["decrypt"]);
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: packed.slice(0, 12) },
    key,
    packed.slice(12),
  );
  const email = new TextDecoder().decode(plain).replace(/\0+$/g, "");
  if (!email.includes("@")) throw new Error("That login name was not accepted.");
  return email;
}

function deviceId() {
  let id = sessionStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

function showError(node, text) {
  node.hidden = false;
  node.textContent = text;
}

function clearError(node) {
  node.hidden = true;
  node.textContent = "";
}

async function readJson(response) {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return { message: "Komboe could not be reached. Try again in a moment." }; }
}

function loginMessage(body, status) {
  if (status === 429) return "Too many sign-in attempts. Wait a minute and try again.";
  const message = body.message || body.error_description || body.Message || "";
  if (/username or password is incorrect/i.test(message)) return "Email or master password is incorrect.";
  if (/two-step token is invalid/i.test(message)) return "That two-step code is incorrect.";
  if (message && message.length < 240 && !/[<>]/.test(message)) return message;
  return "Sign-in did not succeed. Check the email and master password.";
}

function providerId(body) {
  const ids = (body.TwoFactorProviders || []).map(String);
  if (ids.includes("0")) return "0";
  if (ids.includes("1")) return "1";
  return ids[0] || "0";
}

function providerLabel(id) {
  if (id === "1") return "Email code";
  if (id === "3") return "Security key code";
  if (id === "7") return "Security key";
  return "Authenticator code";
}

async function tokenRequest(email, hash, extra) {
  const form = new URLSearchParams({
    grant_type: "password",
    username: email,
    password: hash,
    scope: "api offline_access",
    client_id: "web",
    deviceType: "9",
    deviceIdentifier: deviceId(),
    deviceName: "Komboe",
  });
  Object.entries(extra || {}).forEach(([key, value]) => form.set(key, value));
  return fetch("/identity/connect/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
      "Bitwarden-Client-Name": "web",
      "Bitwarden-Client-Version": "2026.10.1",
    },
    body: form,
    credentials: "omit",
  });
}

export async function profileOk(token) {
  const response = await fetch("/api/accounts/profile", {
    headers: { Authorization: "Bearer " + token, Accept: "application/json" },
    credentials: "omit",
  });
  if (!response.ok) return null;
  return readJson(response);
}

function signedInView(form, open) {
  form.hidden = true;
  open.hidden = false;
}

async function boot() {
  const form = document.getElementById("login-form");
  if (!form) return;
  const open = document.getElementById("open-dashboard");
  const error = document.getElementById("login-error");
  const twoFactor = document.getElementById("twofactor");
  const code = document.getElementById("twofactor-code");
  const codeLabel = document.getElementById("twofactor-label");
  const submit = document.getElementById("login-submit");
  let busy = false;
  let pending = null;
  let emailCodeSent = false;

  const existing = sessionStorage.getItem(TOKEN_KEY);
  if (existing) {
    const profile = await profileOk(existing).catch(() => null);
    if (profile) {
      signedInView(form, open);
      return;
    }
    sessionStorage.removeItem(TOKEN_KEY);
  }

  document.getElementById("email")?.addEventListener("input", () => {
    pending = null;
    twoFactor.hidden = true;
    code.value = "";
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    submit.disabled = true;
    clearError(error);
    const typed = document.getElementById("email").value.trim().toLowerCase();
    const password = document.getElementById("master-password").value;
    try {
      let accountEmail = typed;
      let hash = !twoFactor.hidden && pending && pending.typed === typed ? pending.hash : null;
      if (!hash) {
        const pre = await fetch("/identity/accounts/prelogin", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ email: typed }),
          credentials: "omit",
        });
        const preBody = await readJson(pre);
        if (pre.status === 429) {
          showError(error, loginMessage(preBody, 429));
          return;
        }
        if (!pre.ok) {
          showError(error, loginMessage(preBody, pre.status));
          return;
        }
        if (!typed.includes("@")) {
          const opened = await fetch("/identity/accounts/login-name/open", {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ name: typed }),
            credentials: "omit",
          });
          const openedBody = await readJson(opened);
          if (!opened.ok || !openedBody.envelope || !openedBody.envelopeSalt) {
            showError(error, loginMessage(openedBody, opened.status));
            return;
          }
          try {
            const wrappingKey = await masterKey(openedBody.envelopeSalt, password, openedBody);
            accountEmail = await openKdfEmail(wrappingKey, openedBody.envelope);
          } catch {
            showError(error, "Email or master password is incorrect.");
            return;
          }
          hash = await passwordHash(accountEmail, password, openedBody);
        } else {
          accountEmail = typeof preBody.kdfEmail === "string" && preBody.kdfEmail.includes("@")
            ? preBody.kdfEmail.trim()
            : typed;
          hash = await passwordHash(accountEmail, password, preBody);
        }
        pending = { typed, hash, accountEmail };
      } else {
        accountEmail = pending.accountEmail;
      }
      const extra = {};
      const storedTrust = sessionStorage.getItem(TRUST_KEY);
      if (storedTrust) extra.komboeDeviceTrust = storedTrust;
      if (!twoFactor.hidden && code.value.trim()) {
        extra.twoFactorProvider = twoFactor.dataset.provider || "0";
        extra.twoFactorToken = code.value.trim();
        extra.twoFactorRemember = "0";
        if (pending && pending.challenge) extra.komboeLoginChallenge = pending.challenge;
      }
      const response = await tokenRequest(accountEmail, hash, extra);
      const body = await readJson(response);
      if (response.status === 429) {
        showError(error, loginMessage(body, 429));
        return;
      }
      if (body.TwoFactorProviders) {
        pending = { typed, hash, accountEmail, challenge: body.KomboeLoginChallenge || "" };
        const id = providerId(body);
        twoFactor.hidden = false;
        twoFactor.dataset.provider = id;
        codeLabel.textContent = providerLabel(id);
        code.required = true;
        code.focus();
        if (id === "1" && !emailCodeSent) {
          emailCodeSent = true;
          const sent = await fetch("/api/two-factor/send-email-login", {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({
              email: accountEmail,
              masterPasswordHash: hash,
              deviceIdentifier: deviceId(),
              komboeLoginChallenge: (pending && pending.challenge) || "",
            }),
            credentials: "omit",
          });
          if (!sent.ok) {
            const sentBody = await readJson(sent);
            showError(error, sentBody.message || "The sign-in code could not be sent. Sign-in was not completed.");
            return;
          }
        }
        showError(error, id === "1"
          ? "Enter the code sent to your email."
          : "Enter the two-step code for this account.");
        return;
      }
      if (!response.ok || !body.access_token) {
        showError(error, loginMessage(body, response.status));
        return;
      }
      sessionStorage.setItem(TOKEN_KEY, body.access_token);
      if (body.KomboeDeviceTrust) sessionStorage.setItem(TRUST_KEY, body.KomboeDeviceTrust);
      pending = null;
      document.getElementById("master-password").value = "";
      code.value = "";
      location.assign("vault/");
    } catch {
      showError(error, "Komboe could not be reached. Try again in a moment.");
    } finally {
      busy = false;
      submit.disabled = false;
    }
  });
}

boot();
