# Design: Local-only file database (file-db-v1)

Status: implemented discovery + format; desktop/CLI flag wiring follows.

## Goal
Operate Komboe on an encrypted local SQLite file with **no server**. Zero-knowledge: the file holds only ciphertext and a client-wrapped vault key.

## Format
- SQLite file with `vault_meta(k,v)` and `items(id,ciphertext)`.
- `vault_meta.format = file-db-v1`.
- `vault_meta.wrappedKey` is opaque to any remote party (`pgp-wrap-v1.*` or EncString).

## Client
- Flag: `--local-db <path>` (CLI/desktop).
- Discovery: `GET /api/komboe/local-only` when a server is configured (optional).
