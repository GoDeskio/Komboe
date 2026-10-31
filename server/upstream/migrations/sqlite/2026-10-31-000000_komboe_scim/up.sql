CREATE TABLE komboe_scim_tokens (
    org_uuid   CHAR(36) NOT NULL PRIMARY KEY REFERENCES organizations (uuid) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    created_at DATETIME NOT NULL
);
