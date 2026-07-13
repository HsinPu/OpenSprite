import type {
  ProviderAuthInitialStates,
  ProviderAuthLoadingKey,
  ProviderAuthMessageKey,
} from "../settings/providerAuthInitialState";

type ProviderAuthActionOptions = {
  before?: () => void;
  after?: () => void | Promise<void>;
  clearNotice?: boolean;
};

export type ProviderAuthActionState = ProviderAuthInitialStates;
type ProviderAuthActionCopy = {
  value: {
    notices: Record<string, string>;
  };
};
type ProviderAuthActionConfig = {
  loadingKey: ProviderAuthLoadingKey;
  errorKey: ProviderAuthMessageKey;
  noticeKey: ProviderAuthMessageKey;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function setProviderAuthLoading(
  settingsState: ProviderAuthActionState,
  key: ProviderAuthLoadingKey,
  value: boolean,
): void {
  settingsState[key] = value;
}

function setProviderAuthMessage(
  settingsState: ProviderAuthActionState,
  key: ProviderAuthMessageKey,
  value: string,
): void {
  settingsState[key] = value;
}

export function setProviderAuthError(
  settingsState: ProviderAuthActionState,
  copy: ProviderAuthActionCopy,
  config: ProviderAuthActionConfig,
  fallbackNoticeKey: string,
  error: unknown,
): void {
  setProviderAuthMessage(settingsState, config.errorKey, errorMessage(error) || copy.value.notices[fallbackNoticeKey]);
}

export async function runProviderAuthAction(
  settingsState: ProviderAuthActionState,
  copy: ProviderAuthActionCopy,
  config: ProviderAuthActionConfig,
  fallbackNoticeKey: string,
  action: () => void | Promise<void>,
  options: ProviderAuthActionOptions = {},
): Promise<void> {
  options.before?.();
  setProviderAuthLoading(settingsState, config.loadingKey, true);
  setProviderAuthMessage(settingsState, config.errorKey, "");
  if (options.clearNotice) {
    setProviderAuthMessage(settingsState, config.noticeKey, "");
  }
  try {
    await action();
    await options.after?.();
  } catch (error: unknown) {
    setProviderAuthError(settingsState, copy, config, fallbackNoticeKey, error);
  } finally {
    setProviderAuthLoading(settingsState, config.loadingKey, false);
  }
}
