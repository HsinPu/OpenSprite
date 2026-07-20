import {
  DEFAULT_FRESHNESS_OPTIONS,
  DEFAULT_SEARCH_FRESHNESS,
  DEFAULT_SEARCH_MAX_RESULTS,
  DEFAULT_SEARCH_PROVIDER,
  DEFAULT_SEARCH_PROVIDERS,
  DEFAULT_SEARXNG_URL,
  DEFAULT_SEARXNG_MAX_PAGES,
  normalizeSearxngTargetUrl,
  searxngOptionsMatchTarget,
  type SearchForm,
  type SearchState,
  type SearxngOptionEntry,
  type SearxngOptions,
} from "./searchDefaults";
import { toPayloadSource } from "./payloadBoundary";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type SearchSettingsPayload = {
  web_search?: unknown;
};
type SearchDataPayload = {
  provider?: unknown;
  providers?: unknown;
  freshness?: unknown;
  freshness_options?: unknown;
  max_results?: unknown;
  searxng_max_pages?: unknown;
  searxng_url?: unknown;
  searxng_engines?: unknown;
  searxng_categories?: unknown;
  searxng_options?: unknown;
  searxng_proxy?: unknown;
};
type SearxngOptionsPayload = {
  searxng?: unknown;
};
type SearxngOptionsDataPayload = {
  engines?: unknown;
  categories?: unknown;
  url?: unknown;
  proxy?: unknown;
};
type SearxngOptionPayload = {
  id?: unknown;
  name?: unknown;
  label?: unknown;
  display_name?: unknown;
  displayName?: unknown;
  categories?: unknown;
  shortcut?: unknown;
  enabled?: unknown;
};

interface SearchSettingsState {
  searchLoading: boolean;
  searchOptionsLoading: boolean;
  searchError: string;
  searchOptionsError: string;
  searchNotice: string;
  searchOptionsNotice: string;
  search: SearchState;
  searchForm: SearchForm;
}

interface SearchSettingsCopy {
  notices: {
    searchLoadFailed: string;
    searxngOptionsLoaded: string;
    searxngOptionsLoadFailed: string;
    searchSaved: string;
    searchSaveFailed: string;
  };
}

type SettingsActionContext = {
  settingsState: SearchSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: SearchSettingsCopy };
  setSettingsSuccess: (key: string, message: string) => void;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function toSearchSettingsPayload(value: unknown): SearchSettingsPayload {
  const payload = toPayloadSource<SearchSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    web_search: payload.web_search,
  };
}

function toSearchDataPayload(value: unknown): SearchDataPayload | null {
  const payload = toPayloadSource<SearchDataPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    provider: payload.provider,
    providers: payload.providers,
    freshness: payload.freshness,
    freshness_options: payload.freshness_options,
    max_results: payload.max_results,
    searxng_max_pages: payload.searxng_max_pages,
    searxng_url: payload.searxng_url,
    searxng_engines: payload.searxng_engines,
    searxng_categories: payload.searxng_categories,
    searxng_options: payload.searxng_options,
    searxng_proxy: payload.searxng_proxy,
  };
}

function toSearxngOptionsPayload(value: unknown): SearxngOptionsPayload {
  const payload = toPayloadSource<SearxngOptionsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    searxng: payload.searxng,
  };
}

function toSearxngOptionsDataPayload(value: unknown): SearxngOptionsDataPayload | null {
  const payload = toPayloadSource<SearxngOptionsDataPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    engines: payload.engines,
    categories: payload.categories,
    url: payload.url,
    proxy: payload.proxy,
  };
}

function toSearxngOptionPayload(value: unknown): SearxngOptionPayload | null {
  const payload = toPayloadSource<SearxngOptionPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    id: payload.id,
    name: payload.name,
    label: payload.label,
    display_name: payload.display_name,
    displayName: payload.displayName,
    categories: payload.categories,
    shortcut: payload.shortcut,
    enabled: payload.enabled,
  };
}

function normalizeTextList(value: unknown): string[] {
  const values = Array.isArray(value) ? value : String(value || "").split(/[\n,]+/);
  return values.map((item) => String(item || "").trim()).filter(Boolean);
}

