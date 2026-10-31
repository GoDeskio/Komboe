CREATE TABLE komboe_tags (
    uuid       CHAR(36) NOT NULL PRIMARY KEY,
    user_uuid  CHAR(36) NOT NULL REFERENCES users (uuid) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX komboe_tags_user_uuid ON komboe_tags (user_uuid);
CREATE TABLE komboe_cipher_tags (
    cipher_uuid CHAR(36) NOT NULL REFERENCES ciphers (uuid) ON DELETE CASCADE,
    tag_uuid    CHAR(36) NOT NULL REFERENCES komboe_tags (uuid) ON DELETE CASCADE,
    PRIMARY KEY (cipher_uuid, tag_uuid)
);
