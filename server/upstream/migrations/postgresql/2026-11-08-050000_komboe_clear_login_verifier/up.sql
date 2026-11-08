-- The cheap login-name verifier is not a proof. Clear every stored value.
-- The column stays so this schema matches SQLite, which cannot drop it here.
UPDATE komboe_login_names SET verifier_hash = NULL WHERE verifier_hash IS NOT NULL;
