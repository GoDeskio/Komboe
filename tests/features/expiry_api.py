#!/usr/bin/env python3
"""Org password-expiry policy and the personal setting."""
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

def main():
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    oid, _, _ = ft.org()
    owner = ft.a()
    owner.api("PUT", f"/api/organizations/{oid}/policies/21", {"policy": {"enabled": True, "data": {"days": 30}, "type": 21}})
    policies = owner.api("GET", f"/api/organizations/{oid}/policies")["data"]
    assert any(p["type"] == 21 and p["enabled"] and p["data"]["days"] == 30 for p in policies)
    got = owner.api("GET", "/api/password-expiry")
    assert got["organizationDays"] == 30 and got["days"] == 30, got
    saved = owner.api("PUT", "/api/password-expiry", {"days": 10})
    assert saved["userDays"] == 10 and saved["days"] == 10, saved
    cleared = owner.api("PUT", "/api/password-expiry", {"days": None})
    assert cleared["userDays"] is None and cleared["days"] == 30, cleared
    print("EXPIRY API PASS")

if __name__ == "__main__":
    main()
