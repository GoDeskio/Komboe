# Coolify pull deploy

Use `deploy/coolify/docker-compose.pull.yml` as Coolify's `docker_compose_location`. The host pulls prebuilt images from GHCR and does not compile them. `compose.coolify.yml` at the repository root still has a local compile path; do not point this resource at that file.

The public origin already used by the sandbox is `https://sandbox.komboe.com`. This file does not change DNS. Coolify's proxy terminates TLS and should send traffic to the `server` service on port 8080.

## Image digest

A push to `main` runs the `image` job in `.github/workflows/ci.yml`. That job runs `docker buildx build` for `docker/Dockerfile.server` and `docker/Dockerfile.clients` (`linux/amd64`, provenance and SBOM off) and pushes:

- `ghcr.io/godeskio/komboe-server:<full git sha>`
- `ghcr.io/godeskio/komboe-clients:<full git sha>`

Buildx writes `containerimage.digest` to a metadata file. The job prints that value with the `sha256:` prefix removed. Set these Coolify environment variables to those hex strings before deploying:

| Variable | Secret | What it is |
|---|---|---|
| `KOMBOE_SERVER_DIGEST` | no | Hex digest of `komboe-server` |
| `KOMBOE_CLIENTS_DIGEST` | no | Hex digest of `komboe-clients` |

The compose file pins `ghcr.io/godeskio/<name>@sha256:${DIGEST}`. Re-deploy after changing the two variables. The `clients` container copies the web vault into the `web-vault` volume and exits. The `server` container then starts from the new binary.

## Environment

No new secret is required. `ADMIN_TOKEN` and `SMTP_PASSWORD` are the same values the current sandbox compose already reads.

| Variable | Required | Default |
|---|---|---|
| `ADMIN_TOKEN` | yes | none. Admin page stays disabled until this is set. It is not printed, and the first account signup does not become an admin |
| `SMTP_PASSWORD` | yes, when SMTP auth is used | none |
| `DOMAIN` | no | `https://sandbox.komboe.com` |
| `SMTP_HOST` | no | `smtp.stackmail.com` |
| `SMTP_PORT` | no | `587` |
| `SMTP_SECURITY` | no | `starttls` |
| `SMTP_FROM` | no | `donotreply@komboe.com` |
| `SMTP_FROM_NAME` | no | `Komboe` |
| `SMTP_USERNAME` | no | `donotreply@komboe.com` |

Hard-coded in the compose file, same as the existing sandbox file: `SIGNUPS_ALLOWED=true`, `WEB_VAULT_ENABLED=true`, `WEB_VAULT_FOLDER=/web-vault`, `TEMPLATES_FOLDER=/data/templates`, `ROCKET_PORT=8080`.

Signup creates a normal account. It does not grant the server admin page. There is no first-signup setup token because that flow does not exist. Whoever creates an organization is that organization's owner; that is separate from `/admin`.

## Backup and restore

Both commands are the server binary. In this container the commands are `komboe backup` and `komboe restore <backup.sqlite3>`. Stop `server` before restore. The copy is the SQLite database only. Attachments under `/data` and `config.json` are not included.

```sh
docker compose exec server komboe backup
# prints: Backup to '/data/db_YYYYMMDD_HHMMSS.sqlite3' was successful

docker compose stop server
docker compose run --rm --no-deps server restore /data/db_YYYYMMDD_HHMMSS.sqlite3
docker compose start server
```

The same backup is available in the admin UI at `/admin` → Settings → Backup Database, which calls `POST /admin/config/backup_db`. Sending `USR1` to the server process also runs a backup. Restore has no admin button.

A native build uses the cargo artifact name: `vaultwarden backup` and `vaultwarden restore <file>`, with `DATA_FOLDER` set. See [docs/RUNNING.md](../../docs/RUNNING.md#backup-and-restore).

## Updates

Changing the two digest variables and redeploying is how this stack moves to a new server and web vault. The host pulls the pinned images.

These client update paths are unchanged:

- Desktop **Check for Updates** still downloads and installs when `KOMBOE_UPDATE_FEED=1` (Windows and macOS). Linux auto-update stays off, as it did before.
- `komboe update` still reads `KOMBOE_CLI_RELEASES_URL` and reports the download URL.
- `/admin` → Diagnostics still compares versions when `ADMIN_EXTERNAL_CHECKS=true`. It does not download a server image.
