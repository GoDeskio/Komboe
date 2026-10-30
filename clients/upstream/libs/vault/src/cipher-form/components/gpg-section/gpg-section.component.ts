import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, OnInit } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormBuilder, ReactiveFormsModule } from "@angular/forms";

import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import {
  KOMBOE_GPG_EMAIL,
  KOMBOE_GPG_FINGERPRINT,
  KOMBOE_GPG_KEY_ID,
  KOMBOE_GPG_PASSPHRASE,
  KOMBOE_GPG_PRIVATE,
  KOMBOE_GPG_PUBLIC,
  komboeFieldValue,
  komboeGpgFields,
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

@Component({
  selector: "vault-gpg-section",
  templateUrl: "./gpg-section.component.html",
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
export class GpgSectionComponent implements OnInit {
  readonly originalCipherView = input<CipherView | null>(null);
  readonly disabled = input(false);

  readonly gpgForm = this.formBuilder.group({
    keyId: [""],
    fingerprint: [""],
    email: [""],
    publicKey: [""],
    privateKey: [""],
    passphrase: [""],
  });

  private readonly destroyRef = inject(DestroyRef);

  constructor(
    private readonly cipherFormContainer: CipherFormContainer,
    private readonly formBuilder: FormBuilder,
  ) {
    this.cipherFormContainer.registerChildForm("gpgDetails", this.gpgForm);
    this.gpgForm.valueChanges.pipe(takeUntilDestroyed()).subscribe((value) => {
      this.cipherFormContainer.patchCipher((cipher) => {
        cipher.fields = komboeGpgFields({
          keyId: value.keyId ?? "",
          fingerprint: value.fingerprint ?? "",
          email: value.email ?? "",
          publicKey: value.publicKey ?? "",
          privateKey: value.privateKey ?? "",
          passphrase: value.passphrase ?? "",
        });
        return cipher;
      });
    });
  }

  ngOnInit() {
    const prefill = this.cipherFormContainer.getInitialCipherView() ?? this.originalCipherView();
    const fields = prefill?.fields;
    if (fields?.length) {
      this.gpgForm.setValue({
        keyId: komboeFieldValue(fields, KOMBOE_GPG_KEY_ID),
        fingerprint: komboeFieldValue(fields, KOMBOE_GPG_FINGERPRINT),
        email: komboeFieldValue(fields, KOMBOE_GPG_EMAIL),
        publicKey: komboeFieldValue(fields, KOMBOE_GPG_PUBLIC),
        privateKey: komboeFieldValue(fields, KOMBOE_GPG_PRIVATE),
        passphrase: komboeFieldValue(fields, KOMBOE_GPG_PASSPHRASE),
      });
    }
    if (this.disabled()) {
      this.gpgForm.disable();
    }
    this.cipherFormContainer.formStatusChange$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((status) => {
        if (status === "disabled" || this.disabled()) {
          this.gpgForm.disable();
        } else {
          this.gpgForm.enable();
        }
      });
  }
}
