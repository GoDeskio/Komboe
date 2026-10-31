#!/usr/bin/env python3
"""Verify a Komboe EVENTS_SIEM_JSONL_PATH file: every line's hash = sha256(prevHash || line-without-hash)
and prevHash links to the previous line. Exit 0 if intact, 1 with the first broken line otherwise."""
import hashlib, json, sys
prev = "0" * 64
first = True
for n, raw in enumerate(open(sys.argv[1]), 1):
    if not raw.strip():
        continue
    v = json.loads(raw)
    h = v.pop("hash")
    if first and v.get("prevHash") != prev:
        prev = v.get("prevHash")  # file may start mid-chain after rotation
    first = False
    if v.get("prevHash") != prev:
        print(f"BROKEN link at line {n}"); sys.exit(1)
    body = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    if hashlib.sha256((prev + body).encode()).hexdigest() != h:
        print(f"BROKEN hash at line {n}"); sys.exit(1)
    prev = h
print(f"OK chain intact, head {prev}")
