ALTER TABLE komboe_ldap_configs ADD COLUMN start_tls BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE komboe_ldap_configs ADD COLUMN tls_ca TEXT;
