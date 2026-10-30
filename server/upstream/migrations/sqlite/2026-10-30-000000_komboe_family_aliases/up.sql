CREATE TABLE komboe_org_plans (
    org_uuid        CHAR(36) NOT NULL PRIMARY KEY REFERENCES organizations (uuid) ON DELETE CASCADE,
    kind            TEXT NOT NULL,
    seats           INTEGER NOT NULL,
    price_cents     INTEGER NOT NULL,
    parent_org_uuid CHAR(36),
    updated_at      DATETIME NOT NULL
);
CREATE TABLE komboe_split_requests (
    uuid         CHAR(36) NOT NULL PRIMARY KEY,
    org_uuid     CHAR(36) NOT NULL REFERENCES organizations (uuid) ON DELETE CASCADE,
    user_uuid    CHAR(36) NOT NULL REFERENCES users (uuid) ON DELETE CASCADE,
    status       TEXT NOT NULL,
    note         TEXT,
    new_org_uuid CHAR(36),
    decided_by   CHAR(36),
    created_at   DATETIME NOT NULL,
    decided_at   DATETIME
);
CREATE TABLE komboe_alias_keys (
    user_uuid  CHAR(36) NOT NULL PRIMARY KEY REFERENCES users (uuid) ON DELETE CASCADE,
    key_hash   TEXT NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE TABLE komboe_aliases (
    uuid       CHAR(36) NOT NULL PRIMARY KEY,
    user_uuid  CHAR(36) NOT NULL REFERENCES users (uuid) ON DELETE CASCADE,
    email      TEXT NOT NULL UNIQUE,
    note       TEXT,
    hostname   TEXT,
    enabled    BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL
);
