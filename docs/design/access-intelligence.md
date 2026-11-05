# Access intelligence (#73)

The organization-admin risk report is a clean-room aggregation over membership, device activity, 2FA enrollment, collection-wide access flags, and organization cipher row counts. It reports members without 2FA, members inactive for 90 days, ordinary members with `access_all`, and shared-item counts.

No cipher payload, encrypted item field, key, item name, attachment, or personal-vault count is read or returned. The response declares `metadataOnly` and `vaultDataRead` for regression tests. No `bitwarden_license` source or generated artifact is used.
