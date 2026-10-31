# S3 attachment backend (#96): server built with --features sqlite,s3 against a local moto S3.
@t(96)
def _():
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "s3_attachments.py")], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError((r.stdout + r.stderr)[-800:])
    return DONE("S3 backend (cargo feature s3) against local moto S3: attachment ciphertext lands in the bucket (not local disk), downloads via API, delete removes the object (tests/features/s3_attachments.py)")
