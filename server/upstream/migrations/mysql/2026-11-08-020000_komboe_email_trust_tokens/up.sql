CREATE TABLE komboe_email_trust_tokens (
    token_hash VARCHAR(128) NOT NULL PRIMARY KEY,
    user_uuid VARCHAR(40) NOT NULL,
    verified_at BIGINT NOT NULL,
    revoked_at BIGINT
);
CREATE TABLE komboe_email_login_challenges (
    challenge_id VARCHAR(128) NOT NULL PRIMARY KEY,
    user_uuid VARCHAR(40) NOT NULL,
    code_hash VARCHAR(128),
    expires_at BIGINT NOT NULL,
    used_at BIGINT,
    attempts INTEGER NOT NULL,
    created_at BIGINT NOT NULL
);
DELETE FROM komboe_email_login_trust;
DELETE FROM komboe_email_login_codes;
