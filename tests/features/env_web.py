#!/usr/bin/env python3
"""#16 Environment variables item: created in the real web vault, read back via `bw get dotenv`."""
import importlib.util, json, os, subprocess, sys, tempfile

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

WEB = os.environ.get("KOMBOE_WEB") or os.environ.get("KOMBOE_URL") or "https://127.0.0.1:8443"
NAME = "Ada app env"
TYPED = "# prod secrets\nexport STRIPE_KEY=sk_test_env16secret\nDB_URL='postgres://u:envpw16@db/app'\nGREETING=\"hello env16 world\"\n\nnot a var line\n"
CANON = 'STRIPE_KEY=sk_test_env16secret\nDB_URL=postgres://u:envpw16@db/app\nGREETING="hello env16 world"'
SECRETS = ("sk_test_env16secret", "envpw16", "hello env16 world", "STRIPE_KEY", "GREETING")
CLIENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../clients/upstream")


def reveal(page, field_id, toggle_id, secret):
    field = page.get_by_test_id(field_id)
    field.wait_for()
    textarea = field.evaluate("e => e.tagName") == "TEXTAREA"
    masked = lambda: field.evaluate("e => getComputedStyle(e).webkitTextSecurity") if textarea else field.get_attribute("type")
    assert masked() in ("password", "disc"), (field_id, masked())
    page.get_by_test_id(toggle_id).click()
    page.wait_for_timeout(200)
    assert field.input_value() == secret, (field_id, field.input_value())
    assert masked() in ("text", "none"), (field_id, masked())


def main():
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    from playwright.sync_api import sync_playwright
    user = ft.User()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page.set_default_timeout(25000)
        page.goto(WEB + "/#/login", wait_until="domcontentloaded")
        page.fill("#email", user.email)
        cont = page.get_by_role("button", name="Continue")
        if cont.count():
            cont.click()
        page.fill("#masterPassword", user.pw)
        page.get_by_role("button", name="Log in", exact=True).click()
        page.wait_for_url("**/setup-extension**", timeout=40000)
        page.get_by_role("button", name="Add it later").click()
        page.wait_for_timeout(800)
        page.get_by_role("link", name="Skip to web app").click()
        page.wait_for_function("() => location.hash.includes('vault')", timeout=20000)
        dismiss = page.get_by_role("button", name="Dismiss this checklist")
        if dismiss.count():
            dismiss.click()
        overlay = page.locator(".cdk-overlay-container")
        skip_tour = overlay.get_by_role("button", name="Skip")
        if skip_tour.count():
            skip_tour.click()
            page.wait_for_timeout(300)
        page.locator("#newItemDropdown").click()
        page.get_by_role("menuitem", name="Environment variables", exact=True).click()
        page.fill("input[formcontrolname=name]", NAME)
        page.fill("[data-testid=env-name]", "production")
        page.fill("[data-testid=env-variables]", TYPED)
        reveal(page, "env-variables", "toggle-env-variables", TYPED)
        page.get_by_role("button", name="Save", exact=True).click()
        page.keyboard.press("Escape")
        page.get_by_text(NAME, exact=True).first.wait_for()
        page.get_by_text(NAME, exact=True).first.click()
        assert page.get_by_text("3 variables").count(), "view shows variable count"
        assert page.get_by_test_id("env-name").input_value() == "production"
        reveal(page, "env-variables", "toggle-env-variables", CANON)
        page.keyboard.press("Escape")
        browser.close()
    sync = user.api("GET", "/api/sync")
    (c,) = [c for c in sync["ciphers"] if c["type"] == 2]
    blob = json.dumps(sync)
    for secret in SECRETS:
        assert secret not in blob, f"plaintext {secret!r} in /api/sync"
    k = ft.dec(c["key"], user.uk) if c.get("key") else None
    fields = [(user.d(f["name"], k), user.d(f["value"], k), f["type"]) for f in c["fields"]]
    assert fields == [("__komboe", "env", 0), ("Environment name", "production", 0),
                      ("STRIPE_KEY", "sk_test_env16secret", 1), ("DB_URL", "postgres://u:envpw16@db/app", 1),
                      ("GREETING", "hello env16 world", 1)], fields
    raw = open(os.environ["KOMBOE_DB"], "rb").read()
    for secret in SECRETS:
        if secret.encode() in raw:
            raise SystemExit(f"plaintext {secret!r} stored in the server database")
    # CLI: bw get dotenv prints the same variables, decrypted locally.
    home = tempfile.mkdtemp()
    env = dict(os.environ, BITWARDENCLI_APPDATA_DIR=home, KPW=user.pw,
               NODE_EXTRA_CA_CERTS=os.environ.get("NODE_EXTRA_CA_CERTS", "/workspace/run/tls/cert.pem"))
    run = lambda *a: subprocess.run(["node", os.path.join(CLIENTS, "apps/cli/build/bw.js"), *a], capture_output=True, text=True, timeout=180, env=env)
    run("config", "server", os.environ.get("KOMBOE_URL", "https://localhost:8443"))
    sess = run("login", user.email, "--passwordenv", "KPW", "--raw").stdout.strip().splitlines()[-1]
    out = run("get", "dotenv", NAME, "--session", sess)
    assert out.returncode == 0 and out.stdout.strip() == CANON, (out.stdout, out.stderr)
    tmpl = json.loads(run("get", "template", "item.env", "--session", sess).stdout)
    assert tmpl["fields"][0]["value"] == "env", tmpl
    print("ENV WEB PASS")

if __name__ == "__main__":
    main()
