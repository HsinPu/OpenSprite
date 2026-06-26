type AnyRecord = Record<string, any>;

export function webSearchProviderLabel(copy: AnyRecord, provider: string) {
  return copy.settings.search?.providers?.[provider] || provider;
}

export function webSearchFreshnessLabel(copy: AnyRecord, freshness: string) {
  return copy.settings.search?.freshness?.options?.[freshness] || freshness;
}

export function webSearchProviderOptions(copy: AnyRecord, state: AnyRecord) {
  const providers = state.search?.providers;
  const values = Array.isArray(providers) && providers.length ? providers : ["duckduckgo", "searxng", "jina"];
  return values.map((id: string) => ({ id, label: webSearchProviderLabel(copy, id) }));
}

export function webSearchFreshnessOptions(copy: AnyRecord, state: AnyRecord) {
  const freshnessOptions = state.search?.freshness_options;
  const values = Array.isArray(freshnessOptions) && freshnessOptions.length ? freshnessOptions : ["auto", "none", "day", "week", "month", "year"];
  return values.map((id: string) => ({ id, label: webSearchFreshnessLabel(copy, id) }));
}

export function mergeSelectedSearchOptions(options: AnyRecord[] = [], selected: string[] = []) {
  const merged = new Map<string, AnyRecord>();
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
    merged.set(value, { id: value, label: value, categories: [], shortcut: "", configuredOnly: true });
  }
  return Array.from(merged.values());
}

export function searxngEngineMeta(copy: AnyRecord, option: AnyRecord) {
  const parts = [];
  if (option.shortcut) {
    parts.push(option.shortcut);
  }
  if (Array.isArray(option.categories) && option.categories.length) {
    parts.push(option.categories.join(", "));
  }
  if (option.configuredOnly) {
    parts.push(copy.settings.search?.searxngOptions?.configuredOnly || "Configured but not listed");
  }
  return parts.join(" - ");
}

export function webSearchCredentialStatus(copy: AnyRecord, state: AnyRecord, provider: string) {
  const configured = state.search?.[`${provider}_api_key_configured`] === true;
  return configured ? copy.settings.search?.credentials?.configured || "Configured" : copy.settings.search?.credentials?.notConfigured || "Not configured";
}

export function webSearchSummary(copy: AnyRecord, state: AnyRecord) {
  const form = state.searchForm || {};
  return typeof copy.settings.search?.summary === "function"
    ? copy.settings.search.summary(
      webSearchProviderLabel(copy, form.provider || "searxng"),
      webSearchFreshnessLabel(copy, form.freshness || "auto"),
      Number(form.maxResults || 25),
    )
    : `${form.provider || "searxng"} - ${form.freshness || "auto"} - ${Number(form.maxResults || 25)}`;
}

export function browserBackendOptions(copy: AnyRecord, state: AnyRecord) {
  const backends = state.browser?.backends;
  const values = Array.isArray(backends) && backends.length ? backends : ["agent-browser", "browserbase", "browser-use", "firecrawl"];
  return values.map((id: string) => ({ id, label: copy.settings.browser?.backends?.[id] || id }));
}

export function selectedBrowserBackend(state: AnyRecord) {
  return state.browserForm?.backend || state.browser?.backend || "agent-browser";
}

export function selectedBrowserBackendLabel(copy: AnyRecord, state: AnyRecord) {
  const backend = selectedBrowserBackend(state);
  return copy.settings.browser?.backends?.[backend] || backend;
}

export function browserRuntimeStatus(copy: AnyRecord, state: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const runtime = state.browser?.runtime || {};
  const backend = selectedBrowserBackend(state);
  const backendLabel = selectedBrowserBackendLabel(copy, state);
  if (backend !== "agent-browser") {
    const cloud = state.browser?.cloud?.[backend] || {};
    if (!cloud.configured) {
      return typeof browserCopy.cloudMissing === "function" ? browserCopy.cloudMissing(backendLabel) : `${backendLabel} credentials are not configured.`;
    }
    if (!runtime.available) {
      return typeof browserCopy.cloudAttachRuntimeMissing === "function" ? browserCopy.cloudAttachRuntimeMissing(backendLabel) : `${backendLabel} attach runtime is missing.`;
    }
    return typeof browserCopy.cloudConfigured === "function" ? browserCopy.cloudConfigured(backendLabel) : `${backendLabel} is configured.`;
  }
  if (runtime.available) {
    return typeof browserCopy.runtimeAvailable === "function" ? browserCopy.runtimeAvailable(runtime.command || "agent-browser") : `Available: ${runtime.command || "agent-browser"}`;
  }
  return browserCopy.runtimeMissing || "agent-browser and npx were not found.";
}

export function browserSummary(copy: AnyRecord, state: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
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

export function browserTestSummary(copy: AnyRecord, state: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const result = state.browserTestResult;
  if (!result) {
    return browserCopy.test?.notRun || "No manual browser test has run yet.";
  }
  if (result.ok) {
    return typeof browserCopy.test?.resultPassed === "function" ? browserCopy.test.resultPassed(result.url || "") : `Browser test passed: ${result.url || ""}`;
  }
  const error = result.error || result.open?.error || result.snapshot?.error || "";
  return typeof browserCopy.test?.resultFailed === "function" ? browserCopy.test.resultFailed(error) : `Browser test failed${error ? `: ${error}` : "."}`;
}

export function browserDoctorSummary(copy: AnyRecord, state: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const result = state.browserDoctorResult;
  if (!result) {
    return browserCopy.doctor?.notRun || "Install has not been checked yet.";
  }
  const checks = Array.isArray(result.checks) ? result.checks : [];
  const passed = checks.filter((check: AnyRecord) => check?.ok).length;
  if (result.ok) {
    return typeof browserCopy.doctor?.resultPassed === "function" ? browserCopy.doctor.resultPassed(passed, checks.length) : `Install check passed: ${passed}/${checks.length}`;
  }
  return typeof browserCopy.doctor?.resultFailed === "function" ? browserCopy.doctor.resultFailed(passed, checks.length) : `Install check failed: ${passed}/${checks.length}`;
}

export function browserDoctorCheckSummary(copy: AnyRecord, check: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const status = check?.ok ? browserCopy.doctor?.checkPassed || "Passed" : browserCopy.doctor?.checkFailed || "Failed";
  const detail = String(check?.suggestion || check?.stderr || check?.stdout || "").trim();
  return detail ? `${status}: ${detail}` : status;
}
