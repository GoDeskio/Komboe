import { CommonModule } from "@angular/common";
import { Component } from "@angular/core";
import { RouterModule } from "@angular/router";
import { firstValueFrom } from "rxjs";

import { DeviceType } from "@bitwarden/common/enums";
import { EnvironmentService } from "@bitwarden/common/platform/abstractions/environment.service";
import { PlatformUtilsService } from "@bitwarden/common/platform/abstractions/platform-utils.service";
import { CenterPositionStrategy, DialogService, ItemModule } from "@bitwarden/components";
import { TroubleshootingDialogComponent } from "@bitwarden/logging-angular";
import { I18nPipe } from "@bitwarden/ui-common";

import { BrowserApi } from "../../../../platform/browser/browser-api";
import { PopOutComponent } from "../../../../platform/popup/components/pop-out.component";
import { PopupHeaderComponent } from "../../../../platform/popup/layout/popup-header.component";
import { PopupPageComponent } from "../../../../platform/popup/layout/popup-page.component";
import { AboutDialogComponent } from "../about-dialog/about-dialog.component";

const RateUrls = {
  [DeviceType.ChromeExtension]:
    "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md",
  [DeviceType.FirefoxExtension]:
    "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md",
  [DeviceType.OperaExtension]:
    "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md",
  [DeviceType.EdgeExtension]:
    "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md",
  [DeviceType.VivaldiExtension]:
    "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md",
  [DeviceType.SafariExtension]:
    "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md",
  [DeviceType.DuckDuckGoExtension]:
    "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md",
};

// FIXME(https://bitwarden.atlassian.net/browse/CL-764): Migrate to OnPush
// eslint-disable-next-line @angular-eslint/prefer-on-push-component-change-detection
@Component({
  templateUrl: "about-page-v2.component.html",
  imports: [
    CommonModule,
    RouterModule,
    PopupPageComponent,
    PopupHeaderComponent,
    PopOutComponent,
    ItemModule,
    I18nPipe,
  ],
})
export class AboutPageV2Component {
  constructor(
    private dialogService: DialogService,
    private environmentService: EnvironmentService,
    private platformUtilsService: PlatformUtilsService,
  ) {}

  about() {
    this.dialogService.open(AboutDialogComponent, {
      positionStrategy: new CenterPositionStrategy(),
    });
  }

  troubleshoot() {
    TroubleshootingDialogComponent.open(this.dialogService);
  }

  async launchHelp() {
    const confirmed = await this.dialogService.openSimpleDialog({
      title: { key: "continueToHelpCenter" },
      content: { key: "continueToHelpCenterDesc" },
      type: "info",
      acceptButtonText: { key: "continue" },
    });
    if (confirmed) {
      await BrowserApi.createNewTab("https://github.com/GoDeskio/Komboe/tree/main/docs");
    }
  }

  async openWebVault() {
    const confirmed = await this.dialogService.openSimpleDialog({
      title: { key: "continueToWebApp" },
      content: { key: "continueToWebAppDesc" },
      type: "info",
      acceptButtonText: { key: "continue" },
    });
    if (confirmed) {
      const env = await firstValueFrom(this.environmentService.environment$);
      const url = env.getWebVaultUrl();
      await BrowserApi.createNewTab(url);
    }
  }

  async rate() {
    const confirmed = await this.dialogService.openSimpleDialog({
      title: { key: "continueToBrowserExtensionStore" },
      content: { key: "continueToBrowserExtensionStoreDesc" },
      type: "info",
      acceptButtonText: { key: "continue" },
    });
    if (confirmed) {
      const deviceType = this.platformUtilsService.getDevice();
      await BrowserApi.createNewTab((RateUrls as any)[deviceType]);
    }
  }
}
