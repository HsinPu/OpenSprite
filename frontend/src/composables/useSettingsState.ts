import { createDefaultBrowserForm, createDefaultBrowserState, type BrowserForm, type BrowserOperationResult, type BrowserState } from "./browserDefaults";
import { createDefaultLogForm, createDefaultLogState, type LogForm, type LogState } from "./logDefaults";
import { createDefaultNetworkForm, createDefaultNetworkState, type NetworkForm, type NetworkState } from "./networkDefaults";
import type { ColorSchemePreference, LanguagePreference } from "./chatClientPreferences";
import { createEmptyProviderConnectForm, type ProviderConnectForm } from "./providerConnectForm";
import { createDefaultScheduleForm, createDefaultScheduleState, DEFAULT_CRON_TIMEZONE, type CronJobMode, type ScheduleForm, type ScheduleState } from "./scheduleDefaults";
import { createDefaultSearchForm, createDefaultSearchState, type SearchForm, type SearchState } from "./searchDefaults";
import { createProviderAuthInitialStates, type ProviderAuthInitialStates } from "../settings/providerAuthInitialState";
import type { ModelReasoningEffort } from "./modelReasoning";
import type { McpTransportType } from "./settingsNormalizers";

interface ClientSettingsSource {
  wsUrl: string;
  accessToken: string;
  displayName: string;
  activeExternalChatId: string;
  showRunHistory: boolean;
  showRunTimeline: boolean;
  showRunSummary: boolean;
  showRunTrace: boolean;
  language: LanguagePreference;
  colorScheme: ColorSchemePreference;
}

export interface SettingsForm {
  wsUrl: string;
  accessToken: string;
  displayName: string;
  externalChatId: string;
  showRunHistory: boolean;
  showRunTimeline: boolean;
  showRunSummary: boolean;
  showRunTrace: boolean;
  language: LanguagePreference;
  colorScheme: ColorSchemePreference;
}

export interface CronJobForm {
  showEditor: boolean;
  sessionId: string;
  jobId: string;
  mode: CronJobMode;
  name: string;
  message: string;
  everySeconds: string;
  cronExpr: string;
  at: string;
  timezone: string;
  deliver: boolean;
}

export interface CronJobScheduleView {
  kind?: string;
  display?: string;
  every_ms?: number;
  expr?: string;
  at_ms?: number | string;
  tz?: string;
}

export interface CronJobPayloadView {
  message?: string;
  deliver?: boolean;
}

export interface CronJobStateView {
  next_run_display?: string;
}

export interface CronJobView {
  id: string;
  name: string;
  enabled: boolean;
  schedule: CronJobScheduleView;
  cron_expr: string;
  every_seconds: number;
  session_id: string;
  state: CronJobStateView;
  payload: CronJobPayloadView;
  message: string;
}

export interface ChannelView {
  id: string;
  name?: string;
  type?: string;
  enabled?: boolean;
  description?: string;
  status?: string;
}

export interface ChannelSettings {
  connected: ChannelView[];
  available: ChannelView[];
  channels: ChannelView[];
}

export interface ChannelConnectForm {
  type: string;
  name: string;
  token: string;
}

export interface ProviderView {
  id: string;
  name?: string;
  provider?: string;
  providerName?: string;
  type?: string;
  auth_type?: string;
  base_url?: string;
  default_base_url?: string;
  description?: string;
  credential_id?: string;
  credential_effective_id?: string;
  effective_credential_id?: string;
  credential_label?: string;
  credential_preview?: string;
  connected_count?: number;
  api_key_optional?: boolean;
  requires_api_key?: boolean;
  is_default?: boolean;
  preset_name?: string;
}

export interface ProviderSettings {
  default_provider: string;
  connected: ProviderView[];
  available: ProviderView[];
}

export interface ProviderCredentialView {
  id: string;
  label?: string;
  name?: string;
  secret_preview?: string;
}

export type ProviderCredentialsState = Record<string, ProviderCredentialView[]>;

export interface UpdateStatusView {
  supported: boolean;
  dirty: boolean;
  update_available: boolean;
  commits_behind: number;
  current_rev_short: string;
  branch?: string;
  project_root?: string;
}

