CREATE TABLE komboe_device_trust (
    device_uuid          CHAR(36) NOT NULL,
    user_uuid            CHAR(36) NOT NULL,
    encrypted_user_key   TEXT NOT NULL,
    encrypted_public_key TEXT NOT NULL,
    encrypted_private_key TEXT NOT NULL,
    PRIMARY KEY (device_uuid, user_uuid)
);
