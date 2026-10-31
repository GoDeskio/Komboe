import { ChangeDetectionStrategy, Component } from "@angular/core";

import {
  KOMBOE_LEGAL_NOTICE,
  komboeLicenseUrl,
  komboeSourceUrl,
} from "@bitwarden/common/platform/misc/komboe-legal";

@Component({
  selector: "bit-komboe-legal-notice",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p class="tw-text-xs tw-text-muted tw-max-w-2xl tw-mx-auto tw-mb-1" data-testid="komboe-legal-notice">
      {{ notice }}
    </p>
    <p class="tw-text-xs tw-mb-0">
      <a class="tw-text-primary-600 tw-underline" [href]="licenseUrl" target="_blank" rel="noreferrer" data-testid="komboe-license-link">View license</a>
      ·
      <a class="tw-text-primary-600 tw-underline" [href]="sourceUrl" target="_blank" rel="noreferrer" data-testid="komboe-source-link">Source code</a>
    </p>
  `,
})
export class KomboeLegalNoticeComponent {
  protected readonly notice = KOMBOE_LEGAL_NOTICE;
  protected readonly licenseUrl = komboeLicenseUrl();
  protected readonly sourceUrl = komboeSourceUrl();
}
