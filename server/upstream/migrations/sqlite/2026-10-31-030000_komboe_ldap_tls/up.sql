ALTER TABLE komboe_ldap_configs ADD COLUMN start_tls BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE komboe_ldap_configs ADD COLUMN tls_ca TEXT;
