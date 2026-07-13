import {
  PROVIDER_AUTH_SECTION_CONFIGS,
  type ProviderAuthSectionConfig,
} from "./providerAuthMetadata";
import type { ProviderAuthStatePayload } from "../composables/providerAuthState";

export type ProviderAuthStateKey = ProviderAuthSectionConfig["stateKey"];
export type ProviderAuthLoadingKey = ProviderAuthSectionConfig["loadingKey"];
export type ProviderAuthMessageKey = ProviderAuthSectionConfig["errorKey" | "noticeKey"];

export type ProviderAuthInitialStates =
  & { [Key in ProviderAuthStateKey]: ProviderAuthStatePayload }
  & { [Key in ProviderAuthLoadingKey]: boolean }
  & { [Key in ProviderAuthMessageKey]: string };

export function createProviderAuthInitialStates(): ProviderAuthInitialStates {
  const [openaiCodexConfig, copilotConfig] = PROVIDER_AUTH_SECTION_CONFIGS;
  return {
    [openaiCodexConfig.loadingKey]: false,
    [openaiCodexConfig.errorKey]: "",
    [openaiCodexConfig.noticeKey]: "",
    [openaiCodexConfig.stateKey]: openaiCodexConfig.initialAuth,
    [copilotConfig.loadingKey]: false,
    [copilotConfig.errorKey]: "",
    [copilotConfig.noticeKey]: "",
    [copilotConfig.stateKey]: copilotConfig.initialAuth,
  };
}
