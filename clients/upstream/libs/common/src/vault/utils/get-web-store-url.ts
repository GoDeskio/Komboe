import { DeviceType } from "../../enums";
import { KOMBOE_EXTENSION_DOCS } from "../../komboe/public-links";

/**
 * Where to send someone who wants the browser extension.
 *
 * Komboe is not published on the Chrome, Firefox, Edge, Opera, or Safari stores.
 * Those listings are the upstream commercial extension. Every device gets the
 * load-unpacked guide in this repository instead.
 * `deviceType` stays in the signature so existing callers do not change.
 */
export const getWebStoreUrl = (_deviceType: DeviceType): string => {
  return KOMBOE_EXTENSION_DOCS;
};
