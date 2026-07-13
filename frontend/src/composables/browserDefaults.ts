import { toPayloadSource } from "./payloadBoundary";

export const DEFAULT_BROWSER_BACKEND = "agent-browser";
export const DEFAULT_BROWSER_BACKENDS = ["agent-browser", "browserbase", "browser-use", "firecrawl"];
export const DEFAULT_BROWSER_COMMAND_TIMEOUT = 30;
export const DEFAULT_BROWSER_SESSION_TIMEOUT = 1800;
export const DEFAULT_BROWSER_LAUNCH_ARGS = "--no-sandbox";
export const DEFAULT_BROWSER_TEST_URL = "https://quotes.toscrape.com/js/";

export type BrowserCloudSettings = {
  [key: string]: unknown;
};

export interface BrowserRuntimeState {
  available: boolean;
  command: string;
  install_hint: string;
}

const DEFAULT_BROWSER_RUNTIME: BrowserRuntimeState = {
  available: false,
  command: "",
  install_hint: "",
};

export interface BrowserState {
  enabled: boolean;
  backend: string;
  backends: string[];
  command_timeout: number;
  session_timeout: number;
  cdp_url: string;
  launch_args: string;
  allow_private_urls: boolean;
  cloud: BrowserCloudSettings;
  runtime: BrowserRuntimeState;
}

export interface BrowserForm {
  enabled: boolean;
  backend: string;
  commandTimeout: number;
  sessionTimeout: number;
  cdpUrl: string;
  launchArgs: string;
  allowPrivateUrls: boolean;
  testUrl: string;
}

export interface BrowserResultCheck {
  ok?: boolean;
  name?: string;
  command?: string;
  suggestion?: string;
  error?: string;
  stdout?: string;
  stderr?: string;
}

export interface BrowserOperationResult {
  ok?: boolean;
  url?: string;
  error?: string;
  suggestion?: string;
  already_installed?: boolean;
  browser?: BrowserState;
  runtime?: BrowserRuntimeState;
  open?: BrowserResultCheck;
  snapshot?: BrowserResultCheck;
  after?: BrowserResultCheck;
  install?: BrowserResultCheck;
  checks?: BrowserResultCheck[];
}

export function createDefaultBrowserState(): BrowserState {
  return {
    enabled: false,
    backend: DEFAULT_BROWSER_BACKEND,
    backends: DEFAULT_BROWSER_BACKENDS,
    command_timeout: DEFAULT_BROWSER_COMMAND_TIMEOUT,
    session_timeout: DEFAULT_BROWSER_SESSION_TIMEOUT,
    cdp_url: "",
    launch_args: DEFAULT_BROWSER_LAUNCH_ARGS,
    allow_private_urls: false,
    cloud: {},
    runtime: { ...DEFAULT_BROWSER_RUNTIME },
  };
}

export function createDefaultBrowserForm(): BrowserForm {
  return {
    enabled: false,
    backend: DEFAULT_BROWSER_BACKEND,
    commandTimeout: DEFAULT_BROWSER_COMMAND_TIMEOUT,
    sessionTimeout: DEFAULT_BROWSER_SESSION_TIMEOUT,
    cdpUrl: "",
    launchArgs: DEFAULT_BROWSER_LAUNCH_ARGS,
    allowPrivateUrls: false,
    testUrl: DEFAULT_BROWSER_TEST_URL,
  };
}

function toBrowserCloudSettings(value: unknown): BrowserCloudSettings {
  return toPayloadSource<BrowserCloudSettings>(value) || {};
}

function optionalText(value: unknown): string | undefined {
  const text = String(value || "").trim();
  return text || undefined;
}

function optionalBoolean(value: unknown): boolean | undefined {
  return value === undefined ? undefined : Boolean(value);
}

function definedResultCheck(value: unknown): BrowserResultCheck | undefined {
  const check = normalizeBrowserResultCheck(value);
  return Object.keys(check).length > 0 ? check : undefined;
}

