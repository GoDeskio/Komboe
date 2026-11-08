CREATE TABLE komboe_kdf_email (
    user_uuid CHAR(36) NOT NULL PRIMARY KEY,
    kdf_email TEXT NOT NULL
);
ALTER TABLE komboe_login_names ADD COLUMN envelope TEXT;
ALTER TABLE komboe_login_names ADD COLUMN envelope_salt TEXT;
ALTER TABLE komboe_login_names ADD COLUMN wrap_kdf_type INTEGER;
ALTER TABLE komboe_login_names ADD COLUMN wrap_kdf_iter INTEGER;
ALTER TABLE komboe_login_names ADD COLUMN wrap_kdf_memory INTEGER;
ALTER TABLE komboe_login_names ADD COLUMN wrap_kdf_parallelism INTEGER;