function normalizeOptionEntries(value: unknown): SearxngOptionEntry[] {
  if (!Array.isArray(value)) return [];
  return value.map((item): SearxngOptionEntry | null => {
    if (typeof item === "string") {
      const id = item.trim();
      return id ? { id, label: id, categories: [], shortcut: "", enabled: null } : null;
    }
    const option = toSearxngOptionPayload(item);
    if (!option) return null;
    const id = String(option.id || option.name || "").trim();
    if (!id) return null;
    return {
      id,
      label: String(option.label || option.display_name || option.displayName || id).trim() || id,
      categories: normalizeTextList(option.categories || []),
      shortcut: String(option.shortcut || "").trim(),
      enabled: typeof option.enabled === "boolean" ? option.enabled : null,
    };
  }).filter((item): item is SearxngOptionEntry => item !== null);
}

function normalizeSearxngOptions(value: unknown = {}): SearxngOptions {
  const payload = toSearxngOptionsDataPayload(value) || {};
  return {
    engines: normalizeOptionEntries(payload.engines),
    categories: normalizeOptionEntries(payload.categories),
    url: String(payload.url || "").trim(),
    proxy: String(payload.proxy || "").trim(),
  };
}

function normalizeSearchSettings(search: unknown = {}): SearchState {
  const payload = toSearchDataPayload(search) || {};
  const providers = normalizeTextList(payload.providers);
  const freshnessOptions = normalizeTextList(payload.freshness_options);
  return {
    provider: String(payload.provider || DEFAULT_SEARCH_PROVIDER),
    providers: providers.length ? providers : DEFAULT_SEARCH_PROVIDERS,
    freshness: String(payload.freshness || DEFAULT_SEARCH_FRESHNESS),
    freshness_options: freshnessOptions.length ? freshnessOptions : DEFAULT_FRESHNESS_OPTIONS,
    max_results: Number(payload.max_results || DEFAULT_SEARCH_MAX_RESULTS),
    searxng_max_pages: Number(payload.searxng_max_pages || DEFAULT_SEARXNG_MAX_PAGES),
    searxng_url: String(payload.searxng_url || DEFAULT_SEARXNG_URL),
    searxng_engines: normalizeTextList(payload.searxng_engines),
    searxng_categories: normalizeTextList(payload.searxng_categories),
    searxng_options: normalizeSearxngOptions(payload.searxng_options),
    searxng_proxy: String(payload.searxng_proxy || ""),
  };
}

function normalizeSearchSettingsPreservingMatchingOptions(
  search: unknown,
  currentOptions: SearxngOptions,
): SearchState {
  const payload = toSearchDataPayload(search);
  const normalized = normalizeSearchSettings(payload || {});
  if (
    payload?.searxng_options === undefined
    && searxngOptionsMatchTarget(currentOptions, normalized.searxng_url, normalized.searxng_proxy)
  ) {
    normalized.searxng_options = currentOptions;
  }
  return normalized;
}

function syncSearchForm(settingsState: SearchSettingsState): void {
  settingsState.searchForm.provider = settingsState.search.provider;
  settingsState.searchForm.freshness = settingsState.search.freshness;
  settingsState.searchForm.maxResults = settingsState.search.max_results;
  settingsState.searchForm.searxngMaxPages = settingsState.search.searxng_max_pages;
  settingsState.searchForm.searxngUrl = settingsState.search.searxng_url;
  settingsState.searchForm.searxngEngines = normalizeTextList(settingsState.search.searxng_engines);
  settingsState.searchForm.searxngCategories = normalizeTextList(settingsState.search.searxng_categories);
  settingsState.searchForm.searxngProxy = settingsState.search.searxng_proxy;
}

function currentSearxngTarget(settingsState: SearchSettingsState): { url: string; proxy: string } {
  return {
    url: normalizeSearxngTargetUrl(settingsState.searchForm.searxngUrl),
    proxy: String(settingsState.searchForm.searxngProxy || "").trim(),
  };
}

