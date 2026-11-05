# Clean-room secrets manager (#106)

Projects belong to organizations and administrative membership is checked for every management operation. Secret names are metadata; secret values must arrive as client-side ciphertext and are returned unchanged. The server has no decrypt endpoint or project key.

Service accounts are scoped to exactly one project. Tokens contain 256 random bits, are shown once, and only their SHA-256 digest is stored. Token lookup also checks revocation and every secret query includes the account's project identifier. No `bitwarden_license` code is copied or referenced.
