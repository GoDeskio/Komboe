# Timed email sign-in and login names

This revision changes the login protocol. A server that has the timer tables must be paired with the web vault, desktop app, and browser extension from the same revision. Do not point an older sandbox client at a server where any account has a non-Never email interval.

## What an old client does

An old client does not send `komboeLoginChallenge` or `komboeDeviceTrust`. If the account's timer is due, the server still requires the code. The old client cannot complete that challenge, so sign-in stops. The account is not silently let in.

Leave the interval at Never until the new clients are what users actually run.

## Trust token

`KomboeDeviceTrust` is a bearer secret for one account. It is not bound to a device, a browser profile, or a piece of hardware. Any client that has the secret can skip the timer until it expires or the server revokes it. Logout must POST the secret and only then delete the local copy. A failed POST leaves the copy in place so logout can try again. Until that POST succeeds, the secret remains valid for its window (at most 24 hours).

A token for one account does not satisfy the timer on another account.

An in-window login does not return a new token. Clients must keep the token they already have.

## Mail stops working

Turning the timer on requires mail, email second factor, and a verified mailbox. If any of those later stop, an already enabled timer is still required. Sign-in is not completed and no vault token is issued. That is not a bypass.

The recovery is explicit: a session that is already signed in sets the interval to Never with the master password. There is no unauthenticated switch that turns the factor off.

## Login names

Prelogin does not resolve a login name and does not return a vault-key email for anyone. A new account, an old account, and an unknown email all omit that field. Returning it only for accounts that have a stored salt told an anonymous caller which addresses were registered.

Signing in with a name calls `/identity/accounts/login-name/open`. The KDF in that response is always PBKDF2-SHA256 with 600000 iterations, for a name that exists and for one that does not. It is not the account's KDF. A custom count or Argon2 would not match the miss response, so those parameters stay out of the body. A miss has the same KDF fields and the same envelope bytes every time.

The envelope is sealed with that public wrap and a random salt. Inside it are the registration email, including its case, and the account's own KDF. After the wrap opens, the vault key uses that inner KDF and that email. `users.email` is stored lowercased for lookup and is not the salt. This client's email sign-in still lowercases the typed address, which is how registration derives the salt. A mixed-case salt unlocks through the login name, or through a client that hashes that exact string.

A login name is refused when the account KDF is stronger than the public wrap: PBKDF2 above 600000 iterations, or Argon2. Sealing those accounts with the wrap would be a cheaper password check. Their vault KDF is not changed. They sign in with the email.

Accounts created before migration `20261108040000` have no stored salt. A signed-in client can record one only when it lowercases to `users.email`. A mixed-case salt from before that migration cannot be reconstructed from the lowercased column.

Migration `20261108030000` added `verifier_hash` for the old PBKDF2-100000 proof. Migration `20261108050000` sets every value to null. The column remains because the SQLite build this server uses cannot drop it. The server does not read or write it.

Enrollment is the signed-in device settings page. It sends the master-password hash and the envelope. There is no unauthenticated verifier. Changing the master password or the account email clears the envelope. The person saves the login name again while signed in. If the vault key was derived from an older email, this login cannot invent that salt.

The old `/identity/accounts/login-name/resolve` route is gone. A client that still sends the 100000 verifier cannot learn the email.

## Logout and the extension

The trust token is stored in `sessionStorage` on the web vault and the desktop app. The extension service worker has no `sessionStorage`. It uses `chrome.storage.session`, which the popup shares. Logout POSTs the token and deletes the local copy only after the server accepts it. If that store cannot be read, logout does not report the token as cleared.

## Lock

Lock clears decrypted cipher and folder caches, then the in-memory user key, waits until the account is locked, and reloads the process. Unsaved edits are discarded by that reload. The lock button does not clear the key first and does not open the lock screen without a reload.

## Rollback

Migration `20261108020000` creates the trust and challenge tables and deletes the old device-id trust rows. Migration `20261108030000` adds resend counters and the login-name verifier column. Migration `20261108040000` stores the original vault-key email and the login-name envelope. Migration `20261108050000` clears every verifier hash and does not drop the column.

Rolling the server back to a build that reads device-id trust does not restore those deleted rows, so every account with a timer is challenged again. A rolled-back server also does not understand `KomboeDeviceTrust` or the envelope. Rolling the database back past `20261108020000` drops the new tables. Do that only with a backup taken before the migration, and only while no account depends on the timer. SQLite cannot drop the envelope columns; a rollback there is a forward server build plus a database backup, not a down migration.

Do not publish a release that enables the timer, or that serves the login-name page, until that release's web, desktop, and extension builds are the ones being served. Those clients and the server are one revision. Do not mix an older client with this server.
