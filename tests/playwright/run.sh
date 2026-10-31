#!/bin/sh
# Fresh fixtures, then the E2E run. Needs the HTTPS server (web vault refuses plain HTTP) on KOMBOE_WEB.
set -e; cd "$(dirname "$0")"
KOMBOE_URL=${KOMBOE_FIXTURE_URL:-http://127.0.0.1:8000} python3 fixtures.py
node e2e.mjs
# Desktop (Linux) E2E when a built linux-unpacked dir is given; attaches over CDP.
if [ -n "$KOMBOE_DESKTOP" ] && [ -x "$KOMBOE_DESKTOP/komboe" ]; then node desktop.mjs; fi
# Tags: every tag name the clients created must be absent from the server DB (names are client-side ciphertext).
if [ -n "$KOMBOE_DB" ] && [ -s /tmp/komboe-tag-names.txt ]; then
  python3 -c "import sys;raw=open(sys.argv[1],'rb').read();bad=[n for n in open('/tmp/komboe-tag-names.txt').read().split() if n.encode() in raw];print('TAGS DB', 'FAIL plaintext: '+','.join(bad) if bad else 'ciphertext-only ('+str(len(open('/tmp/komboe-tag-names.txt').read().split()))+' names checked)');sys.exit(1 if bad else 0)" "$KOMBOE_DB"
fi
# Templates/env items: every secret value typed into the clients must be absent from the server DB.
if [ -n "$KOMBOE_DB" ] && [ -s /tmp/komboe-template-secrets.txt ]; then
  python3 -c "import sys;raw=open(sys.argv[1],'rb').read();s=open('/tmp/komboe-template-secrets.txt').read().split();bad=[n for n in s if n.encode() in raw];print('SECRETS DB', 'FAIL plaintext: '+str(len(bad)) if bad else 'ciphertext-only ('+str(len(s))+' secrets checked)');sys.exit(1 if bad else 0)" "$KOMBOE_DB"
fi