export type ModelMetadataEntryView = {
  context_length?: number;
};
export type ModelMetadataByModel = Record<string, ModelMetadataEntryView>;
export const MEDIA_CATEGORIES = ["vision", "ocr", "speech", "video"] as const;
export type MediaCategory = (typeof MEDIA_CATEGORIES)[number];
export type MediaCategoryMap<Value> = {
  [Category in MediaCategory]: Value;
};
export type PartialMediaCategoryMap<Value> = {
  [Category in MediaCategory]?: Value;
};
export type ModelMediaModelsByCategory = PartialMediaCategoryMap<string[]>;

export interface ModelProviderView {
  id: string;
  name?: string;
  type?: string;
  is_default?: boolean;
  selected_model?: string;
  models?: string[];
  model_metadata?: ModelMetadataByModel;
  media_models?: ModelMediaModelsByCategory;
  reasoning_effort?: ModelReasoningEffort;
}

export interface ModelSettings {
  default_provider: string;
  active_model: string;
  providers: ModelProviderView[];
}

export interface MediaSectionView {
  category: MediaCategory;
  enabled: boolean;
  provider_id: string;
  model: string;
}

export interface MediaSettings {
  sections: MediaCategoryMap<MediaSectionView>;
  providers: ModelProviderView[];
}

export interface MediaSelection {
  enabled: boolean;
  providerId: string;
  model: string;
}
export type MediaSelections = MediaCategoryMap<MediaSelection>;
export type MediaCustomModels = MediaCategoryMap<string>;

export interface McpRuntimeView {
  connected: boolean;
  connecting: boolean;
  connect_failures: number;
  retry_after?: number;
  tool_names: string[];
}

export interface McpServerView {
  id?: string;
  name?: string;
  type?: string;
  command?: string;
  args?: string[];
  url?: string;
  tool_timeout?: number;
  enabled_tools?: string[];
  env_configured?: boolean;
  env_keys?: string[];
  headers_configured?: boolean;
  headers_keys?: string[];
}

export interface McpSettings {
  servers: McpServerView[];
  runtime: McpRuntimeView;
}

export interface McpForm {
  showEditor: boolean;
  editingId: string;
  serverId: string;
  type: McpTransportType;
  command: string;
  argsText: string;
  url: string;
  envJson: string;
  headersJson: string;
  toolTimeout: string;
  enabledToolsText: string;
  showAdvanced: boolean;
  showJsonInput: boolean;
  jsonText: string;
}

export type SettingsState = ProviderAuthInitialStates & {
  channelsLoading: boolean;
  channelsError: string;
  channelsNotice: string;
  channels: ChannelSettings;
  channelConnectForm: ChannelConnectForm;
  providersLoading: boolean;
  providersError: string;
  providersNotice: string;
  providers: ProviderSettings;
  credentials: ProviderCredentialsState;
  connectForm: ProviderConnectForm;
  updateLoading: boolean;
  updateError: string;
  updateNotice: string;
  updateStatus: UpdateStatusView;
  scheduleLoading: boolean;
  scheduleError: string;
  scheduleNotice: string;
  schedule: ScheduleState;
  scheduleForm: ScheduleForm;
  networkLoading: boolean;
  networkError: string;
  networkNotice: string;
  network: NetworkState;
  networkForm: NetworkForm;
  logLoading: boolean;
  logError: string;
  logNotice: string;
  log: LogState;
  logForm: LogForm;
  searchLoading: boolean;
  searchOptionsLoading: boolean;
  searchError: string;
  searchOptionsError: string;
  searchNotice: string;
  searchOptionsNotice: string;
  search: SearchState;
  searchForm: SearchForm;
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
  modelsLoading: boolean;
  modelsError: string;
  modelsNotice: string;
  models: ModelSettings;
  selectedTextProviderId: string;
  modelSelections: Record<string, string>;
  reasoningSelections: Record<string, ModelReasoningEffort>;
  customModels: Record<string, string>;
  mediaLoading: boolean;
  mediaError: string;
  mediaNotice: string;
  media: MediaSettings;
  mediaSelections: MediaSelections;
  mediaCustomModels: MediaCustomModels;
  mcpLoading: boolean;
  mcpError: string;
  mcpNotice: string;
  mcpToolGroupsExpanded: Record<string, boolean>;
  mcp: McpSettings;
  mcpForm: McpForm;
  cronJobsLoading: boolean;
  cronJobsError: string;
  cronJobsNotice: string;
  cronJobs: CronJobView[];
  cronJobForm: CronJobForm;
};

