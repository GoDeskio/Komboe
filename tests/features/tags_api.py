#!/usr/bin/env python3
"""Ciphertext tags on the real Komboe server."""
import importlib.util, os, ssl, sys
ssl._create_default_https_context = ssl._create_unverified_context

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

def main():
    u = ft.User()
    label = "Trip-" + ft.uuid.uuid4().hex
    try:
        u.api("POST", "/api/tags", {"name": "plaintext-tag"})
        raise SystemExit("plaintext tag name was stored")
    except ft.HTTPErr as e:
        assert e.code == 400, e
    tag = u.api("POST", "/api/tags", {"name": ft.enc(label.encode(), u.uk)})
    item = u.api("POST", "/api/ciphers", u.cipher())
    u.api("PUT", f"/api/ciphers/{item['id']}/tags", {"tagIds": [tag["id"]]})
    other = ft.User()
    try:
        other.api("PUT", f"/api/ciphers/{item['id']}/tags", {"tagIds": [tag["id"]]})
        raise SystemExit("another user linked a tag")
    except ft.HTTPErr as e:
        assert e.code in (400, 404), e
    sync = u.api("GET", "/api/sync")
    got = next(t for t in sync["tags"] if t["id"] == tag["id"])
    assert ft.dec(got["name"], u.uk).decode() == label
    row = next(c for c in sync["ciphers"] if c["id"] == item["id"])
    assert tag["id"] in row["tagIds"], row.get("tagIds")
    raw = open(os.environ["KOMBOE_DB"], "rb").read()
    assert label.encode() not in raw
    print("TAGS API PASS")

if __name__ == "__main__":
    main()
