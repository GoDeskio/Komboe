CREATE TABLE komboe_password_expiry (
    user_uuid VARCHAR(40) NOT NULL PRIMARY KEY,
    days      INTEGER NOT NULL,
    FOREIGN KEY (user_uuid) REFERENCES users (uuid) ON DELETE CASCADE
);
