# Design: key-file unlock (second factor for the master key)

Source: the REA scan of KeePassXC (key-file and challenge-response unlock), rebuilt independently. No code was copied. Status: design only, and nothing is implemented yet.

## Goal
Optionally require a local key file, as well as the master password, to derive the account's master key. A stolen password alone then can't unlock an exported vault or local cache.

## Zero-knowledge constraints (non-negotiable)
- The key file never leaves the device. The server stores only a flag (`kdfKeyFile: true`) and a public, non-secret salt.
- There is no server-side reset or escrow, and no backdoor. Losing the key file means the same thing as losing the master password: recovery only through the user's existing emergency access or org recovery that the user enrolled in beforehand.

## Derivation
`stretched = Argon2id(password, email-salt)` (the existing KDF), then `fileKey = HKDF-SHA256(SHA-256(keyFileBytes), info="komboe-keyfile-v1")`, then `masterKey = HKDF-SHA256(ikm = stretched || fileKey, info="komboe-master-v2")`.
- The master password hash sent for login is derived from the new master key, so the server can't tell whether a key file was used.
- Enabling or disabling the key file is a master-key rotation (re-wrap the user key), using the existing "change KDF" flow.

## Phases
1. CLI: `komboe config keyfile <path>`, plus derivation behind `KOMBOE_KEYFILE=1`, with test vectors.
2. Web and desktop: a file picker on the lock screen, with the file remembered per device. Never synced.
3. Browser extension and mobile.

## Tests
Known-answer vectors; a wrong file fails exactly like a wrong password; the server sees no new secret material.

## Risks
Users losing the file. Mitigations: a mandatory backup prompt and a printable recovery sheet.
