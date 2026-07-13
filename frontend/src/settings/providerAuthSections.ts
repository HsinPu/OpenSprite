import {
  authCopyForConfig,
  authState,
  authStatusLabel,
  providerAuthDescription,
  providerAuthVisible,
  type ProviderAuthCopyView,
  type ProviderAuthSlotState,
  type ProviderAuthStateView,
} from "./providerAuthHelpers";
import { PROVIDER_AUTH_SECTION_CONFIGS } from "./providerAuthMetadata";

type ProviderAuthClientView = {
  loadProviderAuthStatusById: (providerId: string) => void;
  startProviderAuthLoginById: (providerId: string) => void;
  logoutProviderAuthById: (providerId: string) => void;
};
export type ProviderAuthSectionView = {
  key: string;
  visible: boolean;
  title: string;
  notice: string;
  error: string;
  mark: string;
  name: string;
  status: string;
  description: string;
  loading: boolean;
  configured: boolean;
  copy: ProviderAuthCopyView;
  auth: ProviderAuthStateView;
  onRefresh: () => void;
  onLogin: () => void;
  onLogout: () => void;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

export function providerAuthSections(copy: unknown, state: ProviderAuthSlotState, client: ProviderAuthClientView): ProviderAuthSectionView[] {
  return PROVIDER_AUTH_SECTION_CONFIGS.map((config) => {
    const auth = authState(state, config);
    const loading = Boolean(state[config.loadingKey]);
    const copyForAuth = authCopyForConfig(copy, config);

    return {
      key: config.providerId,
      visible: providerAuthVisible(state, config),
      title: text(copyForAuth.title, `${config.providerName} auth`),
      notice: text(state[config.noticeKey]),
      error: text(state[config.errorKey]),
      mark: config.mark,
      name: text(copyForAuth.name, config.providerName),
      status: authStatusLabel(copyForAuth, auth, loading),
      description: providerAuthDescription(copy, state, config),
      loading,
      configured: Boolean(auth.configured),
      copy: copyForAuth,
      auth,
      onRefresh: () => client.loadProviderAuthStatusById(config.providerId),
      onLogin: () => client.startProviderAuthLoginById(config.providerId),
      onLogout: () => client.logoutProviderAuthById(config.providerId),
    };
  });
}
