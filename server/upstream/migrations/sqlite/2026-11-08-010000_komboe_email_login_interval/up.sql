CREATE TABLE komboe_email_login_policy (
    user_uuid CHAR(36) NOT NULL PRIMARY KEY,
    interval_secs BIGINT
);
CREATE TABLE komboe_email_login_trust (
    user_uuid CHAR(36) NOT NULL,
    device_uuid CHAR(36) NOT NULL,
    verified_at BIGINT NOT NULL,
    PRIMARY KEY (user_uuid, device_uuid)
);
CREATE TABLE komboe_email_login_codes (
    uuid CHAR(36) NOT NULL PRIMARY KEY,
    user_uuid CHAR(36) NOT NULL,
    device_uuid CHAR(36) NOT NULL,
    code_hash TEXT NOT NULL,
    purpose TEXT NOT NULL,
    expires_at BIGINT NOT NULL,
    used_at BIGINT,
    attempts INTEGER NOT NULL,
    created_at BIGINT NOT NULL
);
