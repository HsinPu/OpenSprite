export function buildHttpApiUrl(wsUrl: string, pathname: string): URL {
  const url = new URL(wsUrl);
  url.protocol = url.protocol === "wss:" ? "https:" : "http:";
  url.pathname = pathname;
  url.search = "";
  return url;
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
    const error = Object.assign(new Error(text || `HTTP ${response.status}`), {
      status: response.status,
      statusText: response.statusText,
    });
    throw error;
  }
  const payload: unknown = await response.json();
  return payload;
}
