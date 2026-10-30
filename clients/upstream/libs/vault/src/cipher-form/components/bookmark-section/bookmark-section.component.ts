import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, OnInit } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormBuilder, ReactiveFormsModule } from "@angular/forms";

import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import {
  KOMBOE_BOOKMARK_URL,
  komboeBookmarkFields,
  komboeFieldValue,
} from "@bitwarden/common/vault/utils/komboe-wifi";
import {
  CardComponent,
  FormFieldModule,
  SectionHeaderComponent,
  TypographyModule,
} from "@bitwarden/components";
import { I18nPipe } from "@bitwarden/ui-common";

import { CipherFormContainer } from "../../cipher-form-container";

@Component({
  selector: "vault-bookmark-section",
  templateUrl: "./bookmark-section.component.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CardComponent,
    TypographyModule,
    FormFieldModule,
    ReactiveFormsModule,
    SectionHeaderComponent,
    I18nPipe,
  ],
})
export class BookmarkSectionComponent implements OnInit {
  readonly originalCipherView = input<CipherView | null>(null);
  readonly disabled = input(false);

  readonly bookmarkForm = this.formBuilder.group({
    url: [""],
  });

  private readonly destroyRef = inject(DestroyRef);

  constructor(
    private readonly cipherFormContainer: CipherFormContainer,
    private readonly formBuilder: FormBuilder,
  ) {
    this.cipherFormContainer.registerChildForm("bookmarkDetails", this.bookmarkForm);
    this.bookmarkForm.valueChanges.pipe(takeUntilDestroyed()).subscribe((value) => {
      this.cipherFormContainer.patchCipher((cipher) => {
        cipher.fields = komboeBookmarkFields(value.url ?? "");
        return cipher;
      });
    });
  }

  ngOnInit() {
    const prefill = this.cipherFormContainer.getInitialCipherView() ?? this.originalCipherView();
    const fields = prefill?.fields;
    if (fields?.length) {
      this.bookmarkForm.setValue({
        url: komboeFieldValue(fields, KOMBOE_BOOKMARK_URL),
      });
    }

    if (this.disabled()) {
      this.bookmarkForm.disable();
    }

    this.cipherFormContainer.formStatusChange$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((status) => {
        if (status === "disabled" || this.disabled()) {
          this.bookmarkForm.disable();
        } else {
          this.bookmarkForm.enable();
        }
      });
  }
}
