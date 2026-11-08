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
}

document.getElementById("dash-logout")?.addEventListener("click", () => {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem("komboe.agentSession");
  location.assign("../index.html#signin");
});

load().catch(() => {
  const status = document.getElementById("dash-status");
  if (status) status.textContent = "The vault could not be loaded. Try again in a moment.";
});
