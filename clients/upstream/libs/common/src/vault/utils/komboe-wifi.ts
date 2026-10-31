import { CipherType, FieldType } from "../enums";
import { FieldView } from "../models/view/field.view";

/**
 * Menu-only type. Wi-Fi is stored as a secure note with a marker custom field so the
 * SDK can encrypt and decrypt it. The number is not a server cipher type.
 */
export const KOMBOE_WIFI_TYPE = 9001 as CipherType;

export const KOMBOE_TEMPLATE_FIELD = "__komboe";
export const KOMBOE_WIFI_TEMPLATE = "wifi";

export const KOMBOE_WIFI_SSID = "SSID";
export const KOMBOE_WIFI_PASSWORD = "Password";
export const KOMBOE_WIFI_SECURITY = "Security";
export const KOMBOE_WIFI_HIDDEN = "Hidden network";

type FieldLike = { name?: string; value?: string; type?: number };

export function isKomboeWifi(
  cipher: { type?: number; fields?: FieldLike[] } | null | undefined,
): boolean {
  if (!cipher) {
    return false;
  }
  if (cipher.type === KOMBOE_WIFI_TYPE) {
    return true;
  }
  return (cipher.fields ?? []).some(
    (field) => field.name === KOMBOE_TEMPLATE_FIELD && field.value === KOMBOE_WIFI_TEMPLATE,
  );
}

export function komboeFieldValue(fields: FieldLike[] | undefined, name: string): string {
  return fields?.find((field) => field.name === name)?.value ?? "";
}

export function komboeWifiFields(
  ssid: string,
  password: string,
  security: string,
  hidden: boolean,
): FieldView[] {
  const make = (name: string, value: string, type: FieldType) => {
    const field = new FieldView();
    field.name = name;
    field.value = value;
    field.type = type;
    return field;
  };
  return [
    make(KOMBOE_TEMPLATE_FIELD, KOMBOE_WIFI_TEMPLATE, FieldType.Text),
    make(KOMBOE_WIFI_SSID, ssid, FieldType.Text),
    make(KOMBOE_WIFI_PASSWORD, password, FieldType.Hidden),
    make(KOMBOE_WIFI_SECURITY, security, FieldType.Text),
    make(KOMBOE_WIFI_HIDDEN, hidden ? "true" : "false", FieldType.Boolean),
  ];
}
