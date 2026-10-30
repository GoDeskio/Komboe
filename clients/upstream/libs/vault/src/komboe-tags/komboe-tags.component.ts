import { Component, inject, OnInit } from "@angular/core";
import { firstValueFrom } from "rxjs";

import { ApiService } from "@bitwarden/common/abstractions/api.service";
import { AccountService } from "@bitwarden/common/auth/abstractions/account.service";
import { getUserId } from "@bitwarden/common/auth/services/account.service";
import { CipherService } from "@bitwarden/common/vault/abstractions/cipher.service";
import { EncString, EncryptService } from "@bitwarden/legacy-crypto";
import { KeyService } from "@bitwarden/key-management";

type TagRow = { id: string; name: string; cipherIds: string[] };

@Component({
  selector: "komboe-tags",
  template: `
    <section data-testid="komboe-tags" class="tw-p-2 tw-text-sm">
      <h3 class="tw-m-0 tw-mb-2 tw-font-semibold">Tags</h3>
      <div class="tw-flex tw-gap-1 tw-mb-2">
        <input data-testid="tag-name" class="tw-border tw-rounded tw-px-2 tw-py-1 tw-w-full" [value]="draft" (input)="draft = $any($event.target).value" placeholder="New tag" />
        <button data-testid="tag-create" type="button" class="tw-border tw-rounded tw-px-2" (click)="create()">Add</button>
      </div>
      @for (tag of tags; track tag.id) {
        <button type="button" class="tw-block tw-text-left tw-w-full tw-rounded tw-px-2 tw-py-1" [attr.data-testid]="'tag'" [attr.data-tag-id]="tag.id" (click)="selected = tag.id">{{ tag.name }}</button>
      }
      <label class="tw-block tw-mt-2">Item
        <select data-testid="tag-item" class="tw-border tw-rounded tw-w-full" (change)="cipherId = $any($event.target).value">
          <option value="">Choose</option>
          @for (item of items; track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select>
      </label>
      <button data-testid="tag-assign" type="button" class="tw-mt-2 tw-border tw-rounded tw-px-2 tw-py-1" (click)="assign()">Apply tag</button>
      @if (selected) {
        <ul class="tw-mt-2 tw-pl-4">
          @for (name of taggedNames(); track name) {
            <li data-testid="tagged-item">{{ name }}</li>
          }
        </ul>
      }
      @if (error) {
        <p data-testid="tag-error">{{ error }}</p>
      }
    </section>
  `,
})
export class KomboeTagsComponent implements OnInit {
  private api = inject(ApiService);
  private account = inject(AccountService);
  private keys = inject(KeyService);
  private encrypt = inject(EncryptService);
  private ciphers = inject(CipherService);

  tags: TagRow[] = [];
  items: { id: string; name: string }[] = [];
  draft = "";
  selected = "";
  cipherId = "";
  error = "";

  async ngOnInit() {
    await this.reload();
  }

  taggedNames(): string[] {
    const tag = this.tags.find((t) => t.id === this.selected);
    if (!tag) return [];
    return this.items.filter((item) => tag.cipherIds.includes(item.id)).map((item) => item.name);
  }

  async create() {
    this.error = "";
    const name = this.draft.trim();
    if (!name) return;
    try {
      const userId = await firstValueFrom(this.account.activeAccount$.pipe(getUserId));
      const key = await firstValueFrom(this.keys.userKey$(userId));
      if (!key) throw new Error("Vault is locked");
      const enc = await this.encrypt.encryptString(name, key);
      await this.api.postKomboeTag(enc.toJSON());
      this.draft = "";
      await this.reload();
    } catch (e) {
      this.error = e instanceof Error ? e.message : "Could not save the tag";
    }
  }

  async assign() {
    this.error = "";
    if (!this.selected || !this.cipherId) return;
    try {
      await this.api.putCipherTags(this.cipherId, [this.selected]);
      await this.reload();
    } catch (e) {
      this.error = e instanceof Error ? e.message : "Could not apply the tag";
    }
  }

  private async reload() {
    const userId = await firstValueFrom(this.account.activeAccount$.pipe(getUserId));
    const key = await firstValueFrom(this.keys.userKey$(userId));
    const raw = await this.api.getKomboeTags();
    this.tags = [];
    for (const row of raw?.data ?? []) {
      let name = row.name;
      if (key) {
        try {
          name = await this.encrypt.decryptString(new EncString(row.name), key);
        } catch {
          name = "(locked)";
        }
      }
      this.tags.push({ id: row.id, name, cipherIds: row.cipherIds ?? [] });
    }
    const views = await this.ciphers.getAllDecrypted(userId);
    this.items = views.filter((c) => !c.deletedDate).map((c) => ({ id: c.id, name: c.name }));
  }
}
