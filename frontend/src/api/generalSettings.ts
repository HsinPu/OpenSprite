import { defaultTranslator, isLocale, type Locale, type MessageKey, type Translator } from "../i18n/catalog";

export const timeZones = ["system", "Asia/Taipei", "UTC"] as const;
export type TimeZoneSetting = typeof timeZones[number];

export type GeneralSettings = {
  locale: Locale;
  timeZone: TimeZoneSetting;
};

export type GeneralSettingsErrorCode = "invalid_request" | "settings_store_unavailable" | "internal_error" | "malformed_response" | "network_error";

export class GeneralSettingsApiError extends Error {
  constructor(readonly code: GeneralSettingsErrorCode) {
    super(code);
    this.name = "GeneralSettingsApiError";
  }
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const serverCodes = ["invalid_request", "settings_store_unavailable", "internal_error"] as const;

function responseBody(value: unknown): GeneralSettings {
  if (!record(value)
    || !exactKeys(value, ["locale", "timeZone"])
    || typeof value.locale !== "string"
    || !isLocale(value.locale)
    || typeof value.timeZone !== "string"
    || !timeZones.includes(value.timeZone as TimeZoneSetting)) {
    throw new GeneralSettingsApiError("malformed_response");
  }
  return { locale: value.locale, timeZone: value.timeZone as TimeZoneSetting };
}

function errorCode(value: unknown, allowed: readonly string[]): GeneralSettingsErrorCode {
  if (!record(value)
    || !exactKeys(value, ["error"])
    || !record(value.error)
    || !exactKeys(value.error, ["code", "message", "retryable"])
    || typeof value.error.code !== "string"
    || !serverCodes.includes(value.error.code as (typeof serverCodes)[number])
    || !allowed.includes(value.error.code)
    || typeof value.error.message !== "string"
    || typeof value.error.retryable !== "boolean") {
    throw new GeneralSettingsApiError("malformed_response");
  }
  return value.error.code as GeneralSettingsErrorCode;
}

async function request(init: RequestInit | undefined, errors: ReadonlyMap<number, readonly string[]>): Promise<GeneralSettings> {
  let response: Response;
  try {
    response = await fetch("/api/settings/general", init);
  } catch {
    throw new GeneralSettingsApiError("network_error");
  }
  if (response.status !== 200) {
    if (response.ok) throw new GeneralSettingsApiError("malformed_response");
    let body: unknown;
    try { body = await response.json(); } catch { throw new GeneralSettingsApiError("malformed_response"); }
    throw new GeneralSettingsApiError(errorCode(body, errors.get(response.status) ?? []));
  }
  let body: unknown;
  try { body = await response.json(); } catch { throw new GeneralSettingsApiError("malformed_response"); }
  return responseBody(body);
}

export function getGeneralSettings(): Promise<GeneralSettings> {
  return request(undefined, new Map([[503, ["settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export function putGeneralSettings(settings: GeneralSettings): Promise<GeneralSettings> {
  return request({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings) }, new Map([[400, ["invalid_request"]], [503, ["settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export function generalSettingsErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof GeneralSettingsApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "error.general.invalidRequest",
    settings_store_unavailable: "error.general.settingsStore",
    internal_error: "error.general.internal",
    malformed_response: "error.general.malformed",
    network_error: "error.network",
  } satisfies Record<GeneralSettingsErrorCode, MessageKey>;
  return t(keys[code]);
}
