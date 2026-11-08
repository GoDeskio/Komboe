import assert from "node:assert/strict";
import test from "node:test";

import {
  rememberKomboeEmailSessionAsync,
  revokeKomboeEmailTrust,
} from "../../clients/upstream/libs/common/src/auth/komboe-email-trust.ts";

function installSession(initial = {}) {
  const store = { ...initial };
  const area = {
    async get(keys) {
      const names = Array.isArray(keys) ? keys : [keys];
      const out = {};
      for (const key of names) out[key] = store[key];
      return out;
    },
    async set(items) {
      Object.assign(store, items);
    },
    async remove(keys) {
      for (const key of Array.isArray(keys) ? keys : [keys]) delete store[key];
    },
  };
  globalThis.chrome = { storage: { session: area } };
  return store;
}

test("a service worker with no sessionStorage still posts the trust token", async () => {
  const store = installSession();
  const posts = [];
  globalThis.sessionStorage = undefined;
  globalThis.fetch = async (url, init) => {
    posts.push({ url, body: init.body, authorization: init.headers.Authorization });
    return { ok: true };
  };
  await rememberKomboeEmailSessionAsync({
    deviceTrust: "bearer-secret",
    apiBase: "https://vault.example/api",
  });
  assert.equal(store["komboe.deviceTrust"], "bearer-secret");
  const revoked = await revokeKomboeEmailTrust("access-token");
  assert.equal(revoked, true);
  assert.equal(posts.length, 1);
  assert.equal(posts[0].url, "https://vault.example/api/komboe/email-login-trust/clear");
  assert.equal(JSON.parse(posts[0].body).token, "bearer-secret");
  assert.equal(store["komboe.deviceTrust"], undefined);
});

test("a failed revocation leaves the service-worker copy in place", async () => {
  const store = installSession({ "komboe.deviceTrust": "bearer-secret", "komboe.apiBase": "https://vault.example" });
  globalThis.sessionStorage = undefined;
  globalThis.fetch = async () => ({ ok: false });
  const revoked = await revokeKomboeEmailTrust("access-token");
  assert.equal(revoked, false);
  assert.equal(store["komboe.deviceTrust"], "bearer-secret");
});

test("no supported store does not report success", async () => {
  delete globalThis.chrome;
  globalThis.sessionStorage = undefined;
  let called = false;
  globalThis.fetch = async () => {
    called = true;
    return { ok: true };
  };
  const revoked = await revokeKomboeEmailTrust("access-token");
  assert.equal(revoked, false);
  assert.equal(called, false);
});

test("sessionStorage logout posts before deleting", async () => {
  delete globalThis.chrome;
  const page = new Map();
  globalThis.sessionStorage = {
    getItem: (key) => page.get(key) ?? null,
    setItem: (key, value) => page.set(key, value),
    removeItem: (key) => page.delete(key),
  };
  const posts = [];
  globalThis.fetch = async (url, init) => {
    posts.push(JSON.parse(init.body).token);
    assert.equal(page.get("komboe.deviceTrust"), "page-secret");
    return { ok: true };
  };
  await rememberKomboeEmailSessionAsync({ deviceTrust: "page-secret", apiBase: "/api" });
  const revoked = await revokeKomboeEmailTrust("access-token");
  assert.equal(revoked, true);
  assert.deepEqual(posts, ["page-secret"]);
  assert.equal(page.has("komboe.deviceTrust"), false);
});
