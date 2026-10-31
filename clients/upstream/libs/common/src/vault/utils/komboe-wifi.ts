import { CipherType, FieldType } from "../enums";
import { FieldView } from "../models/view/field.view";

/**
 * Menu-only type. Wi-Fi is stored as a secure note with a marker custom field so the
 * SDK can encrypt and decrypt it. The number is not a server cipher type.
 */
export const KOMBOE_WIFI_TYPE = 9001 as CipherType;
export const KOMBOE_BOOKMARK_TYPE = 9002 as CipherType;
export const KOMBOE_GPG_TYPE = 9003 as CipherType;
export const KOMBOE_ENV_TYPE = 9004 as CipherType;

export const KOMBOE_TEMPLATE_FIELD = "__komboe";
export const KOMBOE_WIFI_TEMPLATE = "wifi";
export const KOMBOE_BOOKMARK_TEMPLATE = "bookmark";
export const KOMBOE_GPG_TEMPLATE = "gpg";
export const KOMBOE_ENV_TEMPLATE = "env";
export const KOMBOE_ENV_NAME = "Environment name";

export const KOMBOE_WIFI_SSID = "SSID";
export const KOMBOE_WIFI_PASSWORD = "Password";
export const KOMBOE_WIFI_SECURITY = "Security";
export const KOMBOE_WIFI_HIDDEN = "Hidden network";
export const KOMBOE_BOOKMARK_URL = "URL";
export const KOMBOE_GPG_KEY_ID = "Key ID";
export const KOMBOE_GPG_FINGERPRINT = "Fingerprint";
export const KOMBOE_GPG_EMAIL = "Email";
export const KOMBOE_GPG_PUBLIC = "Public key";
export const KOMBOE_GPG_PRIVATE = "Private key";
export const KOMBOE_GPG_PASSPHRASE = "Passphrase";

type FieldLike = { name?: string; value?: string; type?: number };

export function isKomboeMenuTemplate(type: number | undefined): boolean {
  return (
    type === KOMBOE_WIFI_TYPE ||
    type === KOMBOE_BOOKMARK_TYPE ||
    type === KOMBOE_GPG_TYPE ||
    type === KOMBOE_ENV_TYPE
  );
}

export function isKomboeGpg(
  cipher: { type?: number; fields?: FieldLike[] } | null | undefined,
): boolean {
  if (!cipher) {
    return false;
  }
  if (cipher.type === KOMBOE_GPG_TYPE) {
    return true;
  }
  return (cipher.fields ?? []).some(
    (field) => field.name === KOMBOE_TEMPLATE_FIELD && field.value === KOMBOE_GPG_TEMPLATE,
  );
}

export function komboeGpgFields(values: {
  keyId: string;
  fingerprint: string;
  email: string;
  publicKey: string;
  privateKey: string;
  passphrase: string;
}): FieldView[] {
  const make = (name: string, value: string, type: FieldType) => {
    const field = new FieldView();
    field.name = name;
    field.value = value;
    field.type = type;
    return field;
  };
  return [
    make(KOMBOE_TEMPLATE_FIELD, KOMBOE_GPG_TEMPLATE, FieldType.Text),
    make(KOMBOE_GPG_KEY_ID, values.keyId, FieldType.Text),
    make(KOMBOE_GPG_FINGERPRINT, values.fingerprint, FieldType.Text),
    make(KOMBOE_GPG_EMAIL, values.email, FieldType.Text),
    make(KOMBOE_GPG_PUBLIC, values.publicKey, FieldType.Text),
    make(KOMBOE_GPG_PRIVATE, values.privateKey, FieldType.Hidden),
    make(KOMBOE_GPG_PASSPHRASE, values.passphrase, FieldType.Hidden),
  ];
}

