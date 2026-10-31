import { ChangeDetectionStrategy, Component, computed, input, signal } from "@angular/core";

import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import {
  KOMBOE_ENV_NAME,
  komboeEnvVars,
  komboeFieldValue,
  toDotenv,
} from "@bitwarden/common/vault/utils/komboe-wifi";
import {
  CardComponent,
  CopyClickDirective,
  FormFieldModule,
  IconButtonModule,
  SectionHeaderComponent,
  TypographyModule,
} from "@bitwarden/components";
import { I18nPipe } from "@bitwarden/ui-common";

@Component({
  selector: "app-env-view",
  templateUrl: "./env-view.component.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CardComponent,
    CopyClickDirective,
    FormFieldModule,
    IconButtonModule,
    SectionHeaderComponent,
    TypographyModule,
    I18nPipe,
  ],
})
export class EnvViewComponent {
  readonly showValues = signal(false);
  readonly cipher = input.required<CipherView>();

  readonly environment = computed(() => komboeFieldValue(this.cipher().fields, KOMBOE_ENV_NAME));
  readonly variables = computed(() => komboeEnvVars(this.cipher().fields));
  readonly dotenv = computed(() => toDotenv(this.variables()));
}
