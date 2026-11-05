#!/usr/bin/env node
/**
 * Headless Phase B extension smoke: validate supported-browser matrix +
 * load contracts (Cerebro / Vivaldi / Tor) + (when present) Chromium MV3 /
 * Firefox zip manifests. Does not launch a browser.
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
  const { spawnSync } = require("node:child_process");
  const r = spawnSync("unzip", ["-p", zipPath, inner], {
    encoding: "buffer",
    maxBuffer: 8 * 1024 * 1024,
  });
  if (r.status !== 0) {
    throw new Error(
      `unzip -p ${zipPath} ${inner} failed: ${(r.stderr || r.stdout || "").toString()}`,
    );
  }
  return JSON.parse(r.stdout.toString("utf8"));
}

function matchAny(haystack, needles) {
  return (haystack || []).some((h) => needles.includes(h));
}

function coversWebMatches(matches, needles) {
  return (matches || []).some(
    (x) =>
      needles.includes(x) ||
      x.includes("http") ||
      x === "<all_urls>" ||
      x === "*://*/*" ||
      x.startsWith("*://"),
  );
}

/**
 * Assert a browser's load_contract against an in-repo source manifest.
 * Contracts live in clients/SUPPORTED-BROWSERS.json (source of truth).
 */
function assertLoadContract(browser) {
  const c = browser.load_contract;
  if (!c) {
    fail(`${browser.id}: missing load_contract in SUPPORTED-BROWSERS.json`);
    return;
  }
  const manifestPath = path.join(ROOT, c.manifest);
  if (!fs.existsSync(manifestPath)) {
    fail(`${browser.id}: load_contract manifest missing: ${manifestPath}`);
    return;
  }
  const m = loadJson(manifestPath);
  if (c.manifest_version != null && m.manifest_version !== c.manifest_version) {
    fail(
      `${browser.id}: expected manifest_version ${c.manifest_version}, got ${m.manifest_version}`,
    );
  } else {
    ok(`${browser.id}: manifest_version=${m.manifest_version}`);
  }

  const perms = new Set(m.permissions || []);
  for (const need of c.required_permissions || []) {
    if (!perms.has(need)) {
      fail(`${browser.id}: load contract missing permission "${need}"`);
    }
  }
  if ((c.required_permissions || []).length) {
    ok(
      `${browser.id}: required permissions present (${c.required_permissions.length})`,
    );
  }

  if (c.host_permissions_any_of) {
    const hosts = m.host_permissions || [];
    // MV2 may put hosts in permissions instead of host_permissions
    const combined = [...hosts, ...(m.permissions || [])];
    if (!matchAny(combined, c.host_permissions_any_of)) {
      fail(
        `${browser.id}: host_permissions/permissions must cover ${c.host_permissions_any_of.join(" | ")}`,
      );
    } else {
      ok(`${browser.id}: host coverage ok`);
    }
  }

  if (c.host_or_match_any_of) {
    const combined = [...(m.host_permissions || []), ...(m.permissions || [])];
    if (!matchAny(combined, c.host_or_match_any_of)) {
      fail(
        `${browser.id}: permissions must cover ${c.host_or_match_any_of.join(" | ")}`,
      );
    } else {
      ok(`${browser.id}: host/permission coverage ok`);
    }
  }

  if (c.requires_action_default_popup) {
    if (!m.action || !m.action.default_popup) {
      fail(`${browser.id}: action.default_popup required`);
    } else {
      ok(`${browser.id}: action.default_popup=${m.action.default_popup}`);
    }
  }

  if (c.requires_browser_action_default_popup) {
    const ba = m.browser_action || m.action;
    if (!ba || !ba.default_popup) {
      fail(`${browser.id}: browser_action.default_popup required (Firefox/Tor)`);
    } else {
      ok(`${browser.id}: browser_action.default_popup=${ba.default_popup}`);
    }
  }

  if (c.requires_web_content_scripts) {
    const cs = m.content_scripts || [];
    if (!cs.length) {
      fail(`${browser.id}: content_scripts required`);
    } else {
      const matches = cs.flatMap((x) => x.matches || []);
      const needles = c.content_script_match_any_of || [];
      if (!coversWebMatches(matches, needles)) {
        fail(
          `${browser.id}: content_scripts must match web pages (${needles.join(" | ")})`,
        );
      } else {
        ok(
          `${browser.id}: content_scripts matches=${JSON.stringify(matches)}`,
        );
      }
    }
  }
}

const matrixPath = path.join(ROOT, "clients/SUPPORTED-BROWSERS.json");
let matrix;
if (!fs.existsSync(matrixPath)) {
  fail(`missing ${matrixPath}`);
} else {
  matrix = loadJson(matrixPath);
  const browsers = matrix.browsers || [];
  const ids = new Set(browsers.map((b) => b.id));
  const required = [
    "chrome",
    "edge",
    "brave",
    "opera",
    "vivaldi",
    "cerebro",
    "firefox",
    "tor",
    "safari",
  ];
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
  ok(
    `support matrix: ${browsers.length} browsers (${browsers.filter((b) => b.status === "supported").length} supported)`,
  );
  console.log(
    "SUPPORTED:",
    browsers
      .filter((b) => b.status === "supported")
      .map((b) => b.name)
      .join(", "),
  );

  // Matrix-driven load contracts for browsers that declare one.
  for (const id of ["cerebro", "vivaldi", "tor"]) {
    const b = browsers.find((x) => x.id === id);
    if (!b) {
      fail(`missing browser ${id}`);
      continue;
    }
    console.log(`\n--- load contract: ${b.name} ---`);
    assertLoadContract(b);
  }
}

// Source manifests (always available in-repo) — basic presence checks
const mv3Src = path.join(ROOT, "clients/upstream/apps/browser/src/manifest.v3.json");
const mv2Src = path.join(ROOT, "clients/upstream/apps/browser/src/manifest.json");
if (fs.existsSync(mv3Src)) {
  const m = loadJson(mv3Src);
  if (m.manifest_version !== 3) fail(`src manifest.v3.json mv=${m.manifest_version}`);
  else ok(`src Chromium MV3 manifest present (mv=${m.manifest_version})`);
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
