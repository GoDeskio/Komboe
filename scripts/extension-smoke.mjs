#!/usr/bin/env node
/**
 * Headless Phase B extension smoke: validate supported-browser matrix +
 * (when present) Chromium MV3 / Firefox zip manifests. Does not launch a browser.
 *
 * Usage:
 *   node scripts/extension-smoke.mjs
 *   KOMBOE_ARTIFACTS=/path/to/artifacts node scripts/extension-smoke.mjs
 *
 * Exit 0 on pass; non-zero on failure.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const ART = process.env.KOMBOE_ARTIFACTS || "/workspace/artifacts";
const require = createRequire(import.meta.url);

function fail(msg) {
  console.error("FAIL:", msg);
  process.exitCode = 1;
}

function ok(msg) {
  console.log("OK:", msg);
}

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function readZipJson(zipPath, inner) {
  // Prefer system unzip -p to avoid a native zip dependency.
  const { spawnSync } = require("node:child_process");
  const r = spawnSync("unzip", ["-p", zipPath, inner], { encoding: "buffer", maxBuffer: 8 * 1024 * 1024 });
  if (r.status !== 0) {
    throw new Error(`unzip -p ${zipPath} ${inner} failed: ${(r.stderr || r.stdout || "").toString()}`);
  }
  return JSON.parse(r.stdout.toString("utf8"));
}

const matrixPath = path.join(ROOT, "clients/SUPPORTED-BROWSERS.json");
if (!fs.existsSync(matrixPath)) {
  fail(`missing ${matrixPath}`);
} else {
  const matrix = loadJson(matrixPath);
  const browsers = matrix.browsers || [];
  const ids = new Set(browsers.map((b) => b.id));
  const required = ["chrome", "edge", "brave", "opera", "vivaldi", "cerebro", "firefox", "tor", "safari"];
  for (const id of required) {
    if (!ids.has(id)) fail(`SUPPORTED-BROWSERS.json missing browser id: ${id}`);
  }
  const cerebro = browsers.find((b) => b.id === "cerebro");
  if (!cerebro || cerebro.family !== "chromium" || cerebro.build !== "chromium_mv3") {
    fail("Cerebro Browser must be chromium / chromium_mv3");
  } else {
    ok(`Cerebro Browser listed (status=${cerebro.status}, tested=${cerebro.tested})`);
  }
  const vivaldi = browsers.find((b) => b.id === "vivaldi");
  const tor = browsers.find((b) => b.id === "tor");
  if (!vivaldi || vivaldi.build !== "chromium_mv3") fail("Vivaldi must use chromium_mv3");
  if (!tor || tor.build !== "firefox") fail("Tor Browser must use firefox build");
  ok(`support matrix: ${browsers.length} browsers (${browsers.filter((b) => b.status === "supported").length} supported)`);
  console.log(
    "SUPPORTED:",
    browsers
      .filter((b) => b.status === "supported")
      .map((b) => b.name)
      .join(", "),
  );
}

// Source manifests (always available in-repo)
const mv3Src = path.join(ROOT, "clients/upstream/apps/browser/src/manifest.v3.json");
const mv2Src = path.join(ROOT, "clients/upstream/apps/browser/src/manifest.json");
if (fs.existsSync(mv3Src)) {
  const m = loadJson(mv3Src);
  if (m.manifest_version !== 3) fail(`src manifest.v3.json mv=${m.manifest_version}`);
  else ok(`src Chromium MV3 manifest present (mv=${m.manifest_version})`);
  if (!Array.isArray(m.content_scripts) || m.content_scripts.length === 0) {
    fail("src MV3 manifest missing content_scripts (autofill)");
  } else {
    ok(`src MV3 content_scripts: ${m.content_scripts.length}`);
  }
} else {
  fail(`missing ${mv3Src}`);
}
if (fs.existsSync(mv2Src)) {
  const m = loadJson(mv2Src);
  ok(`src Firefox-oriented manifest present (mv=${m.manifest_version})`);
} else {
  fail(`missing ${mv2Src}`);
}

// Built artifacts (optional on a fresh checkout)
function checkZip(name, expectMv, brandCheck = true) {
  const p = path.join(ART, name);
  if (!fs.existsSync(p) || fs.statSync(p).size === 0) {
    console.log(`SKIP: artifact not present: ${p}`);
    return;
  }
  try {
    const m = readZipJson(p, "manifest.json");
    if (m.manifest_version !== expectMv) {
      fail(`${name} expected manifest_version ${expectMv}, got ${m.manifest_version}`);
    } else {
      ok(`${name}: manifest_version=${m.manifest_version}`);
    }
    if (brandCheck) {
      try {
        const msgs = readZipJson(p, "_locales/en/messages.json");
        const extName = msgs?.extName?.message || "";
        if (!/Komboe/i.test(extName)) fail(`${name}: extName is not Komboe (${JSON.stringify(extName)})`);
        else ok(`${name}: branded extName=${JSON.stringify(extName)}`);
      } catch (e) {
        fail(`${name}: could not read _locales/en/messages.json: ${e.message}`);
      }
    }
    if (expectMv === 3) {
      if (!Array.isArray(m.content_scripts) || m.content_scripts.length === 0) {
        fail(`${name}: missing content_scripts`);
      } else {
        ok(`${name}: content_scripts ok (${m.content_scripts.length})`);
      }
    }
  } catch (e) {
    fail(`${name}: ${e.message}`);
  }
}

checkZip("komboe-chrome-mv3.zip", 3);
checkZip("komboe-firefox.zip", 2);

if (process.exitCode && process.exitCode !== 0) {
  console.error("\nextension-smoke: FAILED");
  process.exit(process.exitCode);
}
console.log("\nextension-smoke: PASS");