export function createSettingsForm(state: ClientSettingsSource): SettingsForm {
  return {
    wsUrl: state.wsUrl,
    accessToken: state.accessToken,
    displayName: state.displayName,
    externalChatId: state.activeExternalChatId,
    showRunHistory: state.showRunHistory,
    showRunTimeline: state.showRunTimeline,
    showRunSummary: state.showRunSummary,
    showRunTrace: state.showRunTrace,
    language: state.language,
    colorScheme: state.colorScheme,
  };
}

export function createSettingsState(): SettingsState {
  return {
    channelsLoading: false,
    channelsError: "",
    channelsNotice: "",
    channels: {
      connected: [],
      available: [],
      channels: [],
    },
    channelConnectForm: {
      type: "",
      name: "",
      token: "",
    },
    providersLoading: false,
    providersError: "",
    providersNotice: "",
    providers: {
      default_provider: "",
      connected: [],
      available: [],
    },
    credentials: {},
    ...createProviderAuthInitialStates(),
    connectForm: createEmptyProviderConnectForm(),
    updateLoading: false,
    updateError: "",
    updateNotice: "",
    updateStatus: {
      supported: false,
      update_available: false,
      commits_behind: 0,
      dirty: false,
      branch: "",
      current_rev_short: "",
      project_root: "",
    },
    modelsLoading: false,
    modelsError: "",
    modelsNotice: "",
    models: {
      default_provider: "",
      active_model: "",
      providers: [],
    },
    selectedTextProviderId: "",
    modelSelections: {},
    reasoningSelections: {},
    customModels: {},
    mediaLoading: false,
    mediaError: "",
    mediaNotice: "",
    media: {
      sections: {
        vision: { category: "vision", enabled: false, provider_id: "", model: "" },
        ocr: { category: "ocr", enabled: false, provider_id: "", model: "" },
        speech: { category: "speech", enabled: false, provider_id: "", model: "" },
        video: { category: "video", enabled: false, provider_id: "", model: "" },
      },
      providers: [],
    },
    mediaSelections: {
      vision: { enabled: false, providerId: "", model: "" },
      ocr: { enabled: false, providerId: "", model: "" },
      speech: { enabled: false, providerId: "", model: "" },
      video: { enabled: false, providerId: "", model: "" },
    },
    mediaCustomModels: {
      vision: "",
      ocr: "",
      speech: "",
      video: "",
    },
    scheduleLoading: false,
    scheduleError: "",
    scheduleNotice: "",
    schedule: createDefaultScheduleState(),
    scheduleForm: createDefaultScheduleForm(),
    networkLoading: false,
    networkError: "",
    networkNotice: "",
    network: createDefaultNetworkState(),
    networkForm: createDefaultNetworkForm(),
    searchLoading: false,
    searchOptionsLoading: false,
    searchError: "",
    searchOptionsError: "",
    searchNotice: "",
    searchOptionsNotice: "",
    search: createDefaultSearchState(),
    searchForm: createDefaultSearchForm(),
    browserLoading: false,
    browserTestLoading: false,
    browserDoctorLoading: false,
    browserInstallLoading: false,
    browserError: "",
    browserNotice: "",
    browserTestResult: null,
    browserDoctorResult: null,
    browserInstallResult: null,
    browser: createDefaultBrowserState(),
    browserForm: createDefaultBrowserForm(),
    logLoading: false,
    logError: "",
    logNotice: "",
    log: createDefaultLogState(),
    logForm: createDefaultLogForm(),
    cronJobsLoading: false,
    cronJobsError: "",
    cronJobsNotice: "",
    cronJobs: [],
    cronJobForm: {
      showEditor: false,
      sessionId: "",
      jobId: "",
      mode: "cron",
      name: "",
      message: "",
      everySeconds: "3600",
      cronExpr: "0 9 * * *",
      at: "",
      timezone: DEFAULT_CRON_TIMEZONE,
      deliver: true,
    },
    mcpLoading: false,
    mcpError: "",
    mcpNotice: "",
    mcpToolGroupsExpanded: {},
    mcp: {
      servers: [],
      runtime: {
        connected: false,
        connecting: false,
        connect_failures: 0,
        tool_names: [],
      },
    },
    mcpForm: {
      showEditor: false,
      editingId: "",
      serverId: "",
      type: "stdio",
      command: "",
      argsText: "",
      url: "",
      envJson: "",
      headersJson: "",
      toolTimeout: "30",
      enabledToolsText: "*",
      showAdvanced: false,
      showJsonInput: false,
      jsonText: "",
    },
  };
}
