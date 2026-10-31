import { ChangeDetectionStrategy, Component, OnInit, signal } from "@angular/core";
import { RouterModule } from "@angular/router";

import { PlatformUtilsService } from "@bitwarden/common/platform/abstractions/platform-utils.service";
import { KomboeLegalNoticeComponent, TypographyModule } from "@bitwarden/components";

/** About Komboe: version plus the legal notice (attribution, warranty, license and source links). */
@Component({
  selector: "app-about",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterModule, TypographyModule, KomboeLegalNoticeComponent],
  template: `
    <main class="tw-mx-auto tw-mt-12 tw-max-w-2xl tw-px-4 tw-text-center" data-testid="about-page">
      <h1 bitTypography="h1">About Komboe</h1>
      <p bitTypography="body1" data-testid="about-version">Version {{ version() }}</p>
      <bit-komboe-legal-notice></bit-komboe-legal-notice>
      <p bitTypography="body2" class="tw-mt-6">
        License texts ship with this web vault:
        <a href="LICENSE.txt" target="_blank" rel="noreferrer">LICENSE.txt</a>,
        <a href="LICENSE_GPL.txt" target="_blank" rel="noreferrer">LICENSE_GPL.txt</a>,
        <a href="THIRD-PARTY-NOTICES.md" target="_blank" rel="noreferrer">THIRD-PARTY-NOTICES.md</a>
      </p>
      <p bitTypography="body2"><a routerLink="/">Back</a></p>
    </main>
  `,
})
export class AboutComponent implements OnInit {
  protected version = signal("");
  constructor(private platformUtilsService: PlatformUtilsService) {}
  async ngOnInit() {
    this.version.set(await this.platformUtilsService.getApplicationVersion());
  }
}
