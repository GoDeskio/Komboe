CREATE TABLE komboe_login_names (
    user_uuid CHAR(36) NOT NULL PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE
);
