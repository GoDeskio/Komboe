# Tags (#4) on the real Komboe server and web vault.
@t(4)
def _():
    import subprocess
    env = os.environ.copy()
    api = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "tags_api.py")], capture_output=True, text=True, timeout=120, env=env)
    if api.returncode != 0:
        raise RuntimeError((api.stdout + api.stderr)[-400:])
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "tags_web.py")], capture_output=True, text=True, timeout=180, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-400:])
    return DONE("encrypted tags in the Vaultwarden server and the web vault: create a tag, attach it to a login, filter it, plaintext absent from the database")
