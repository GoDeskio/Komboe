/**
 * Owned Komboe destinations that are safe to put in user-facing links.
 *
 * The marketing site declares https://komboe.com/terms.html, privacy.html, and
 * downloads.html, but that site is staging-only and is not deployed
 * (`apps/web-marketing/README.md`: "Not deployed. No DNS changes."). komboe.com
 * did not resolve when these links were chosen. The GitHub URLs below are the
 * same files and docs, and they are reachable. Do not invent a new legal path,
 * and do not send people to bitwarden.com for Terms, Privacy, help, or installs.
 *
 * Import formats and protocol hosts (vault.bitwarden.com, the cloud region
 * table, WebAuthn callback hosts) are not links and do not belong here.
 */
export const KOMBOE_SOURCE = "https://github.com/GoDeskio/Komboe";
export const KOMBOE_ISSUES = "https://github.com/GoDeskio/Komboe/issues";
export const KOMBOE_DOCS = "https://github.com/GoDeskio/Komboe/tree/main/docs";
export const KOMBOE_EXTENSION_DOCS =
  "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md";
export const KOMBOE_MOBILE_DOCS = "https://github.com/GoDeskio/Komboe/tree/main/mobile";
export const KOMBOE_TERMS =
  "https://github.com/GoDeskio/Komboe/blob/main/apps/web-marketing/terms.html";
export const KOMBOE_PRIVACY =
  "https://github.com/GoDeskio/Komboe/blob/main/apps/web-marketing/privacy.html";
export const KOMBOE_NOTICE = "https://github.com/GoDeskio/Komboe/blob/main/NOTICE";

/** Every URL this module publishes. Regression checks compare link targets to this list. */
export const KOMBOE_PUBLIC_LINKS = [
  KOMBOE_SOURCE,
  KOMBOE_ISSUES,
  KOMBOE_DOCS,
  KOMBOE_EXTENSION_DOCS,
  KOMBOE_MOBILE_DOCS,
  KOMBOE_TERMS,
  KOMBOE_PRIVACY,
  KOMBOE_NOTICE,
] as const;
