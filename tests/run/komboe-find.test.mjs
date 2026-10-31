import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { find, score } from "../../scripts/komboe-find.mjs";

const items = [
  { id: "1", name: "GitHub", login: { username: "dustin", password: "S3cret-GH", uris: [{ uri: "https://github.com/login" }] } },
  { id: "2", name: "Work mail", login: { username: "d@godesk.io", password: "Mail-Pw", totp: "JBSWY3DP", uris: [{ uri: "mail.godesk.io" }] } },
  { id: "3", name: "Gitea old", favorite: true, login: { username: "x", password: "pw3" } },
  { id: "4", name: "Bank", notes: "github recovery codes" },
  { id: "5", name: "GitHub deleted", deletedDate: "2026-01-01", login: {} },
];

test("score prefers exact, prefix, word, substring, then fuzzy", () => {
  assert.ok(score("git", "git") > score("git", "github"));
  assert.ok(score("git", "github") > score("hub", "my hub"));
  assert.ok(score("hub", "my hub") > score("thu", "github"));
  assert.ok(score("ghb", "github") > 0);
  assert.equal(score("zz", "github"), 0);
});

test("find ranks by name/user/host, skips deleted and never searches notes", () => {
  assert.deepEqual(find(items, "git").map(r => r.id), ["3", "1"]); // favorite wins a tie
  assert.deepEqual(find(items, "godesk").map(r => r.id), ["2"]);
  assert.deepEqual(find(items, "recovery"), []);
  assert.deepEqual(find(items, "git dustin").map(r => r.id), ["1"]);
});

test("CLI prints no secrets", () => {
  const p = spawnSync(process.execPath, [new URL("../../scripts/komboe-find.mjs", import.meta.url).pathname, "mail"], { input: JSON.stringify(items), encoding: "utf8" });
  assert.equal(p.status, 0);
  assert.match(p.stdout, /^2\tWork mail\td@godesk.io\tmail.godesk.io/);
  assert.doesNotMatch(p.stdout, /Mail-Pw|JBSWY3DP/);
});
