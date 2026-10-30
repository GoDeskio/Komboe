# Password expiry (#37) on the real Komboe server and web vault.
@t(37)
def _():
    import subprocess
    env = os.environ.copy()
    api = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "expiry_api.py")], capture_output=True, text=True, timeout=120, env=env)
    if api.returncode != 0:
        raise RuntimeError((api.stdout + api.stderr)[-500:])
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "expiry_web.py")], capture_output=True, text=True, timeout=180, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-500:])
    return DONE("password expiry: org policy type 21 and a personal setting; a login shows Password expired in the web vault")
