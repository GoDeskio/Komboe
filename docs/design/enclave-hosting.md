# Enclave hosting (self-hosted default)

Status: decision. No enclave image is built or deployed by this change.

Confidential SSO (see [confidential-sso.md](confidential-sso.md)) needs a key broker the server operator cannot read. The broker has to run inside a hardware-attested enclave. Komboe still ships **no Key Connector** and **no admin password reset**. The enclave is not an escrow the operator can open.

## Default

**Confidential Containers (CoCo) on AMD SEV-SNP**, on hardware the operator owns.

- Stack: [Confidential Containers](https://confidentialcontainers.org/) with Kata Containers, guest firmware that can produce an SEV-SNP attestation report, and a measured container image of the broker.
- Hardware: an AMD EPYC processor with SEV-SNP enabled in the firmware. The same CoCo guest can target Intel TDX when the machine has TDX; SEV-SNP is the default because it is the self-hosted TEE operators can actually buy and rack.
- The client pins the launch measurement. It opens the tunnel only after the attestation report matches that measurement. The host kernel and the Komboe server process see ciphertext only.

## Why this one

| Option | Self-hosted on owned hardware | Why it is or isn't the default |
|---|---|---|
| Confidential Containers + AMD SEV-SNP | Yes | Default. Open source, operator-owned machines, hardware attestation, no cloud account |
| Confidential Containers + Intel TDX | Yes | Same stack, use it when the machine is TDX instead of SEV-SNP |
| AWS Nitro Enclaves | No | Only runs inside AWS. Fine for a later hosted offering, not the self-hosted default |
| Intel SGX / Gramine | Partly | SGX is retired on current client CPUs and the enclave page cache is small. Not the default |
| A process on the same VM as the server | n/a | The operator can read its memory. That would be Key Connector, which Komboe does not ship |

## Rules that do not change

- The enclave does not add an admin password reset, a recovery key, or a Key Connector endpoint.
- Lost master password still means a lost vault, unless the user already has a trusted device or a passkey with a client-wrapped PRF key.
- Clients must refuse a measurement they do not pin. A rebuilt broker is a different measurement and does not get the old keys.
- No production deploy, DNS change, or cloud bill is part of choosing this default.

## What is still missing

A reproducible guest image, a published measurement, and an attestation verifier in the client. Until those exist, SSO keeps using the master password plus trusted-device unlock.