export function useSearchSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }: SettingsActionContext) {
  let searchSettingsRequestGeneration = 0;
  let searchSettingsSaveInFlight = false;
  let searxngOptionsRequestGeneration = 0;

  function invalidateSearxngOptionsRequest(): void {
    searxngOptionsRequestGeneration += 1;
    settingsState.searchOptionsLoading = false;
  }

  async function loadSearchSettings(): Promise<void> {
    if (searchSettingsSaveInFlight) return;
    const requestGeneration = ++searchSettingsRequestGeneration;
    invalidateSearxngOptionsRequest();
    settingsState.searchLoading = true;
    settingsState.searchError = "";
    settingsState.searchNotice = "";
    settingsState.searchOptionsError = "";
    settingsState.searchOptionsNotice = "";
    try {
      const payload = toSearchSettingsPayload(await requestSettingsJson("/api/settings/web-search"));
      if (requestGeneration !== searchSettingsRequestGeneration) return;
      settingsState.search = normalizeSearchSettingsPreservingMatchingOptions(
        payload.web_search,
        settingsState.search.searxng_options,
      );
      syncSearchForm(settingsState);
    } catch (error: unknown) {
      if (requestGeneration === searchSettingsRequestGeneration) {
        settingsState.searchError = errorMessage(error) || copy.value.notices.searchLoadFailed;
      }
    } finally {
      if (requestGeneration === searchSettingsRequestGeneration) {
        settingsState.searchLoading = false;
      }
    }
  }

  async function loadSearxngOptions(): Promise<void> {
    const requestGeneration = ++searxngOptionsRequestGeneration;
    const { url: searxngUrl, proxy: searxngProxy } = currentSearxngTarget(settingsState);
    settingsState.searchOptionsLoading = true;
    settingsState.searchOptionsError = "";
    settingsState.searchOptionsNotice = "";
    try {
      const payload = toSearxngOptionsPayload(await requestSettingsJson("/api/settings/web-search/searxng-options", {
        method: "POST",
        body: JSON.stringify({ url: searxngUrl, proxy: searxngProxy }),
      }));
      const currentTarget = currentSearxngTarget(settingsState);
      if (
        requestGeneration !== searxngOptionsRequestGeneration
        || currentTarget.url !== searxngUrl
        || currentTarget.proxy !== searxngProxy
      ) {
        return;
      }
      settingsState.search.searxng_options = {
        ...normalizeSearxngOptions(payload.searxng),
        url: searxngUrl,
        proxy: searxngProxy,
      };
      settingsState.searchOptionsNotice = copy.value.notices.searxngOptionsLoaded;
    } catch (error: unknown) {
      const currentTarget = currentSearxngTarget(settingsState);
      if (
        requestGeneration === searxngOptionsRequestGeneration
        && currentTarget.url === searxngUrl
        && currentTarget.proxy === searxngProxy
      ) {
        settingsState.searchOptionsError = errorMessage(error) || copy.value.notices.searxngOptionsLoadFailed;
      }
    } finally {
      if (requestGeneration === searxngOptionsRequestGeneration) {
        settingsState.searchOptionsLoading = false;
      }
    }
  }

  async function saveSearchSettings(): Promise<void> {
    if (searchSettingsSaveInFlight) return;
    searchSettingsSaveInFlight = true;
    const requestGeneration = ++searchSettingsRequestGeneration;
    invalidateSearxngOptionsRequest();
    settingsState.searchLoading = true;
    settingsState.searchError = "";
    settingsState.searchNotice = "";
    try {
      const form = settingsState.searchForm;
      const payload = toSearchSettingsPayload(await requestSettingsJson("/api/settings/web-search", {
        method: "PUT",
        body: JSON.stringify({
          provider: form.provider,
          freshness: form.freshness,
          max_results: form.maxResults,
          searxng_max_pages: form.searxngMaxPages,
          searxng_url: form.searxngUrl,
          searxng_engines: normalizeTextList(form.searxngEngines),
          searxng_categories: normalizeTextList(form.searxngCategories),
          searxng_proxy: form.searxngProxy,
        }),
      }));
      if (requestGeneration !== searchSettingsRequestGeneration) return;
      settingsState.search = normalizeSearchSettingsPreservingMatchingOptions(
        payload.web_search,
        settingsState.search.searxng_options,
      );
      syncSearchForm(settingsState);
      setSettingsSuccess("searchNotice", copy.value.notices.searchSaved);
    } catch (error: unknown) {
      if (requestGeneration === searchSettingsRequestGeneration) {
        settingsState.searchError = errorMessage(error) || copy.value.notices.searchSaveFailed;
      }
    } finally {
      searchSettingsSaveInFlight = false;
      if (requestGeneration === searchSettingsRequestGeneration) {
        settingsState.searchLoading = false;
      }
    }
  }

  return {
    loadSearchSettings,
    loadSearxngOptions,
    saveSearchSettings,
  };
}
