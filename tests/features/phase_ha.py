# Two Komboe nodes, one Postgres database.
import subprocess
from komboe.platform.crypto import dec, enc, enc_str, master_key, password_hash, stretch
@t(95)
def _():
    import psycopg2
    subprocess.run(["sudo", "pg_ctlcluster", "16", "main", "start"], check=False, capture_output=True)
    subprocess.run(["sudo", "-u", "postgres", "psql", "-c", "CREATE USER komboe WITH PASSWORD 'komboe' LOGIN"], check=False, capture_output=True)
    subprocess.run(["sudo", "-u", "postgres", "psql", "-c", "DROP DATABASE IF EXISTS komboe_ha"], check=True, capture_output=True)
    subprocess.run(["sudo", "-u", "postgres", "psql", "-c", "CREATE DATABASE komboe_ha OWNER komboe"], check=True, capture_output=True)
    dsn = "postgresql://komboe:komboe@127.0.0.1/komboe_ha"
    from komboe.platform.server import serve_in_thread
    node_a, _db_a = serve_in_thread(dsn)
    node_b, _db_b = serve_in_thread(dsn)
    base_a = f"http://127.0.0.1:{node_a.server_address[1]}"
    base_b = f"http://127.0.0.1:{node_b.server_address[1]}"
    email, pw, secret = f"ha-{uuid.uuid4().hex[:8]}@komboe.test", "Ha-master-" + uuid.uuid4().hex, "ha-secret-" + uuid.uuid4().hex
    mk = master_key(pw, email); uk = os.urandom(64)
    http("POST", "/api/accounts/register", {"email": email, "masterPasswordHash": password_hash(mk, pw), "kdfIterations": 600000, "userSymmetricKey": enc(uk, stretch(mk)), "name": "HA"}, base=base_a)
    token = http("POST", "/identity/login", {"email": email, "masterPasswordHash": password_hash(mk, pw)}, base=base_a)["accessToken"]
    made = http("POST", "/api/ciphers", {"type": 1, "name": enc_str("ha-item", uk), "data": enc_str(secret, uk)}, token=token, base=base_a)
    seen = http("GET", "/api/sync", token=token, base=base_b)
    row = next(c for c in seen["ciphers"] if c["id"] == made["id"])
    assert dec(row["data"], uk).decode() == secret
    node_a.shutdown()
    seen = http("GET", "/api/sync", token=token, base=base_b)
    assert any(c["id"] == made["id"] for c in seen["ciphers"])
    conn = psycopg2.connect(dsn)
    cur = conn.cursor(); cur.execute("SELECT data FROM ciphers"); stored = cur.fetchall()
    assert stored and secret not in stored[0][0] and uk not in stored[0][0].encode()
    node_b.shutdown()
    return DONE("two Komboe nodes share one Postgres database; a write on A is readable on B after A stops, and the row is ciphertext")
