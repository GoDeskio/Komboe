CREATE TABLE komboe_email_login_policy (
    user_uuid VARCHAR(40) NOT NULL PRIMARY KEY,
    interval_secs BIGINT
);
CREATE TABLE komboe_email_login_trust (
    user_uuid VARCHAR(40) NOT NULL,
    device_uuid VARCHAR(40) NOT NULL,
    verified_at BIGINT NOT NULL,
    PRIMARY KEY (user_uuid, device_uuid)
);
CREATE TABLE komboe_email_login_codes (
    uuid VARCHAR(40) NOT NULL PRIMARY KEY,
    user_uuid VARCHAR(40) NOT NULL,
    device_uuid VARCHAR(40) NOT NULL,
    code_hash VARCHAR(64) NOT NULL,
    purpose VARCHAR(32) NOT NULL,
    expires_at BIGINT NOT NULL,
    used_at BIGINT,
    attempts INTEGER NOT NULL,
    created_at BIGINT NOT NULL
);
