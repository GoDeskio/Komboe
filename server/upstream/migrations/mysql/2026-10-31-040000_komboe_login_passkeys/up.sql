CREATE TABLE komboe_login_passkeys (
    uuid                  VARCHAR(40) NOT NULL PRIMARY KEY,
    user_uuid             VARCHAR(40) NOT NULL,
    name                  TEXT NOT NULL,
    cred_id               VARCHAR(512) NOT NULL UNIQUE,
    credential            TEXT NOT NULL,
    supports_prf          BOOLEAN NOT NULL,
    encrypted_user_key    TEXT,
    encrypted_public_key  TEXT,
    encrypted_private_key TEXT
);
