# Komboe email

SMTP is configured only with environment variables. The default sender is `no-reply@komboe.com` with the display name Komboe. Override it with `SMTP_FROM` and `SMTP_FROM_NAME` when a self-hosted server should use its own address.

```sh
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_FROM=no-reply@komboe.com
SMTP_FROM_NAME=Komboe
SMTP_USERNAME=
SMTP_PASSWORD=
```

`SMTP_SECURITY` is `starttls`, `force_tls`, or `off`. Local tests use `off` against Mailpit.

Every message has an HTML part and a plain-text part. HTML uses the padlock-K mark (`logo-komboe.png`) and the Sora font (`sora.woff2`, SIL OFL 1.1, self-hosted, no font CDN). There is no GoDesk name in the templates.

## Messages

| Kind | When it is sent |
|---|---|
| Sign-up verification | A new account must confirm the email address before the vault exists |
| Sign-in verification code | Email two-step login, including the code that finishes a sign-in |
| New device | A session starts from a device this account has not used. The message names the device and links to Settings → Security → Devices and Deauthorize sessions |
| Master password changed | The master password was changed and other sessions were signed out |
| Two-step login changed | Email two-step login was turned on, or a two-step method was turned off |
| Recovery code used | The two-step recovery code was used and two-step login was removed |
| Failed sign-in | A master password was rejected. At most one of these per address every 10 minutes |
| Incomplete two-step login | The password was accepted and the second step was not finished in time |
| Emergency access | Invite, acceptance, confirmation, request, reminder, approval, rejection, timeout |
| Sharing invite | An organization invite, plus accepted and confirmed notices |
| Account deletion | The delete-account message with the confirmation link |

## DNS for komboe.com

These records are what a receiving server expects for mail from `komboe.com`. They are not applied by this repository. Do not change live DNS from here.

| Record | Name | Purpose |
|---|---|---|
| SPF | `komboe.com` TXT | `v=spf1 include:_spf.example.com -all` listing only the hosts that actually send. Replace the include with the SMTP provider's SPF mechanism |
| DKIM | `komboe._domainkey.komboe.com` TXT | Public key that matches the private key used to sign outbound mail. The selector name is chosen with the SMTP provider |
| DMARC | `_dmarc.komboe.com` TXT | `v=DMARC1; p=quarantine; rua=mailto:dmarc@komboe.com; adkim=s; aspf=s` once SPF and DKIM both pass. Start with `p=none` while checking reports |

The envelope sender and the `From` address should both be on `komboe.com` so SPF and DKIM alignment succeed. A self-hosted server that sends as `no-reply@komboe.com` must be listed in the komboe.com SPF record, or it should use its own domain in `SMTP_FROM`.

## Local sink

`docker-compose.yml` runs Mailpit. The server is pointed at it with `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, and `SMTP_SECURITY=off`. The inbox is `http://localhost:8025`.

`python3 tests/features/email_templates.py` checks that each required template has HTML and plain text, the Komboe mark, Sora, and no GoDesk name, then sends those messages through Mailpit and reads them back.
