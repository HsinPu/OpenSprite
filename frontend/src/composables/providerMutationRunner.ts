type ProviderMutationOptions = {
  before?: () => void;
  after?: () => void | Promise<void>;
};

interface ProviderMutationState {
  providersLoading: boolean;
  providersError: string;
  providersNotice: string;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

export async function runProviderMutation(
  settingsState: ProviderMutationState,
  fallbackNotice: string,
  action: () => void | Promise<void>,
  options: ProviderMutationOptions = {},
): Promise<void> {
  settingsState.providersLoading = true;
  settingsState.providersError = "";
  settingsState.providersNotice = "";
  options.before?.();
  try {
    await action();
    await options.after?.();
  } catch (error: unknown) {
    settingsState.providersError = errorMessage(error) || fallbackNotice;
  } finally {
    settingsState.providersLoading = false;
  }
}
