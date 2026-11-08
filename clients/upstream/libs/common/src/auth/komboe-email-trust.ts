/**
 * Timed-email bearer token.
 * Web and desktop keep it in sessionStorage. The extension service worker has no
 * sessionStorage, so the same keys also live in chrome.storage.session (MV3),
 * which the service worker and the popup share. The local copy is removed only
 * after the server accepts the revocation.
 */

const TRUST_KEY = "komboe.deviceTrust";
const CHALLENGE_KEY = "komboe.loginChallenge";
const API_BASE_KEY = "komboe.apiBase";

type SessionArea = {
  get: (keys: string | string[]) => Promise<Record<string, unknown>>;
  set: (items: Record<string, unknown>) => Promise<void>;
  remove: (keys: string | string[]) => Promise<void>;
};

export type KomboeEmailSession = {
  deviceTrust?: string;
  loginChallenge?: string;
  apiBase?: string;
};

function extensionSession(): SessionArea | null {
  const root = globalThis as {
    chrome?: { storage?: { session?: SessionArea } };
    browser?: { storage?: { session?: SessionArea } };
  };
  const area = root.chrome?.storage?.session ?? root.browser?.storage?.session;
  if (
    !area ||
    typeof area.get !== "function" ||
    typeof area.set !== "function" ||
    typeof area.remove !== "function"
  ) {
    return null;
  }
  return area;
}

function pageSession(): Storage | null {
  try {
    return globalThis.sessionStorage ?? null;
  } catch {
    return null;
  }
}

function writePage(values: KomboeEmailSession): void {
  const page = pageSession();
  if (!page) {
    return;
  }
  if (values.deviceTrust) {
    page.setItem(TRUST_KEY, values.deviceTrust);
    page.removeItem(CHALLENGE_KEY);
  }
  if (values.loginChallenge) {
    page.setItem(CHALLENGE_KEY, values.loginChallenge);
  }
  if (values.apiBase) {
    page.setItem(API_BASE_KEY, values.apiBase);
  }
}

function extensionItems(values: KomboeEmailSession): Record<string, string> {
  const items: Record<string, string> = {};
  if (values.deviceTrust) {
    items[TRUST_KEY] = values.deviceTrust;
  }
  if (values.loginChallenge) {
    items[CHALLENGE_KEY] = values.loginChallenge;
  }
  if (values.apiBase) {
    items[API_BASE_KEY] = values.apiBase;
  }
  return items;
}

/** Sync page write, plus a service-worker write that the caller does not await. */
export function rememberKomboeEmailSession(values: KomboeEmailSession): void {
  writePage(values);
  const area = extensionSession();
  const items = extensionItems(values);
  if (!area || Object.keys(items).length === 0) {
    return;
  }
  void area.set(items).catch((): undefined => undefined);
  if (values.deviceTrust) {
    void area.remove(CHALLENGE_KEY).catch((): undefined => undefined);
  }
}

/** Same write, awaited, so logout cannot run before the service worker has the token. */
export async function rememberKomboeEmailSessionAsync(values: KomboeEmailSession): Promise<void> {
  writePage(values);
  const area = extensionSession();
  const items = extensionItems(values);
  if (!area || Object.keys(items).length === 0) {
    return;
  }
  await area.set(items);
  if (values.deviceTrust) {
    await area.remove(CHALLENGE_KEY);
  }
}

async function readKey(key: string): Promise<string | null> {
  const area = extensionSession();
  if (area) {
    try {
      const stored = await area.get([key]);
      const value = stored?.[key];
      if (typeof value === "string" && value) {
        return value;
      }
    } catch {
      // Fall through to the page store.
    }
  }
  const page = pageSession();
  if (!page) {
    return null;
  }
  return page.getItem(key);
}

export async function revokeKomboeEmailTrust(
  accessToken: string | null | undefined,
): Promise<boolean> {
  const area = extensionSession();
  const page = pageSession();
  // Neither store exists. Do not report success: the token may still be held somewhere
  // this context cannot see, and no revocation was sent.
  if (!area && !page) {
    return false;
  }
  const trust = await readKey(TRUST_KEY);
  if (!trust) {
    return true;
  }
  if (!accessToken) {
    return false;
  }
  const apiBase = (await readKey(API_BASE_KEY)) || "";
  const trimmed = apiBase.replace(/\/$/, "");
  const url = trimmed
    ? (trimmed.endsWith("/api") ? trimmed : trimmed + "/api") + "/komboe/email-login-trust/clear"
    : "/api/komboe/email-login-trust/clear";
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + accessToken,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ token: trust }),
    });
    if (!response.ok) {
      return false;
    }
  } catch {
    return false;
  }
  if (page) {
    page.removeItem(TRUST_KEY);
    page.removeItem(CHALLENGE_KEY);
  }
  if (area) {
    try {
      await area.remove([TRUST_KEY, CHALLENGE_KEY]);
    } catch {
      return false;
    }
  }
  return true;
}
