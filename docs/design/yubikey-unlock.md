# Design: YubiKey (hardware) vault unlock

Status: proposal. No code in this PR.

## Goal
Unlock the vault with a hardware security key instead of typing the master password. This is not just 2FA at login: the key material itself comes from the device. Use the WebAuthn **PRF extension** (hmac-secret on YubiKey 5 and later), as the upstream "passkey unlock" model does.

## Invariants
- Zero-knowledge: the server stores only `wrappedUserKey = Enc(PRF-derived key, userKey)` plus the public credential data. Neither is useful without the device.
- The master password stays a valid unlock path, so recovery still works. No admin reset is added.

## Threat model
| Threat | Mitigation |
|---|---|
| Server compromise | The wrapped key needs the PRF output, which never leaves the authenticator and client. The server cannot unwrap it |
| Stolen YubiKey | A user-verification PIN is required (`userVerification: "required"`). The user can revoke the credential from another session, which deletes the wrapped key server-side |
| Phishing site | WebAuthn origin binding: the PRF salt is evaluated only for the Komboe RP ID |
| Lost key | Master password unlock still works. Users are encouraged to register two keys |
| Downgrade to a non-PRF credential | Only credentials that return PRF results at registration can be enrolled for unlock |
| Wrong-key confusion | Each credential has its own wrapped key and a random 32-byte salt. HKDF with the domain label `komboe-unlock-v1` |

## Phased plan
1. **Phase 1:** web vault enrollment and unlock (Chromium plus a PRF-capable key). Server: a `user_unlock_credentials` table (credential id, public key, salt, wrapped key, name, created) and three endpoints (list, add, delete). Tests: a server unit test plus a client spec with a mocked `navigator.credentials`.
2. **Phase 2:** browser extension unlock (an extension-page WebAuthn popup).
3. **Phase 3:** desktop (Electron WebAuthn, or a native CTAP2 hmac-secret via libfido2 where PRF is unavailable).
4. **Phase 4:** mobile (Android Credential Manager PRF, and iOS 18+ PRF).

## Open questions
- Whether a hardware key can **replace** the master password entirely ("passwordless vault"). Not proposed: it would change the recovery model.
- Firefox PRF support status has to be checked when Phase 2 starts.
