# XChaCha20-Poly1305 vault encryption (feature #100): design

Status: **design only, not implemented** (#100 stays `partial`). This doc covers why, and what the work is.

## Goal
Move vault data from AES-256-CBC + HMAC-SHA256 (EncString type 2) to AEAD XChaCha20-Poly1305. That gives a 192-bit random nonce,
one primitive instead of encrypt-then-MAC, and no padding oracle surface. The zero-knowledge model stays the same:
all encryption is client-side, the server only stores opaque ciphertext, and there is **no** escrow, recovery key, admin reset or Key Connector.

## What upstream already has (clients web-v2026.10.1)
The client crypto SDK (`@bitwarden/sdk-internal`, from source in `sdk-internal`, GPL-3.0) already defines
**EncString type 7 `CoseEncrypt0`**: a COSE_Encrypt0 envelope whose content algorithm is XChaCha20-Poly1305
(`libs/legacy-crypto/src/enums/encryption-type.enum.ts`). That makes it the "new EncString type" we need, so Komboe will **not**
invent its own type number. Inventing one would fork the wire format and break interop with the SDK.
Type 7 comes with "account encryption v2", which is gated by these client feature flags:
`pm-27278-v2-password-registration`, `force-upgrade-v2-encryption` and the related ones. Komboe must never enable the
`*-key-connector-*` and TDE variants (hard rule: no Key Connector).

Account encryption v2 is more than a cipher swap:
- The user key becomes a COSE key (XChaCha20-Poly1305), and items are encrypted as type 7.
- The account gets an **Ed25519 signing key pair**. The signing key is wrapped by the user key, the public key is signed,
  and the RSA public key is signed by the signing key.
- The account carries a signed **security state** (a version counter that guards against server-side downgrades).

## Server acceptance (Vaultwarden 1.37.4 base): missing today
- `User` has only `akey`, `private_key` and `public_key`. `account_keys_json()` returns `signatureKeyPair: null` and `securityState: null`.
- Registration (`/identity/accounts/register`, `/accounts/set-password`) and rotation (`/accounts/key-management/rotate-user-account-keys`)
  take the v1 shapes only. v2 sends `accountKeys.signatureKeyPair {wrappedSigningKey, verifyingKey}`,
  `publicKeyEncryptionKeyPair.signedPublicKey` and `securityState {securityState, securityVersion}`.
- `SUPPORTED_FEATURE_FLAGS` has none of the v2 flags, so the clients never take the v2 path.

Server changes:
1. DB migration (sqlite, mysql, postgres): new nullable columns `signing_key_wrapped`, `verifying_key`, `signed_public_key`,
   `security_state` and `security_version` on `users`.
2. Accept and return them in register, set-password, rotate-user-account-keys, `/sync` and `/accounts/profile` (`accountKeys`)
   and in the identity token response. The server stores them as opaque values. It must **not** try to decrypt or check
   anything other than shape and size. It can verify signatures, but doesn't have to, because the client checks them.
3. Treat cipher, folder and send fields as opaque strings, which they already are. Type-7 strings pass through unchanged.
   Field length limits must allow the longer COSE strings (about 1.3x).
4. Add the v2 password-registration and force-upgrade flags to `SUPPORTED_FEATURE_FLAGS`, off by default, behind
   `KOMBOE_AEAD_V2=true` (env flag).
5. Downgrade protection: reject a rotate or set-keys call whose `securityVersion` is lower than the stored one.

## Migration
- New accounts: once the flag is on, the client registers v2 directly.
- Existing accounts: `force-upgrade-v2-encryption` triggers the client-side **user-key rotation** that upstream already ships
  (`v2-key-rotation-migration.ts`). On unlock, the client makes a new v2 user key and signing keys, re-encrypts every
  item, folder, send, attachment key and org-key wrap, and posts them in one `rotate-user-account-keys` call.
  The server applies the call in one DB transaction, or not at all.
- Emergency access and org memberships are rewrapped during rotation, as in v1 rotation. Emergency access stays consent-based;
  it is not escrow.
- Exports: encrypted JSON exports already carry their own envelope, so they're unaffected. Unencrypted exports are unaffected.

## Compatibility
- Old clients (before v2) can't read type 7 and would show "[error: cannot decrypt]". The flag must stay off until every
  Komboe client we ship (web, extension, desktop, CLI and Android, all built from the pinned tree) understands type 7.
  Android pulls its SDK from GitHub Packages, so check its version.
- v1 and v2 accounts live side by side on one server. An org can have both. Org keys stay RSA-wrapped per member.
- Rollback: once an account is rotated to v2, it can't go back without another rotation. Back up the DB before turning the flag on.

## Tests (to add when implemented)
- Server unit tests: the new columns round-trip, downgrade is rejected, and unknown or oversized fields are rejected.
- Feature suite: register a v2 user through the API and check `accountKeys.securityState` is non-null. Check that the stored
  cipher strings start with `7.`, and that the DB (`KOMBOE_DB`) holds no plaintext.
- Playwright: log in as a v1 user with the force-upgrade flag on, check that items still decrypt after rotation and that
  the server's cipher rows changed to type 7, then log in with the CLI and extension to show interop.

## Why it isn't implemented in Phase D
Every piece of the work is in the **server** (schema, endpoints, flag gating). Rebuilding Vaultwarden needs its Cargo
dependency tree, which was deleted to free disk (about 3 GB), plus a DB migration, and both are bigger than this box allows right now.
No client fork is needed. Next step: a server PR doing items 1-5 behind `KOMBOE_AEAD_V2`, off by default, with the tests above.
