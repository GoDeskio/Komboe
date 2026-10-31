import { Component, inject, input, OnInit } from "@angular/core";

import { ApiService } from "@bitwarden/common/abstractions/api.service";
import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import { CalloutModule } from "@bitwarden/components";

@Component({
  selector: "komboe-password-expiry-settings",
  template: `
    <section data-testid="password-expiry" class="tw-p-2 tw-text-sm">
      <h3 class="tw-m-0 tw-mb-2 tw-font-semibold">Password expiry</h3>
      <p class="tw-m-0 tw-mb-2 tw-text-muted">Days before a login password expires. 0 expires immediately.</p>
      <div class="tw-flex tw-gap-1">
        <input
          data-testid="password-expiry-days"
          class="tw-border tw-rounded tw-px-2 tw-py-1 tw-w-full"
          type="number"
          min="0"
          max="3650"
          [value]="days"
          (input)="days = $any($event.target).value"
        />
        <button data-testid="password-expiry-save" type="button" class="tw-border tw-rounded tw-px-2" (click)="save()">
          Save
        </button>
      </div>
      @if (message) {
        <p data-testid="password-expiry-saved" class="tw-mt-2 tw-mb-0">{{ message }}</p>
      }
    </section>
  `,
})
export class KomboePasswordExpirySettingsComponent implements OnInit {
  private readonly api = inject(ApiService);
  days = "";
  message = "";

  async ngOnInit() {
    const current = await this.api.getPasswordExpiry();
    if (current.userDays != null) {
      this.days = String(current.userDays);
    }
  }

  async save() {
    const parsed = this.days === "" ? null : Number(this.days);
    if (parsed != null && (!Number.isInteger(parsed) || parsed < 0 || parsed > 3650)) {
      this.message = "Enter a whole number of days from 0 to 3650";
      return;
    }
    try {
      const saved = await this.api.putPasswordExpiry(parsed);
      this.message = saved.userDays == null ? "Expiry cleared" : `Expires after ${saved.userDays} days`;
    } catch {
      this.message = "Could not save password expiry";
    }
  }
}

@Component({
  selector: "komboe-password-expiry",
  imports: [CalloutModule],
  template: `
    @if (expired) {
      <bit-callout type="warning" title="Password expired" data-testid="password-expired">
        This login password is older than the expiry policy.
      </bit-callout>
    }
  `,
})
export class KomboePasswordExpiryComponent implements OnInit {
  readonly cipher = input.required<CipherView>();
  private readonly api = inject(ApiService);
  expired = false;

  async ngOnInit() {
    const password = this.cipher().login?.password;
    if (!password) {
      return;
    }
    const policy = await this.api.getPasswordExpiry();
    if (policy.days == null) {
      return;
    }
    if (policy.days === 0) {
      this.expired = true;
      return;
    }
    const when =
      // Password age: last password change, else when the item was created. Other edits must not reset it.
      this.cipher().login?.passwordRevisionDate ??
      this.cipher().creationDate ??
      this.cipher().revisionDate;
    if (!when) {
      return;
    }
    this.expired = Date.now() - new Date(when).getTime() >= policy.days * 86_400_000;
  }
}
