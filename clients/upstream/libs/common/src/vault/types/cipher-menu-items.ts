import { CipherType } from "../enums";
import { KOMBOE_WIFI_TYPE } from "../utils/komboe-wifi";

/**
 * Represents a menu item for creating a new cipher of a specific type
 */
export type CipherMenuItem = {
  /** The cipher type this menu item represents */
  type: CipherType;
  /** The icon class name (e.g., "bwi-globe") */
  icon: string;
  /** The i18n key for the label text */
  labelKey: string;
  /** The i18n key for the subtitle text */
  subtitleKey: string;
};

/**
 * All available cipher menu items with their associated icons and labels
 */
export const CIPHER_MENU_ITEMS = Object.freeze([
  {
    type: CipherType.Login,
    icon: "bwi-globe",
    labelKey: "typeLogin",
    subtitleKey: "typeLoginSubtitle",
  },
  {
    type: CipherType.Card,
    icon: "bwi-credit-card",
    labelKey: "typeCard",
    subtitleKey: "typeCardSubtitle",
  },
  {
    type: CipherType.BankAccount,
    icon: "bwi-bank",
    labelKey: "typeBankAccount",
    subtitleKey: "typeBankAccountSubtitle",
  },
  {
    type: CipherType.Identity,
    icon: "bwi-id-card",
    labelKey: "typeIdentity",
    subtitleKey: "typeIdentitySubtitle",
  },
  {
    type: CipherType.DriversLicense,
    icon: "bwi-id-card",
    labelKey: "typeDriversLicense",
    subtitleKey: "typeDriversLicenseSubtitle",
  },
  {
    type: CipherType.Passport,
    icon: "bwi-passport",
    labelKey: "typePassport",
    subtitleKey: "typePassportSubtitle",
  },
  {
    type: CipherType.SecureNote,
    icon: "bwi-sticky-note",
    labelKey: "typeNote",
    subtitleKey: "typeNoteSubtitle",
  },
  {
    type: CipherType.SshKey,
    icon: "bwi-key",
    labelKey: "typeSshKey",
    subtitleKey: "typeSshKeySubtitle",
  },
  {
    type: KOMBOE_WIFI_TYPE,
    icon: "bwi-wireless",
    labelKey: "typeWifi",
    subtitleKey: "typeWifiSubtitle",
  },
] as const) satisfies readonly CipherMenuItem[];

/**
 * Updated menu items for the new item dialog. Same templates as {@link CIPHER_MENU_ITEMS},
 * with the dialog's icon and label tweaks.
 */
export const DIALOG_CIPHER_MENU_ITEMS = CIPHER_MENU_ITEMS.map((item) => {
  if (item.type === CipherType.Login) {
    return {
      ...item,
      icon: "bwi-lock",
    };
  }

  if (item.type === CipherType.Identity) {
    return {
      ...item,
      icon: "bwi-user",
    };
  }

  if (item.type === CipherType.SecureNote) {
    return {
      ...item,
      labelKey: "typeSecureNote",
    };
  }

  return item;
});
