import { Component, input, ChangeDetectionStrategy } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { RouterTestingModule } from "@angular/router/testing";
import { mock, MockProxy } from "jest-mock-extended";
import { of } from "rxjs";

import { LogoutService } from "@bitwarden/auth/common";
import { AccountService } from "@bitwarden/common/auth/abstractions/account.service";
import { TokenService } from "@bitwarden/common/auth/abstractions/token.service";
import {
  VaultTimeoutAction,
  VaultTimeoutSettingsService,
} from "@bitwarden/common/key-management/vault-timeout";
import { EnvironmentService } from "@bitwarden/common/platform/abstractions/environment.service";
import { I18nService } from "@bitwarden/common/platform/abstractions/i18n.service";
import { PlatformUtilsService } from "@bitwarden/common/platform/abstractions/platform-utils.service";
import { FakeAccountService, mockAccountServiceWith } from "@bitwarden/common/spec";
import { UserId } from "@bitwarden/common/types/guid";
import { LockService } from "@bitwarden/unlock";
import { DynamicAvatarComponent } from "@bitwarden/web-vault/app/components/dynamic-avatar.component";
import { AccountMenuComponent } from "@bitwarden/web-vault/app/layouts/header/account-menu.component";
import { SharedModule } from "@bitwarden/web-vault/app/shared";

@Component({
  selector: "dynamic-avatar",
  standalone: true,
  template: "",
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class MockDynamicAvatarComponent {
  readonly text = input<string | undefined>();
  readonly size = input<string | undefined>();
}

describe("AccountMenuComponent", () => {
  const userId = "UserId" as UserId;

  let fixture: ComponentFixture<AccountMenuComponent>;
  let component: AccountMenuComponent;

  let logoutService: MockProxy<LogoutService>;
  let lockService: MockProxy<LockService>;
  let accountService: FakeAccountService;
  let vaultTimeoutSettingsService: MockProxy<VaultTimeoutSettingsService>;
  let platformUtilsService: MockProxy<PlatformUtilsService>;

  let tokenService: MockProxy<TokenService>;

  beforeEach(async () => {
    tokenService = mock<TokenService>();
    tokenService.getAccessToken.mockResolvedValue("tok");
    globalThis.fetch = jest.fn().mockResolvedValue({ ok: false }) as any;
    sessionStorage.clear();
    logoutService = mock<LogoutService>();
    lockService = mock<LockService>();
    accountService = mockAccountServiceWith(userId);
    vaultTimeoutSettingsService = mock<VaultTimeoutSettingsService>();
    vaultTimeoutSettingsService.availableVaultTimeoutActions$.mockReturnValue(
      of([VaultTimeoutAction.Lock]),
    );
    platformUtilsService = mock<PlatformUtilsService>();
    platformUtilsService.isSelfHost.mockReturnValue(false);

    await TestBed.configureTestingModule({
      imports: [SharedModule, RouterTestingModule, AccountMenuComponent],
      providers: [
        { provide: LogoutService, useValue: logoutService },
        { provide: LockService, useValue: lockService },
        { provide: AccountService, useValue: accountService },
        { provide: VaultTimeoutSettingsService, useValue: vaultTimeoutSettingsService },
        { provide: PlatformUtilsService, useValue: platformUtilsService },
        { provide: TokenService, useValue: tokenService },
        {
          provide: EnvironmentService,
          useValue: { environment$: of({ getIdentityUrl: () => "https://k.test/identity" }) },
        },
        { provide: I18nService, useValue: { t: (key: string) => key } },
      ],
    })
      .overrideComponent(AccountMenuComponent, {
        remove: { imports: [DynamicAvatarComponent] },
        add: { imports: [MockDynamicAvatarComponent] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(AccountMenuComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  describe("logout", () => {
    it("logs out the active user with the userInitiated reason", async () => {
      await component["logout"]();

      expect(logoutService.logout).toHaveBeenCalledWith(userId, "userInitiated");
    });

    it("stores the IdP single-logout URL for SAML accounts before logging out", async () => {
      (globalThis.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ url: "https://idp.test/slo?SAMLRequest=x" }),
      });

      await component["logout"]();

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "https://k.test/identity/connect/saml-logout",
        expect.objectContaining({ method: "POST", headers: { Authorization: "Bearer tok" } }),
      );
      expect(sessionStorage.getItem("komboe.samlSloUrl")).toBe(
        "https://idp.test/slo?SAMLRequest=x",
      );
      expect(logoutService.logout).toHaveBeenCalledWith(userId, "userInitiated");
    });

    it("ignores non-http SLO URLs", async () => {
      (globalThis.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ url: "javascript:alert(1)" }),
      });
      await component["logout"]();
      expect(sessionStorage.getItem("komboe.samlSloUrl")).toBeNull();
    });

    it("does not call logout when there is no active account", async () => {
      accountService.activeAccountSubject.next(null);
      fixture.detectChanges();

      await component["logout"]();

      expect(logoutService.logout).not.toHaveBeenCalled();
    });
  });
});
