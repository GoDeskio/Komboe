#!/usr/bin/env python3
"""Self-hosted defaults do not contact Komboe, Bitwarden, GitHub, Cloudflare, or HIBP."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
config = (ROOT / "server/upstream/src/config.rs").read_text()
admin = (ROOT / "server/upstream/src/api/admin.rs").read_text()
updater = (ROOT / "clients/upstream/apps/desktop/src/main/updater.main.ts").read_text()
cli = (ROOT / "clients/upstream/apps/cli/src/commands/update.command.ts").read_text()
password = (
    ROOT / "clients/upstream/libs/auth/src/angular/input-password/input-password.component.ts"
).read_text()
env = (ROOT / "server/upstream/.env.template").read_text()

assert 'push_enabled:           bool,   false,  def,    false;' in config
assert 'push_relay_uri:         String, false,  def,    String::new();' in config
assert 'push_identity_uri:      String, false,  def,    String::new();' in config
assert "https://push.bitwarden.com" not in config
assert "https://identity.bitwarden.com" not in config
assert "disable_icon_download:  bool,   true,   def,    true;" in config
assert "admin_external_checks:  bool,   true,   def,    false;" in config
assert "hibp_api_key:           Pass,   true,   option;" in config
assert "sso_enabled:                    bool,   true,   def,    false;" in config

assert "let external_checks = CONFIG.admin_external_checks();" in admin
assert "let has_http_access = has_http_access().await;" not in admin
assert "if external_checks { has_http_access().await } else { false }" in admin

assert 'process.env.KOMBOE_UPDATE_FEED !== "1"' in updater
assert "github.com/bitwarden/clients/releases" not in updater
assert "KOMBOE_UPDATE_URL" in updater

assert "KOMBOE_CLI_RELEASES_URL" in cli
assert "bitwarden/clients" not in cli
assert "api.github.com" not in cli

assert 'nonNullable.control(false)' in password
assert "checkForBreaches?.value ?? false" in password

assert "# DISABLE_ICON_DOWNLOAD=true" in env
assert "# ADMIN_EXTERNAL_CHECKS=false" in env
assert "# PUSH_RELAY_URI=https://push.example.com" in env
assert "https://push.bitwarden.com" not in env

print("PHONE HOME DEFAULTS PASS")
