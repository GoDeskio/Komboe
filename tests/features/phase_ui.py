# Proton-style Komboe dashboard (#105). Loaded into run.py after the earlier phases.
@t(105)
def _():
    import subprocess
    script = os.path.join(ROOT, "tests/features/dashboard_e2e.py")
    proc = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError((proc.stdout + proc.stderr)[-500:])
    return DONE("Proton-style three-pane vault: light/dark, Sora wordmark, padlock-K bytes match the locked variants; browser E2E creates a login and the server DB holds only ciphertext")
