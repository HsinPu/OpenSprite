import {
  normalizeBrowserOperationResult,
  normalizeBrowserResultCheck,
  normalizeBrowserSettings,
  type BrowserForm,
  type BrowserOperationResult,
  type BrowserResultCheck,
  type BrowserState,
} from "./browserDefaults";
import { toPayloadSource } from "./payloadBoundary";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type BrowserSettingsPayload = {
  browser?: unknown;
  restart_required?: unknown;
};
type BrowserOperationPayload = {
  browser?: unknown;
  ok?: unknown;
  url?: unknown;
  suggestion?: unknown;
  error?: unknown;
  already_installed?: unknown;
  checks?: unknown;
  after?: unknown;
  install?: unknown;
  open?: unknown;
  snapshot?: unknown;
  runtime?: unknown;
};
type BrowserOperationRequestPayload = {
  url?: string;
};
type BrowserLoadingKey = "browserTestLoading" | "browserDoctorLoading" | "browserInstallLoading";
type BrowserResultKey = "browserTestResult" | "browserDoctorResult" | "browserInstallResult";

interface BrowserSettingsState {
  browserLoading: boolean;
  browserTestLoading: boolean;
  browserDoctorLoading: boolean;
  browserInstallLoading: boolean;
  browserError: string;
  browserNotice: string;
  browserTestResult: BrowserOperationResult | null;
  browserDoctorResult: BrowserOperationResult | null;
  browserInstallResult: BrowserOperationResult | null;
  browser: BrowserState;
  browserForm: BrowserForm;
}

interface BrowserSettingsCopy {
  notices: {
    browserLoadFailed: string;
    browserRestartRequired: string;
    browserSaved: string;
    browserSaveFailed: string;
    browserTestFailed: string;
    browserDoctorFailed: string;
    browserInstallFailed: string;
  };
  settings: {
    browser: {
      testPassed: (url: string) => string;
      testFailed: (reason: string) => string;
      doctorPassed: (passed: number, total: number) => string;
      doctorFailed: (passed: number, total: number) => string;
      installAlreadyInstalled: string;
      installPassed: string;
      installFailed: (reason: string) => string;
    };
  };
}

type SettingsActionContext = {
  settingsState: BrowserSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: BrowserSettingsCopy };
  setSettingsSuccess: (key: string, message: string) => void;
};
type BrowserOperationSummary = (payload: BrowserOperationResult, copy: SettingsActionContext["copy"]) => string;
type BrowserOperationAfterPayload = (payload: BrowserOperationResult) => void;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function toBrowserSettingsPayload(value: unknown): BrowserSettingsPayload {
  const payload = toPayloadSource<BrowserSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    browser: payload.browser,
    restart_required: payload.restart_required,
  };
}

function toBrowserOperationPayload(value: unknown): BrowserOperationPayload {
  const payload = toPayloadSource<BrowserOperationPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    browser: payload.browser,
    ok: payload.ok,
    url: payload.url,
    suggestion: payload.suggestion,
    error: payload.error,
    already_installed: payload.already_installed,
    checks: payload.checks,
    after: payload.after,
    install: payload.install,
    open: payload.open,
    snapshot: payload.snapshot,
    runtime: payload.runtime,
  };
}

function optionalText(value: unknown): string {
  return String(value || "").trim();
}

function resultReason(value: BrowserResultCheck | null | undefined): string {
  return optionalText(value?.suggestion || value?.error);
}

function browserChecks(value: unknown): BrowserResultCheck[] {
  if (!Array.isArray(value)) return [];
  return value.map(normalizeBrowserResultCheck).filter((check) => Object.keys(check).length > 0);
}

function syncBrowserForm(settingsState: BrowserSettingsState): void {
  settingsState.browserForm.enabled = settingsState.browser.enabled;
  settingsState.browserForm.backend = settingsState.browser.backend;
  settingsState.browserForm.commandTimeout = settingsState.browser.command_timeout;
  settingsState.browserForm.sessionTimeout = settingsState.browser.session_timeout;
  settingsState.browserForm.cdpUrl = settingsState.browser.cdp_url;
  settingsState.browserForm.launchArgs = settingsState.browser.launch_args;
  settingsState.browserForm.allowPrivateUrls = settingsState.browser.allow_private_urls;
}

function summarizeBrowserTest(payload: BrowserOperationResult, copy: SettingsActionContext["copy"]): string {
  const browserCopy = copy.value.settings.browser;
  if (payload.ok === true) {
    return browserCopy.testPassed(optionalText(payload.url));
  }
  return browserCopy.testFailed(
    optionalText(payload.suggestion || payload.error)
      || resultReason(payload.open)
      || resultReason(payload.snapshot),
  );
}

function summarizeBrowserDoctor(payload: BrowserOperationResult, copy: SettingsActionContext["copy"]): string {
  const browserCopy = copy.value.settings.browser;
  const checks = browserChecks(payload.checks);
  const passed = checks.filter((check) => check.ok === true).length;
  return payload.ok === true ? browserCopy.doctorPassed(passed, checks.length) : browserCopy.doctorFailed(passed, checks.length);
}

