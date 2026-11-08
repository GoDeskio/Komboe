ALTER TABLE komboe_login_names DROP COLUMN wrap_kdf_parallelism;
ALTER TABLE komboe_login_names DROP COLUMN wrap_kdf_memory;
ALTER TABLE komboe_login_names DROP COLUMN wrap_kdf_iter;
ALTER TABLE komboe_login_names DROP COLUMN wrap_kdf_type;
ALTER TABLE komboe_login_names DROP COLUMN envelope_salt;
ALTER TABLE komboe_login_names DROP COLUMN envelope;
DROP TABLE komboe_kdf_email;
