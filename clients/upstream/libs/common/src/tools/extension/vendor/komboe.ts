import { Field } from "../data";
import { Extension } from "../metadata";
import { ExtensionMetadata, VendorMetadata } from "../type";

import { Vendor } from "./data";

// Komboe: self-hosted alias service (SimpleLogin-compatible API on the Komboe server).
export const Komboe: VendorMetadata = {
  id: Vendor.komboe,
  name: "Komboe Aliases",
};

export const KomboeExtensions: ExtensionMetadata[] = [
  {
    site: Extension.forwarder,
    product: {
      vendor: Komboe,
    },
    host: {
      authentication: true,
      selfHost: "always",
    },
    requestedFields: [Field.baseUrl, Field.token],
  },
];
