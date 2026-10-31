# Design: Komboe SSH agent

Status: proposal. No code in this PR.

## Goal
Store SSH private keys as vault items (cipher type `SshKey`, which already exists in the upstream model), and serve them through a local SSH agent from the desktop app. Private keys never leave the client unencrypted.

## Invariants
- Zero-knowledge: keys sync only as vault ciphertext.
- Signing happens in the desktop process. The raw key is never written to disk or exposed on the socket.

## Threat model
| Threat | Mitigation |
|---|---|
| Any local process uses the agent socket | Socket at `$XDG_RUNTIME_DIR/komboe-ssh.sock` with mode 0600 (named pipe with an owner-only DACL on Windows). Per-request **user approval** prompt showing the requesting process, key and host. "Remember for N minutes" is optional |
| A forwarded agent is abused by a remote host | Docs recommend no `ForwardAgent`. When the request is from a forwarded session (detectable via the `session-bind@openssh.com` extension), always prompt and show the destination |
| Signing while the vault is locked | The agent lists no keys and refuses to sign while locked. "Unlock to sign" prompt |
| Memory scraping | Keys are decrypted per sign operation and zeroized after. Existing desktop memory hardening applies |
| A malicious key import (e.g. weak or RSA-1024) | Validate on import: reject RSA < 2048 and DSA. Ed25519 is the default for generated keys |
| Signing protocol confusion | Only standard agent messages are implemented (`REQUEST_IDENTITIES`, `SIGN_REQUEST`, and the `session-bind` extension). Add, remove and lock are refused |

## Phased plan
1. **Phase 1:** a vault item UI for SSH keys in web, browser and desktop (generate Ed25519, import OpenSSH or PEM, copy the public key). Reuse the upstream SDK key parsing. No agent yet.
2. **Phase 2:** a desktop agent on Linux and macOS (Rust, in the existing desktop native module). List and sign with an approval prompt. Tests: a protocol unit test with recorded agent frames, plus an integration test with `ssh-keygen -Y sign` against the socket in CI.
3. **Phase 3:** Windows named pipe, and coexistence with the OpenSSH agent service (a detection warning).
4. **Phase 4:** per-key policy (always prompt, prompt once per session, or allowed host list) and an audit log of signs in the local event log.

## Open questions
- Git commit signing (`gpg.format=ssh`) works for free once Phase 2 ships. Document it.
- Organization-shared SSH keys follow the existing collection permissions. Signing still needs a local prompt.
