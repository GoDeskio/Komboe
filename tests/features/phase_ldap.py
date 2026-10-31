# LDAP/AD (#39): real slapd, no directory user passwords stored.
@t(39)
def _():
    import subprocess
    env = os.environ.copy()
    api = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "ldap_api.py")], capture_output=True, text=True, timeout=180, env=env)
    if api.returncode != 0:
        raise RuntimeError((api.stdout + api.stderr)[-800:])
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "ldap_web.py")], capture_output=True, text=True, timeout=180, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-800:])
    return DONE("LDAP sync against slapd: a directory user is invited into a group, disappears from the directory and is revoked, and the directory password is not stored. The web vault runs the sync")
