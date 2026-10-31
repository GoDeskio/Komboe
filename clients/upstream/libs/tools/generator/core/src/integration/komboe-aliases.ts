// Komboe: alias forwarder for the self-hosted Komboe alias service (derived from the
// upstream SimpleLogin integration in this repo; the server speaks the same API).
import {
  GENERATOR_DISK,
  GENERATOR_MEMORY,
  UserKeyDefinition,
} from "@bitwarden/common/platform/state";
import { VendorId } from "@bitwarden/common/tools/extension";
import { Vendor } from "@bitwarden/common/tools/extension/vendor/data";
import { IntegrationContext, IntegrationId } from "@bitwarden/common/tools/integration";
import {
  ApiSettings,
  IntegrationRequest,
  SelfHostedApiSettings,
} from "@bitwarden/common/tools/integration/rpc";
import { PrivateClassifier } from "@bitwarden/common/tools/private-classifier";
import { PublicClassifier } from "@bitwarden/common/tools/public-classifier";
import { BufferedKeyDefinition } from "@bitwarden/common/tools/state/buffered-key-definition";
import { ObjectKey } from "@bitwarden/common/tools/state/object-key";

import { ForwarderConfiguration, ForwarderContext } from "../engine";
import { CreateForwardingEmailRpcDef } from "../engine/forwarder-configuration";
import { SelfHostedApiOptions } from "../types";

// integration types
export type KomboeAliasesSettings = SelfHostedApiSettings;
export type KomboeAliasesOptions = SelfHostedApiOptions;
export type KomboeAliasesConfiguration = ForwarderConfiguration<KomboeAliasesSettings>;

// default values
const defaultSettings = Object.freeze({
  token: "",
  domain: "",
  baseUrl: "",
});

// supported RPC calls
const createForwardingEmail = Object.freeze({
  url(request: IntegrationRequest, context: ForwarderContext<KomboeAliasesSettings>) {
    const endpoint = context.baseUrl() + "/api/alias/random/new";
    const hostname = context.website(request, { extractHostname: true });
    const url = hostname !== "" ? `${endpoint}?hostname=${hostname}` : endpoint;

    return url;
  },
  body(request: IntegrationRequest, context: ForwarderContext<KomboeAliasesSettings>) {
    return { note: context.generatedBy(request) };
  },
  hasJsonPayload(response: Response) {
    return response.status === 200 || response.status === 201;
  },
  processJson(json: any) {
    return [json?.alias];
  },
} as CreateForwardingEmailRpcDef<KomboeAliasesSettings>);

// forwarder configuration
const forwarder = Object.freeze({
  defaultSettings,
  createForwardingEmail,
  request: ["token", "baseUrl"],
  settingsConstraints: {
    token: { required: true },
    baseUrl: { required: true },
  },
  local: {
    settings: {
      // FIXME: integration should issue keys at runtime
      // based on integrationId & extension metadata
      // e.g. key: "forwarder.KomboeAliases.local.settings",
      key: "komboeAliasesForwarder",
      target: "object",
      format: "secret-state",
      frame: 512,
      classifier: new PrivateClassifier<KomboeAliasesSettings>(),
      state: GENERATOR_DISK,
      initial: defaultSettings,
      options: {
        deserializer: (value) => value,
        clearOn: ["logout"],
      },
    } satisfies ObjectKey<KomboeAliasesSettings>,
    import: {
      key: "forwarder.KomboeAliases.local.import",
      target: "object",
      format: "plain",
      classifier: new PublicClassifier<KomboeAliasesSettings>(["token", "baseUrl"]),
      state: GENERATOR_MEMORY,
      options: {
        deserializer: (value) => value,
        clearOn: ["logout", "lock"],
      },
    } satisfies ObjectKey<KomboeAliasesSettings, Record<string, never>, KomboeAliasesSettings>,
  },
  settings: new UserKeyDefinition<KomboeAliasesSettings>(GENERATOR_DISK, "komboeAliasesForwarder", {
    deserializer: (value) => value,
    clearOn: [],
  }),
  importBuffer: new BufferedKeyDefinition<KomboeAliasesSettings>(
    GENERATOR_DISK,
    "komboeAliasesBuffer",
    {
      deserializer: (value) => value,
      clearOn: ["logout"],
    },
  ),
} as const);

// integration-wide configuration
export const KomboeAliases = Object.freeze({
  id: Vendor.komboe as IntegrationId & VendorId,
  name: "Komboe Aliases",
  selfHost: "always",
  extends: ["forwarder"],
  // No hosted default: the alias API is served by the user's own Komboe server
  // (SimpleLogin-compatible `/api/alias/random/new`, authenticated with a `kmb_` key).
  baseUrl: "",
  authenticate(_request: IntegrationRequest, context: IntegrationContext<ApiSettings>) {
    return { Authentication: context.authenticationToken() };
  },
  forwarder,
} as KomboeAliasesConfiguration);
