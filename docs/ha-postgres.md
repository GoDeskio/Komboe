# Running Komboe (Vaultwarden) as two or more nodes

Each node runs the same binary built with `--features postgresql` and points at the same Postgres database.
All nodes need:

- the same `DATABASE_URL`;
- the same `DOMAIN` (the public URL behind the load balancer). It is the JWT issuer, so a node with a different `DOMAIN` rejects other nodes' tokens with 401;
- the same JWT signing key: share `DATA_FOLDER` (or at least `RSA_KEY_FILENAME`). Otherwise each node creates its own key and tokens don't carry across nodes;
- shared storage for attachments and sends (the shared `DATA_FOLDER`, or an object store).

`tests/features/ha_postgres.py` checks this with two processes on a local Postgres. Set `KOMBOE_HA_BIN` and `KOMBOE_PG_URL`.
