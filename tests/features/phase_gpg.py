# GPG keys (#17) on the real Komboe web vault.
@t(17)
def _():
    import subprocess
    env = os.environ.copy()
    web = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "gpg_web.py")],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-500:])
    return DONE(
        "GPG key template in the web vault: private key and passphrase have show/hide toggles and are absent from the database"
    )
