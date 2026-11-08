import { CommonModule } from "@angular/common";
import { Component, inject, signal } from "@angular/core";
import { Router } from "@angular/router";
import { firstValueFrom } from "rxjs";

import { AccountService } from "@bitwarden/common/auth/abstractions/account.service";
import { getUserId } from "@bitwarden/common/auth/services/account.service";
import { KDF_CONFIG } from "@bitwarden/common/key-management/state-definitions";
import { StateProvider } from "@bitwarden/common/platform/state";
import { ApiService } from "@bitwarden/common/abstractions/api.service";
import {
  envelopeKeyBytes,
  LOGIN_NAME_WRAP_ITERATIONS,
  LOGIN_NAME_WRAP_KDF_TYPE,
  loginNamePlaintext,
  loginNameWrapAllowed,
  randomEnvelopeSalt,
  sealLoginNamePlaintext,
} from "@bitwarden/common/auth/kdf-identity";
import { UserId } from "@bitwarden/common/types/guid";
import { UserKey } from "@bitwarden/common/types/key";
import { LockComponent } from "@bitwarden/key-management-ui";
import { KeyService } from "@bitwarden/key-management";
import {
  KdfConfig,
  KdfType,
  LegacyCompatKeyService,
  PBKDF2KdfConfig,
  SymmetricCryptoKey,
} from "@bitwarden/legacy-crypto";
import { LogoutService } from "@bitwarden/auth/common";
import { LockService, LockSource, UnlockService } from "@bitwarden/unlock";

type DeviceUnlockApi = {
  storageKey: (userId: string) => string;
  assertVaultUserKey: (userKey: Uint8Array) => void;
  enrollDeviceUnlock: (userKey: Uint8Array, secret: string, kind: string) => Promise<Record<string, unknown>>;
  unlockDevice: (record: any, secret: string) => Promise<any>;
  biometricCapability: () => { supported: boolean; reason: string };
};

