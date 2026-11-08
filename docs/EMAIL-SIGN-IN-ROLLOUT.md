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

Prelogin does not resolve a login name and does not return an email or the account KDF. The client sends a separate verifier (PBKDF2-SHA256, login name as salt, 100000 iterations). Only a match returns the email and the real KDF, and the vault key is still derived from that email. A wrong verifier gets the same error as an unknown name.

The verifier is not the vault key. Guessing it online is rate-limited with the other login attempts. A database copy of the stored hash is not the verifier. Changing the master password or the account email clears the verifier; the person saves the login name again while signed in. If the account email changed and the vault key was still derived from the previous email, this login cannot invent that older salt.

## Rollback

Migration `20261108020000` creates the trust and challenge tables and deletes the old device-id trust rows. Migration `20261108030000` adds resend counters and the login-name verifier column.

Rolling the server back to a build that reads device-id trust does not restore those deleted rows, so every account with a timer is challenged again. A rolled-back server also does not understand `KomboeDeviceTrust`. Rolling the database back past `20261108020000` drops the new tables. Do that only with a backup taken before the migration, and only while no account depends on the timer.

Do not publish a release that enables the timer for existing accounts until that release's web and extension builds are the ones being served.
