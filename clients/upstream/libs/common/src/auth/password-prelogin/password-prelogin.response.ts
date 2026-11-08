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
  /** Exact vault-key email when prelogin looked up an email. Null for an unknown email. */
  kdfEmail: string | null;
  /** Login-name envelope. Null for an email prelogin. */
  envelope: string | null;
  envelopeSalt: string | null;

  constructor(response: any) {
    super(response);
    this.kdfSettings = new KdfConfigResponse(this.getResponseProperty("KdfSettings"));
    this.salt = this.getResponseProperty("Salt");
    this.email = this.getResponseProperty("Email");
    this.kdfEmail = this.getResponseProperty("KdfEmail");
    this.envelope = this.getResponseProperty("Envelope");
    this.envelopeSalt = this.getResponseProperty("EnvelopeSalt");
  }
}
