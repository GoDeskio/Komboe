ALTER TABLE komboe_login_names DROP COLUMN verifier_hash;
ALTER TABLE komboe_email_login_challenges DROP COLUMN send_count;
ALTER TABLE komboe_email_login_challenges DROP COLUMN last_sent_at;
