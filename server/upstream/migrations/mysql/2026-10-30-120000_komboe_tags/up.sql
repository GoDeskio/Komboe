CREATE TABLE komboe_tags (
    uuid       VARCHAR(40) NOT NULL PRIMARY KEY,
    user_uuid  VARCHAR(40) NOT NULL,
    name       TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (user_uuid) REFERENCES users (uuid) ON DELETE CASCADE
);
CREATE INDEX komboe_tags_user_uuid ON komboe_tags (user_uuid);
CREATE TABLE komboe_cipher_tags (
    cipher_uuid VARCHAR(40) NOT NULL,
    tag_uuid    VARCHAR(40) NOT NULL,
    PRIMARY KEY (cipher_uuid, tag_uuid),
    FOREIGN KEY (cipher_uuid) REFERENCES ciphers (uuid) ON DELETE CASCADE,
    FOREIGN KEY (tag_uuid) REFERENCES komboe_tags (uuid) ON DELETE CASCADE
);
