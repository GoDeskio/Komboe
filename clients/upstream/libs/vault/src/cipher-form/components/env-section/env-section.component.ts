import {
  ChangeDetectionStrategy,
  Component,
  signal,
  DestroyRef,
  inject,
  input,
  OnInit,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormBuilder, ReactiveFormsModule } from "@angular/forms";

import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import {
  KOMBOE_ENV_NAME,
  komboeEnvFields,
  komboeEnvVars,
  komboeFieldValue,
  toDotenv,
} from "@bitwarden/common/vault/utils/komboe-wifi";
import {
  CardComponent,
  FormFieldModule,
  IconButtonModule,
  SectionHeaderComponent,
  TypographyModule,
} from "@bitwarden/components";
import { I18nPipe } from "@bitwarden/ui-common";

import { CipherFormContainer } from "../../cipher-form-container";

/**
 * Komboe environment variables template. The user edits dotenv text; each KEY=VALUE line is
 * stored as its own hidden custom field, so every value is encrypted client-side like any other
 * field and other clients still show the variables.
 */
@Component({
  selector: "vault-env-section",
  templateUrl: "./env-section.component.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CardComponent,
    TypographyModule,
    FormFieldModule,
    ReactiveFormsModule,
    SectionHeaderComponent,
    IconButtonModule,
    I18nPipe,
  ],
})
export class EnvSectionComponent implements OnInit {
  readonly showValues = signal(false);
  readonly originalCipherView = input<CipherView | null>(null);
  readonly disabled = input(false);

  readonly envForm = this.formBuilder.group({
    environment: [""],
    variables: [""],
  });

  private readonly destroyRef = inject(DestroyRef);

  constructor(
    private readonly cipherFormContainer: CipherFormContainer,
    private readonly formBuilder: FormBuilder,
  ) {
    this.cipherFormContainer.registerChildForm("envDetails", this.envForm);
    this.envForm.valueChanges.pipe(takeUntilDestroyed()).subscribe((value) => {
      this.cipherFormContainer.patchCipher((cipher) => {
        cipher.fields = komboeEnvFields(value.environment ?? "", value.variables ?? "");
        return cipher;
      });
    });
  }

  ngOnInit() {
    const prefill = this.cipherFormContainer.getInitialCipherView() ?? this.originalCipherView();
    const fields = prefill?.fields;
    if (fields?.length) {
      this.envForm.setValue({
        environment: komboeFieldValue(fields, KOMBOE_ENV_NAME),
        variables: toDotenv(komboeEnvVars(fields)),
      });
    }
    // Komboe: write the template fields now so an item saved without edits keeps its type marker.
    if (!this.disabled()) {
      this.envForm.updateValueAndValidity({ emitEvent: true });
    }
    if (this.disabled()) {
      this.envForm.disable();
    }
    this.cipherFormContainer.formStatusChange$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((status) => {
        if (status === "disabled" || this.disabled()) {
          this.envForm.disable();
        } else {
          this.envForm.enable();
        }
      });
  }
}
