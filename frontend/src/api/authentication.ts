export type AuthStatus =
  | { state: "setup_required" }
  | { state: "unauthenticated" }
  | { state: "authenticated"; expiresAt: string };

export type AuthErrorCode =
  | "invalid_request"
  | "invalid_credentials"
  | "setup_required"
  | "setup_unavailable"
  | "rate_limited"
  | "authentication_required"
  | "access_store_unavailable"
  | "internal_error"
  | "malformed_response"
  | "network_error";

export class AuthenticationApiError extends Error {
  constructor(readonly code: AuthErrorCode, readonly retryAfterSeconds: number | null = null) {
    super(code);
    this.name = "AuthenticationApiError";
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, keys: readonly string[]) => Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));
const authCodes = new Set<AuthErrorCode>(["invalid_request", "invalid_credentials", "setup_required", "setup_unavailable", "rate_limited", "authentication_required", "access_store_unavailable", "internal_error"]);

function parseStatus(value: unknown): AuthStatus {
  if (!isRecord(value) || typeof value.state !== "string") throw new AuthenticationApiError("malformed_response");
  if (value.state === "setup_required" || value.state === "unauthenticated") {
    if (!exactKeys(value, ["state"])) throw new AuthenticationApiError("malformed_response");
    return { state: value.state };
  }
  if (value.state === "authenticated" && exactKeys(value, ["state", "expiresAt"]) && typeof value.expiresAt === "string" && !Number.isNaN(Date.parse(value.expiresAt))) {
    return { state: "authenticated", expiresAt: value.expiresAt };
  }
  throw new AuthenticationApiError("malformed_response");
}

async function request(path: string, init?: RequestInit): Promise<AuthStatus> {
  let response: Response;
  try { response = await fetch(path, { ...init, credentials: "same-origin" }); }
  catch { throw new AuthenticationApiError("network_error"); }
  let value: unknown;
  try { value = await response.json(); } catch { throw new AuthenticationApiError("malformed_response"); }
  if (!response.ok) {
    const code = isRecord(value) && exactKeys(value, ["error"]) && isRecord(value.error) && exactKeys(value.error, ["code", "message", "retryable"]) && typeof value.error.code === "string" && typeof value.error.message === "string" && typeof value.error.retryable === "boolean" && authCodes.has(value.error.code as AuthErrorCode)
      ? value.error.code as AuthErrorCode : "malformed_response";
    const retry = response.headers.get("Retry-After");
    throw new AuthenticationApiError(code, retry !== null && /^\d+$/.test(retry) ? Number(retry) : null);
  }
  return parseStatus(value);
}

async function voidRequest(path: string): Promise<void> {
  let response: Response;
  try { response = await fetch(path, { method: "POST", credentials: "same-origin" }); }
  catch { throw new AuthenticationApiError("network_error"); }
  if (response.status === 204) return;
  let value: unknown;
  try { value = await response.json(); } catch { throw new AuthenticationApiError("malformed_response"); }
  const code = isRecord(value) && exactKeys(value, ["error"]) && isRecord(value.error) && exactKeys(value.error, ["code", "message", "retryable"]) && typeof value.error.code === "string" && typeof value.error.message === "string" && typeof value.error.retryable === "boolean" && authCodes.has(value.error.code as AuthErrorCode)
    ? value.error.code as AuthErrorCode : "malformed_response";
  throw new AuthenticationApiError(code);
}

const jsonRequest = (method: string, body?: object): RequestInit => ({
  method,
  headers: body ? { "Content-Type": "application/json" } : undefined,
  body: body ? JSON.stringify(body) : undefined,
});

export const getAuthStatus = () => request("/api/auth/status");
export const setupAccess = (bootstrapToken: string, password: string) => request("/api/auth/setup", jsonRequest("POST", { bootstrapToken, password }));
export const login = (password: string) => request("/api/auth/login", jsonRequest("POST", { password }));
export const logout = () => voidRequest("/api/auth/logout");
export const logoutAll = () => voidRequest("/api/auth/logout-all");
export const changePassword = (currentPassword: string, newPassword: string) => request("/api/auth/password", jsonRequest("PUT", { currentPassword, newPassword }));
