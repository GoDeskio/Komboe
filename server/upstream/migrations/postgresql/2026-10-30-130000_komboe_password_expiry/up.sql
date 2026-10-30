CREATE TABLE komboe_password_expiry (
    user_uuid CHAR(36) NOT NULL PRIMARY KEY REFERENCES users (uuid) ON DELETE CASCADE,
    days      INTEGER NOT NULL
);
