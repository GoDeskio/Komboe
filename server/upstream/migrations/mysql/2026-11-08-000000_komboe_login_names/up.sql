CREATE TABLE komboe_login_names (
    user_uuid VARCHAR(40) NOT NULL PRIMARY KEY,
    name      VARCHAR(32) NOT NULL,
    UNIQUE KEY komboe_login_names_name (name)
);