export function normalizeBrowserResultCheck(value: unknown): BrowserResultCheck {
  const payload = toPayloadSource<BrowserResultCheck>(value) || {};
  const check: BrowserResultCheck = {};
  const ok = optionalBoolean(payload.ok);
  if (ok !== undefined) check.ok = ok;
  const name = optionalText(payload.name);
  if (name !== undefined) check.name = name;
  const command = optionalText(payload.command);
  if (command !== undefined) check.command = command;
  const suggestion = optionalText(payload.suggestion);
  if (suggestion !== undefined) check.suggestion = suggestion;
  const error = optionalText(payload.error);
  if (error !== undefined) check.error = error;
  const stdout = optionalText(payload.stdout);
  if (stdout !== undefined) check.stdout = stdout;
  const stderr = optionalText(payload.stderr);
  if (stderr !== undefined) check.stderr = stderr;
  return check;
}

export function normalizeBrowserOperationResult(value: unknown): BrowserOperationResult {
  const payload = toPayloadSource<BrowserOperationResult>(value) || {};
  const result: BrowserOperationResult = {};
  const ok = optionalBoolean(payload.ok);
  if (ok !== undefined) result.ok = ok;
  const url = optionalText(payload.url);
  if (url !== undefined) result.url = url;
  const error = optionalText(payload.error);
  if (error !== undefined) result.error = error;
  const suggestion = optionalText(payload.suggestion);
  if (suggestion !== undefined) result.suggestion = suggestion;
  const alreadyInstalled = optionalBoolean(payload.already_installed);
  if (alreadyInstalled !== undefined) result.already_installed = alreadyInstalled;
  if (payload.browser !== undefined) result.browser = normalizeBrowserSettings(payload.browser);
  const runtime = normalizeOptionalBrowserRuntime(payload.runtime);
  if (runtime !== undefined) result.runtime = runtime;
  const open = definedResultCheck(payload.open);
  if (open !== undefined) result.open = open;
  const snapshot = definedResultCheck(payload.snapshot);
  if (snapshot !== undefined) result.snapshot = snapshot;
  const after = definedResultCheck(payload.after);
  if (after !== undefined) result.after = after;
  const install = definedResultCheck(payload.install);
  if (install !== undefined) result.install = install;
  if (Array.isArray(payload.checks)) {
    const checks = payload.checks.map(normalizeBrowserResultCheck).filter((check) => Object.keys(check).length > 0);
    if (checks.length) result.checks = checks;
  }
  return result;
}

function normalizeTextList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function normalizeBrowserRuntime(value: unknown, fallback: BrowserRuntimeState): BrowserRuntimeState {
  const payload = toPayloadSource<BrowserRuntimeState>(value) || {};
  if (!Object.keys(payload).length) {
    return fallback;
  }
  return {
    available: payload.available === true,
    command: String(payload.command || ""),
    install_hint: String(payload.install_hint ?? ""),
  };
}

function normalizeOptionalBrowserRuntime(value: unknown): BrowserRuntimeState | undefined {
  const payload = toPayloadSource<BrowserRuntimeState>(value) || {};
  return Object.keys(payload).length ? normalizeBrowserRuntime(payload, DEFAULT_BROWSER_RUNTIME) : undefined;
}

export function normalizeBrowserSettings(browser: unknown = {}): BrowserState {
  const payload = toPayloadSource<BrowserState>(browser) || {};
  const backends = normalizeTextList(payload.backends);
  const defaultState = createDefaultBrowserState();
  return {
    ...defaultState,
    enabled: payload.enabled === true,
    backend: String(payload.backend || DEFAULT_BROWSER_BACKEND),
    backends: backends.length ? backends : DEFAULT_BROWSER_BACKENDS,
    command_timeout: Number(payload.command_timeout || DEFAULT_BROWSER_COMMAND_TIMEOUT),
    session_timeout: Number(payload.session_timeout || DEFAULT_BROWSER_SESSION_TIMEOUT),
    cdp_url: String(payload.cdp_url || ""),
    launch_args: String(payload.launch_args || DEFAULT_BROWSER_LAUNCH_ARGS),
    allow_private_urls: payload.allow_private_urls === true,
    cloud: toBrowserCloudSettings(payload.cloud),
    runtime: normalizeBrowserRuntime(payload.runtime, defaultState.runtime),
  };
}
