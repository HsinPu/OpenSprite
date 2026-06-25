import { normalizeBrowserSettings } from "./browserDefaults";

function syncBrowserForm(settingsState) {
  settingsState.browserForm.enabled = settingsState.browser.enabled;
  settingsState.browserForm.backend = settingsState.browser.backend;
  settingsState.browserForm.commandTimeout = settingsState.browser.command_timeout;
  settingsState.browserForm.sessionTimeout = settingsState.browser.session_timeout;
  settingsState.browserForm.cdpUrl = settingsState.browser.cdp_url;
  settingsState.browserForm.launchArgs = settingsState.browser.launch_args;
  settingsState.browserForm.allowPrivateUrls = settingsState.browser.allow_private_urls;
}

function summarizeBrowserTest(payload, copy) {
  const browserCopy = copy.value.settings.browser;
  if (payload?.ok) {
    return browserCopy.testPassed(payload.url || "");
  }
  return browserCopy.testFailed(payload?.suggestion || payload?.error || payload?.open?.suggestion || payload?.open?.error || payload?.snapshot?.suggestion || payload?.snapshot?.error || "");
}

function summarizeBrowserDoctor(payload, copy) {
  const browserCopy = copy.value.settings.browser;
  const checks = Array.isArray(payload?.checks) ? payload.checks : [];
  const passed = checks.filter((check) => check?.ok).length;
  return payload?.ok ? browserCopy.doctorPassed(passed, checks.length) : browserCopy.doctorFailed(passed, checks.length);
}

function summarizeBrowserInstall(payload, copy) {
  const browserCopy = copy.value.settings.browser;
  if (payload?.already_installed) {
    return browserCopy.installAlreadyInstalled;
  }
  return payload?.ok ? browserCopy.installPassed : browserCopy.installFailed(payload?.after?.suggestion || payload?.install?.suggestion || "");
}

export function useBrowserSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }) {
  async function runBrowserOperation(loadingKey, resultKey, endpoint, summarize, failedNotice, body = null, afterPayload = null) {
    settingsState[loadingKey] = true;
    settingsState.browserError = "";
    settingsState.browserNotice = "";
    settingsState[resultKey] = null;
    try {
      const requestOptions = body ? { method: "POST", body: JSON.stringify(body) } : { method: "POST" };
      const payload = await requestSettingsJson(endpoint, requestOptions);
      settingsState.browser = normalizeBrowserSettings(payload.browser || settingsState.browser || {});
      settingsState[resultKey] = payload;
      afterPayload?.(payload);
      settingsState.browserNotice = summarize(payload, copy);
    } catch (error) {
      settingsState.browserError = error?.message || failedNotice;
    } finally {
      settingsState[loadingKey] = false;
    }
  }

  async function loadBrowserSettings() {
    settingsState.browserLoading = true;
    settingsState.browserError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/browser");
      settingsState.browser = normalizeBrowserSettings(payload.browser || {});
      syncBrowserForm(settingsState);
    } catch (error) {
      settingsState.browserError = error?.message || copy.value.notices.browserLoadFailed;
    } finally {
      settingsState.browserLoading = false;
    }
  }

  async function saveBrowserSettings() {
    settingsState.browserLoading = true;
    settingsState.browserError = "";
    settingsState.browserNotice = "";
    try {
      const payload = await requestSettingsJson("/api/settings/browser", {
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
      });
      settingsState.browser = normalizeBrowserSettings(payload.browser || {});
      syncBrowserForm(settingsState);
      setSettingsSuccess(
        "browserNotice",
        payload.restart_required ? copy.value.notices.browserRestartRequired : copy.value.notices.browserSaved,
      );
    } catch (error) {
      settingsState.browserError = error?.message || copy.value.notices.browserSaveFailed;
    } finally {
      settingsState.browserLoading = false;
    }
  }

  async function runBrowserTest() {
    await runBrowserOperation(
      "browserTestLoading",
      "browserTestResult",
      "/api/settings/browser/test",
      summarizeBrowserTest,
      copy.value.notices.browserTestFailed,
      { url: settingsState.browserForm.testUrl },
    );
  }

  async function runBrowserDoctor() {
    await runBrowserOperation(
      "browserDoctorLoading",
      "browserDoctorResult",
      "/api/settings/browser/doctor",
      summarizeBrowserDoctor,
      copy.value.notices.browserDoctorFailed,
    );
  }

  async function runBrowserInstall() {
    await runBrowserOperation(
      "browserInstallLoading",
      "browserInstallResult",
      "/api/settings/browser/install",
      summarizeBrowserInstall,
      copy.value.notices.browserInstallFailed,
      null,
      (payload) => {
        settingsState.browserDoctorResult = payload.after ? { ok: payload.ok, browser: payload.browser, runtime: payload.runtime, checks: [payload.after] } : settingsState.browserDoctorResult;
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
