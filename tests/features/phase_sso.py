# SSO OIDC (#40): real Dex process. Keycloak browser E2E stays pending.
@t(40)
def _():
    import subprocess
    env = os.environ.copy()
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sso_dex.py")], capture_output=True, text=True, timeout=180, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-800:])
    return DONE("OIDC authorization-code + PKCE against Dex: IdP user logs in, no master-password hash and no user key stored. Keycloak browser E2E pending")
