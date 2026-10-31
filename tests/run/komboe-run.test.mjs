import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parseRef, parseEnvFile, resolveEnv } from "../../scripts/komboe-run.mjs";

const item = { name: "db", login: { username: "app", password: "s3cret", uris: [{ uri: "https://db" }] }, notes: "n", fields: [{ name: "API key", value: "k-1" }] };

test("parseRef", () => {
  assert.deepEqual(parseRef("komboe://db/password"), { item: "db", field: "password" });
  assert.deepEqual(parseRef("komboe://my%20db/API%20key"), { item: "my db", field: "API key" });
  assert.equal(parseRef("plain"), null);
});

test("parseEnvFile handles comments, export and quotes", () => {
  assert.deepEqual(parseEnvFile("# c\nexport A=1\nB=\"komboe://db/password\"\n\n"), { A: "1", B: "komboe://db/password" });
});

test("resolveEnv fetches each item once and reports missing fields", () => {
  let calls = 0;
  const { env, errors } = resolveEnv({ U: "komboe://db/username", P: "komboe://db/password", K: "komboe://db/API key", X: "komboe://db/nope", Q: "plain" }, () => (calls++, item));
  assert.equal(calls, 1);
  assert.equal(env.U, "app"); assert.equal(env.P, "s3cret"); assert.equal(env.K, "k-1"); assert.equal(env.Q, "plain");
  assert.match(errors[0], /X: field "nope"/);
});

test("CLI end to end with a stub Komboe CLI; secret is not printed by komboe-run", () => {
  const dir = mkdtempSync(join(tmpdir(), "kr-"));
  const stub = join(dir, "bw.js");
  writeFileSync(stub, `if(process.argv[4]!=="db"){process.exit(1)}process.stdout.write(${JSON.stringify(JSON.stringify(item))})`);
  const script = new URL("../../scripts/komboe-run.mjs", import.meta.url).pathname;
  const ok = spawnSync(process.execPath, [script, "--", process.execPath, "-e", "process.stdout.write(process.env.P.length+'')"], { encoding: "utf8", env: { ...process.env, KOMBOE_CLI: stub, P: "komboe://db/password" } });
  assert.equal(ok.status, 0); assert.equal(ok.stdout, "6");
  const bad = spawnSync(process.execPath, [script, "--", "true"], { encoding: "utf8", env: { ...process.env, KOMBOE_CLI: stub, P: "komboe://missing/password" } });
  assert.equal(bad.status, 1); assert.match(bad.stderr, /could not be read/); assert.doesNotMatch(bad.stderr + bad.stdout, /s3cret/);
});
