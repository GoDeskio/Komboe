-- Takeover grants are intentionally and irreversibly downgraded to view-only.
UPDATE emergency_access SET atype = 0 WHERE atype <> 0;
CREATE TABLE komboe_siem_configs (
    org_uuid CHAR(36) PRIMARY KEY NOT NULL REFERENCES organizations(uuid) ON DELETE CASCADE,
    kind TEXT NOT NULL, endpoint TEXT NOT NULL, hmac_secret TEXT,
    enabled BOOLEAN NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE komboe_anomalies (
    uuid CHAR(36) PRIMARY KEY NOT NULL, user_uuid CHAR(36) NOT NULL REFERENCES users(uuid) ON DELETE CASCADE,
    kind TEXT NOT NULL, ip_prefix TEXT NOT NULL, device_id TEXT,
    detail TEXT NOT NULL, risk INTEGER NOT NULL, created_at DATETIME NOT NULL
);
CREATE INDEX komboe_anomalies_user ON komboe_anomalies(user_uuid, created_at);
CREATE TABLE komboe_billing (
    org_uuid CHAR(36) PRIMARY KEY NOT NULL REFERENCES organizations(uuid) ON DELETE CASCADE,
    plan TEXT NOT NULL, billing_interval TEXT NOT NULL, status TEXT NOT NULL,
    stripe_customer_id TEXT, stripe_subscription_id TEXT, updated_at DATETIME NOT NULL
);
CREATE TABLE komboe_projects (
    uuid CHAR(36) PRIMARY KEY NOT NULL, org_uuid CHAR(36) NOT NULL REFERENCES organizations(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL, created_by CHAR(36) NOT NULL, created_at DATETIME NOT NULL
);
CREATE INDEX komboe_projects_org ON komboe_projects(org_uuid);
CREATE TABLE komboe_secrets (
    uuid CHAR(36) PRIMARY KEY NOT NULL, project_uuid CHAR(36) NOT NULL REFERENCES komboe_projects(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL, ciphertext TEXT NOT NULL, created_by CHAR(36) NOT NULL,
    created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE komboe_service_accounts (
    uuid CHAR(36) PRIMARY KEY NOT NULL, project_uuid CHAR(36) NOT NULL REFERENCES komboe_projects(uuid) ON DELETE CASCADE,
    name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE, created_by CHAR(36) NOT NULL,
    created_at DATETIME NOT NULL, revoked_at DATETIME
);
