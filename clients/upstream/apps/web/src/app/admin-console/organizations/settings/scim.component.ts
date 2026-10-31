import { CommonModule } from "@angular/common";
import { Component, OnInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { firstValueFrom } from "rxjs";

import { ApiService } from "@bitwarden/common/abstractions/api.service";
import { EnvironmentService } from "@bitwarden/common/platform/abstractions/environment.service";
import {
  ButtonModule,
  FormFieldModule,
  IconButtonModule,
  InputModule,
  TypographyModule,
} from "@bitwarden/components";

@Component({
  selector: "app-org-scim",
  templateUrl: "scim.component.html",
  imports: [CommonModule, FormFieldModule, IconButtonModule, InputModule, ButtonModule, TypographyModule],
})
export class ScimComponent implements OnInit {
  organizationId = "";
  scimUrl = "";
  enabled = false;
  token = "";
  error = "";

  constructor(
    private route: ActivatedRoute,
    private apiService: ApiService,
    private environmentService: EnvironmentService,
  ) {}

  async ngOnInit() {
    this.organizationId = this.findOrgId();
    const env = await firstValueFrom(this.environmentService.environment$);
    this.scimUrl = env.getScimUrl();
    const status = await this.apiService.send(
      "GET",
      `/organizations/${this.organizationId}/scim`,
      null,
      true,
      true,
    );
    this.enabled = !!status?.enabled;
  }

  async generate() {
    this.error = "";
    try {
      const created = await this.apiService.send(
        "POST",
        `/organizations/${this.organizationId}/scim/token`,
        null,
        true,
        true,
      );
      this.token = created?.token ?? "";
      this.enabled = true;
    } catch (e) {
      this.error = e instanceof Error ? e.message : "Could not create a SCIM token";
    }
  }

  private findOrgId(): string {
    let current: ActivatedRoute | null = this.route;
    while (current) {
      const id = current.snapshot.paramMap.get("organizationId");
      if (id) {
        return id;
      }
      current = current.parent;
    }
    return "";
  }
}
