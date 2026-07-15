import { normalizeBrowserResultCheck, type BrowserForm, type BrowserOperationResult, type BrowserResultCheck, type BrowserRuntimeState, type BrowserState } from "../composables/browserDefaults";
import { toPayloadSource } from "../composables/payloadBoundary";
import type { SearchForm, SearchState, SearxngOptionEntry } from "../composables/searchDefaults";

type SettingsCopyText = {
  title?: string;
  description?: string;
  placeholder?: string;
};

export type SearchSettingsCopyView = {
  loading?: string;
  title?: string;
  provider?: SettingsCopyText;
  providers?: Record<string, string>;
  freshness?: SettingsCopyText & {
    options?: Record<string, string>;
  };
  maxResults?: SettingsCopyText;
  searxngMaxPages?: SettingsCopyText;
  searxngUrl?: SettingsCopyText;
  searxngOptions?: SettingsCopyText & {
    collapse?: string;
    expand?: string;
    loadTitle?: string;
    loadDescription?: string;
    loading?: string;
    load?: string;
    emptyEngines?: string;
    emptyCategories?: string;
    configuredOnly?: string;
  };
  searxngEngines?: SettingsCopyText;
  searxngCategories?: SettingsCopyText;
  searxngProxy?: SettingsCopyText;
  currentTitle?: string;
  save?: string;
  summary?: (providerLabel: string, freshnessLabel: string, maxResults: number) => string;
};

export type SearchSettingsCopy = {
  settings: {
    search?: SearchSettingsCopyView;
  };
};

export type SearchSettingsStateLike = {
  search?: Partial<SearchState>;
  searchForm?: Partial<SearchForm>;
};

export type SearchSelectOption = {
  id: string;
  label: string;
};

export type SearchOptionEntry = SearxngOptionEntry;

type BrowserCopyFormatter<T extends unknown[]> = (...args: T) => string;

export type BrowserSettingsCopyView = {
  loading?: string;
  title?: string;
  enabled?: SettingsCopyText;
  backend?: SettingsCopyText;
  backends?: Record<string, string>;
  cdpUrl?: SettingsCopyText;
  launchArgs?: SettingsCopyText;
  commandTimeout?: SettingsCopyText;
  sessionTimeout?: SettingsCopyText;
  allowPrivateUrls?: SettingsCopyText;
  currentTitle?: string;
  disabled?: string;
  enabledSummary?: string;
  cdpEnabled?: string;
  runtimeTitle?: string;
  runtimeAvailable?: BrowserCopyFormatter<[string]>;
  runtimeMissing?: string;
  cloudConfigured?: BrowserCopyFormatter<[string]>;
  cloudMissing?: BrowserCopyFormatter<[string]>;
  cloudAttachRuntimeMissing?: BrowserCopyFormatter<[string]>;
  cloudEnabled?: BrowserCopyFormatter<[string]>;
  test?: SettingsCopyText & {
    title?: string;
    urlTitle?: string;
    currentTitle?: string;
    notRun?: string;
    run?: string;
    running?: string;
    resultPassed?: BrowserCopyFormatter<[string]>;
    resultFailed?: BrowserCopyFormatter<[string]>;
  };
  doctor?: {
    title?: string;
    currentTitle?: string;
    notRun?: string;
    run?: string;
    running?: string;
    resultPassed?: BrowserCopyFormatter<[number, number]>;
    resultFailed?: BrowserCopyFormatter<[number, number]>;
    checkPassed?: string;
    checkFailed?: string;
  };
  install?: {
    run?: string;
    running?: string;
  };
  save?: string;
};

export type BrowserSettingsCopy = {
  settings: {
    browser?: BrowserSettingsCopyView;
  };
};

export type BrowserSettingsStateLike = {
  browser?: Partial<BrowserState>;
  browserForm?: Partial<BrowserForm>;
  browserTestResult?: BrowserOperationResult | null;
  browserDoctorResult?: BrowserOperationResult | null;
  browserInstallResult?: BrowserOperationResult | null;
};

type BrowserCloudBackendPayload = {
  configured?: unknown;
};

function searchCopyFor(copy: SearchSettingsCopy): SearchSettingsCopyView {
  return copy.settings.search ?? {};
}

