export function buildHttpApiUrl(wsUrl: string, pathname: string): URL {
  const url = new URL(wsUrl);
  url.protocol = url.protocol === "wss:" ? "https:" : "http:";
  url.pathname = pathname;
  url.search = "";
  return url;
}

type ErrorResponsePayload = {
  error?: unknown;
  message?: unknown;
};

function isErrorResponsePayload(value: unknown): value is ErrorResponsePayload {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function payloadErrorMessage(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (!isErrorResponsePayload(value)) {
    return "";
  }
  const error = typeof value.error === "string" ? value.error.trim() : "";
  const message = typeof value.message === "string" ? value.message.trim() : "";
  return error || message;
}

function responseErrorMessage(text: string, status: number): string {
  const body = text.trim();
  if (!body) {
    return `HTTP ${status}`;
  }
  try {
    return payloadErrorMessage(JSON.parse(body)) || body;
  } catch {
    return body;
  }
}

export async function requestSettingsJson(
  wsUrl: string,
  pathname: string,
  options: RequestInit = {},
): Promise<unknown> {
  const [apiPathname, queryString] = String(pathname).split("?", 2);
  const url = buildHttpApiUrl(wsUrl, apiPathname);
  url.search = queryString || "";
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(url.toString(), {
    ...options,
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    const error = Object.assign(new Error(responseErrorMessage(text, response.status)), {
      status: response.status,
      statusText: response.statusText,
    });
    throw error;
  }
  const payload: unknown = await response.json();
  return payload;
}
