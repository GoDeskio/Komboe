# SIEM export (#35)

Organization owners/admins configure one HTTPS webhook or RFC5424 syslog destination. Plain HTTP is accepted only for an explicit loopback host so local listeners can test the flow. Webhooks carry `X-Komboe-Signature: sha256=<hex>` over the exact body; syslog supports TCP and certificate-verified TLS. Export is best-effort and never blocks event persistence.

The allow-listed event envelope contains event type, organization/acting-user identifiers, timestamp, device type, and IP address. It never serializes ciphers, keys, item names, credentials, attachments, or other vault data. Configuration responses never return the HMAC secret.
