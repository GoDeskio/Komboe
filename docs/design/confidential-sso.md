# Design: confidential SSO (an SSO key broker the server operator can't read)

Source: the REA scan of the Dashlane CLI (`auth/confidential-sso`, an attested tunnel), rebuilt independently. No code was copied. Status: design only, **blocked on infrastructure**.

## Problem
With SSO and no master password ("key connector"), someone has to hold the user's key. Komboe deliberately ships **no Key Connector**, because an operator-held key breaks zero-knowledge.

## Approach
Run the key broker inside a hardware-attested enclave (AWS Nitro Enclaves or AMD SEV-SNP):
1. The client verifies the enclave's attestation document (code measurement pinned in the client) before it opens an end-to-end tunnel (Noise or HPKE).
2. The enclave validates the IdP assertion and releases the user's key share **only through the tunnel**.
3. The host operator sees ciphertext only. A code change changes the measurement, which clients reject.

## Why it is not built now
- It needs enclave-capable hosting, a reproducible enclave build and a measurement-pinning release process, none of which exist yet.
- Until then, Komboe keeps SSO with a master password, plus trusted-device unlock (#42). No operator-held keys and no backdoor.

## Phases (once unblocked)
Reproducible enclave image, then an attestation verifier in the SDK with tests against recorded attestation documents, then a tunnel, then IdP validation inside the enclave, then a client opt-in per org.
