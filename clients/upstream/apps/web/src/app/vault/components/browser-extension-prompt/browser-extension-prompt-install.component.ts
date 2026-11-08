import { CommonModule } from "@angular/common";
import { Component, OnInit } from "@angular/core";
import { map } from "rxjs";

import { PlatformUtilsService } from "@bitwarden/common/platform/abstractions/platform-utils.service";
import { getWebStoreUrl } from "@bitwarden/common/vault/utils/get-web-store-url";
import { LinkModule } from "@bitwarden/components";
import { I18nPipe } from "@bitwarden/ui-common";

import {
  BrowserExtensionPromptService,
  BrowserPromptState,
} from "../../services/browser-extension-prompt.service";

// FIXME(https://bitwarden.atlassian.net/browse/CL-764): Migrate to OnPush
// eslint-disable-next-line @angular-eslint/prefer-on-push-component-change-detection
@Component({
  selector: "vault-browser-extension-prompt-install",
  templateUrl: "./browser-extension-prompt-install.component.html",
  imports: [CommonModule, I18nPipe, LinkModule],
})
export class BrowserExtensionPromptInstallComponent implements OnInit {
  /** The install link should only show for the error states */
  protected shouldShow$ = this.browserExtensionPromptService.pageState$.pipe(
    map((state) => state === BrowserPromptState.Error || state === BrowserPromptState.ManualOpen),
  );

  /** All available page states */
  protected BrowserPromptState = BrowserPromptState;

  /**
   * Installation link for the extension. Komboe is not in the upstream stores.
   */
  protected webStoreUrl = getWebStoreUrl(this.platformService.getDevice());

  constructor(
    private browserExtensionPromptService: BrowserExtensionPromptService,
    private platformService: PlatformUtilsService,
  ) {}

  ngOnInit(): void {
    this.webStoreUrl = getWebStoreUrl(this.platformService.getDevice());
  }
}
