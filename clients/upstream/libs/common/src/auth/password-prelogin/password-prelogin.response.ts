import { KdfConfigResponse } from "../../key-management/models/response/kdf-config.response";
import { BaseResponse } from "../../models/response/base.response";

export class PasswordPreloginResponse extends BaseResponse {
  kdfSettings: KdfConfigResponse;
  salt: string;
  /**
   * Present only when the identifier was a login name. It is the account email.
   * Callers that typed an email must ignore this and keep the typed value.
   */
  email: string | null;

  constructor(response: any) {
    super(response);
    this.kdfSettings = new KdfConfigResponse(this.getResponseProperty("KdfSettings"));
    this.salt = this.getResponseProperty("Salt");
    this.email = this.getResponseProperty("Email");
  }
}
