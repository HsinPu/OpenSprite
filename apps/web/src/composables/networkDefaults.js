export const DEFAULT_HTTP_PROXY = "";
export const DEFAULT_HTTPS_PROXY = "";
export const DEFAULT_NO_PROXY = "127.0.0.1,localhost";

export function createDefaultNetworkState() {
  return {
    http_proxy: DEFAULT_HTTP_PROXY,
    https_proxy: DEFAULT_HTTPS_PROXY,
    no_proxy: DEFAULT_NO_PROXY,
  };
}

export function createDefaultNetworkForm() {
  return {
    httpProxy: DEFAULT_HTTP_PROXY,
    httpsProxy: DEFAULT_HTTPS_PROXY,
    noProxy: DEFAULT_NO_PROXY,
  };
}

export function normalizeNetworkSettings(network = {}) {
  return {
    http_proxy: network.http_proxy || DEFAULT_HTTP_PROXY,
    https_proxy: network.https_proxy || DEFAULT_HTTPS_PROXY,
    no_proxy: network.no_proxy || DEFAULT_NO_PROXY,
  };
}
