# SCIM (#41): the server is the SCIM provider. Deprovisioning revokes membership.
@t(41)
def _():
    import subprocess
    env = os.environ.copy()
    api = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "scim_api.py")], capture_output=True, text=True, timeout=180, env=env)
    if api.returncode != 0:
        raise RuntimeError((api.stdout + api.stderr)[-800:])
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "scim_web.py")], capture_output=True, text=True, timeout=180, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-800:])
    return DONE("SCIM Users and Groups against the server: a directory user is invited, deprovisioned by revoke, and no vault key is stored. The web vault shows a one-time token with a show/hide toggle")
