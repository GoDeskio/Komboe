#!/usr/bin/env python3
"""Interval email sign-in decisions. Mirrors server/upstream/src/api/core/email_interval.rs."""
ALLOWED = {60, 300, 600, 900, 1800, 3600, 21600, 86400}


def parse_interval(seconds):
    if seconds is None or seconds == 0:
        return None
    if seconds in ALLOWED:
        return seconds
    raise ValueError("unsupported interval")


def challenge_due(interval, verified_at, now):
    if interval is None or interval <= 0:
        return False
    if verified_at is None:
        return True
    return now >= verified_at + interval


def judge(expires_at, used_at, attempts, matches, now):
    if used_at is not None:
        return "used"
    if now >= expires_at:
        return "expired"
    if attempts >= 5:
        return "too_many"
    return "ok" if matches else "mismatch"


def main():
    assert parse_interval(None) is None
    assert parse_interval(0) is None
    assert parse_interval(60) == 60
    try:
        parse_interval(7)
        raise SystemExit("bad interval accepted")
    except ValueError:
        pass

    assert challenge_due(None, None, 1000) is False
    assert challenge_due(60, None, 1000) is True
    assert challenge_due(60, 1000, 1059) is False
    assert challenge_due(60, 1000, 1060) is True
    # A failed login must not move verified_at. The same timestamp still expires on time.
    verified = 1000
    assert challenge_due(60, verified, 1010) is False
    assert challenge_due(60, verified, 1060) is True

    assert judge(1100, None, 0, True, 1000) == "ok"
    assert judge(1000, None, 0, True, 1000) == "expired"
    assert judge(1100, 1, 0, True, 1050) == "used"
    assert judge(1100, None, 5, True, 1050) == "too_many"
    assert judge(1100, None, 1, False, 1050) == "mismatch"

    auth = open("apps/web-marketing/assets/auth.js", encoding="utf-8").read()
    vault = open("apps/web-marketing/assets/vault.js", encoding="utf-8").read()
    server = open("server/upstream/src/api/core/email_interval.rs", encoding="utf-8").read()
    assert "passwordHash(accountEmail" in auth
    assert "could not be sent" in auth
    assert "email-login-interval" in vault
    assert "Never" in vault
    assert "challenge_due" in server
    assert "clear_user" in server
    assert "TwoFactorProviders" in server
    print("EMAIL INTERVAL PASS")


if __name__ == "__main__":
    main()
