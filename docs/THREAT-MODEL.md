<p align="center"><img alt="Komboe" src="../branding/wordmark/komboe-wordmark-light.svg" width="300"></p>

# Komboe Threat Model (outline)

1. **Assets:** vault items, master password, user/org keys, alias mappings, billing metadata.
2. **Actors:** remote attacker, compromised server/operator (including us), malicious org admin, malicious member, compromised device, supply-chain attacker (upstream/dependency), network attacker.
3. **Trust boundaries:** device ↔ server, client ↔ alias service, org admin ↔ member personal vault, upstream imports ↔ Komboe tree.
4. **Key assumptions:** server is untrusted for confidentiality; no escrow exists to be seized.
5. **Threats & mitigations (to fill):** server breach (ciphertext only, strong KDF); weak master password (KDF params, strength meter); admin overreach (no admin reset, personal vault unreadable); phishing/autofill (origin matching); malicious extension update (signed releases, reproducible builds); upstream compromise (pinned tags, review, license check); alias abuse.
6. **Out of scope:** fully compromised unlocked endpoint.
7. **Open items:** external audit before commercial launch; Marcus legal review.
