# Design: Secret Service / FreeDesktop integration

Status: implemented in desktop native (`oo7` Keyring on Linux).

Komboe desktop uses the FreeDesktop Secret Service API via the `oo7` crate (`get_password` / `set_password` / `delete_password` in `desktop_native/core/src/password/unix.rs`). Session unlock prompts go through the keyring; locked keyrings fail closed on delete to avoid noisy misbehavior notices.
