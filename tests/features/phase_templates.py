# Item templates (#15) on the real Komboe web vault.
@t(15)
def _():
    import subprocess
    env = os.environ.copy()
    web = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "templates_web.py")],
        capture_output=True,
        text=True,
        timeout=240,
        env=env,
    )
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-500:])
    return DONE(
        "Wi-Fi, passport, license, and bank templates in the web vault: each item is created, its secret has a show/hide toggle, and the secret is absent from the database"
    )
