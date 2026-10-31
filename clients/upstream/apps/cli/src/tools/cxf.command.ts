// Komboe: FIDO Credential Exchange Format (CXF) import/export for the CLI, including passkeys.
// The SDK converts between CXF and ciphers on the client; the server only receives ciphertext.
import { firstValueFrom, switchMap } from "rxjs";

import { AccountService } from "@bitwarden/common/auth/abstractions/account.service";
import { getUserId } from "@bitwarden/common/auth/services/account.service";
import { SdkService } from "@bitwarden/common/platform/abstractions/sdk/sdk.service";
import { UserId } from "@bitwarden/common/types/guid";
import { CipherService } from "@bitwarden/common/vault/abstractions/cipher.service";
import { SyncService } from "@bitwarden/common/vault/abstractions/sync/sync.service.abstraction";
import { Cipher } from "@bitwarden/common/vault/models/domain/cipher";
import type { BitwardenClient } from "@bitwarden/sdk-internal";

import { Response } from "../models/response";
import { MessageResponse } from "../models/response/message.response";
import { CliUtils } from "../utils";

export class CxfCommand {
  constructor(
    private sdkService: SdkService,
    private cipherService: CipherService,
    private accountService: AccountService,
    private syncService: SyncService,
  ) {}

  private withSdk<T>(userId: UserId, fn: (sdk: BitwardenClient) => T | Promise<T>): Promise<T> {
    return firstValueFrom(
      this.sdkService.userClient$(userId).pipe(
        switchMap(async (client) => {
          if (!client) {
            throw new Error("SDK not available");
          }
          using ref = client.take();
          return await fn(ref.value);
        }),
      ),
    );
  }

  async import(filepath: string, organizationId?: string): Promise<Response> {
    if (organizationId != null) {
      return Response.badRequest("CXF import into an organization is not supported yet.");
    }
    if (!filepath) {
      return Response.badRequest("`filepath` was not provided.");
    }
    let payload: string;
    try {
      payload = await CliUtils.readFile(filepath);
    } catch {
      return Response.badRequest(`Could not read file: ${filepath}`);
    }
    try {
      const userId = await firstValueFrom(this.accountService.activeAccount$.pipe(getUserId));
      const contexts = await this.withSdk(userId, (sdk) => sdk.exporters().import_cxf(payload));
      let count = 0;
      for (const ctx of contexts) {
        // Decrypt locally, then save through the normal client path (re-encrypted client-side).
        const view = await this.cipherService.decrypt(Cipher.fromSdkCipher(ctx.cipher), userId);
        view.id = null;
        await this.cipherService.createWithServer(view, userId);
        count++;
      }
      await this.syncService.fullSync(true);
      return Response.success(
        new MessageResponse(`Imported ${count} item(s) from ${filepath}`, null),
      );
    } catch (e) {
      return Response.badRequest(`CXF import failed: ${e?.message ?? e}`);
    }
  }

  async export(output: string | undefined, organizationId?: string): Promise<Response> {
    if (organizationId != null) {
      return Response.badRequest("CXF export of an organization vault is not supported yet.");
    }
    try {
      const account = await firstValueFrom(this.accountService.activeAccount$);
      const userId = account.id;
      const ciphers = (await this.cipherService.getAll(userId))
        .filter((c) => c.deletedDate == null && c.organizationId == null)
        .map((c) => c.toSdkCipher());
      const cxf = await this.withSdk(userId, (sdk) =>
        sdk
          .exporters()
          .export_cxf({ id: userId, email: account.email, name: account.name }, ciphers),
      );
      return await CliUtils.saveResultToFile(cxf, output, "komboe_export.cxf.json");
    } catch (e) {
      return Response.error(`CXF export failed: ${e?.message ?? e}`);
    }
  }
}
