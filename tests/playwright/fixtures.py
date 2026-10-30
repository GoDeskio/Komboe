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
alias_key = owner.api("POST", "/api/komboe/alias/api-key")["apiKey"]
json.dump({"owner": {"email": owner.email, "pw": owner.pw}, "kid": {"email": kid.email, "pw": kid.pw}, "orgId": oid, "aliasKey": alias_key},
          open(os.path.join(os.path.dirname(__file__), "fixtures.local.json"), "w"))
print("FIXTURES OK")
