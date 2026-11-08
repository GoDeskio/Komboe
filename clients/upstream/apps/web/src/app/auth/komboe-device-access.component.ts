import { CommonModule } from "@angular/common";
import { Component, inject, signal } from "@angular/core";
import { Router } from "@angular/router";
import { firstValueFrom } from "rxjs";

import { AccountService } from "@bitwarden/common/auth/abstractions/account.service";
import { getUserId } from "@bitwarden/common/auth/services/account.service";
import { UserId } from "@bitwarden/common/types/guid";
import { UserKey } from "@bitwarden/common/types/key";
import { LockComponent } from "@bitwarden/key-management-ui";
import { KeyService } from "@bitwarden/key-management";
import { SymmetricCryptoKey } from "@bitwarden/legacy-crypto";
import { UnlockService } from "@bitwarden/unlock";

type DeviceUnlockApi = {
  storageKey: (userId: string) => string;
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
          password. It is not a new account password, and it is not sent to the server.
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
    </section>
  `,
})
export class KomboeDeviceAccessComponent {
  protected mode: "enroll" | "unlock" = "unlock";

  private readonly accountService = inject(AccountService);
  private readonly keyService = inject(KeyService);
  private readonly unlockService = inject(UnlockService);

  protected readonly dots = [0, 1, 2, 3, 4, 5, 6, 7, 8];
  protected readonly pin = signal("");
  protected readonly pattern = signal("");
  protected readonly message = signal("");
  protected readonly userKeyReady = signal(false);
  protected readonly record = signal<any>(null);
  protected readonly biometric = signal({ supported: false, reason: "" });

  constructor() {
    this.mode = inject(Router).url.includes("device-access") ? "enroll" : "unlock";
    void this.start();
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
      const record = await api.enrollDeviceUnlock(userKey.toEncoded(), secret, kind);
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
    const key = new SymmetricCryptoKey(result.userKey) as UserKey;
    await this.unlockService.unlockWithDecryptedUserKey(userId, key);
    this.message.set("Vault unlocked on this device.");
  }

  private async start(): Promise<void> {
    const api = await this.api();
    this.biometric.set(api.biometricCapability());
    const userId = await this.userId();
    const raw = localStorage.getItem(api.storageKey(userId));
    this.record.set(raw ? JSON.parse(raw) : null);
    const userKey = await firstValueFrom(this.keyService.userKey$(userId));
    this.userKeyReady.set(userKey != null);
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
