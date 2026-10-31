# KeePass KDBX import/export (#77) through the real Komboe CLI.
@t(77)
def _():
    import subprocess
    r = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "kdbx_cli.py")],
        capture_output=True,
        text=True,
        timeout=600,
        env=os.environ.copy(),
    )
    if r.returncode != 0:
        raise RuntimeError((r.stdout + r.stderr)[-500:])
    return DONE(
        "KDBX: kdbxweb and pykeepass-written KDBX 4 files import (encrypted at rest, protected fields hidden); export writes KDBX 4 read by pykeepass and re-imported"
    )
