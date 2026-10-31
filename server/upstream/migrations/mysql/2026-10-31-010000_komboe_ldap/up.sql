CREATE TABLE komboe_ldap_configs (
    org_uuid      VARCHAR(40) NOT NULL PRIMARY KEY,
    url           TEXT NOT NULL,
    bind_dn       TEXT NOT NULL,
    bind_password TEXT NOT NULL,
    user_base     TEXT NOT NULL,
    user_filter   TEXT NOT NULL,
    email_attr    TEXT NOT NULL,
    group_base    TEXT NOT NULL,
    group_filter  TEXT NOT NULL,
    member_attr   TEXT NOT NULL,
    FOREIGN KEY (org_uuid) REFERENCES organizations (uuid) ON DELETE CASCADE
);