@Component({
  selector: "app-komboe-device-access",
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="tw-mx-auto tw-mt-4 tw-w-full tw-max-w-md tw-px-4" data-testid="device-access">
      <h2 class="tw-text-lg tw-font-semibold">This device</h2>
      <p>{{ biometric().reason }}</p>
      @if (mode === "enroll") {
        <p>
          A PIN or pattern unlocks this browser after you have signed in with your email and master
          password. It is not a new account password, and it is not sent to the server. The
          wrong-attempt counter only applies in this browser. Someone who copies this browser's
          storage can guess a short PIN or pattern offline. This is not hardware-bound. The email
          timer proof is a bearer secret in this browser session, not a device binding. This page
          does not enroll a passkey or collect biometrics. Use the master password when the PIN is
          not enough.
        </p>
        @if (!userKeyReady()) {
          <p role="status">
            Unlock with your master password on this device before enrolling a PIN or pattern.
          </p>
        } @else {
          <label class="tw-mt-3 tw-block">
            PIN (6 to 12 digits)
            <input class="tw-mt-1 tw-w-full" type="password" inputmode="numeric" data-testid="device-pin" (input)="pin.set($any($event.target).value)" />
          </label>
          <button type="button" class="tw-mt-2" data-testid="enroll-pin" (click)="enroll('pin')">Use this PIN on this device</button>
          <p class="tw-mt-4">Pattern: tap at least 4 different dots, from 1 to 9.</p>
          <div class="tw-mt-2 tw-grid tw-w-40 tw-grid-cols-3 tw-gap-2" data-testid="pattern-pad">
            @for (dot of dots; track dot) {
              <button type="button" class="tw-h-10 tw-rounded tw-border" [attr.data-dot]="dot" (click)="addDot(dot)">{{ dot + 1 }}</button>
            }
          </div>
          <button type="button" class="tw-mt-2" data-testid="enroll-pattern" (click)="enroll('pattern')">Use this pattern on this device</button>
          <button type="button" class="tw-mt-2" (click)="pattern.set('')">Clear pattern</button>
        }
      } @else {
        @if (!record()) {
          <p role="status">No PIN or pattern is enrolled on this browser. Use your master password.</p>
        } @else {
          <p>Unlock this browser with the {{ record().kind }} you enrolled. Your master password still works.</p>
          @if (record().kind === "pin") {
            <label class="tw-mt-3 tw-block">
              PIN
              <input class="tw-mt-1 tw-w-full" type="password" inputmode="numeric" data-testid="unlock-pin" (input)="pin.set($any($event.target).value)" />
            </label>
            <button type="button" data-testid="unlock-pin-submit" (click)="unlock('pin')">Unlock</button>
          } @else {
            <div class="tw-mt-2 tw-grid tw-w-40 tw-grid-cols-3 tw-gap-2">
              @for (dot of dots; track dot) {
                <button type="button" class="tw-h-10 tw-rounded tw-border" (click)="addDot(dot)">{{ dot + 1 }}</button>
              }
            </div>
            <button type="button" data-testid="unlock-pattern-submit" (click)="unlock('pattern')">Unlock</button>
          }
        }
      }
      @if (message()) {
        <p role="alert" data-testid="device-access-message">{{ message() }}</p>
      }
      @if (mode === "enroll") {
        <h3 class="tw-mt-6 tw-text-base tw-font-semibold">Login name</h3>
        @if (loginNameAllowed() === false) {
          <p data-testid="login-name-unavailable">
            A login name is not available for this account. Argon2, and PBKDF2 above 600000
            iterations, stay on email sign-in. A login name would check the password with a
            cheaper key, so it is not offered. Email sign-in still uses this account's own key
            derivation.
          </p>
        } @else if (loginNameAllowed() === true) {
          <p>
            A login name signs in without typing the email. The vault key still uses the email
            from when the account was created, including its case, and this account's own key
            derivation. The envelope is sealed with PBKDF2-SHA256 at 600000 iterations. That is
            not this account's key derivation, and it is not a cheaper check. Changing the master
            password clears the login name.
          </p>
          @if (savedLoginName()) {
            <p>Current login name: {{ savedLoginName() }}</p>
          }
          <label class="tw-mt-3 tw-block">
            Exact vault email
            <input class="tw-mt-1 tw-w-full" type="email" data-testid="login-name-kdf-email" [value]="kdfEmail()" (input)="kdfEmail.set($any($event.target).value)" />
          </label>
          <label class="tw-mt-3 tw-block">
            Login name
            <input class="tw-mt-1 tw-w-full" type="text" autocomplete="username" data-testid="login-name" (input)="loginName.set($any($event.target).value)" />
          </label>
          <label class="tw-mt-3 tw-block">
            Master password
            <input class="tw-mt-1 tw-w-full" type="password" autocomplete="current-password" data-testid="login-name-password" (input)="loginPassword.set($any($event.target).value)" />
          </label>
          <button type="button" class="tw-mt-2" data-testid="save-login-name" (click)="saveLoginName()">Save this login name</button>
        }
        @if (loginNameMessage()) {
          <p role="status" data-testid="login-name-message">{{ loginNameMessage() }}</p>
        }
      }
      <p>
        <button type="button" data-testid="device-lock" (click)="lock()">Lock</button>
        <button type="button" data-testid="device-logout" (click)="logout()">Log out</button>
      </p>
    </section>
  `,
})
export class KomboeDeviceAccessComponent {
  protected mode: "enroll" | "unlock" = "unlock";

  private readonly accountService = inject(AccountService);
  private readonly keyService = inject(KeyService);
  private readonly unlockService = inject(UnlockService);
  private readonly lockService = inject(LockService);
  private readonly logoutService = inject(LogoutService);
  private readonly stateProvider = inject(StateProvider);
  private readonly apiService = inject(ApiService);
  private readonly legacyKey = inject(LegacyCompatKeyService);
  private readonly router = inject(Router);

  protected readonly dots = [0, 1, 2, 3, 4, 5, 6, 7, 8];
  protected readonly pin = signal("");
  protected readonly pattern = signal("");
  protected readonly message = signal("");
  protected readonly userKeyReady = signal(false);
  protected readonly record = signal<any>(null);
  protected readonly biometric = signal({ supported: false, reason: "" });
  protected readonly savedLoginName = signal("");
  protected readonly loginName = signal("");
  protected readonly loginPassword = signal("");
  protected readonly kdfEmail = signal("");
  protected readonly loginNameMessage = signal("");
  /** Null until this device knows the account KDF. False hides the form before any submit. */
  protected readonly loginNameAllowed = signal<boolean | null>(null);

  constructor() {
    this.mode = this.router.url.includes("device-access") ? "enroll" : "unlock";
    void this.start();
  }

  protected async lock(): Promise<void> {
    this.message.set("locking");
    // LockService clears cipher caches and the user key, then reloads the process.
    // Nulling the key here would drop it before that wipe, and navigating to /lock
    // without a reload would leave decrypted caches in this process. Unsaved edits
    // are discarded by the reload.
    try {
      await this.lockService.lock(await this.userId(), LockSource.Manual);
    } catch (error) {
      this.message.set(error instanceof Error ? error.message : "Could not lock.");
    }
  }

  protected async saveLoginName(): Promise<void> {
    this.loginNameMessage.set("");
    if (this.loginNameAllowed() !== true) {
      this.loginNameMessage.set(
        "A login name is not available for this account. Sign in with your email.",
      );
      return;
    }
    const name = this.loginName().trim();
    const password = this.loginPassword();
    const kdfEmail = this.kdfEmail().trim();
    if (!name || !password || !kdfEmail.includes("@")) {
      this.loginNameMessage.set("Enter the vault email, a login name, and the master password.");
      return;
    }
    try {
      const userId = await this.userId();
      const kdf = await firstValueFrom(this.stateProvider.getUser(userId, KDF_CONFIG).state$);
      if (!kdf || !loginNameWrapAllowed(kdf.kdfType, kdf.iterations)) {
        this.loginNameAllowed.set(false);
        this.loginNameMessage.set(
          "A login name is not available for this account. Sign in with your email.",
        );
        return;
      }
      const masterKey = await this.legacyKey.makeMasterKeyPreservingSalt(password, kdfEmail, kdf);
      const masterPasswordHash = await this.legacyKey.hashMasterKey(password, masterKey);
      await this.apiService.send(
        "PUT",
        "/komboe/kdf-email",
        { kdfEmail, masterPasswordHash },
        true,
        true,
      );
      const accountKdf = this.kdfBody(kdf);
      const envelopeSalt = randomEnvelopeSalt();
      const wrapKdf = new PBKDF2KdfConfig(LOGIN_NAME_WRAP_ITERATIONS);
      const wrappingKey = await this.legacyKey.makeMasterKeyPreservingSalt(password, envelopeSalt, wrapKdf);
      const envelope = await sealLoginNamePlaintext(
        envelopeKeyBytes(wrappingKey.toEncoded()),
        loginNamePlaintext({
          kdfEmail,
          kdfType: accountKdf.kdf,
          kdfIterations: accountKdf.kdfIterations,
          kdfMemory: accountKdf.kdfMemory,
          kdfParallelism: accountKdf.kdfParallelism,
        }),
      );
      const saved = await this.apiService.send(
        "PUT",
        "/komboe/login-name",
        {
          name,
          masterPasswordHash,
          envelope,
          envelopeSalt,
          kdf: LOGIN_NAME_WRAP_KDF_TYPE,
          kdfIterations: LOGIN_NAME_WRAP_ITERATIONS,
          kdfMemory: null,
          kdfParallelism: null,
        },
        true,
        true,
      );
      this.savedLoginName.set(saved?.name || name.toLowerCase());
      this.loginPassword.set("");
      this.loginNameMessage.set("Login name saved. Sign in with it and the master password.");
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : (error as { message?: string } | null)?.message;
      this.loginNameMessage.set(message || "The login name was not saved.");
    }
  }

  protected async logout(): Promise<void> {
    await this.logoutService.logout(await this.userId(), "userInitiated");
  }

  protected addDot(dot: number): void {
    const current = this.pattern();
    if (current.includes(String(dot))) {
      return;
    }
    this.pattern.set(current + String(dot));
  }

  protected async enroll(kind: "pin" | "pattern"): Promise<void> {
    const api = await this.api();
    const userId = await this.userId();
    const userKey = await firstValueFrom(this.keyService.userKey$(userId));
    if (!userKey) {
      this.message.set("Unlock with your master password on this device before enrolling a PIN or pattern.");
      return;
    }
    const secret = kind === "pin" ? this.pin() : this.pattern();
    try {
      const encoded = userKey.toEncoded();
      api.assertVaultUserKey(encoded);
      const record = await api.enrollDeviceUnlock(encoded, secret, kind);
      localStorage.setItem(api.storageKey(userId), JSON.stringify(record));
      this.pin.set("");
      this.pattern.set("");
      this.message.set("This device can now unlock with that secret. Logging out removes it.");
    } catch (error) {
      this.message.set(error instanceof Error ? error.message : "Could not enroll.");
    }
  }

  protected async unlock(kind: "pin" | "pattern"): Promise<void> {
    const api = await this.api();
    const userId = await this.userId();
    const stored = this.record();
    if (!stored || stored.kind !== kind) {
      this.message.set("That unlock method is not enrolled on this browser.");
      return;
    }
    const secret = kind === "pin" ? this.pin() : this.pattern();
    const result = await api.unlockDevice(stored, secret);
    this.pin.set("");
    this.pattern.set("");
    if (result.wiped || !result.record) {
      localStorage.removeItem(api.storageKey(userId));
      this.record.set(null);
      this.message.set(result.error);
      return;
    }
    localStorage.setItem(api.storageKey(userId), JSON.stringify(result.record));
    this.record.set(result.record);
    if (!result.userKey) {
      this.message.set(result.error);
      return;
    }
    api.assertVaultUserKey(result.userKey);
    const key = new SymmetricCryptoKey(result.userKey) as UserKey;
    await this.unlockService.unlockWithDecryptedUserKey(userId, key);
    this.message.set("Vault unlocked on this device.");
    await this.router.navigate(["/vault"]);
  }

  private async start(): Promise<void> {
    const api = await this.api();
    this.biometric.set(api.biometricCapability());
    const userId = await this.userId();
    const raw = localStorage.getItem(api.storageKey(userId));
    this.record.set(raw ? JSON.parse(raw) : null);
    const userKey = await firstValueFrom(this.keyService.userKey$(userId));
    this.userKeyReady.set(userKey != null);
    if (this.mode !== "enroll") {
      return;
    }
    const account = await firstValueFrom(this.accountService.activeAccount$);
    this.kdfEmail.set(account?.email ?? "");
    const kdf = await firstValueFrom(this.stateProvider.getUser(userId, KDF_CONFIG).state$);
    this.loginNameAllowed.set(kdf != null && loginNameWrapAllowed(kdf.kdfType, kdf.iterations));
    try {
      const salt = await this.apiService.send("GET", "/komboe/kdf-email", null, true, true);
      if (typeof salt?.kdfEmail === "string" && salt.kdfEmail.includes("@")) {
        this.kdfEmail.set(salt.kdfEmail);
      }
      const current = await this.apiService.send("GET", "/komboe/login-name", null, true, true);
      if (typeof current?.name === "string") {
        this.savedLoginName.set(current.name);
      }
    } catch {
      // The form still works with the account email when the salt was not stored.
    }
  }

  private kdfBody(kdf: KdfConfig): {
    kdf: number;
    kdfIterations: number;
    kdfMemory: number | null;
    kdfParallelism: number | null;
  } {
    if (kdf.kdfType === KdfType.Argon2id) {
      return {
        kdf: kdf.kdfType,
        kdfIterations: kdf.iterations,
        kdfMemory: kdf.memory,
        kdfParallelism: kdf.parallelism,
      };
    }
    return {
      kdf: kdf.kdfType,
      kdfIterations: kdf.iterations,
      kdfMemory: null,
      kdfParallelism: null,
    };
  }

  private async userId(): Promise<UserId> {
    return await firstValueFrom(getUserId(this.accountService.activeAccount$));
  }

  private async api(): Promise<DeviceUnlockApi> {
    // Plain JS so the browser fixture and node tests load this exact file.
    return import("./komboe-device-unlock.mjs") as Promise<DeviceUnlockApi>;
  }
}

@Component({
  selector: "app-komboe-lock-page",
  standalone: true,
  imports: [LockComponent, KomboeDeviceAccessComponent],
  template: `
    <bit-lock></bit-lock>
    <app-komboe-device-access></app-komboe-device-access>
  `,
})
export class KomboeLockPageComponent {}
