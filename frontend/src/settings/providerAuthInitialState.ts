import {
  PROVIDER_AUTH_SECTION_CONFIGS,
  providerAuthStateKeys,
} from "./providerAuthMetadata";

function providerAuthInitialState(keys: ReturnType<typeof providerAuthStateKeys>, auth: Record<string, unknown>) {
  return {
    [keys.loadingKey]: false,
    [keys.errorKey]: "",
    [keys.noticeKey]: "",
    [keys.stateKey]: auth,
  };
}

export function createProviderAuthInitialStates() {
  return Object.assign(
    {},
    ...PROVIDER_AUTH_SECTION_CONFIGS.map((config) => providerAuthInitialState(config, config.initialAuth)),
  );
}
