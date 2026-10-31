# Trusted devices (#42): SSO unlock without a master password. The server stores ciphertext only.
@t(42)
def _():
    import subprocess
    env = os.environ.copy()
    api = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "trusted_api.py")], capture_output=True, text=True, timeout=180, env=env)
    if api.returncode != 0:
        raise RuntimeError((api.stdout + api.stderr)[-800:])
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "trusted_web.py")], capture_output=True, text=True, timeout=240, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-800:])
    return DONE("SSO without a master password: the web vault trusts the browser, a later SSO login opens the vault, and the server stores only the device-wrapped user key")
