import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";


export const startupViews = ["new", "recent"] as const;
export type StartupView = typeof startupViews[number];
export const sendBehaviors = ["enter", "modifier-enter"] as const;
export type SendBehavior = typeof sendBehaviors[number];

export type ConversationSettings = {
  startupView: StartupView;
  sendBehavior: SendBehavior;
  autoScroll: boolean;
  executionPanelDefaultExpanded: boolean;
};

export type ConversationSettingsErrorCode = "invalid_request" | "settings_store_unavailable" | "internal_error" | "malformed_response" | "network_error";

export class ConversationSettingsApiError extends Error {
  constructor(readonly code: ConversationSettingsErrorCode) {
    super(code);
    this.name = "ConversationSettingsApiError";
  }
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const serverCodes = ["invalid_request", "settings_store_unavailable", "internal_error"] as const;

function responseBody(value: unknown): ConversationSettings {
  if (!record(value)
    || !exactKeys(value, ["startupView", "sendBehavior", "autoScroll", "executionPanelDefaultExpanded"])
    || typeof value.startupView !== "string"
    || !startupViews.includes(value.startupView as StartupView)
    || typeof value.sendBehavior !== "string"
    || !sendBehaviors.includes(value.sendBehavior as SendBehavior)
    || typeof value.autoScroll !== "boolean"
    || typeof value.executionPanelDefaultExpanded !== "boolean") {
    throw new ConversationSettingsApiError("malformed_response");
  }
  return {
    startupView: value.startupView as StartupView,
    sendBehavior: value.sendBehavior as SendBehavior,
    autoScroll: value.autoScroll,
    executionPanelDefaultExpanded: value.executionPanelDefaultExpanded,
  };
}

function errorCode(value: unknown, allowed: readonly string[]): ConversationSettingsErrorCode {
  if (!record(value)
    || !exactKeys(value, ["error"])
    || !record(value.error)
    || !exactKeys(value.error, ["code", "message", "retryable"])
    || typeof value.error.code !== "string"
    || !serverCodes.includes(value.error.code as (typeof serverCodes)[number])
    || !allowed.includes(value.error.code)
    || typeof value.error.message !== "string"
    || typeof value.error.retryable !== "boolean") {
    throw new ConversationSettingsApiError("malformed_response");
  }
  return value.error.code as ConversationSettingsErrorCode;
}

async function request(init: RequestInit | undefined, errors: ReadonlyMap<number, readonly string[]>): Promise<ConversationSettings> {
  let response: Response;
  try {
    response = await apiFetch("/api/settings/conversation", init);
  } catch {
    throw new ConversationSettingsApiError("network_error");
  }
  if (response.status !== 200) {
    if (response.ok) throw new ConversationSettingsApiError("malformed_response");
    let body: unknown;
    try { body = await response.json(); } catch { throw new ConversationSettingsApiError("malformed_response"); }
    throw new ConversationSettingsApiError(errorCode(body, errors.get(response.status) ?? []));
  }
  let body: unknown;
  try { body = await response.json(); } catch { throw new ConversationSettingsApiError("malformed_response"); }
  return responseBody(body);
}

export function getConversationSettings(): Promise<ConversationSettings> {
  return request(undefined, new Map([[503, ["settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export function putConversationSettings(settings: ConversationSettings): Promise<ConversationSettings> {
  return request({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings) }, new Map([[400, ["invalid_request"]], [503, ["settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export function conversationSettingsErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof ConversationSettingsApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "error.conversationSettings.invalidRequest",
    settings_store_unavailable: "error.conversationSettings.settingsStore",
    internal_error: "error.conversationSettings.internal",
    malformed_response: "error.conversationSettings.malformed",
    network_error: "error.network",
  } satisfies Record<ConversationSettingsErrorCode, MessageKey>;
  return t(keys[code]);
}
import { apiFetch } from "./http";
