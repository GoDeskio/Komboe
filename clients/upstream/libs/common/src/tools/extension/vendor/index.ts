import { deepFreeze } from "../../util";

import { AddyIo, AddyIoExtensions } from "./addyio";
import { Bitwarden } from "./bitwarden";
import { DuckDuckGo, DuckDuckGoExtensions } from "./duckduckgo";
import { Fastmail, FastmailExtensions } from "./fastmail";
import { ForwardEmail, ForwardEmailExtensions } from "./forwardemail";
import { Komboe, KomboeExtensions } from "./komboe";
import { Mozilla, MozillaExtensions } from "./mozilla";
import { SimpleLogin, SimpleLoginExtensions } from "./simplelogin";

export const Vendors = deepFreeze([
  AddyIo,
  Bitwarden,
  DuckDuckGo,
  Fastmail,
  ForwardEmail,
  Komboe,
  Mozilla,
  SimpleLogin,
]);

export const VendorExtensions = deepFreeze(
  [
    AddyIoExtensions,
    DuckDuckGoExtensions,
    FastmailExtensions,
    ForwardEmailExtensions,
    KomboeExtensions,
    MozillaExtensions,
    SimpleLoginExtensions,
  ].flat(),
);
