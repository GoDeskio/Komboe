# Environment variables (#16) on the real Komboe web vault.
@t(16)
def _():
    import subprocess
    env = os.environ.copy()
    web = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "env_web.py")],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-500:])
    return DONE(
        "Environment variables template: web form takes .env text, each variable stored as an encrypted hidden field; `bw get dotenv` prints it; no plaintext on the server"
    )
