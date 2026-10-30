# Bookmarks (#18) on the real Komboe web vault.
@t(18)
def _():
    import subprocess
    env = os.environ.copy()
    web = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "bookmarks_web.py")],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    if web.returncode != 0:
        raise RuntimeError((web.stdout + web.stderr)[-500:])
    return DONE(
        "Bookmark template in the web vault: a saved URL is created, shown again after reopen, and absent from the database"
    )
