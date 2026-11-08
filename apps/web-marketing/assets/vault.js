import { biometricCapability } from "./device-unlock.js";
import { passwordHash } from "./auth.js";

const INTERVALS = [
  [null, "Never"],
  [60, "1 minute"],
  [300, "5 minutes"],
  [600, "10 minutes"],
  [900, "15 minutes"],
  [1800, "30 minutes"],
  [3600, "1 hour"],
  [21600, "6 hours"],
  [86400, "24 hours"],
];

const TOKEN_KEY = "komboe.accessToken";

async function load() {
  const root = document.getElementById("dashboard");
  if (!root || root.dataset.mode === "signup") return;
  const status = document.getElementById("dash-status");
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (!token) {
    status.textContent = "Sign in on the home page to open this vault.";
    return;
  }
  const headers = { Authorization: "Bearer " + token, Accept: "application/json" };
  const profileResponse = await fetch("/api/accounts/profile", { headers, credentials: "omit" });
  if (profileResponse.status === 401 || profileResponse.status === 403) {
    sessionStorage.removeItem(TOKEN_KEY);
    status.textContent = "That sign-in expired. Sign in again on the home page.";
    return;
  }
  if (!profileResponse.ok) {
    status.textContent = "The vault could not be loaded. Try again in a moment.";
    return;
  }
  const profile = await profileResponse.json();
  let count = "—";
  const syncResponse = await fetch("/api/sync?excludeDomains=true", { headers, credentials: "omit" });
  if (syncResponse.ok) {
    const sync = await syncResponse.json();
    count = String((sync.ciphers || []).length);
  }
  status.hidden = true;
  document.getElementById("dash-email").textContent = profile.email || "";
  document.getElementById("dash-name").textContent = profile.name || "Your vault";
  document.getElementById("dash-count").textContent = count;
  document.getElementById("dash-body").hidden = false;
  const select = document.getElementById("email-interval");
  if (select && !select.options.length) {
    for (const [value, label] of INTERVALS) {
      const option = document.createElement("option");
      option.value = value == null ? "" : String(value);
      option.textContent = label;
      select.appendChild(option);
    }
  }
  const current = await fetch("/api/komboe/email-login-interval", { headers, credentials: "omit" });
  if (current.ok && select) {
    const body = await current.json();
    select.value = body.intervalSeconds == null ? "" : String(body.intervalSeconds);
  }
  document.getElementById("email-interval-save")?.addEventListener("click", async () => {
    const status = document.getElementById("email-interval-status");
    const password = document.getElementById("email-interval-password").value;
    if (!password) {
      status.textContent = "Enter your master password to confirm this change.";
      return;
    }
    const pre = await fetch("/identity/accounts/prelogin", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email: profile.email }),
      credentials: "omit",
    });
    if (!pre.ok) {
      status.textContent = "The change was not saved.";
      return;
    }
    const hash = await passwordHash(profile.email, password, await pre.json());
    const choice = select.value === "" ? null : Number(select.value);
    const saved = await fetch("/api/komboe/email-login-interval", {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      credentials: "omit",
      body: JSON.stringify({ intervalSeconds: choice, masterPasswordHash: hash }),
    });
    document.getElementById("email-interval-password").value = "";
    status.textContent = saved.ok
      ? "Saved. Devices must enter a new email code the next time this timer applies."
      : "The change was not saved. The master password was not accepted.";
  });
  const note = document.getElementById("device-unlock-note");
  if (note) {
    note.textContent = biometricCapability(navigator).reason
      + " A PIN or pattern enrolls in the web vault only after the master password has unlocked that device. This page does not hold the vault key, so it does not store a PIN, pattern, or biometric sample. A short PIN copied out of browser storage can be guessed offline; the wrong-attempt counter does not stop that.";
  }
}

document.getElementById("dash-logout")?.addEventListener("click", async () => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) {
    await fetch("/api/komboe/email-login-trust/clear", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + token,
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ token: sessionStorage.getItem("komboe.deviceTrust") || "" }),
      credentials: "omit",
    }).catch(() => {});
    sessionStorage.removeItem("komboe.deviceTrust");
  }
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem("komboe.agentSession");
  Object.keys(localStorage).forEach((key) => {
    if (key.startsWith("komboe.deviceUnlock.v1.")) localStorage.removeItem(key);
  });
  location.assign("../index.html#signin");
});

load().catch(() => {
  const status = document.getElementById("dash-status");
  if (status) status.textContent = "The vault could not be loaded. Try again in a moment.";
});
