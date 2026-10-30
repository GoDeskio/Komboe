CREATE TABLE komboe_org_plans (
    org_uuid        VARCHAR(40) NOT NULL PRIMARY KEY REFERENCES organizations (uuid) ON DELETE CASCADE,
    kind            VARCHAR(255) NOT NULL,
    seats           INTEGER NOT NULL,
    price_cents     INTEGER NOT NULL,
    parent_org_uuid VARCHAR(40),
    updated_at      DATETIME NOT NULL
);
CREATE TABLE komboe_split_requests (
    uuid         VARCHAR(40) NOT NULL PRIMARY KEY,
    org_uuid     VARCHAR(40) NOT NULL REFERENCES organizations (uuid) ON DELETE CASCADE,
    user_uuid    VARCHAR(40) NOT NULL REFERENCES users (uuid) ON DELETE CASCADE,
    status       VARCHAR(255) NOT NULL,
    note         VARCHAR(255),
    new_org_uuid VARCHAR(40),
    decided_by   VARCHAR(40),
    created_at   DATETIME NOT NULL,
    decided_at   DATETIME
);
CREATE TABLE komboe_alias_keys (
    user_uuid  VARCHAR(40) NOT NULL PRIMARY KEY REFERENCES users (uuid) ON DELETE CASCADE,
    key_hash   VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE TABLE komboe_aliases (
    uuid       VARCHAR(40) NOT NULL PRIMARY KEY,
    user_uuid  VARCHAR(40) NOT NULL REFERENCES users (uuid) ON DELETE CASCADE,
    email      VARCHAR(255) NOT NULL UNIQUE,
    note       VARCHAR(255),
    hostname   VARCHAR(255),
    enabled    BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL
);
