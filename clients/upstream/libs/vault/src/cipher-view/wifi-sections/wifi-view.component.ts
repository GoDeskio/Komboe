import { ChangeDetectionStrategy, Component, input } from "@angular/core";

import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import {
  KOMBOE_WIFI_HIDDEN,
  KOMBOE_WIFI_PASSWORD,
  KOMBOE_WIFI_SECURITY,
  KOMBOE_WIFI_SSID,
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
  selector: "app-wifi-view",
  templateUrl: "./wifi-view.component.html",
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
export class WifiViewComponent {
  readonly cipher = input.required<CipherView>();

  ssid(): string {
    return komboeFieldValue(this.cipher().fields, KOMBOE_WIFI_SSID);
  }

  password(): string {
    return komboeFieldValue(this.cipher().fields, KOMBOE_WIFI_PASSWORD);
  }

  security(): string {
    return komboeFieldValue(this.cipher().fields, KOMBOE_WIFI_SECURITY);
  }

  hidden(): boolean {
    return komboeFieldValue(this.cipher().fields, KOMBOE_WIFI_HIDDEN) === "true";
  }
}
