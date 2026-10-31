CREATE TABLE komboe_passkey_challenges (
    token      TEXT NOT NULL PRIMARY KEY,
    state      TEXT NOT NULL,
    created_at BIGINT NOT NULL
);
CREATE INDEX idx_komboe_passkey_challenges_created ON komboe_passkey_challenges (created_at);
