CREATE TABLE komboe_ldap_configs (
    org_uuid      CHAR(36) NOT NULL PRIMARY KEY REFERENCES organizations (uuid) ON DELETE CASCADE,
    url           TEXT NOT NULL,
    bind_dn       TEXT NOT NULL,
    bind_password TEXT NOT NULL,
    user_base     TEXT NOT NULL,
    user_filter   TEXT NOT NULL,
    email_attr    TEXT NOT NULL,
    group_base    TEXT NOT NULL,
    group_filter  TEXT NOT NULL,
    member_attr   TEXT NOT NULL
);
