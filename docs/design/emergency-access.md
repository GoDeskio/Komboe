# View-only emergency access (#67)

Komboe deliberately removes takeover, password replacement, policy-discovery, and early-approval routes. Only view grants can be created or updated, and migration irreversibly downgrades legacy takeover rows to view-only. The grantor must confirm a nonempty key encrypted for the grantee before access can be initiated.

The view handler independently checks grant type, grantee identity, confirmed key, recovery state, and `recovery_initiated_at + wait_time`; it does not trust a scheduler-updated status alone. The grantor may reject an initiated or timed-out request and receives the existing initiation notifications. No path changes a grantor password, disables 2FA, or removes memberships.
