CREATE TABLE komboe_scim_tokens (
    org_uuid   VARCHAR(40) NOT NULL PRIMARY KEY,
    token_hash TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (org_uuid) REFERENCES organizations (uuid) ON DELETE CASCADE
);
