CREATE TABLE komboe_kdf_email (
    user_uuid CHAR(36) NOT NULL PRIMARY KEY,
    kdf_email VARCHAR(256) NOT NULL,
    FOREIGN KEY (user_uuid) REFERENCES users (uuid)
);
ALTER TABLE komboe_login_names ADD COLUMN envelope TEXT NULL;
ALTER TABLE komboe_login_names ADD COLUMN envelope_salt VARCHAR(64) NULL;
ALTER TABLE komboe_login_names ADD COLUMN wrap_kdf_type INTEGER NULL;
ALTER TABLE komboe_login_names ADD COLUMN wrap_kdf_iter INTEGER NULL;
ALTER TABLE komboe_login_names ADD COLUMN wrap_kdf_memory INTEGER NULL;
ALTER TABLE komboe_login_names ADD COLUMN wrap_kdf_parallelism INTEGER NULL;
