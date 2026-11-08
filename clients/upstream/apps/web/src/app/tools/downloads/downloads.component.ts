import { ChangeDetectionStrategy, Component } from "@angular/core";

import {
  KOMBOE_EXTENSION_DOCS,
  KOMBOE_MOBILE_DOCS,
  KOMBOE_SOURCE,
} from "@bitwarden/common/komboe/public-links";
import { LinkModule, TypographyModule } from "@bitwarden/components";

/**
 * Persistent Downloads page. Install and extension steps live here, not on the vault dashboard.
 */
@Component({
  selector: "app-downloads",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TypographyModule, LinkModule],
  template: `
    <main class="tw-mx-auto tw-mt-8 tw-w-full tw-max-w-3xl tw-px-4" data-testid="downloads-page">
      <h1 bitTypography="h1">Downloads</h1>
      <p bitTypography="body1">
        Install Komboe from the project docs. Store listings for the upstream password manager are
        not Komboe.
      </p>
      <ul class="tw-mt-4 tw-space-y-3">
        <li>
          <a bitLink [href]="extensionDocs" target="_blank" rel="noreferrer" data-testid="downloads-extension">
            Browser extension
          </a>
        </li>
        <li>
          <a bitLink [href]="mobileDocs" target="_blank" rel="noreferrer" data-testid="downloads-mobile">
            Mobile and desktop source
          </a>
        </li>
        <li>
          <a bitLink [href]="source" target="_blank" rel="noreferrer" data-testid="downloads-source">
            Source code
          </a>
        </li>
      </ul>
      <p bitTypography="body2" class="tw-mt-6">
        Import an existing vault from Tools. Creating an account stays on the sign-up page.
      </p>
    </main>
  `,
})
export class DownloadsComponent {
  protected readonly extensionDocs = KOMBOE_EXTENSION_DOCS;
  protected readonly mobileDocs = KOMBOE_MOBILE_DOCS;
  protected readonly source = KOMBOE_SOURCE;
}
