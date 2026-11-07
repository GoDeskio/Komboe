#!/usr/bin/env python3
"""The default SMTP sender is donotreply@komboe.com."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    config = (ROOT / "server/upstream/src/config.rs").read_text()
    assert 'donotreply@komboe.com' in config
    assert "no-reply@komboe.com" not in config
    for rel in (
        "docker-compose.yml",
        "compose.coolify.yml",
        "deploy/coolify/docker-compose.pull.yml",
        "docs/EMAIL.md",
        "server/upstream/.env.template",
    ):
        text = (ROOT / rel).read_text()
        assert "donotreply@komboe.com" in text, rel
        assert "no-reply@komboe.com" not in text, rel
    print("SMTP FROM PASS")


if __name__ == "__main__":
    main()
