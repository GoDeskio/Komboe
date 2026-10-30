import { ChangeDetectionStrategy, Component, input } from "@angular/core";

import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import { KOMBOE_BOOKMARK_URL, komboeFieldValue } from "@bitwarden/common/vault/utils/komboe-wifi";
import {
  CardComponent,
  FormFieldModule,
  SectionHeaderComponent,
  TypographyModule,
} from "@bitwarden/components";
import { I18nPipe } from "@bitwarden/ui-common";

@Component({
  selector: "app-bookmark-view",
  templateUrl: "./bookmark-view.component.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CardComponent,
    FormFieldModule,
    SectionHeaderComponent,
    TypographyModule,
    I18nPipe,
  ],
})
export class BookmarkViewComponent {
  readonly cipher = input.required<CipherView>();

  url(): string {
    return komboeFieldValue(this.cipher().fields, KOMBOE_BOOKMARK_URL);
  }
}
