-- Komboe: account encryption v2 (XChaCha20-Poly1305 / COSE) key material.
-- All values are opaque client-produced blobs; the server never decrypts them.
CREATE TABLE komboe_account_keys_v2 (
    user_uuid           TEXT NOT NULL PRIMARY KEY REFERENCES users (uuid),
    wrapped_signing_key TEXT NOT NULL,
    verifying_key       TEXT NOT NULL,
    signed_public_key   TEXT,
    security_state      TEXT NOT NULL,
    security_version    BIGINT NOT NULL
);