function browserCopyFor(copy: BrowserSettingsCopy): BrowserSettingsCopyView {
  return copy.settings.browser ?? {};
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((entry) => String(entry || "").trim()).filter(Boolean) : [];
}

export function webSearchProviderLabel(copy: SearchSettingsCopy, provider: string): string {
  return searchCopyFor(copy).providers?.[provider] || provider;
}

export function webSearchFreshnessLabel(copy: SearchSettingsCopy, freshness: string): string {
  return searchCopyFor(copy).freshness?.options?.[freshness] || freshness;
}

export function webSearchProviderOptions(copy: SearchSettingsCopy, state: SearchSettingsStateLike): SearchSelectOption[] {
  const providers = state.search?.providers;
  const values = Array.isArray(providers) && providers.length ? providers : ["duckduckgo", "searxng"];
  return values.map((id) => ({ id, label: webSearchProviderLabel(copy, id) }));
}

export function webSearchFreshnessOptions(copy: SearchSettingsCopy, state: SearchSettingsStateLike): SearchSelectOption[] {
  const freshnessOptions = state.search?.freshness_options;
  const values = Array.isArray(freshnessOptions) && freshnessOptions.length ? freshnessOptions : ["none", "day", "week", "month", "year"];
  return values.map((id) => ({ id, label: webSearchFreshnessLabel(copy, id) }));
}

export function mergeSelectedSearchOptions(options: SearxngOptionEntry[] = [], selected: string[] = []): SearchOptionEntry[] {
  const merged = new Map<string, SearchOptionEntry>();
  for (const option of Array.isArray(options) ? options : []) {
    const id = String(option?.id || "").trim();
    if (!id) {
      continue;
    }
    merged.set(id, {
      ...option,
      id,
      label: String(option.label || id).trim() || id,
      configuredOnly: false,
    });
  }
  for (const id of Array.isArray(selected) ? selected : []) {
    const value = String(id || "").trim();
    if (!value || merged.has(value)) {
      continue;
    }
    merged.set(value, { id: value, label: value, categories: [], shortcut: "", enabled: null, configuredOnly: true });
  }
  return Array.from(merged.values());
}

export function searxngEngineMeta(copy: SearchSettingsCopy, option: SearchOptionEntry): string {
  const parts: string[] = [];
  if (option.shortcut) {
    parts.push(option.shortcut);
  }
  const categories = stringList(option.categories);
  if (categories.length) {
    parts.push(categories.join(", "));
  }
  if (option.configuredOnly) {
    parts.push(searchCopyFor(copy).searxngOptions?.configuredOnly || "Configured but not listed");
  }
  return parts.join(" - ");
}

export function webSearchSummary(copy: SearchSettingsCopy, state: SearchSettingsStateLike): string {
  const form = state.searchForm || {};
  const searchCopy = searchCopyFor(copy);
  return typeof searchCopy.summary === "function"
    ? searchCopy.summary(
      webSearchProviderLabel(copy, form.provider || "searxng"),
      webSearchFreshnessLabel(copy, form.freshness || "none"),
      Number(form.maxResults || 25),
    )
    : `${form.provider || "searxng"} - ${form.freshness || "none"} - ${Number(form.maxResults || 25)}`;
}

export function browserBackendOptions(copy: BrowserSettingsCopy, state: BrowserSettingsStateLike): SearchSelectOption[] {
  const backends = state.browser?.backends;
  const values = Array.isArray(backends) && backends.length ? backends : ["agent-browser", "browserbase", "browser-use", "firecrawl"];
  return values.map((id) => ({ id, label: browserCopyFor(copy).backends?.[id] || id }));
}

export function selectedBrowserBackend(state: BrowserSettingsStateLike): string {
  return text(state.browserForm?.backend, text(state.browser?.backend, "agent-browser"));
}

export function selectedBrowserBackendLabel(copy: BrowserSettingsCopy, state: BrowserSettingsStateLike): string {
  const backend = selectedBrowserBackend(state);
  return browserCopyFor(copy).backends?.[backend] || backend;
}