function summarizeBrowserInstall(payload: BrowserOperationResult, copy: SettingsActionContext["copy"]): string {
  const browserCopy = copy.value.settings.browser;
  if (payload.already_installed === true) {
    return browserCopy.installAlreadyInstalled;
  }
  return payload.ok === true ? browserCopy.installPassed : browserCopy.installFailed(resultReason(payload.after) || resultReason(payload.install));
}

export function useBrowserSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }: SettingsActionContext) {
  async function runBrowserOperation(
    loadingKey: BrowserLoadingKey,
    resultKey: BrowserResultKey,
    endpoint: string,
    summarize: BrowserOperationSummary,
    failedNotice: string,
    body: BrowserOperationRequestPayload | null = null,
    afterPayload: BrowserOperationAfterPayload | null = null,
  ): Promise<void> {
    settingsState[loadingKey] = true;
    settingsState.browserError = "";
    settingsState.browserNotice = "";
    settingsState[resultKey] = null;
    try {
      const requestOptions = body ? { method: "POST", body: JSON.stringify(body) } : { method: "POST" };
      const rawPayload = toBrowserOperationPayload(await requestSettingsJson(endpoint, requestOptions));
      const payload = normalizeBrowserOperationResult(rawPayload);
      settingsState.browser = payload.browser || settingsState.browser;
      settingsState[resultKey] = payload;
      afterPayload?.(payload);
      settingsState.browserNotice = summarize(payload, copy);
    } catch (error: unknown) {
      settingsState.browserError = errorMessage(error) || failedNotice;
    } finally {
      settingsState[loadingKey] = false;
    }
  }

  async function loadBrowserSettings(): Promise<void> {
    settingsState.browserLoading = true;
    settingsState.browserError = "";
    try {
      const payload = toBrowserSettingsPayload(await requestSettingsJson("/api/settings/browser"));
      settingsState.browser = normalizeBrowserSettings(payload.browser || {});
      syncBrowserForm(settingsState);
    } catch (error: unknown) {
      settingsState.browserError = errorMessage(error) || copy.value.notices.browserLoadFailed;
    } finally {
      settingsState.browserLoading = false;
    }
  }

  async function saveBrowserSettings(): Promise<void> {
    settingsState.browserLoading = true;
    settingsState.browserError = "";
    settingsState.browserNotice = "";
    try {
      const payload = toBrowserSettingsPayload(await requestSettingsJson("/api/settings/browser", {
        method: "PUT",
        body: JSON.stringify({
          enabled: settingsState.browserForm.enabled,
          backend: settingsState.browserForm.backend,
          command_timeout: settingsState.browserForm.commandTimeout,
          session_timeout: settingsState.browserForm.sessionTimeout,
          cdp_url: settingsState.browserForm.cdpUrl,
          launch_args: settingsState.browserForm.launchArgs,
          allow_private_urls: settingsState.browserForm.allowPrivateUrls,
        }),
      }));
      settingsState.browser = normalizeBrowserSettings(payload.browser || {});
      syncBrowserForm(settingsState);
      setSettingsSuccess(
        "browserNotice",
        payload.restart_required ? copy.value.notices.browserRestartRequired : copy.value.notices.browserSaved,
      );
    } catch (error: unknown) {
      settingsState.browserError = errorMessage(error) || copy.value.notices.browserSaveFailed;
    } finally {
      settingsState.browserLoading = false;
    }
  }

  async function runBrowserTest(): Promise<void> {
    await runBrowserOperation(
      "browserTestLoading",
      "browserTestResult",
      "/api/settings/browser/test",
      summarizeBrowserTest,
      copy.value.notices.browserTestFailed,
      { url: settingsState.browserForm.testUrl },
    );
  }

  async function runBrowserDoctor(): Promise<void> {
    await runBrowserOperation(
      "browserDoctorLoading",
      "browserDoctorResult",
      "/api/settings/browser/doctor",
      summarizeBrowserDoctor,
      copy.value.notices.browserDoctorFailed,
    );
  }

  async function runBrowserInstall(): Promise<void> {
    await runBrowserOperation(
      "browserInstallLoading",
      "browserInstallResult",
      "/api/settings/browser/install",
      summarizeBrowserInstall,
      copy.value.notices.browserInstallFailed,
      null,
      (payload) => {
        const after = normalizeBrowserResultCheck(payload.after);
        settingsState.browserDoctorResult = Object.keys(after).length
          ? normalizeBrowserOperationResult({ ok: payload.ok === true, browser: payload.browser, runtime: payload.runtime, checks: [after] })
          : settingsState.browserDoctorResult;
      },
    );
  }

  return {
    loadBrowserSettings,
    saveBrowserSettings,
    runBrowserTest,
    runBrowserDoctor,
    runBrowserInstall,
  };
}