export function isKomboeBookmark(
  cipher: { type?: number; fields?: FieldLike[] } | null | undefined,
): boolean {
  if (!cipher) {
    return false;
  }
  if (cipher.type === KOMBOE_BOOKMARK_TYPE) {
    return true;
  }
  return (cipher.fields ?? []).some(
    (field) => field.name === KOMBOE_TEMPLATE_FIELD && field.value === KOMBOE_BOOKMARK_TEMPLATE,
  );
}

export function komboeBookmarkFields(url: string): FieldView[] {
  const marker = new FieldView();
  marker.name = KOMBOE_TEMPLATE_FIELD;
  marker.value = KOMBOE_BOOKMARK_TEMPLATE;
  marker.type = FieldType.Text;
  const link = new FieldView();
  link.name = KOMBOE_BOOKMARK_URL;
  link.value = url;
  link.type = FieldType.Text;
  return [marker, link];
}

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

/** A variable name as accepted by POSIX shells and dotenv loaders (dots allowed for dotenv). */
const ENV_KEY = /^[A-Za-z_][A-Za-z0-9_.]*$/;

export function isKomboeEnv(
  cipher: { type?: number; fields?: FieldLike[] } | null | undefined,
): boolean {
  if (!cipher) {
    return false;
  }
  if (cipher.type === KOMBOE_ENV_TYPE) {
    return true;
  }
  return (cipher.fields ?? []).some(
    (field) => field.name === KOMBOE_TEMPLATE_FIELD && field.value === KOMBOE_ENV_TEMPLATE,
  );
}

/** Parses dotenv text (KEY=VALUE lines, `export ` prefix, # comments, quoted values). */
export function parseDotenv(text: string): { key: string; value: string }[] {
  const out: { key: string; value: string }[] = [];
  for (const rawLine of (text ?? "").split(/\r?\n/)) {
    let line = rawLine.trim();
    if (line === "" || line.startsWith("#")) {
      continue;
    }
    if (line.startsWith("export ")) {
      line = line.slice(7).trim();
    }
    const eq = line.indexOf("=");
    if (eq <= 0) {
      continue;
    }
    const key = line.slice(0, eq).trim();
    if (!ENV_KEY.test(key)) {
      continue;
    }
    let value = line.slice(eq + 1).trim();
    if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
      try {
        value = JSON.parse(value);
      } catch {
        value = value.slice(1, -1);
      }
    } else if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) {
      value = value.slice(1, -1);
    } else {
      const hash = value.search(/\s#/);
      if (hash >= 0) {
        value = value.slice(0, hash).trim();
      }
    }
    const existing = out.find((v) => v.key === key);
    if (existing) {
      existing.value = value;
    } else {
      out.push({ key, value });
    }
  }
  return out;
}

/** Serializes variables as dotenv text; values that need it are double-quoted with escapes. */
export function toDotenv(vars: { key: string; value: string }[]): string {
  return vars
    .map(({ key, value }) =>
      /^[A-Za-z0-9_./:@+,-]*$/.test(value) ? `${key}=${value}` : `${key}=${JSON.stringify(value)}`,
    )
    .join("\n");
}

/** Variables stored on an environment item, in order (one hidden custom field each). */
export function komboeEnvVars(fields: FieldLike[] | undefined): { key: string; value: string }[] {
  return (fields ?? [])
    .filter((f) => f.name !== KOMBOE_TEMPLATE_FIELD && f.name !== KOMBOE_ENV_NAME && f.name)
    .filter((f) => ENV_KEY.test(f.name as string))
    .map((f) => ({ key: f.name as string, value: f.value ?? "" }));
}

export function komboeEnvFields(environment: string, dotenv: string): FieldView[] {
  const make = (name: string, value: string, type: FieldType) => {
    const field = new FieldView();
    field.name = name;
    field.value = value;
    field.type = type;
    return field;
  };
  return [
    make(KOMBOE_TEMPLATE_FIELD, KOMBOE_ENV_TEMPLATE, FieldType.Text),
    make(KOMBOE_ENV_NAME, environment, FieldType.Text),
    ...parseDotenv(dotenv).map((v) => make(v.key, v.value, FieldType.Hidden)),
  ];
}
