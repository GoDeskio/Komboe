# Proton-style dashboard (#105) inside the real web vault.
@t(105)
def _():
    import subprocess
    env = os.environ.copy()
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "dashboard_web.py")], capture_output=True, text=True, timeout=180, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-500:])
    return DONE("web vault uses Sora, the locked padlock-K logo, and a light/dark toggle on the vault page")
