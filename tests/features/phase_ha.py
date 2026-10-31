# Postgres HA (#95): two Vaultwarden processes, one database.
@t(95)
def _():
    import subprocess
    env = os.environ.copy()
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "ha_postgres.py")], capture_output=True, text=True, timeout=180, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-800:])
    return DONE("two Vaultwarden processes on one Postgres 16 database with a shared DOMAIN, RSA key and data folder: A-minted token works on B, B writes read on A, 20 concurrent writes split across nodes all land, B serves after A dies")
