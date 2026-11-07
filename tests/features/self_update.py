#!/usr/bin/env python3
"""Desktop and CLI update commands still download an update when opted in."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    updater = (ROOT / "clients/upstream/apps/desktop/src/main/updater.main.ts").read_text()
    cli = (ROOT / "clients/upstream/apps/cli/src/commands/update.command.ts").read_text()
    admin = (ROOT / "server/upstream/src/api/admin.rs").read_text()

    assert 'process.env.KOMBOE_UPDATE_FEED !== "1"' in updater
    assert "KOMBOE_UPDATE_URL" in updater
    assert "await autoUpdater.checkForUpdates()" in updater
    assert "await autoUpdater.downloadUpdate()" in updater
    assert "autoUpdater.quitAndInstall(true, true)" in updater

    assert "KOMBOE_CLI_RELEASES_URL" in cli
    assert "A new version is available" in cli
    assert "You can download this update at" in cli

    assert "fn diagnostics" in admin
    assert "latest_release" in admin
    assert "admin_external_checks" in admin
    print("SELF UPDATE PASS")


if __name__ == "__main__":
    main()
