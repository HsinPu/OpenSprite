export function buildHttpApiUrl(wsUrl, pathname) {
  const url = new URL(wsUrl);
  url.protocol = url.protocol === "wss:" ? "https:" : "http:";
  url.pathname = pathname;
  url.search = "";
  return url;
}

export async function requestSettingsJson(wsUrl, pathname, options = {}) {
  const [apiPathname, queryString] = String(pathname).split("?", 2);
  const url = buildHttpApiUrl(wsUrl, apiPathname);
  url.search = queryString || "";
  const response = await fetch(url.toString(), {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    const error = new Error(text || `HTTP ${response.status}`);
    error.status = response.status;
    error.statusText = response.statusText;
    throw error;
  }
  return response.json();
}
