# Login anomaly detection (#55)

Login outcomes feed a metadata-only detector. IPv4 addresses are reduced to `/24` and IPv6 to `/64` before anomaly storage. Signals are a simultaneous new device/new prefix, a prefix change inside one hour (conservative impossible-travel proxy), and five consecutive failures. Raw passwords, tokens, and vault data are never recorded.

Anomalies are stored per user and trigger a generic security email. `KOMBOE_ANOMALY_STEP_UP=true` rejects high-risk successful authentication once so the client must authenticate again; normal account 2FA remains authoritative. The in-memory comparison state intentionally resets on restart, avoiding a new durable device-tracking profile.
