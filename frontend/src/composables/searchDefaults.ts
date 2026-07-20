export const DEFAULT_SEARCH_PROVIDER = "duckduckgo";
export const DEFAULT_SEARCH_PROVIDERS = ["duckduckgo", "searxng"];
export const DEFAULT_SEARCH_FRESHNESS = "none";
export const DEFAULT_FRESHNESS_OPTIONS = ["none", "day", "week", "month", "year"];
export const DEFAULT_SEARXNG_URL = "https://searx.be";
export const DEFAULT_SEARCH_MAX_RESULTS = 25;
export const DEFAULT_SEARXNG_MAX_PAGES = 5;

export interface SearxngOptionEntry {
  id: string;
  label: string;
  categories: string[];
  shortcut: string;
  enabled: boolean | null;
  configuredOnly?: boolean;
}

export interface SearxngOptions {
  engines: SearxngOptionEntry[];
  categories: SearxngOptionEntry[];
  url: string;
  proxy: string;
}

export interface SearchState {
  provider: string;
  providers: string[];
  freshness: string;
  freshness_options: string[];
  max_results: number;
  searxng_max_pages: number;
  searxng_url: string;
  searxng_engines: string[];
  searxng_categories: string[];
  searxng_options: SearxngOptions;
  searxng_proxy: string;
}

export interface SearchForm {
  provider: string;
  freshness: string;
  maxResults: number;
  searxngMaxPages: number;
  searxngUrl: string;
  searxngEngines: string[];
  searxngCategories: string[];
  searxngProxy: string;
}

export function createDefaultSearchState(): SearchState {
  return {
    provider: DEFAULT_SEARCH_PROVIDER,
    providers: [...DEFAULT_SEARCH_PROVIDERS],
    freshness: DEFAULT_SEARCH_FRESHNESS,
    freshness_options: [...DEFAULT_FRESHNESS_OPTIONS],
    max_results: DEFAULT_SEARCH_MAX_RESULTS,
    searxng_max_pages: DEFAULT_SEARXNG_MAX_PAGES,
    searxng_url: DEFAULT_SEARXNG_URL,
    searxng_engines: [],
    searxng_categories: [],
    searxng_options: {
      engines: [],
      categories: [],
      url: "",
      proxy: "",
    },
    searxng_proxy: "",
  };
}

export function normalizeSearxngTargetUrl(url: unknown): string {
  return String(url || "").trim() || DEFAULT_SEARXNG_URL;
}

export function searxngOptionsMatchTarget(
  options: SearxngOptions,
  url: unknown,
  proxy: unknown,
): boolean {
  return options.url === normalizeSearxngTargetUrl(url)
    && options.proxy === String(proxy || "").trim();
}

export function createDefaultSearchForm(): SearchForm {
  return {
    provider: DEFAULT_SEARCH_PROVIDER,
    freshness: DEFAULT_SEARCH_FRESHNESS,
    maxResults: DEFAULT_SEARCH_MAX_RESULTS,
    searxngMaxPages: DEFAULT_SEARXNG_MAX_PAGES,
    searxngUrl: DEFAULT_SEARXNG_URL,
    searxngEngines: [],
    searxngCategories: [],
    searxngProxy: "",
  };
}
