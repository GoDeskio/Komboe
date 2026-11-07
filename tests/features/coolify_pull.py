#!/usr/bin/env python3
"""The Coolify compose file is pull-only and matches the sandbox service shape."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PULL = ROOT / "deploy/coolify/docker-compose.pull.yml"
SANDBOX = ROOT / "compose.coolify.yml"


def main():
    text = PULL.read_text()
    sandbox = SANDBOX.read_text()
    assert not re.search(r"(?m)^\s*build\s*:", text)
    assert "pull_policy:" not in text
    assert "ghcr.io/godeskio/komboe-server@sha256:${KOMBOE_SERVER_DIGEST:?set to the digest printed by the main image job}" in text
    assert "ghcr.io/godeskio/komboe-clients@sha256:${KOMBOE_CLIENTS_DIGEST:?set to the digest printed by the main image job}" in text
    assert 'restart: "no"' in text
    assert "komboe-data:/data" in text
    assert "web-vault:/web-vault" in text
    assert "extension:/extension" in text
    assert 'http://127.0.0.1:8080/alive' in text
    assert "donotreply@komboe.com" in text
    for key in (
        "SIGNUPS_ALLOWED",
        "WEB_VAULT_ENABLED",
        "WEB_VAULT_FOLDER",
        "TEMPLATES_FOLDER",
        "DOMAIN",
        "ROCKET_PORT",
        "ADMIN_TOKEN",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_SECURITY",
        "SMTP_FROM",
        "SMTP_FROM_NAME",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
    ):
        assert key in text, key
        assert key in sandbox, key
    assert "condition: service_completed_successfully" in text
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "refs/heads/main" in workflow
    assert "ghcr.io" in workflow
    assert "containerimage.digest" in workflow
    assert "docker/Dockerfile.server" in workflow
    assert "docker/Dockerfile.clients" in workflow
    print("COOLIFY PULL PASS")


if __name__ == "__main__":
    main()
