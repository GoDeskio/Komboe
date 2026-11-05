# Stripe test-mode billing (#103/#104)

Billing reads only `STRIPE_SECRET_KEY` and refuses every value not beginning `sk_test_`; it never logs the key. Checkout records a local test session and pending subscription for monthly or annual team/business plans. Live Stripe network calls are optional and not required for deterministic tests.

Webhooks require `STRIPE_WEBHOOK_SECRET`, verify Stripe's `t.payload` HMAC-SHA256 in constant time, and reject timestamps outside five minutes. Organization identity comes from signed event metadata. Unknown event types are acknowledged without mutation. Organizations without an active paid plan have a three-seat free limit enforced by the common invitation path.
