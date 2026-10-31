import { ChangeDetectionStrategy, Component, inject, input } from "@angular/core";
import { toSignal } from "@angular/core/rxjs-interop";
import { firstValueFrom, map, Observable } from "rxjs";

import { LogoutService } from "@bitwarden/auth/common";
import { AccountService } from "@bitwarden/common/auth/abstractions/account.service";
import { TokenService } from "@bitwarden/common/auth/abstractions/token.service";
import {
  VaultTimeoutAction,
  VaultTimeoutSettingsService,
} from "@bitwarden/common/key-management/vault-timeout";
import { EnvironmentService } from "@bitwarden/common/platform/abstractions/environment.service";
import { PlatformUtilsService } from "@bitwarden/common/platform/abstractions/platform-utils.service";
import { UserId } from "@bitwarden/common/types/guid";
import { LockService, LockSource } from "@bitwarden/unlock";

import { DynamicAvatarComponent } from "../../components/dynamic-avatar.component";
import { SharedModule } from "../../shared";

/** Session-storage key the app shell reads after local logout to continue to the IdP (Komboe SAML SLO). */
export const SAML_SLO_URL_KEY = "komboe.samlSloUrl";

@Component({
  selector: "app-account-menu",
  templateUrl: "./account-menu.component.html",
  imports: [SharedModule, DynamicAvatarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccountMenuComponent {
  /**
   * Shows the name and email next to the avatar. Used by the side-nav footer trigger when the
   * nav is expanded; the header trigger leaves this off and stays icon-only.
   */
  readonly expanded = input(false);

  private readonly platformUtilsService = inject(PlatformUtilsService);
  private readonly vaultTimeoutSettingsService = inject(VaultTimeoutSettingsService);
  private readonly accountService = inject(AccountService);
  private readonly logoutService = inject(LogoutService);
  private readonly lockService = inject(LockService);
  private readonly tokenService = inject(TokenService);
  private readonly environmentService = inject(EnvironmentService);

  protected readonly account = toSignal(this.accountService.activeAccount$);

  protected readonly canLock$: Observable<boolean> = this.vaultTimeoutSettingsService
    .availableVaultTimeoutActions$()
    .pipe(map((actions) => actions.includes(VaultTimeoutAction.Lock)));
  protected readonly selfHosted = this.platformUtilsService.isSelfHost();
  protected readonly hostname = globalThis.location.hostname;

  protected async lock() {
    const userId = this.account()?.id;
    if (userId) {
      await this.lockService.lock(userId, LockSource.Manual);
    }
  }

  protected async logout() {
    const userId = this.account()?.id;
    if (userId) {
      await this.startSamlSingleLogout(userId);
      await this.logoutService.logout(userId, "userInitiated");
    }
  }

  /**
   * Komboe: when the account signed in through SAML and the server has an IdP SLO URL configured,
   * ask the server to end all sessions and build a LogoutRequest. The app shell then sends the
   * browser to the IdP after local keys are wiped. Non-SAML accounts get an error and log out
   * normally. Only the access token is sent; no key material leaves the client.
   */
  private async startSamlSingleLogout(userId: UserId) {
    try {
      const token = await this.tokenService.getAccessToken(userId as UserId);
      if (!token) {
        return;
      }
      const env = await firstValueFrom(this.environmentService.environment$);
      const res = await fetch(env.getIdentityUrl() + "/connect/saml-logout", {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) {
        return;
      }
      const url = (await res.json())?.url;
      if (typeof url === "string" && /^https?:\/\//i.test(url)) {
        globalThis.sessionStorage?.setItem(SAML_SLO_URL_KEY, url);
      }
    } catch {
      // Fall back to a normal logout.
    }
  }
}
