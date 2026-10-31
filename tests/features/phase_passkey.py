# Log in with a passkey (#50) on the real Komboe web vault.
@t(50)
def _():
    import subprocess
    web = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "passkey_web.py")],
        capture_output=True,
        text=True,
        timeout=300,
        env=os.environ.copy(),
    )
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-500:])
    return DONE(
        "Passkey login: registered in web settings (discoverable, user-verified, PRF), signed out, signed back in with only the passkey to an unlocked vault; server stores client-wrapped keys only, passkey is not 2FA, forged/replayed assertions refused"
    )
