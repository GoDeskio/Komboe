CREATE TABLE komboe_unlock_credentials (
    uuid CHAR(36) PRIMARY KEY NOT NULL,
    user_uuid CHAR(36) NOT NULL REFERENCES users(uuid) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    credential_id TEXT NOT NULL,
    public_data TEXT NOT NULL,
    salt TEXT NOT NULL,
    wrapped_user_key TEXT NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE UNIQUE INDEX komboe_unlock_cred_unique ON komboe_unlock_credentials(user_uuid, credential_id);
CREATE INDEX komboe_unlock_cred_user ON komboe_unlock_credentials(user_uuid);

CREATE TABLE komboe_pgp_auth_keys (
    uuid CHAR(36) PRIMARY KEY NOT NULL,
    user_uuid CHAR(36) NOT NULL REFERENCES users(uuid) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    public_key_armored TEXT NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE UNIQUE INDEX komboe_pgp_auth_fp ON komboe_pgp_auth_keys(user_uuid, fingerprint);

CREATE TABLE komboe_pgp_auth_challenges (
    token TEXT PRIMARY KEY NOT NULL,
    user_uuid CHAR(36) NOT NULL REFERENCES users(uuid) ON DELETE CASCADE,
    nonce TEXT NOT NULL,
    expires_at DATETIME NOT NULL
);

CREATE TABLE komboe_pgp_vault_keys (
    user_uuid CHAR(36) PRIMARY KEY NOT NULL REFERENCES users(uuid) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    public_key_armored TEXT NOT NULL,
    wrapped_vault_key TEXT NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE komboe_agent_sessions (
    uuid CHAR(36) PRIMARY KEY NOT NULL,
    user_uuid CHAR(36) NOT NULL REFERENCES users(uuid) ON DELETE CASCADE,
    created_at DATETIME NOT NULL,
    last_action TEXT NOT NULL
);
CREATE INDEX komboe_agent_sessions_user ON komboe_agent_sessions(user_uuid);
