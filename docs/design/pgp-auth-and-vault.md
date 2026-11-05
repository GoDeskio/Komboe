# PGP auth + OpenPGP vault wrap

- **Auth:** register armored public key → challenge nonce → verify signature (3-step). Private keys rejected.
- **Vault:** `PUT /api/komboe/pgp-vault-key` stores an OpenPGP-encrypted vault key; `serverCanDecrypt=false`.
