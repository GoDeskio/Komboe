import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, OnInit } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormBuilder, ReactiveFormsModule } from "@angular/forms";

import { CipherView } from "@bitwarden/common/vault/models/view/cipher.view";
import {
  KOMBOE_WIFI_HIDDEN,
  KOMBOE_WIFI_PASSWORD,
  KOMBOE_WIFI_SECURITY,
  KOMBOE_WIFI_SSID,
  komboeFieldValue,
  komboeWifiFields,
} from "@bitwarden/common/vault/utils/komboe-wifi";
import {
  CardComponent,
  CheckboxModule,
  FormFieldModule,
  IconButtonModule,
  SectionHeaderComponent,
  SelectModule,
  TypographyModule,
} from "@bitwarden/components";
import { I18nPipe } from "@bitwarden/ui-common";

import { CipherFormContainer } from "../../cipher-form-container";

@Component({
  selector: "vault-wifi-section",
  templateUrl: "./wifi-section.component.html",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CardComponent,
    TypographyModule,
    FormFieldModule,
    ReactiveFormsModule,
    SelectModule,
    CheckboxModule,
    SectionHeaderComponent,
    IconButtonModule,
    I18nPipe,
  ],
})
export class WifiSectionComponent implements OnInit {
  readonly originalCipherView = input<CipherView | null>(null);
  readonly disabled = input(false);

  readonly securityOptions = ["WPA2", "WPA3", "WPA2/WPA3", "WEP", "Open", "Enterprise"];

  readonly wifiForm = this.formBuilder.group({
    ssid: [""],
    password: [""],
    security: ["WPA2"],
    hidden: [false],
  });

  private readonly destroyRef = inject(DestroyRef);

  constructor(
    private readonly cipherFormContainer: CipherFormContainer,
    private readonly formBuilder: FormBuilder,
  ) {
    this.cipherFormContainer.registerChildForm("wifiDetails", this.wifiForm);
    this.wifiForm.valueChanges.pipe(takeUntilDestroyed()).subscribe((value) => {
      this.cipherFormContainer.patchCipher((cipher) => {
        cipher.fields = komboeWifiFields(
          value.ssid ?? "",
          value.password ?? "",
          value.security ?? "WPA2",
          !!value.hidden,
        );
        return cipher;
      });
    });
  }

  ngOnInit() {
    const prefill = this.cipherFormContainer.getInitialCipherView() ?? this.originalCipherView();
    const fields = prefill?.fields;
    if (fields?.length) {
      this.wifiForm.setValue({
        ssid: komboeFieldValue(fields, KOMBOE_WIFI_SSID),
        password: komboeFieldValue(fields, KOMBOE_WIFI_PASSWORD),
        security: komboeFieldValue(fields, KOMBOE_WIFI_SECURITY) || "WPA2",
        hidden: komboeFieldValue(fields, KOMBOE_WIFI_HIDDEN) === "true",
      });
    }

    if (this.disabled()) {
      this.wifiForm.disable();
    }

    this.cipherFormContainer.formStatusChange$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((status) => {
        if (status === "disabled" || this.disabled()) {
          this.wifiForm.disable();
        } else {
          this.wifiForm.enable();
        }
      });
  }
}
