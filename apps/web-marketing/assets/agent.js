const TOKEN_KEY = "komboe.accessToken";
const SESSION_KEY = "komboe.agentSession";

function out(text) {
  const node = document.getElementById("assistant-out");
  if (node) node.textContent = text;
}

async function session() {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  const cached = sessionStorage.getItem(SESSION_KEY);
  if (cached) return { token, id: cached };
  const response = await fetch("/api/komboe/agent/session", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: "{}",
    credentials: "omit",
  });
  if (response.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY);
    return null;
  }
  if (!response.ok) return null;
  const body = await response.json();
  sessionStorage.setItem(SESSION_KEY, body.sessionId);
  return { token, id: body.sessionId };
}

let busy = false;

async function act(action, args) {
  if (busy) return;
  const box = await session();
  if (!box) {
    out("Sign in on the home page. This assistant uses your Komboe agent and does not read vault items.");
    return;
  }
  busy = true;
  document.querySelectorAll("#assistant button").forEach((button) => { button.disabled = true; });
  try {
    const response = await fetch("/api/komboe/agent/act", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + box.token,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      credentials: "omit",
      body: JSON.stringify({ sessionId: box.id, action, args: args || {} }),
    });
    if (response.status === 429) {
      out("Too many assistant requests. Wait a minute and try again.");
      return;
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      out(body.message || "The assistant could not complete that.");
      return;
    }
    const result = body.result || {};
    if (result.password) {
      out("Generated password (not saved): " + result.password);
      return;
    }
    if (result.explanation) {
      out(result.explanation);
      return;
    }
    if (result.steps) {
      out(result.steps.map((step) => step.title + " — " + step.why).join("\n"));
      return;
    }
    if (result.items) {
      out(result.items.map((item) => item.title).join("\n"));
      return;
    }
    out("Done.");
  } catch {
    out("The assistant could not be reached. Try again in a moment.");
  } finally {
    busy = false;
    document.querySelectorAll("#assistant button").forEach((button) => { button.disabled = false; });
  }
}

const root = document.getElementById("assistant");
if (root) {
  document.getElementById("assistant-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const feature = (document.getElementById("assistant-q")?.value || "komboe").trim().slice(0, 80);
    act("explain_feature", { feature });
  });
  document.getElementById("assistant-password")?.addEventListener("click", () => {
    act("generate_password", { length: 20 });
  });
  document.getElementById("assistant-steps")?.addEventListener("click", () => {
    act("suggest_next_steps", {});
  });
}
