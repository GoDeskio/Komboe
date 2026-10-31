// Komboe: FIDO Credential Exchange Format (CXF) import/export for the CLI, including passkeys.
// The SDK converts between CXF and ciphers on the client; the server only receives ciphertext.
import * as crypto from "crypto";

import { argon2id } from "hash-wasm";
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

// Password-protected CXF: the CXF JSON sealed with AES-256-GCM under an Argon2id key derived
// from the export password. Built and opened only on the client.
const ENVELOPE = "komboe-cxf-encrypted";
const KDF = { memory: 65536, iterations: 3, parallelism: 4 };

async function deriveKey(
  password: string,
  salt: Buffer,
  p: { memory: number; iterations: number; parallelism: number },
) {
  return Buffer.from(
    await argon2id({
      password,
      salt,
      memorySize: p.memory,
      iterations: p.iterations,
      parallelism: p.parallelism,
      hashLength: 32,
      outputType: "binary",
    }),
  );
}

export async function sealCxf(cxf: string, password: string): Promise<string> {
  const salt = crypto.randomBytes(16);
  const iv = crypto.randomBytes(12);
  const key = await deriveKey(password, salt, KDF);
  const c = crypto.createCipheriv("aes-256-gcm", key, iv);
  c.setAAD(Buffer.from(ENVELOPE));
  const ct = Buffer.concat([c.update(cxf, "utf8"), c.final(), c.getAuthTag()]);
  return JSON.stringify({
    format: ENVELOPE,
    version: 1,
    kdf: { algorithm: "argon2id", ...KDF, salt: salt.toString("base64") },
    cipher: "aes-256-gcm",
    iv: iv.toString("base64"),
    data: ct.toString("base64"),
  });
}

/** Returns the plain CXF JSON; throws on a wrong password or tampered file. */
export async function openCxf(payload: string, password?: string): Promise<string> {
  let env: any;
  try {
    env = JSON.parse(payload);
  } catch {
    return payload;
  }
  if (env?.format !== ENVELOPE) {
    return payload;
  }
  if (!password) {
    throw new Error("This CXF file is password protected. Use --passwordenv or --passwordfile.");
  }
  if (env.version !== 1 || env.cipher !== "aes-256-gcm" || env.kdf?.algorithm !== "argon2id") {
    throw new Error("Unsupported encrypted CXF file.");
  }
  const key = await deriveKey(password, Buffer.from(env.kdf.salt, "base64"), env.kdf);
  const raw = Buffer.from(env.data, "base64");
  const d = crypto.createDecipheriv("aes-256-gcm", key, Buffer.from(env.iv, "base64"));
  d.setAAD(Buffer.from(ENVELOPE));
  d.setAuthTag(raw.subarray(raw.length - 16));
  try {
    return Buffer.concat([d.update(raw.subarray(0, raw.length - 16)), d.final()]).toString("utf8");
  } catch {
    throw new Error("Invalid file password.");
  }
}

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

  async import(filepath: string, organizationId?: string, password?: string): Promise<Response> {
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
      payload = await openCxf(payload, password);
    } catch (e) {
      return Response.badRequest(e?.message ?? String(e));
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

  async export(
    output: string | undefined,
    organizationId?: string,
    password?: string,
  ): Promise<Response> {
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
      if (password) {
        return await CliUtils.saveResultToFile(
          await sealCxf(cxf, password),
          output,
          "komboe_export.cxf.encrypted.json",
        );
      }
      return await CliUtils.saveResultToFile(cxf, output, "komboe_export.cxf.json");
    } catch (e) {
      return Response.error(`CXF export failed: ${e?.message ?? e}`);
    }
  }
}
