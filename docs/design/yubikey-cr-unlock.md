# YubiKey challenge-response / WebAuthn PRF unlock

Status: server endpoints live (`/api/komboe/unlock-credentials`).

Server stores only `wrappedUserKey`, salt, and public credential metadata. PRF/CR output never leaves the authenticator + client. Kinds: `webauthn_prf`, `yubikey_hmac_sha1`. See also `yubikey-unlock.md`.
