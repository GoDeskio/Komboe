-- The cheap login-name verifier is not a proof. Clear every stored value.
-- SQLite in this server cannot drop the column. The server no longer reads or writes it.
UPDATE komboe_login_names SET verifier_hash = NULL WHERE verifier_hash IS NOT NULL;
