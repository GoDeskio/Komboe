// Komboe legal notice (GPL/AGPL attribution). Text approved by legal; do not edit without review.

// prettier-ignore
// Single literal on purpose so the exact text is greppable in shipped bundles.
export const KOMBOE_LEGAL_NOTICE = "Komboe © 2026 GODESK IO LLC. Komboe is based on Vaultwarden (© Vaultwarden contributors, AGPL-3.0) and Bitwarden clients (© Bitwarden Inc., GPL-3.0). Komboe is not affiliated with or endorsed by Bitwarden Inc. or the Vaultwarden project. This program comes with ABSOLUTELY NO WARRANTY. It is free software: you may redistribute and modify it under the GNU GPL v3 / AGPL v3.";

export const KOMBOE_REPO_URL = "https://github.com/GoDeskio/Komboe";

/** Git tag (or commit) this build was made from; injected at build time. */
export function komboeSourceRef(): string {
  let ref: string | undefined;
  try {
    ref = process.env.KOMBOE_SOURCE_REF;
  } catch {
    ref = undefined;
  }
  return ref && /^[\w.\-/]+$/.test(ref) ? ref : "main";
}

export function komboeSourceUrl(): string {
  return `${KOMBOE_REPO_URL}/tree/${komboeSourceRef()}`;
}

export function komboeLicenseUrl(): string {
  return `${KOMBOE_REPO_URL}/blob/${komboeSourceRef()}/LICENSE`;
}
