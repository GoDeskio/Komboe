import { ChangeDetectionStrategy, Component, input } from "@angular/core";

import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import {
  KOMBOE_GPG_EMAIL,
  KOMBOE_GPG_FINGERPRINT,
  KOMBOE_GPG_KEY_ID,
  KOMBOE_GPG_PASSPHRASE,
  KOMBOE_GPG_PRIVATE,
  KOMBOE_GPG_PUBLIC,
  komboeFieldValue,
} from "@bitwarden/common/vault/utils/komboe-wifi";
import {
  CardComponent,
  FormFieldModule,
  IconButtonModule,
  SectionHeaderComponent,
  TypographyModule,
} from "@bitwarden/components";
import { I18nPipe } from "@bitwarden/ui-common";

@Component({
  selector: "app-gpg-view",
  templateUrl: "./gpg-view.component.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CardComponent,
    FormFieldModule,
    IconButtonModule,
    SectionHeaderComponent,
    TypographyModule,
    I18nPipe,
  ],
})
export class GpgViewComponent {
  readonly cipher = input.required<CipherView>();

  value(name: string): string {
    return komboeFieldValue(this.cipher().fields, name);
  }

  readonly keyIdName = KOMBOE_GPG_KEY_ID;
  readonly fingerprintName = KOMBOE_GPG_FINGERPRINT;
  readonly emailName = KOMBOE_GPG_EMAIL;
  readonly publicName = KOMBOE_GPG_PUBLIC;
  readonly privateName = KOMBOE_GPG_PRIVATE;
  readonly passphraseName = KOMBOE_GPG_PASSPHRASE;
}
