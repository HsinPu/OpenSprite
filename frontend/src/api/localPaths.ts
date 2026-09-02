import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";


export type LocalPathKind = "executable" | "directory";
export type LocalPathErrorCode = "invalid_request" | "invalid_selection" | "picker_busy" | "picker_unavailable" | "internal_error" | "malformed_response" | "network_error";

export class LocalPathApiError extends Error {
  constructor(readonly code: LocalPathErrorCode) {
    super(code);
    this.name = "LocalPathApiError";
  }
}

const serverCodes: LocalPathErrorCode[] = ["invalid_request", "invalid_selection", "picker_busy", "picker_unavailable", "internal_error"];
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));

function errorCode(value: unknown): LocalPathErrorCode {
  if (!record(value) || !exactKeys(value, ["error"]) || !record(value.error) || !exactKeys(value.error, ["code", "message", "retryable"]) || typeof value.error.code !== "string" || !serverCodes.includes(value.error.code as LocalPathErrorCode) || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") throw new LocalPathApiError("malformed_response");
  return value.error.code as LocalPathErrorCode;
}

export async function pickLocalPath(kind: LocalPathKind): Promise<string | null> {
  let response: Response;
  try {
    response = await fetch("/api/local-paths/pick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind }),
    });
  } catch {
    throw new LocalPathApiError("network_error");
  }
  if (response.status === 204) return null;
  let body: unknown;
  try { body = await response.json(); } catch { throw new LocalPathApiError("malformed_response"); }
  if (response.status !== 200) throw new LocalPathApiError(errorCode(body));
  if (!record(body) || !exactKeys(body, ["path"]) || typeof body.path !== "string" || !body.path || body.path.length > 32768) throw new LocalPathApiError("malformed_response");
  return body.path;
}

export function localPathErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof LocalPathApiError ? error.code : "network_error";
  const keys: Record<LocalPathErrorCode, MessageKey> = {
    invalid_request: "error.localPath.invalidRequest",
    invalid_selection: "error.localPath.invalidSelection",
    picker_busy: "error.localPath.busy",
    picker_unavailable: "error.localPath.unavailable",
    internal_error: "error.localPath.internal",
    malformed_response: "error.localPath.malformed",
    network_error: "error.network",
  };
  return t(keys[code]);
}
