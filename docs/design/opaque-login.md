# Design: OPAQUE login (aPAKE)

Status: proposal. No code in this PR.

## Goal
Replace "send the master-password hash to the server" with an augmented PAKE (OPAQUE, RFC 9807). After the change, the server never sees anything derived from the master password that would let it run an offline guessing attack.

## Invariants (unchanged)
- Zero-knowledge: the server only ever stores ciphertext and OPAQUE registration records.
- Admin password reset and Key Connector stay absent.
- The vault key is still unwrapped client-side. OPAQUE only replaces *authentication*.

## Threat model
| Threat | Today | With OPAQUE |
|---|---|---|
| A DB dump allows offline guessing | Possible against the stored server-side hash of the auth hash (KDF-hardened) | Still possible, but only against the OPRF-hardened record, and the attacker needs the server OPRF key too. Pre-computation is impossible |
| A malicious or compromised server logs logins | Sees the auth hash on every login and can replay it | Sees only OPAQUE messages. Nothing replayable |
| TLS-terminating proxy or log leak | Auth hash leaks | Nothing usable leaks |
| Phishing clone server | Gets the auth hash | Gets nothing usable (mutual auth: the client verifies the server's envelope) |
| Downgrade to legacy login | n/a | Mitigated: an account flag `opaque_only` plus the client remembering the method per account |
| Server OPRF key loss | n/a | Every user must re-register. The key goes in the existing secret store with a backup and rotation procedure |

Out of scope: a compromised client device, or a weak master password combined with a full server compromise (key plus DB).

## Building blocks
- Ciphersuite: ristretto255 + SHA-512, with Argon2id as the KSF using the account's existing KDF parameters.
- Rust server: an audited crate (`opaque-ke`, MIT/Apache). TS clients: a WASM build of the same crate through the existing SDK WASM path. This avoids writing a second implementation.
- Wire format: four new endpoints under `/identity/opaque/`: `register/start`, `register/finish`, `login/start`, `login/finish`. `login/finish` returns the normal token response.

## Phased plan
1. **Phase 0 (spike, behind a flag):** add the server crate and a test vector suite. No routes.
2. **Phase 1 (dual registration):** on the next successful legacy login or password change, the client also registers OPAQUE. The server stores `opaque_record` next to the existing hash. Legacy login is unchanged.
3. **Phase 2 (prefer OPAQUE):** clients try OPAQUE first when `/prelogin` advertises it, and fall back to legacy. Add metrics for the fallback rate.
4. **Phase 3 (opt-in strict):** a per-account `opaque_only` setting. The legacy hash is deleted for those accounts.
5. **Phase 4 (default):** new accounts are OPAQUE-only. Existing accounts are migrated as in Phase 1, and the legacy path is removed after a deprecation window.

Each phase is its own PR with tests: RFC test vectors, a round-trip integration test in `tests/`, and a downgrade test.

## Open questions
- Emergency access and organization invites must keep working. They do not use the master password hash, but they need to be checked.
- Rate limiting moves to `login/start`.
- CLI and mobile need the WASM or native bindings. This sets the mobile timeline.
