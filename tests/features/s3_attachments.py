#!/usr/bin/env python3
"""S3 attachment backend (#96): a Komboe server built with `--features sqlite,s3` stores attachments in an
S3 bucket (local moto S3 server; no cloud account). Upload -> object in bucket holds ciphertext only ->
download through the API -> delete removes the object.
Needs: KOMBOE_S3_BIN (server built with s3), a python with moto[server] + boto3 (KOMBOE_MOTO_PY)."""
import base64, importlib.util, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request, uuid

PORT, S3PORT = 18096, 18097
os.environ["KOMBOE_URL"] = f"http://127.0.0.1:{PORT}"
spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec); spec.loader.exec_module(ft)

BIN = os.environ.get("KOMBOE_S3_BIN", "/workspace/komboe/server/upstream/target/release/vaultwarden")
MOTO_PY = os.environ.get("KOMBOE_MOTO_PY", "/workspace/run/motovenv/bin/python")
BUCKET, ENDPOINT = "komboe-attachments", f"http://127.0.0.1:{S3PORT}"
CREDS = {"AWS_ACCESS_KEY_ID": "komboe-test", "AWS_SECRET_ACCESS_KEY": "komboe-test-secret", "AWS_REGION": "us-east-1"}


def wait_port(port, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.3)
    raise SystemExit(f"port {port} did not open")


def s3(script):
    env = dict(os.environ, **CREDS)
    pre = f"import boto3; c = boto3.client('s3', endpoint_url='{ENDPOINT}', region_name='us-east-1')\n"
    return subprocess.run([MOTO_PY, "-c", pre + script], env=env, check=True, capture_output=True, text=True).stdout


def main():
    folder = tempfile.mkdtemp(prefix="komboe-s3-")
    moto = subprocess.Popen([os.path.join(os.path.dirname(MOTO_PY), "moto_server"), "-p", str(S3PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    vw = None
    try:
        wait_port(S3PORT)
        s3(f"c.create_bucket(Bucket='{BUCKET}')")
        env = dict(os.environ, **CREDS)
        env.update({"DATA_FOLDER": os.path.join(folder, "data"), "ROCKET_PORT": str(PORT), "ROCKET_ADDRESS": "127.0.0.1",
                    "DOMAIN": f"http://127.0.0.1:{PORT}", "SIGNUPS_ALLOWED": "true", "WEB_VAULT_ENABLED": "false",
                    "ATTACHMENTS_FOLDER": f"s3://{BUCKET}/attachments?endpoint={ENDPOINT}&region=us-east-1"
                                          "&enable_virtual_host_style=false&default_storage_class=STANDARD",
                    "LOGIN_RATELIMIT_MAX_BURST": "1000"})
        os.makedirs(env["DATA_FOLDER"])
        vw = subprocess.Popen([BIN], env=env, stdout=open(os.path.join(folder, "vw.log"), "w"), stderr=subprocess.STDOUT)
        wait_port(PORT); time.sleep(0.4)

        u = ft.User()
        cid = u.api("POST", "/api/ciphers", u.cipher())["id"]
        fk = os.urandom(64); data = b"S3-ATTACHMENT-" + uuid.uuid4().hex.encode()
        iv, ct, mac = map(base64.b64decode, ft.enc(data, fk)[2:].split("|")); payload = b"\x02" + iv + mac + ct
        r = u.api("POST", f"/api/ciphers/{cid}/attachment/v2", {"key": ft.enc(fk, u.uk), "fileName": u.e("f.bin"), "fileSize": len(payload)})
        aid, bnd = r["attachmentId"], uuid.uuid4().hex
        mp = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"f\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + payload + f"\r\n--{bnd}--\r\n".encode()
        urllib.request.urlopen(urllib.request.Request(ft.URL + f"/api/ciphers/{cid}/attachment/{aid}", data=mp, method="POST",
            headers={"Authorization": "Bearer " + u.at, "Content-Type": f"multipart/form-data; boundary={bnd}"})).read()

        key = f"attachments/{cid}/{aid}"
        stored = s3(f"import sys; sys.stdout.write(c.get_object(Bucket='{BUCKET}', Key='{key}')['Body'].read().hex())")
        stored = bytes.fromhex(stored)
        assert stored == payload and data not in stored, "bucket must hold the client ciphertext"
        assert not os.path.exists(os.path.join(env["DATA_FOLDER"], "attachments", cid)), "attachment written to local disk"
        print(f"  upload ok: object s3://{BUCKET}/{key} ({len(stored)} bytes, ciphertext only)")

        att = next(x for x in u.api("GET", "/api/sync")["ciphers"] if x["id"] == cid)["attachments"][0]
        got = urllib.request.urlopen(att["url"] if att["url"].startswith("http") else ft.URL + att["url"]).read()
        assert got == payload
        print("  download ok via API")

        u.api("DELETE", f"/api/ciphers/{cid}/attachment/{aid}")
        left = s3(f"print(c.list_objects_v2(Bucket='{BUCKET}', Prefix='attachments/').get('KeyCount', 0))").strip()
        assert left == "0", f"object not deleted ({left} left)"
        print("  delete ok: object removed from bucket")
        print("S3 ATTACHMENTS PASS")
    finally:
        if vw:
            vw.terminate(); vw.wait(timeout=10)
        moto.terminate(); moto.wait(timeout=10)
        if os.environ.get("KEEP") != "1":
            shutil.rmtree(folder, ignore_errors=True)
        else:
            print("kept", folder)


if __name__ == "__main__":
    main()
