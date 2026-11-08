ALTER TABLE komboe_email_login_challenges ADD COLUMN last_sent_at BIGINT NULL;
ALTER TABLE komboe_email_login_challenges ADD COLUMN send_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE komboe_login_names ADD COLUMN verifier_hash VARCHAR(128) NULL;
