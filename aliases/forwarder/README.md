# Komboe alias forwarder (local-test)

Komboe-original, AGPL-3.0-or-later. See `docs/RUNNING.md` ("Alias mail forwarder") for how to run it.

- Inbound: `<alias>@KOMBOE_ALIAS_DOMAIN`, catch-all custom domains, `<any>@<sub>.KOMBOE_ALIAS_DOMAIN`, and reverse aliases `ra+<token>@...`.
- State lives in its own SQLite (`FWD_DB`): mailboxes, blocks, counters and reverse-alias mappings. Mail bodies are never stored.
- API (`Authentication: kmb_...`): `POST /fwd/mailboxes`, `POST /fwd/mailboxes/verify`, `PUT /fwd/mailboxes/<email>/pgp`,
  `PUT /fwd/aliases/<id>/mailboxes`, `POST /fwd/aliases/<id>/block|unblock`, `GET /fwd/aliases/<id>/stats`, `POST /fwd/domains`, `POST /fwd/subdomains`.
- Not production-ready: it doesn't verify domain TXT records, check SPF/DKIM/DMARC on inbound mail, sign outbound DKIM or rate-limit.
  Reverse-alias sender checks rely on the envelope sender.
