-- Takeover grants are intentionally and irreversibly downgraded to view-only.
UPDATE emergency_access SET atype = 0 WHERE atype <> 0;
CREATE TABLE komboe_siem_configs (
    org_uuid VARCHAR(40) PRIMARY KEY NOT NULL REFERENCES organizations(uuid) ON DELETE CASCADE,
    kind VARCHAR(20) NOT NULL, endpoint TEXT NOT NULL, hmac_secret TEXT,
    enabled BOOLEAN NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE komboe_anomalies (
    uuid VARCHAR(40) PRIMARY KEY NOT NULL, user_uuid VARCHAR(40) NOT NULL REFERENCES users(uuid) ON DELETE CASCADE,
    kind VARCHAR(40) NOT NULL, ip_prefix VARCHAR(80) NOT NULL, device_id VARCHAR(255),
    detail TEXT NOT NULL, risk INTEGER NOT NULL, created_at DATETIME NOT NULL,
    INDEX komboe_anomalies_user(user_uuid, created_at)
);
CREATE TABLE komboe_billing (
    org_uuid VARCHAR(40) PRIMARY KEY NOT NULL REFERENCES organizations(uuid) ON DELETE CASCADE,
    plan VARCHAR(30) NOT NULL, billing_interval VARCHAR(20) NOT NULL, status VARCHAR(30) NOT NULL,
    stripe_customer_id VARCHAR(255), stripe_subscription_id VARCHAR(255), updated_at DATETIME NOT NULL
);
CREATE TABLE komboe_projects (
    uuid VARCHAR(40) PRIMARY KEY NOT NULL, org_uuid VARCHAR(40) NOT NULL REFERENCES organizations(uuid) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL, created_by VARCHAR(40) NOT NULL, created_at DATETIME NOT NULL,
    INDEX komboe_projects_org(org_uuid)
);
CREATE TABLE komboe_secrets (
    uuid VARCHAR(40) PRIMARY KEY NOT NULL, project_uuid VARCHAR(40) NOT NULL REFERENCES komboe_projects(uuid) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL, ciphertext LONGTEXT NOT NULL, created_by VARCHAR(40) NOT NULL,
    created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE komboe_service_accounts (
    uuid VARCHAR(40) PRIMARY KEY NOT NULL, project_uuid VARCHAR(40) NOT NULL REFERENCES komboe_projects(uuid) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL, token_hash VARCHAR(255) NOT NULL UNIQUE, created_by VARCHAR(40) NOT NULL,
    created_at DATETIME NOT NULL, revoked_at DATETIME
);
