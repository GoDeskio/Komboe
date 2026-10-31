# Proton-style dashboard (#105) inside the real web vault.
if "t" not in globals():  # standalone run: execute the check this phase wraps
    import os, runpy, sys
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_web.py"), run_name="__main__")
    sys.exit(0)
@t(105)
def _():
    import subprocess
    env = os.environ.copy()
    web = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "dashboard_web.py")], capture_output=True, text=True, timeout=180, env=env)
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-500:])
    return DONE("web vault uses Sora, the locked padlock-K logo, and a light/dark toggle on the vault page")
