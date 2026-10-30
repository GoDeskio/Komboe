"""Create Playwright fixtures against a running Komboe server (uses the feature-suite client)."""
import json, os, sys
sys.argv = [sys.argv[0]]; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "features"))
import run as R
ns = R.__dict__
owner = R.User(); oid, ok = ns["mkorg"](owner, "Rivera Family")
owner.api("PUT", f"/api/komboe/organizations/{oid}/plan", {"kind": "family", "seats": 6, "pricePerMemberCents": 100})
kid = R.User(); ns["add_member"](owner, oid, ok, kid)
for n in ("Kid email", "Game account"): kid.api("POST", "/api/ciphers", kid.cipher({"name": kid.e(n)}))
kid.api("POST", f"/api/komboe/organizations/{oid}/split-requests", {"note": "Moving out, starting my own family"})
ext = R.User()
ext.api("POST", "/api/ciphers", ext.cipher({"name": ext.e("Autofill test"), "login": {"username": ext.e("auto@komboe.test"),
        "password": ext.e("Autofill-Pass-1"), "uris": [{"uri": ext.e("https://autofill.komboe.test/login"), "match": None}]}}))
alias_key = owner.api("POST", "/api/komboe/alias/api-key")["apiKey"]
hp = R.User()
for nm, pw_, uri in [("Weak reused A", "123456", "http://insecure.komboe.test/login"), ("Weak reused B", "123456", "https://github.com/login"),
                     ("Strong unique", "Tq9!vL2#pR7@xW4$zN", "https://b.komboe.test")]:
    hp.api("POST", "/api/ciphers", hp.cipher({"name": hp.e(nm), "login": {"username": hp.e("health@komboe.test"), "password": hp.e(pw_),
           "uris": [{"uri": hp.e(uri), "match": None}]}}))
json.dump({"health": {"email": hp.email, "pw": hp.pw}, "owner": {"email": owner.email, "pw": owner.pw}, "kid": {"email": kid.email, "pw": kid.pw}, "ext": {"email": ext.email, "pw": ext.pw}, "orgId": oid, "aliasKey": alias_key},
          open(os.path.join(os.path.dirname(__file__), "fixtures.local.json"), "w"))
print("FIXTURES OK")
