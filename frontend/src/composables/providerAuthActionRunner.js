export async function runProviderAuthAction(settingsState, copy, config, fallbackNoticeKey, action, options = {}) {
  options.before?.();
  settingsState[config.loadingKey] = true;
  settingsState[config.errorKey] = "";
  if (options.clearNotice) {
    settingsState[config.noticeKey] = "";
  }
  try {
    await action();
  } catch (error) {
    settingsState[config.errorKey] = error?.message || copy.value.notices[fallbackNoticeKey];
  } finally {
    settingsState[config.loadingKey] = false;
  }
}
