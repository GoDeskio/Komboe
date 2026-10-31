import { CommonModule } from "@angular/common";
import { Component, OnInit } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { ActivatedRoute } from "@angular/router";

import { ApiService } from "@bitwarden/common/abstractions/api.service";
import {
  ButtonModule,
  FormFieldModule,
  IconButtonModule,
  InputModule,
  TypographyModule,
} from "@bitwarden/components";

@Component({
  selector: "app-org-directory",
  templateUrl: "directory.component.html",
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormFieldModule,
    IconButtonModule,
    InputModule,
    ButtonModule,
    TypographyModule,
  ],
})
export class DirectoryComponent implements OnInit {
  organizationId = "";
  result = "";
  error = "";
  protected formGroup = this.formBuilder.group({
    url: ["", Validators.required],
    bindDn: ["", Validators.required],
    bindPassword: [""],
    userBase: ["", Validators.required],
    userFilter: ["(objectClass=inetOrgPerson)"],
    groupBase: [""],
  });

  constructor(
    private route: ActivatedRoute,
    private apiService: ApiService,
    private formBuilder: FormBuilder,
  ) {}

  async ngOnInit() {
    this.organizationId = this.findOrgId();
    const current = await this.apiService.send("GET", `/organizations/${this.organizationId}/ldap`, null, true, true);
    if (current?.enabled) {
      this.formGroup.patchValue({
        url: current.url,
        bindDn: current.bindDn,
        userBase: current.userBase,
        userFilter: current.userFilter,
        groupBase: current.groupBase,
      });
    }
  }

  async sync() {
    this.error = "";
    this.result = "";
    const value = this.formGroup.getRawValue();
    try {
      await this.apiService.send(
        "PUT",
        `/organizations/${this.organizationId}/ldap`,
        {
          url: value.url,
          bindDn: value.bindDn,
          bindPassword: value.bindPassword,
          userBase: value.userBase,
          userFilter: value.userFilter,
          groupBase: value.groupBase,
        },
        true,
        true,
      );
      const synced = await this.apiService.send(
        "POST",
        `/organizations/${this.organizationId}/ldap/sync`,
        null,
        true,
        true,
      );
      this.result = `users ${synced.users}, groups ${synced.groups}, revoked ${synced.revoked}`;
    } catch (e) {
      this.error = e instanceof Error ? e.message : "Directory sync failed";
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