export function browserRuntimeStatus(copy: BrowserSettingsCopy, state: BrowserSettingsStateLike): string {
  const browserCopy = browserCopyFor(copy);
  const runtime: Partial<BrowserRuntimeState> = state.browser?.runtime || {};
  const backend = selectedBrowserBackend(state);
  const backendLabel = selectedBrowserBackendLabel(copy, state);
  if (backend !== "agent-browser") {
    const cloud = toPayloadSource<BrowserCloudBackendPayload>(state.browser?.cloud?.[backend]) || {};
    if (!cloud.configured) {
      return typeof browserCopy.cloudMissing === "function" ? browserCopy.cloudMissing(backendLabel) : `${backendLabel} credentials are not configured.`;
    }
    if (!runtime.available) {
      return typeof browserCopy.cloudAttachRuntimeMissing === "function" ? browserCopy.cloudAttachRuntimeMissing(backendLabel) : `${backendLabel} attach runtime is missing.`;
    }
    return typeof browserCopy.cloudConfigured === "function" ? browserCopy.cloudConfigured(backendLabel) : `${backendLabel} is configured.`;
  }
  if (runtime.available) {
    const command = text(runtime.command, "agent-browser");
    return typeof browserCopy.runtimeAvailable === "function" ? browserCopy.runtimeAvailable(command) : `Available: ${command}`;
  }
  return browserCopy.runtimeMissing || "agent-browser and npx were not found.";
}

export function browserSummary(copy: BrowserSettingsCopy, state: BrowserSettingsStateLike): string {
  const browserCopy = browserCopyFor(copy);
  const form = state.browserForm || {};
  const backend = selectedBrowserBackend(state);
  const backendLabel = selectedBrowserBackendLabel(copy, state);
  if (!form.enabled) {
    return browserCopy.disabled || "Browser tools are disabled.";
  }
  if (String(form.cdpUrl || "").trim()) {
    return browserCopy.cdpEnabled || "Browser tools attach through CDP.";
  }
  if (backend !== "agent-browser") {
    return typeof browserCopy.cloudEnabled === "function" ? browserCopy.cloudEnabled(backendLabel) : `Browser tools use ${backendLabel}.`;
  }
  return browserCopy.enabledSummary || "Browser tools are enabled.";
}

export function browserTestSummary(copy: BrowserSettingsCopy, state: BrowserSettingsStateLike): string {
  const browserCopy = browserCopyFor(copy);
  const result = state.browserTestResult;
  if (!result) {
    return browserCopy.test?.notRun || "No manual browser test has run yet.";
  }
  if (result.ok) {
    const url = text(result.url);
    return typeof browserCopy.test?.resultPassed === "function" ? browserCopy.test.resultPassed(url) : `Browser test passed: ${url}`;
  }
  const error = text(result.error, text(result.open?.error, text(result.snapshot?.error)));
  return typeof browserCopy.test?.resultFailed === "function" ? browserCopy.test.resultFailed(error) : `Browser test failed${error ? `: ${error}` : "."}`;
}

export function browserDoctorChecks(value: BrowserOperationResult | null | undefined): BrowserResultCheck[] {
  const checks = value?.checks;
  return Array.isArray(checks)
    ? checks.map(normalizeBrowserResultCheck).filter((check) => Object.keys(check).length > 0)
    : [];
}

export function browserDoctorSummary(copy: BrowserSettingsCopy, state: BrowserSettingsStateLike): string {
  const browserCopy = browserCopyFor(copy);
  const result = state.browserDoctorResult;
  if (!result) {
    return browserCopy.doctor?.notRun || "Install has not been checked yet.";
  }
  const checks = browserDoctorChecks(result);
  const passed = checks.filter((check) => check.ok).length;
  if (result.ok) {
    return typeof browserCopy.doctor?.resultPassed === "function" ? browserCopy.doctor.resultPassed(passed, checks.length) : `Install check passed: ${passed}/${checks.length}`;
  }
  return typeof browserCopy.doctor?.resultFailed === "function" ? browserCopy.doctor.resultFailed(passed, checks.length) : `Install check failed: ${passed}/${checks.length}`;
}

export function browserDoctorCheckSummary(copy: BrowserSettingsCopy, check: BrowserResultCheck): string {
  const browserCopy = browserCopyFor(copy);
  const status = check?.ok ? browserCopy.doctor?.checkPassed || "Passed" : browserCopy.doctor?.checkFailed || "Failed";
  const detail = text(check?.suggestion, text(check?.stderr, text(check?.stdout))).trim();
  return detail ? `${status}: ${detail}` : status;
}
