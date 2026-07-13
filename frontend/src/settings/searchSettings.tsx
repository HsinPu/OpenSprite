import { useState } from "react";
import { SaveOutlined } from "@ant-design/icons";
import { Button, Input, InputNumber, Select } from "antd";
import type { SearchForm, SearchState } from "../composables/searchDefaults";
import {
  mergeSelectedSearchOptions,
  searxngEngineMeta,
  type SearchOptionEntry,
  type SearchSettingsCopy,
  type SearchSettingsCopyView,
  type SearchSettingsStateLike,
  webSearchCredentialStatus,
  webSearchFreshnessOptions,
  webSearchProviderOptions,
  webSearchSummary,
} from "./searchBrowserHelpers";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type ValueRef<T> = { value: T };

type SearchSettingsStateView = SearchSettingsStateLike & {
  searchLoading: boolean;
  searchOptionsLoading: boolean;
  searchError: string;
  searchOptionsError: string;
  searchNotice: string;
  searchOptionsNotice: string;
  search: SearchState;
  searchForm: SearchForm;
};

type SearchSettingsClient = {
  copy: ValueRef<SearchSettingsCopy>;
  settingsState: SearchSettingsStateView;
  loadSearxngOptions: () => void;
  saveSearchSettings: () => void;
};

export function SearchSettings({ client }: { client: SearchSettingsClient }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const [searxngOptionsExpanded, setSearxngOptionsExpanded] = useState(false);
  const searchCopy: SearchSettingsCopyView = copy.settings.search ?? {};
  const form = state.searchForm;
  const providerOptions = webSearchProviderOptions(copy, state);
  const freshnessOptions = webSearchFreshnessOptions(copy, state);
  const engineOptions = mergeSelectedSearchOptions(state.search.searxng_options.engines, form.searxngEngines);
  const categoryOptions = mergeSelectedSearchOptions(state.search.searxng_options.categories, form.searxngCategories);
  const summary = webSearchSummary(copy, state);

  return (
    <section className="settings-page">
      <SettingsStatus message={state.searchLoading ? searchCopy.loading || "Loading search settings..." : ""} />
      <SettingsStatus message={state.searchNotice} />
      <SettingsStatus message={state.searchError} type="error" />

      <SettingsSectionTitle>{searchCopy.title || "Web search"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={searchCopy.provider?.title || "Provider"} description={searchCopy.provider?.description || ""} className="settings-row--field">
          <Select value={form.provider} disabled={state.searchLoading} options={providerOptions.map((provider) => ({ value: provider.id, label: provider.label }))} onChange={(value) => (form.provider = value)} />
        </SettingsRow>
        <SettingsRow title={searchCopy.freshness?.title || "Freshness"} description={searchCopy.freshness?.description || ""} className="settings-row--field">
          <Select value={form.freshness} disabled={state.searchLoading} options={freshnessOptions.map((freshness) => ({ value: freshness.id, label: freshness.label }))} onChange={(value) => (form.freshness = value)} />
        </SettingsRow>
        <SettingsRow title={searchCopy.maxResults?.title || "Max results"} description={searchCopy.maxResults?.description || ""} className="settings-row--field">
          <InputNumber className="settings-control" value={Number(form.maxResults || 25)} min={1} max={100} disabled={state.searchLoading} onChange={(value) => (form.maxResults = Number(value || 25))} />
        </SettingsRow>
        <SettingsRow title={searchCopy.duckduckgoMaxPages?.title || "DuckDuckGo max pages"} description={searchCopy.duckduckgoMaxPages?.description || ""} className="settings-row--field">
          <InputNumber className="settings-control" value={Number(form.duckduckgoMaxPages || 10)} min={1} max={50} disabled={state.searchLoading} onChange={(value) => (form.duckduckgoMaxPages = Number(value || 10))} />
        </SettingsRow>
        <SettingsRow title={searchCopy.searxngMaxPages?.title || "SearXNG max pages"} description={searchCopy.searxngMaxPages?.description || ""} className="settings-row--field">
          <InputNumber className="settings-control" value={Number(form.searxngMaxPages || 5)} min={1} max={50} disabled={state.searchLoading} onChange={(value) => (form.searxngMaxPages = Number(value || 5))} />
        </SettingsRow>
        <SettingsRow title={searchCopy.searxngUrl?.title || "SearXNG URL"} description={searchCopy.searxngUrl?.description || ""} className="settings-row--field">
          <Input value={form.searxngUrl} placeholder={searchCopy.searxngUrl?.placeholder || "https://searx.be"} disabled={state.searchLoading} onChange={(event) => (form.searxngUrl = event.target.value)} />
        </SettingsRow>

        <SettingsRow title={searchCopy.searxngOptions?.title || "SearXNG options"} description={searchCopy.searxngOptions?.description || ""}>
          <Button
            aria-expanded={searxngOptionsExpanded}
            onClick={() => {
              const next = !searxngOptionsExpanded;
              setSearxngOptionsExpanded(next);
              const hasOptions = Boolean(state.search?.searxng_options?.engines?.length || state.search?.searxng_options?.categories?.length);
              if (next && !hasOptions && !state.searchOptionsLoading) {
                client.loadSearxngOptions();
              }
            }}
          >
            {searxngOptionsExpanded ? searchCopy.searxngOptions?.collapse || "Collapse" : searchCopy.searxngOptions?.expand || "Expand"}
          </Button>
        </SettingsRow>

        {searxngOptionsExpanded ? (
          <div className="settings-collapsible-section">
            <div className="settings-row">
              <div>
                <strong>{searchCopy.searxngOptions?.loadTitle || "Load available options"}</strong>
                <span>{searchCopy.searxngOptions?.loadDescription || ""}</span>
                {state.searchOptionsNotice ? <span>{state.searchOptionsNotice}</span> : null}
                {state.searchOptionsError ? <span className="settings-row__error">{state.searchOptionsError}</span> : null}
              </div>
              <Button loading={state.searchOptionsLoading} disabled={state.searchLoading || state.searchOptionsLoading} onClick={client.loadSearxngOptions}>
                {state.searchOptionsLoading ? searchCopy.searxngOptions?.loading || "Loading..." : searchCopy.searxngOptions?.load || "Load options"}
              </Button>
            </div>
            <SettingsRow title={searchCopy.searxngEngines?.title || "SearXNG engines"} description={searchCopy.searxngEngines?.description || ""} className="settings-row--field settings-row--choice-list">
              {engineOptions.length ? (
                <Select
                  mode="multiple"
                  className="settings-control"
                  value={form.searxngEngines || []}
                  disabled={state.searchLoading}
                  options={engineOptions.map((option: SearchOptionEntry) => ({ value: option.id, label: `${option.label}${searxngEngineMeta(copy, option) ? ` - ${searxngEngineMeta(copy, option)}` : ""}` }))}
                  onChange={(values) => (form.searxngEngines = values)}
                />
              ) : <p className="settings-empty-inline">{searchCopy.searxngOptions?.emptyEngines || "No engines loaded."}</p>}
            </SettingsRow>
            <SettingsRow title={searchCopy.searxngCategories?.title || "SearXNG categories"} description={searchCopy.searxngCategories?.description || ""} className="settings-row--field settings-row--choice-list">
              {categoryOptions.length ? (
                <Select
                  mode="multiple"
                  className="settings-control"
                  value={form.searxngCategories || []}
                  disabled={state.searchLoading}
                  options={categoryOptions.map((option: SearchOptionEntry) => ({ value: option.id, label: `${option.label}${option.configuredOnly ? ` - ${searchCopy.searxngOptions?.configuredOnly || "Configured but not listed"}` : ""}` }))}
                  onChange={(values) => (form.searxngCategories = values)}
                />
              ) : <p className="settings-empty-inline">{searchCopy.searxngOptions?.emptyCategories || "No categories loaded."}</p>}
            </SettingsRow>
          </div>
        ) : null}

        <SettingsRow title={searchCopy.proxy?.title || "Search proxy"} description={searchCopy.proxy?.description || ""} className="settings-row--field">
          <Input value={form.proxy} placeholder={searchCopy.proxy?.placeholder || "http://proxy-host:port"} disabled={state.searchLoading} onChange={(event) => (form.proxy = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={searchCopy.currentTitle || "Current setting"} description={summary}>
          <Button icon={<SaveOutlined />} loading={state.searchLoading} disabled={state.searchLoading} onClick={client.saveSearchSettings}>
            {searchCopy.save || "Save search settings"}
          </Button>
        </SettingsRow>
      </SettingsCard>

      <SettingsSectionTitle>{searchCopy.credentialsTitle || "Provider API keys"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow
          title={searchCopy.credentials?.jina?.title || "Jina API key"}
          description={typeof searchCopy.credentials?.description === "function"
            ? searchCopy.credentials.description(webSearchCredentialStatus(copy, state, "jina"))
            : webSearchCredentialStatus(copy, state, "jina")}
          className="settings-row--field"
        >
          <Input.Password value={form.jinaApiKey} autoComplete="new-password" placeholder={searchCopy.credentials?.placeholder || "Leave blank to keep existing key"} disabled={state.searchLoading} onChange={(event) => (form.jinaApiKey = event.target.value)} />
        </SettingsRow>
      </SettingsCard>
    </section>
  );
}
