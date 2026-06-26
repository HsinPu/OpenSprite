import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

async function read(relativePath) {
  return readFile(join(root, relativePath), "utf8");
}

async function listSourceFiles(relativePath) {
  const entries = await readdir(join(root, relativePath), { recursive: true, withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile())
    .map((entry) => join(entry.parentPath, entry.name).replace(root, "").replace(/\\/g, "/"));
}

function assertIncludes(content, needle, label) {
  if (!content.includes(needle)) {
    throw new Error(`${label}: missing ${needle}`);
  }
}

function assertNotIncludes(content, needle, label) {
  if (content.includes(needle)) {
    throw new Error(`${label}: unexpected ${needle}`);
  }
}

function assertRegex(content, pattern, label) {
  if (!pattern.test(content)) {
    throw new Error(`${label}: expected ${pattern}`);
  }
}

const [
  packageJsonRaw,
  viteConfig,
  tsconfigRaw,
  indexHtml,
  app,
  appProviders,
  openSpriteShell,
  main,
  styles,
  reactiveCompat,
  chatClient,
  providerSettingsActions,
  providerSettingsLoader,
  providerSettingsRequests,
  providerAuthActions,
  providerAuthActionRunner,
  providerAuthRequests,
  providerAuthConfigs,
  providerAuthPollTimers,
  providerAuthState,
  providerConnectForm,
  providerMutationRunner,
  settingsSectionLoaders,
  useSettingsState,
  confirmFlow,
  shellLayout,
  authGate,
  chatPanel,
  confirmDialog,
  emptyState,
  messageList,
  mobileNavControls,
  sidebarNav,
  traceSidebar,
  browserSettings,
  runInspector,
  runHistorySelector,
  runSummaryCard,
  runTimeline,
  runTraceViewer,
  workStateCard,
  authProviderCard,
  providerAuthSection,
  providerAuthSections,
  providerConstants,
  providerEmptyState,
  providerHelpers,
  availableProviderRow,
  connectedProviderRow,
  availableProvidersSection,
  connectedProvidersSection,
  providerConnectDialog,
  logSettings,
  providerSettings,
  modelSettings,
  channelSettings,
  generalSettings,
  mcpSettings,
  networkSettings,
  scheduleSettings,
  searchSettings,
  settingsModal,
  shortcutSettings,
  settingsPrimitives,
] = await Promise.all([
  read("package.json"),
  read("vite.config.ts"),
  read("tsconfig.json"),
  read("index.html"),
  read("src/App.tsx"),
  read("src/providers/appProviders.tsx"),
  read("src/components/openSpriteShell.tsx"),
  read("src/main.tsx"),
  read("styles.css"),
  read("src/lib/reactiveCompat.ts"),
  read("src/composables/useChatClient.js"),
  read("src/composables/useProviderSettingsActions.js"),
  read("src/composables/providerSettingsLoader.js"),
  read("src/composables/providerSettingsRequests.js"),
  read("src/composables/useProviderAuthActions.js"),
  read("src/composables/providerAuthActionRunner.js"),
  read("src/composables/providerAuthRequests.js"),
  read("src/composables/providerAuthConfigs.js"),
  read("src/composables/providerAuthPollTimers.js"),
  read("src/composables/providerAuthState.js"),
  read("src/composables/providerConnectForm.js"),
  read("src/composables/providerMutationRunner.js"),
  read("src/composables/settingsSectionLoaders.js"),
  read("src/composables/useSettingsState.js"),
  read("src/composables/useConfirmDialog.ts"),
  read("src/composables/useShellLayout.ts"),
  read("src/components/authGate.tsx"),
  read("src/components/chatPanel.tsx"),
  read("src/components/confirmDialog.tsx"),
  read("src/components/emptyState.tsx"),
  read("src/components/messageList.tsx"),
  read("src/components/mobileNavControls.tsx"),
  read("src/components/sidebarNav.tsx"),
  read("src/components/traceSidebar.tsx"),
  read("src/settings/browserSettings.tsx"),
  read("src/components/runInspector.tsx"),
  read("src/components/runHistorySelector.tsx"),
  read("src/components/runSummaryCard.tsx"),
  read("src/components/runTimeline.tsx"),
  read("src/components/runTraceViewer.tsx"),
  read("src/components/workStateCard.tsx"),
  read("src/settings/authProviderCard.tsx"),
  read("src/settings/providerAuthSection.tsx"),
  read("src/settings/providerAuthSections.ts"),
  read("src/settings/providerConstants.ts"),
  read("src/settings/providerEmptyState.tsx"),
  read("src/settings/providerHelpers.ts"),
  read("src/settings/availableProviderRow.tsx"),
  read("src/settings/connectedProviderRow.tsx"),
  read("src/settings/availableProvidersSection.tsx"),
  read("src/settings/connectedProvidersSection.tsx"),
  read("src/settings/providerConnectDialog.tsx"),
  read("src/settings/logSettings.tsx"),
  read("src/settings/providerSettings.tsx"),
  read("src/settings/modelSettings.tsx"),
  read("src/settings/channelSettings.tsx"),
  read("src/settings/generalSettings.tsx"),
  read("src/settings/mcpSettings.tsx"),
  read("src/settings/networkSettings.tsx"),
  read("src/settings/scheduleSettings.tsx"),
  read("src/settings/searchSettings.tsx"),
  read("src/settings/settingsModal.tsx"),
  read("src/settings/shortcutSettings.tsx"),
  read("src/settings/settingsPrimitives.tsx"),
]);

const packageJson = JSON.parse(packageJsonRaw);
const sourceFiles = await listSourceFiles("src");

for (const dependency of ["react", "react-dom", "antd", "@ant-design/icons"]) {
  if (!packageJson.dependencies?.[dependency]) {
    throw new Error(`package dependencies: missing ${dependency}`);
  }
}

for (const dependency of ["@vitejs/plugin-react", "typescript", "@types/react", "@types/react-dom"]) {
  if (!packageJson.devDependencies?.[dependency]) {
    throw new Error(`package devDependencies: missing ${dependency}`);
  }
}

if (packageJson.dependencies?.vue || packageJson.devDependencies?.["@vitejs/plugin-vue"]) {
  throw new Error("package dependencies: Vue dependencies should be removed");
}

if (sourceFiles.some((file) => file.endsWith(".vue"))) {
  throw new Error("source tree: Vue single-file components should be removed");
}

assertIncludes(packageJsonRaw, "\"build\": \"tsc --noEmit && vite build\"", "typescript build gate");
assertIncludes(viteConfig, "@vitejs/plugin-react", "Vite React plugin");
assertNotIncludes(viteConfig, "@vitejs/plugin-vue", "Vite Vue plugin removed");
assertIncludes(tsconfigRaw, "\"jsx\": \"react-jsx\"", "TypeScript React JSX mode");
assertIncludes(indexHtml, "/src/main.tsx", "React TypeScript entry");
assertNotIncludes(indexHtml, "/src/main.js", "legacy JS entry removed");

assertIncludes(main, "createRoot", "React root mount");
assertIncludes(main, "antd/dist/reset.css", "Ant Design reset stylesheet");
assertIncludes(app, "AppProviders", "React shell uses app providers");
assertIncludes(app, "OpenSpriteShell", "React app mounts shell component");
assertIncludes(appProviders, "ConfigProvider", "Ant Design provider");
assertIncludes(appProviders, "<AntdApp>{children}</AntdApp>", "Ant Design app context provider");
assertIncludes(appProviders, "colorPrimary: \"#2563eb\"", "Ant Design theme token retained");
assertIncludes(openSpriteShell, "useReactiveStore", "React subscription bridge");
assertIncludes(openSpriteShell, "useConfirmDialog(client)", "app shell delegates confirm dialog flow");
assertIncludes(openSpriteShell, "useShellLayout(client)", "app shell delegates resize layout logic");
assertIncludes(confirmFlow, "action: () => client.deleteSessions(targets)", "confirm flow keeps session delete action");
assertIncludes(confirmFlow, "action: () => client.clearWebSessions()", "confirm flow keeps web history cleanup action");
assertIncludes(confirmFlow, "setConfirmDialog((dialog) => ({ ...dialog, busy: true }))", "confirm flow keeps busy state");
assertIncludes(confirmFlow, "copy.sidebar.confirmDeleteChat(client.getSessionTitle(targets[0]))", "confirm flow keeps single-session delete copy");
assertIncludes(shellLayout, "SIDEBAR_WIDTH_DEFAULT = 268", "shell layout keeps sidebar default width");
assertIncludes(shellLayout, "TRACE_WIDTH_MIN = 440", "shell layout keeps trace minimum width");
assertIncludes(shellLayout, "window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY", "shell layout persists sidebar width");
assertIncludes(shellLayout, "setSidebarWidth(clampSidebarWidth(moveEvent.clientX))", "shell layout keeps sidebar drag math");
assertIncludes(shellLayout, "setTraceInspectorWidth(clampTraceWidth(window.innerWidth - moveEvent.clientX))", "shell layout keeps trace drag math");
assertIncludes(settingsModal, "useTransition", "settings modal uses transition for deferred content");
assertIncludes(openSpriteShell, "useChatClient", "existing chat client flow reused");
assertIncludes(openSpriteShell, "SidebarNav", "React sidebar shell");
assertIncludes(sidebarNav, "<Checkbox", "sidebar selection uses Ant Checkbox controls");
assertIncludes(sidebarNav, "<Segmented", "sidebar filters use Ant Segmented controls");
assertIncludes(sidebarNav, "client.setSessionChannelFilter(String(value))", "sidebar keeps channel filter action");
assertIncludes(sidebarNav, "client.setShowHiddenSessions(checked)", "sidebar keeps hidden session toggle");
assertIncludes(sidebarNav, "deleteSessions(selectedSessions)", "sidebar keeps bulk delete flow");
assertIncludes(sidebarNav, "client.setActiveSession(session.externalChatId)", "sidebar keeps session switching");
assertIncludes(sidebarNav, "onPointerDown={beginSidebarResize}", "sidebar keeps resize handle");
assertIncludes(openSpriteShell, "ChatPanel", "React chat panel");
assertIncludes(chatPanel, "client.submitMessage", "chat panel keeps composer submit flow");
assertIncludes(chatPanel, "client.applyCommandHint(command)", "chat panel keeps command hint flow");
assertIncludes(chatPanel, "client.setMessageStageRef", "chat panel keeps message stage ref");
assertIncludes(chatPanel, "client.setMessageInputRef", "chat panel keeps composer input ref");
assertIncludes(chatPanel, "client.resizeComposer()", "chat panel keeps composer resizing");
assertIncludes(chatPanel, "client.handleComposerKeydown", "chat panel keeps keyboard handling");
assertIncludes(chatPanel, "sendDisabled.value", "chat panel keeps send disabled state");
assertIncludes(chatPanel, "viewTraceForRun={viewTraceForRun}", "chat panel passes trace callback to message list");
assertIncludes(openSpriteShell, "TraceSidebar", "React trace sidebar");
assertIncludes(traceSidebar, "RunInspector", "trace sidebar renders run inspector");
assertIncludes(traceSidebar, "onPointerDown={beginTraceResize}", "trace sidebar keeps resize handle");
assertIncludes(traceSidebar, "client.toggleTraceInspectorCollapsed", "trace sidebar keeps collapse action");
assertIncludes(traceSidebar, "aria-label=\"Run trace inspector\"", "trace sidebar keeps inspector landmark");
assertIncludes(openSpriteShell, "SettingsModal", "React settings modal");
assertIncludes(authGate, "auth-gate", "auth gate component keeps auth overlay layout");
assertIncludes(authGate, "client.submitAccessToken", "auth gate keeps token submit flow");
assertIncludes(authGate, "client.settingsForm.accessToken", "auth gate keeps access token field");
assertIncludes(authGate, "client.openSettings(\"general\")", "auth gate keeps settings fallback action");
assertIncludes(emptyState, "empty-state", "empty state component keeps starter screen layout");
assertIncludes(emptyState, "prompt-card", "empty state keeps prompt card layout");
assertIncludes(emptyState, "applyPrompt(prompt.text)", "empty state keeps prompt application flow");
assertIncludes(chatPanel, "MessageList", "React message list");
assertIncludes(messageList, "MessageTextRenderer", "React message renderer");
assertIncludes(messageList, "message__trace-button", "message list keeps trace action button");
assertIncludes(messageList, "viewTraceForRun(message.traceRunId)", "message list keeps trace run selection callback");
assertIncludes(messageList, "normalizeMessages", "message list keeps message normalization");
assertIncludes(messageList, "message__artifact", "message list keeps artifact cards");
assertIncludes(openSpriteShell, "viewTraceForRun", "assistant message trace action");
assertIncludes(openSpriteShell, "client.selectRun(runId)", "trace action selects the requested run");
assertIncludes(openSpriteShell, "client.toggleTraceInspectorCollapsed()", "trace action opens collapsed inspector");
assertIncludes(chatPanel, "client.currentRuns.value", "run history uses active session runs");
assertIncludes(openSpriteShell, "MobileNavControls", "React mobile nav controls");
assertIncludes(mobileNavControls, "mobile-nav-toggle", "mobile nav keeps toggle button");
assertIncludes(mobileNavControls, "aria-controls=\"sidebar\"", "mobile nav keeps sidebar aria target");
assertIncludes(mobileNavControls, "icon={sidebarOpen ? <CloseOutlined /> : <MenuUnfoldOutlined />}", "mobile nav keeps open/close icons");
assertIncludes(mobileNavControls, "mobile-nav-backdrop", "mobile nav keeps backdrop button");
assertIncludes(mobileNavControls, "onClick={client.toggleSidebar}", "mobile nav keeps sidebar toggle action");
assertIncludes(confirmDialog, "okButtonProps={{ danger: true, loading: dialog.busy }}", "confirm dialog keeps destructive loading state");
assertIncludes(confirmDialog, "cancelButtonProps={{ disabled: dialog.busy }}", "confirm dialog disables cancel while busy");
assertIncludes(confirmDialog, "onCancel={dialog.busy ? undefined : onCancel}", "confirm dialog blocks cancel while busy");
assertIncludes(confirmDialog, "Alert type=\"warning\"", "confirm dialog keeps warning detail");
assertIncludes(generalSettings, "client.settingsState", "settings API state remains wired through settings modules");
assertIncludes(browserSettings, "client.saveBrowserSettings", "browser settings save action");
assertIncludes(browserSettings, "client.runBrowserTest", "browser manual test action");
assertIncludes(mcpSettings, "client.saveMcpServer", "MCP settings action");
assertIncludes(modelSettings, "client.selectModel", "model selection action");
assertIncludes(openSpriteShell, "clearWebSessions={clearWebSessions}", "app shell wires web history cleanup callback");
assertIncludes(generalSettings, "onClick={clearWebSessions}", "general settings keeps web history cleanup button");
assertIncludes(generalSettings, "form.externalChatId", "general settings keeps external chat id control");
assertIncludes(generalSettings, "client.runUpdate", "general settings keeps update apply action");
assertIncludes(generalSettings, "client.saveConnectionSettings", "general settings keeps connection save action");
assertIncludes(generalSettings, "client.toggleSettingsConnection", "general settings keeps gateway toggle action");
assertIncludes(generalSettings, "client.loadUpdateStatus", "general settings keeps update check action");
assertIncludes(generalSettings, "form.showRunTrace", "general settings keeps run trace visibility toggle");
assertIncludes(generalSettings, "form.colorScheme", "general settings keeps color scheme control");
assertIncludes(providerSettings, "client.deleteCredential", "provider settings keeps credential deletion");
assertIncludes(providerSettings, "ProviderAuthSection", "provider settings delegates auth provider section");
assertIncludes(providerSettings, "providerAuthSections(copy, state, client)", "provider settings delegates auth section assembly");
assertIncludes(providerConstants, "CODEX_PROVIDER_ID = \"openai-codex\"", "provider constants keep Codex provider id");
assertIncludes(providerConstants, "COPILOT_PROVIDER_ID = \"copilot\"", "provider constants keep Copilot provider id");
assertIncludes(providerConstants, "PROVIDER_AUTH_PROVIDER_IDS = Object.keys(PROVIDER_AUTH_SECTIONS)", "provider constants derive auth provider ids from section metadata");
assertIncludes(providerConstants, "export function providerAuthSectionForId", "provider constants centralize provider auth section lookup");
assertIncludes(providerConstants, "return providerAuthSectionForId(providerId)?.authKey || \"\"", "provider constants derive auth keys through section lookup");
assertNotIncludes(providerConstants, "PROVIDER_AUTH_KEYS", "provider constants avoid duplicate auth key map ownership");
assertIncludes(providerConstants, "CODEX_PROVIDER_NAME = \"OpenAI Codex\"", "provider constants keep Codex provider name");
assertIncludes(providerConstants, "COPILOT_PROVIDER_NAME = \"GitHub Copilot\"", "provider constants keep Copilot provider name");
assertIncludes(providerConstants, "CODEX_AUTH_KEY = \"codexAuth\"", "provider constants keep Codex auth key");
assertIncludes(providerConstants, "COPILOT_AUTH_KEY = \"copilotAuth\"", "provider constants keep Copilot auth key");
assertNotIncludes(providerConstants, "export const CODEX_AUTH_KEY", "provider constants keep Codex auth key internal");
assertNotIncludes(providerConstants, "export const COPILOT_AUTH_KEY", "provider constants keep Copilot auth key internal");
assertIncludes(providerConstants, "function providerAuthStateKeys", "provider constants expose auth state key factory");
assertIncludes(providerConstants, "function providerAuthInitialState", "provider constants expose auth initial state factory");
assertIncludes(providerConstants, "function createProviderAuthInitialStates", "provider constants centralize provider auth initial states");
assertIncludes(providerConstants, "function providerDeviceAuthInitialState", "provider constants share device auth initial state defaults");
assertIncludes(providerConstants, "PROVIDER_AUTH_SECTION_CONFIGS", "provider constants centralize provider auth section metadata");
assertIncludes(providerConstants, "CODEX_AUTH_STATE_KEYS = providerAuthStateKeys(CODEX_AUTH_KEY)", "provider constants keep Codex auth state keys");
assertIncludes(providerConstants, "COPILOT_AUTH_STATE_KEYS = providerAuthStateKeys(COPILOT_AUTH_KEY)", "provider constants keep Copilot auth state keys");
assertIncludes(providerConstants, "connectedNoticeKey: authKey.replace(/Auth$/, \"ProviderConnected\")", "provider constants derive provider connected notices from auth keys");
assertNotIncludes(providerConstants, "export const CODEX_AUTH_STATE_KEYS", "provider constants keep Codex auth state keys internal");
assertNotIncludes(providerConstants, "export const COPILOT_AUTH_STATE_KEYS", "provider constants keep Copilot auth state keys internal");
assertIncludes(providerConstants, "DEFAULT_PROVIDER_AUTH_PROVIDER_ID = PROVIDER_AUTH_SECTION_CONFIGS[0].providerId", "provider constants derive default auth provider from metadata");
assertIncludes(providerConstants, "function providerAuthKeyForId", "provider constants expose provider auth key lookup");
assertIncludes(providerConstants, "initialAuth: providerDeviceAuthInitialState(", "provider constants keep auth initial payloads in provider metadata");
assertIncludes(providerConstants, "deviceKey: \"deviceAuthId\"", "provider constants keep Codex device auth key in metadata");
assertIncludes(providerConstants, "payloadDeviceKey: \"device_auth_id\"", "provider constants keep Codex device auth payload key in metadata");
assertIncludes(providerConstants, "pollRequiresUserCode: true", "provider constants keep Codex poll user code requirement in metadata");
assertIncludes(providerConstants, "includeAccountStatus: true", "provider constants keep Codex account status support in metadata");
assertIncludes(providerConstants, "loginExtra: { command: \"\" }", "provider constants keep Codex login extras in metadata");
assertIncludes(providerConstants, "logoutReset: { expired: false, expires_at: null, account_id: \"\", command: \"\" }", "provider constants keep Codex logout reset state in metadata");
assertIncludes(providerConstants, "deviceKey: \"deviceCode\"", "provider constants keep Copilot device auth key in metadata");
assertIncludes(providerConstants, "payloadDeviceKey: \"device_code\"", "provider constants keep Copilot device auth payload key in metadata");
assertIncludes(providerConstants, "logoutReset: { path: \"\" }", "provider constants keep Copilot logout reset state in metadata");
assertIncludes(providerConstants, "PROVIDER_AUTH_SECTION_CONFIGS.map((config) => providerAuthInitialState(config, config.initialAuth))", "provider constants build auth initial states from provider metadata");
assertNotIncludes(providerConstants, "providerAuthInitialState(CODEX_AUTH_STATE_KEYS", "provider constants avoid Codex-specific auth initial state assembly");
assertNotIncludes(providerConstants, "providerAuthInitialState(COPILOT_AUTH_STATE_KEYS", "provider constants avoid Copilot-specific auth initial state assembly");
assertIncludes(providerHelpers, "providerAuthKeyForId(provider?.provider)", "provider helpers delegate provider auth key lookup");
assertIncludes(providerConstants, "function providerAuthEndpoint", "provider constants expose auth endpoint builder");
assertIncludes(providerConstants, "`/api/settings/auth/${providerId}${action ? `/${action}` : \"\"}`", "provider constants keep auth endpoint path shape");
assertIncludes(providerConstants, "function providerSettingsEndpoint", "provider constants expose provider settings endpoint builder");
assertIncludes(providerConstants, "function providerCredentialEndpoint", "provider constants expose provider credential endpoint builder");
assertIncludes(providerConstants, "function providerAuthRequestConfig", "provider constants expose auth request metadata factory");
assertIncludes(providerConstants, "loginEndpoint: providerAuthEndpoint(providerId, \"login\")", "provider constants keep auth login endpoint metadata");
assertIncludes(providerConstants, "logoutEndpoint: providerAuthEndpoint(providerId, \"logout\")", "provider constants keep auth logout endpoint metadata");
assertIncludes(providerConstants, "pollEndpoint: providerAuthEndpoint(providerId, \"poll\")", "provider constants keep auth poll endpoint metadata");
assertIncludes(providerConstants, "Object.keys(providerAuthStateKeys(\"\"))", "provider constants derive auth request keys from state key factory");
assertIncludes(providerConstants, "PROVIDER_AUTH_REQUEST_KEYS.map((key) => [key, config[key]])", "provider constants keep auth request fields separate from UI provider metadata");
assertIncludes(providerConstants, "OPENAI_CODEX_OAUTH_AUTH_TYPE = \"openai_codex_oauth\"", "provider constants keep Codex OAuth auth type");
assertIncludes(providerConstants, "GITHUB_COPILOT_OAUTH_AUTH_TYPE = \"github_copilot_oauth\"", "provider constants keep Copilot OAuth auth type");
assertIncludes(providerConstants, "function isOAuthProviderAuthType", "provider constants expose OAuth auth type helper");
assertIncludes(providerAuthSections, "providerAuthVisible(", "provider auth sections keep visibility helper");
assertIncludes(providerConstants, "providerId: CODEX_PROVIDER_ID", "provider constants keep Codex auth provider section");
assertIncludes(providerConstants, "providerId: COPILOT_PROVIDER_ID", "provider constants keep Copilot auth provider section");
assertIncludes(providerAuthSections, "PROVIDER_AUTH_SECTION_CONFIGS.map", "provider auth sections consume provider section metadata");
assertIncludes(providerAuthSections, "key: config.providerId", "provider auth sections derive section key from provider id");
assertIncludes(providerConstants, "...CODEX_AUTH_STATE_KEYS", "provider constants reuse Codex auth state keys for section metadata");
assertIncludes(providerConstants, "...COPILOT_AUTH_STATE_KEYS", "provider constants reuse Copilot auth state keys for section metadata");
assertIncludes(providerConstants, "providerName: CODEX_PROVIDER_NAME", "provider constants reuse Codex provider name for section metadata");
assertIncludes(providerConstants, "providerName: COPILOT_PROVIDER_NAME", "provider constants reuse Copilot provider name for section metadata");
assertNotIncludes(providerAuthSections, "CODEX_AUTH_STATE_KEYS", "provider auth sections avoid owning Codex auth state metadata");
assertNotIncludes(providerAuthSections, "COPILOT_AUTH_STATE_KEYS", "provider auth sections avoid owning Copilot auth state metadata");
assertIncludes(providerAuthSections, "`${config.providerName} auth`", "provider auth sections derive default title from provider name");
assertIncludes(providerAuthSections, "authCopy.name || config.providerName", "provider auth sections derive default name from provider name");
assertIncludes(providerAuthSections, "client.loadProviderAuthStatusById(config.providerId)", "provider auth sections refresh through provider id");
assertIncludes(providerAuthSections, "client.startProviderAuthLoginById(config.providerId)", "provider auth sections login through provider id");
assertIncludes(providerAuthSections, "client.logoutProviderAuthById(config.providerId)", "provider auth sections logout through provider id");
assertNotIncludes(providerAuthSections, "key: \"codex\"", "provider auth sections avoid Codex-specific section key metadata");
assertNotIncludes(providerAuthSections, "key: \"copilot\"", "provider auth sections avoid Copilot-specific section key metadata");
assertNotIncludes(providerAuthSections, "refreshAction:", "provider auth sections no longer store action-name strings");
assertNotIncludes(providerAuthSections, "loginAction:", "provider auth sections no longer store login action-name strings");
assertNotIncludes(providerAuthSections, "logoutAction:", "provider auth sections no longer store logout action-name strings");
assertNotIncludes(providerSettingsActions, "const providerAuthStatusConfigs", "provider settings actions no longer own auth status configs");
assertNotIncludes(providerAuthActions, "const providerAuthStatusConfigs", "provider auth actions no longer split auth status configs");
assertIncludes(providerAuthActions, "const providerAuthConfigs = createProviderAuthConfigs();", "provider auth actions assemble auth provider configs");
assertIncludes(providerAuthConfigs, "export function createProviderAuthConfigs", "provider auth configs centralize provider-specific auth config");
assertNotIncludes(providerAuthConfigs, "createProviderAuthRuntimeConfigs", "provider auth configs avoid runtime config assembly");
assertIncludes(providerAuthConfigs, "function resolveProviderAuthConfigId", "provider auth configs keep provider id fallback internal");
assertNotIncludes(providerAuthConfigs, "export function resolveProviderAuthConfigId", "provider auth configs avoid exporting internal provider id fallback");
assertIncludes(providerAuthConfigs, "export function getProviderAuthConfig", "provider auth configs centralize provider config lookup");
assertIncludes(providerAuthConfigs, "DEFAULT_PROVIDER_AUTH_PROVIDER_ID", "provider auth configs use metadata-derived default provider");
assertNotIncludes(providerAuthConfigs, ": CODEX_PROVIDER_ID;", "provider auth configs avoid direct Codex fallback");
assertIncludes(providerAuthActions, "getProviderAuthConfig(providerAuthConfigs, providerId)", "provider auth actions reuse provider config lookup helper");
assertIncludes(providerAuthConfigs, "PROVIDER_AUTH_PROVIDER_IDS", "provider auth configs build configs from provider id metadata");
assertIncludes(providerAuthConfigs, "Object.fromEntries", "provider auth configs derive provider config map from metadata");
assertIncludes(providerAuthConfigs, "providerAuthSectionForId(providerId)", "provider auth configs resolve each provider section by id");
assertNotIncludes(providerAuthConfigs, "CODEX_PROVIDER_ID", "provider auth configs avoid hardcoded Codex config entry");
assertNotIncludes(providerAuthConfigs, "COPILOT_PROVIDER_ID", "provider auth configs avoid hardcoded Copilot config entry");
assertIncludes(providerAuthConfigs, "function deviceAuthBaseConfig", "provider auth configs share device auth base config helper");
assertIncludes(providerAuthConfigs, "deviceAuthBaseConfig(providerAuthSectionForId(providerId))", "provider auth configs reuse shared base config for every provider id");
assertIncludes(providerAuthConfigs, "function deviceAuthPollConfig", "provider auth configs share device auth poll config helper");
assertIncludes(providerAuthConfigs, "...deviceAuthPollConfig(config)", "provider auth configs reuse shared poll config inside base config");
assertIncludes(providerAuthConfigs, "auth[config.deviceKey]", "provider auth configs read device key from metadata");
assertIncludes(providerAuthConfigs, "config.payloadDeviceKey", "provider auth configs read payload key from metadata");
assertNotIncludes(providerAuthConfigs, "\"deviceAuthId\"", "provider auth configs avoid hardcoded Codex device auth key");
assertNotIncludes(providerAuthConfigs, "\"device_auth_id\"", "provider auth configs avoid hardcoded Codex device auth payload key");
assertNotIncludes(providerAuthConfigs, "\"deviceCode\"", "provider auth configs avoid hardcoded Copilot device auth key");
assertNotIncludes(providerAuthConfigs, "\"device_code\"", "provider auth configs avoid hardcoded Copilot device auth payload key");
assertIncludes(providerAuthActions, "loadProviderAuthStatusById,", "provider auth actions expose provider-id auth status action");
assertNotIncludes(providerAuthActions, "async function loadProviderAuthStatus(config)", "provider auth actions avoid status loader wrapper");
assertNotIncludes(providerAuthActions, "async function loadCodexAuthStatus", "provider auth actions avoid Codex-specific status wrapper");
assertNotIncludes(providerAuthActions, "async function loadCopilotAuthStatus", "provider auth actions avoid Copilot-specific status wrapper");
assertIncludes(providerAuthConfigs, "function normalizeConfiguredPathStatus", "provider auth configs share configured/path status normalization");
assertIncludes(providerAuthConfigs, "function normalizeProviderAccountStatus", "provider auth configs share provider account status normalization");
assertIncludes(providerAuthConfigs, "normalizeStatus: (payload) => normalizeConfiguredPathStatus(payload, normalizeProviderAccountStatus(config, payload))", "provider auth configs normalize status through shared provider metadata");
assertIncludes(providerAuthConfigs, "normalizeProviderAccountStatus(config, payload)", "provider auth configs read account status from provider metadata");
assertIncludes(providerAuthRequests, "export function requestProviderAuthStatus", "provider auth requests centralize auth status request");
assertIncludes(providerAuthRequests, "requestSettingsJson(config.endpoint)", "provider auth requests keep shared auth status request");
assertIncludes(providerAuthActions, "requestProviderAuthStatus(requestSettingsJson, config)", "provider auth actions delegate auth status request");
assertIncludes(providerSettingsLoader, "export async function loadProviderSettingsState", "provider settings loader centralizes provider list loading");
assertIncludes(providerSettingsLoader, "requestSettingsJson(\"/api/settings/providers\")", "provider settings loader keeps provider catalog request");
assertIncludes(providerSettingsLoader, "requestSettingsJson(\"/api/settings/credentials\")", "provider settings loader keeps credential catalog request");
assertIncludes(providerSettingsActions, "loadProviderSettingsState(settingsState, requestSettingsJson, copy)", "provider settings actions delegate provider list loading");
assertNotIncludes(providerSettingsActions, "requestSettingsJson(\"/api/settings/providers\")", "provider settings actions no longer own provider catalog request");
assertNotIncludes(providerSettingsActions, "const oauthProviderConfigs", "provider settings actions no longer own OAuth provider configs");
assertNotIncludes(providerAuthActions, "const oauthProviderConfigs", "provider auth actions fold OAuth metadata into auth provider configs");
assertIncludes(providerSettingsRequests, "export function requestProviderConnect", "provider settings requests centralize provider connect request");
assertIncludes(providerSettingsRequests, "providerSettingsEndpoint(form.providerId, \"connect\")", "provider settings requests keep provider connect endpoint helper");
assertIncludes(providerSettingsActions, "requestProviderConnect(requestSettingsJson, settingsState.connectForm)", "provider settings actions delegate provider connect request");
assertNotIncludes(providerSettingsActions, "providerSettingsEndpoint(", "provider settings actions no longer own provider endpoint assembly");
assertIncludes(providerSettingsActions, "createProviderConnectForm(provider)", "provider settings actions reuse provider connect form helper");
assertIncludes(providerConnectForm, "export function createEmptyProviderConnectForm", "provider connect form centralizes empty form state");
assertIncludes(providerConnectForm, "export function createProviderConnectForm", "provider connect form centralizes provider-derived form state");
assertIncludes(providerConnectForm, "export function resetProviderConnectForm", "provider connect form centralizes connect form reset");
assertIncludes(providerConnectForm, "export function providerConnectPayloadFromForm", "provider connect form centralizes connect payload shape");
assertIncludes(providerSettingsRequests, "providerConnectPayloadFromForm(form)", "provider settings requests reuse connect payload helper");
assertIncludes(providerConnectForm, "export function providerOAuthConnectPayload", "provider connect form centralizes OAuth connect payload shape");
assertIncludes(providerAuthRequests, "providerOAuthConnectPayload(provider, options)", "provider auth requests reuse OAuth connect payload helper");
assertIncludes(providerConnectForm, "export function providerCredentialPayload", "provider connect form centralizes credential payload shape");
assertIncludes(providerSettingsRequests, "providerCredentialPayload(credentialId)", "provider settings requests reuse credential payload helper");
assertIncludes(providerHelpers, "export function providerCatalogKey", "provider helpers centralize provider key resolution");
assertIncludes(providerHelpers, "providerCatalogKey(provider) === presetId", "provider helpers reuse provider key resolution for connected providers");
assertIncludes(providerHelpers, "const providerKey = providerCatalogKey(provider)", "provider helpers reuse provider key resolution for credentials");
assertIncludes(providerSettingsActions, "providerCatalogKey(provider)", "provider settings actions reuse shared provider key helper");
assertNotIncludes(providerConnectForm, "providerCredentialKey", "provider connect form no longer owns provider key resolution");
assertNotIncludes(providerSettingsActions, "providerCredentialKey", "provider settings actions avoid form-owned provider key helper");
assertIncludes(useSettingsState, "connectForm: createEmptyProviderConnectForm()", "settings state reuses provider connect form defaults");
assertIncludes(chatClient, "resetProviderConnectForm(settingsState.connectForm)", "chat client reuses provider connect form reset helper");
assertNotIncludes(chatClient, "Object.assign(settingsState.connectForm, createEmptyProviderConnectForm())", "chat client no longer owns provider connect form reset fields");
assertIncludes(chatClient, "const loadSettingsSection = createSettingsSectionLoader({", "chat client delegates settings section loading");
assertNotIncludes(chatClient, "function loadSettingsSection(sectionName)", "chat client no longer owns settings section loader dispatch");
assertIncludes(settingsSectionLoaders, "export function createSettingsSectionLoader", "settings section loaders centralize section dispatch");
assertIncludes(settingsSectionLoaders, "providers: () => {", "settings section loaders keep provider section loader");
assertIncludes(settingsSectionLoaders, "loadProviderSettings();", "settings section loaders keep provider settings refresh");
assertIncludes(settingsSectionLoaders, "PROVIDER_AUTH_PROVIDER_IDS", "settings section loaders use shared provider auth refresh list");
assertIncludes(settingsSectionLoaders, "loadProviderAuthStatusById(providerId)", "settings section loaders refresh auth through provider id");
assertIncludes(settingsSectionLoaders, "loadScheduleSettings();", "settings section loaders keep schedule settings refresh");
assertIncludes(settingsSectionLoaders, "loadCronJobs();", "settings section loaders keep cron jobs refresh");
assertIncludes(providerSettingsRequests, "export function requestProviderDisconnect", "provider settings requests centralize provider disconnect request");
assertIncludes(providerSettingsRequests, "export function requestProviderCredentialUpdate", "provider settings requests centralize provider credential update request");
assertIncludes(providerSettingsRequests, "export function requestProviderCredentialDelete", "provider settings requests centralize provider credential delete request");
assertIncludes(providerSettingsRequests, "providerSettingsEndpoint(provider.id, \"disconnect\")", "provider settings requests keep provider disconnect endpoint helper");
assertIncludes(providerSettingsRequests, "providerSettingsEndpoint(provider.id, \"credential\")", "provider settings requests keep provider credential endpoint helper");
assertIncludes(providerSettingsRequests, "providerCredentialEndpoint(providerKey, credentialId)", "provider settings requests keep credential endpoint helper");
assertIncludes(providerSettingsActions, "requestProviderDisconnect(requestSettingsJson, provider)", "provider settings actions delegate provider disconnect request");
assertIncludes(providerSettingsActions, "requestProviderCredentialUpdate(requestSettingsJson, provider, credentialId)", "provider settings actions delegate provider credential update request");
assertIncludes(providerSettingsActions, "requestProviderCredentialDelete(requestSettingsJson, providerKey, credentialId)", "provider settings actions delegate provider credential delete request");
assertIncludes(providerMutationRunner, "export async function runProviderMutation", "provider mutation runner centralizes provider mutation lifecycle");
assertIncludes(providerMutationRunner, "settingsState.providersLoading = true", "provider mutation runner sets provider loading");
assertIncludes(providerMutationRunner, "settingsState.providersNotice = \"\"", "provider mutation runner clears provider notice");
assertIncludes(providerMutationRunner, "await options.after?.();", "provider mutation runner supports shared success follow-up");
assertIncludes(providerSettingsActions, "async function runProviderSettingsMutation", "provider settings actions centralize mutation refresh");
assertIncludes(providerSettingsActions, "runProviderMutation(settingsState, fallbackNotice, action, { after: refreshProviderState })", "provider settings mutation helper refreshes after success");
assertIncludes(providerSettingsActions, "await runProviderSettingsMutation(copy.value.notices.providerConnectFailed", "provider connect uses settings mutation helper");
assertIncludes(providerSettingsActions, "await runProviderSettingsMutation(copy.value.notices.providerDisconnectFailed", "provider disconnect uses settings mutation helper");
assertIncludes(providerSettingsActions, "await runProviderSettingsMutation(copy.value.notices.providerCredentialUpdateFailed", "provider credential update uses settings mutation helper");
assertIncludes(providerSettingsActions, "await runProviderSettingsMutation(copy.value.notices.providerCredentialDeleteFailed", "provider credential delete uses settings mutation helper");
assertIncludes(providerAuthActions, "await runProviderMutation(settingsState, copy.value.notices.providerConnectFailed", "provider auth OAuth connect uses shared provider mutation lifecycle");
assertIncludes(providerAuthActions, "after: async () => {", "provider auth OAuth connect uses shared success follow-up");
assertIncludes(providerAuthActions, "await refreshProviderState();", "provider auth OAuth connect refreshes provider state after connect");
assertIncludes(providerAuthActions, "await startProviderAuthLoginById(config.providerId);", "provider auth OAuth connect starts login after refresh");
assertIncludes(providerAuthActions, "copy.value.notices[config.connectedNoticeKey]", "provider auth OAuth connect resolves provider notice from metadata");
assertIncludes(providerAuthRequests, "export function requestProviderOAuthConnect", "provider auth requests centralize OAuth connect request");
assertIncludes(providerAuthRequests, "providerSettingsEndpoint(providerId, \"connect\")", "provider auth requests keep provider connect endpoint helper");
assertIncludes(providerAuthActions, "requestProviderOAuthConnect(requestSettingsJson, provider, config)", "provider auth actions delegate OAuth connect request");
assertNotIncludes(providerAuthActions, "providerSettingsEndpoint(", "provider auth actions no longer own provider endpoint assembly");
assertNotIncludes(providerAuthActions, "function providerAuthRuntimeConfig", "provider auth actions no longer own runtime config fields");
assertNotIncludes(providerAuthConfigs, "connectedNoticeKey: \"codexProviderConnected\"", "provider auth configs avoid hardcoded Codex connected notice key");
assertNotIncludes(providerAuthConfigs, "connectedNoticeKey: \"copilotProviderConnected\"", "provider auth configs avoid hardcoded Copilot connected notice key");
assertNotIncludes(providerAuthConfigs, "startAuthLogin", "provider auth configs avoid auth login closure");
assertNotIncludes(providerAuthConfigs, "loadStatus", "provider auth configs avoid auth status loading closure");
assertNotIncludes(providerAuthConfigs, "connectedNotice: () =>", "provider auth configs avoid notice lookup closures");
assertNotIncludes(providerAuthConfigs, "copy.value.notices", "provider auth configs avoid owning localized copy lookup");
assertNotIncludes(providerAuthConfigs, "providerName", "provider auth configs avoid UI display metadata");
assertIncludes(providerAuthConfigs, "normalizeDeviceAuthLogin", "provider auth configs reuse device login normalization");
assertIncludes(providerAuthState, "export function normalizeDeviceAuthLogin", "provider auth state centralizes device login normalization");
assertIncludes(providerAuthConfigs, "normalizeDeviceAuthLogin(payload, config.deviceKey, config.payloadDeviceKey, config.loginExtra)", "provider auth configs keep device auth login normalization through metadata");
assertNotIncludes(providerAuthConfigs, "codexAuthConfig.payloadDeviceKey, { command: \"\" }", "provider auth configs avoid hardcoded Codex login extras");
assertIncludes(providerAuthConfigs, "function normalizeAuthorizedDeviceAuth", "provider auth configs share authorized device auth normalization");
assertIncludes(providerAuthConfigs, "function resetDeviceAuthLogout", "provider auth configs share device auth logout reset");
assertIncludes(providerAuthConfigs, "clearedDeviceAuthState", "provider auth configs reuse cleared device auth state");
assertIncludes(providerAuthState, "export function clearedDeviceAuthState", "provider auth state centralizes cleared device auth state");
assertIncludes(providerAuthConfigs, "resetDeviceAuthLogout(auth, config.deviceKey, config.logoutReset)", "provider auth configs read logout reset from metadata");
assertNotIncludes(providerAuthConfigs, "resetDeviceAuthLogout(auth, codexAuthConfig.deviceKey, {", "provider auth configs avoid hardcoded Codex logout reset state");
assertNotIncludes(providerAuthConfigs, "resetDeviceAuthLogout(auth, copilotAuthConfig.deviceKey, { path: \"\" })", "provider auth configs avoid hardcoded Copilot logout reset state");
assertIncludes(providerAuthConfigs, "normalizeAuthorized: (auth, currentAuth) => normalizeAuthorizedDeviceAuth(auth, currentAuth, config.deviceKey, normalizeProviderAccountStatus(config, auth))", "provider auth configs normalize authorized auth through shared provider metadata");
assertIncludes(providerAuthConfigs, "normalizeProviderAccountStatus(config, auth)", "provider auth configs read authorized account status from provider metadata");
assertIncludes(providerAuthActions, "settingsState[config.noticeKey]", "provider auth actions reuse provider auth notice state key");
assertIncludes(providerAuthActions, "const config = getProviderAuthConfig(providerAuthConfigs, providerCatalogKey(provider))", "provider auth actions reuse shared provider key helper for OAuth connect");
assertNotIncludes(providerAuthActions, "connectOAuthBackedProvider", "provider auth actions avoid OAuth connect wrapper");
assertNotIncludes(providerAuthActions, "async function connectCodexProvider", "provider auth actions avoid unused Codex-specific OAuth wrapper");
assertNotIncludes(providerAuthActions, "async function connectCopilotProvider", "provider auth actions avoid unused Copilot-specific OAuth wrapper");
assertNotIncludes(providerAuthActions, "function resolveProviderAuthId", "provider auth actions no longer own provider id fallback");
assertNotIncludes(providerAuthActions, "connectOAuthProviderById", "provider auth actions avoid OAuth provider id wrapper");
assertIncludes(useSettingsState, "createProviderAuthInitialStates()", "settings state initializes provider auth through provider metadata");
assertNotIncludes(useSettingsState, "deviceAuthId", "settings state avoids Codex device auth field ownership");
assertNotIncludes(useSettingsState, "deviceCode", "settings state avoids Copilot device auth field ownership");
assertIncludes(chatClient, "useProviderAuthActions({", "chat client delegates provider auth actions");
assertIncludes(chatClient, "clearProviderAuthPollTimers();", "chat client clears delegated provider auth poll timers");
assertNotIncludes(chatClient, "const providerAuthPollTimers", "chat client no longer owns provider auth poll timers");
assertIncludes(providerAuthActions, "createProviderAuthPollTimers()", "provider auth actions delegate provider auth poll timer storage");
assertIncludes(providerAuthPollTimers, "const providerAuthPollTimers = new Map()", "provider auth poll timers centralize provider auth poll timers");
assertIncludes(providerAuthPollTimers, "providerAuthPollTimers.set(providerId", "provider auth poll timers store auth poll timers by provider id");
assertIncludes(providerAuthPollTimers, "window.setTimeout", "provider auth poll timers keep browser timer scheduling");
assertNotIncludes(providerAuthConfigs, "clearPoll", "provider auth configs avoid auth poll clearing closure");
assertIncludes(providerAuthActions, "clearProviderAuthPollTimer(config.providerId)", "provider auth actions clear polling through provider id");
assertNotIncludes(providerAuthConfigs, "schedulePoll", "provider auth configs avoid auth poll scheduling closure");
assertIncludes(providerAuthActions, "scheduleProviderAuthPoll(config.providerId, settingsState[config.authKey]", "provider auth actions schedule polling through resolved provider config");
assertIncludes(providerAuthActions, "scheduleProviderAuthPollById(config.providerId)", "provider auth actions reschedule polling through provider id");
assertNotIncludes(chatClient, "let codexAuthPollTimer", "chat client removes split Codex auth timer state");
assertNotIncludes(chatClient, "let copilotAuthPollTimer", "chat client removes split Copilot auth timer state");
assertNotIncludes(providerAuthActions, "const providerAuthFlowConfigs", "provider auth actions no longer split auth flow configs");
assertIncludes(providerAuthConfigs, "providerAuthSectionForId", "provider auth configs reuse centralized auth section lookup");
assertIncludes(providerAuthConfigs, "providerAuthRequestConfig(config)", "provider auth configs build request metadata from provider section lookup");
assertNotIncludes(providerAuthConfigs, "PROVIDER_AUTH_SECTIONS", "provider auth configs avoid local auth section indexes");
assertNotIncludes(providerAuthConfigs, "CODEX_AUTH_STATE_KEYS", "provider auth configs avoid direct Codex auth state key ownership");
assertNotIncludes(providerAuthConfigs, "COPILOT_AUTH_STATE_KEYS", "provider auth configs avoid direct Copilot auth state key ownership");
assertIncludes(providerAuthConfigs, "[config.payloadDeviceKey]: auth[config.deviceKey]", "provider auth configs build device auth poll body from metadata");
assertIncludes(providerAuthConfigs, "config.pollRequiresUserCode ? { user_code: auth.userCode } : {}", "provider auth configs keep optional user code poll body through metadata");
assertNotIncludes(providerAuthConfigs, "buildPollBody: (auth) => ({ [codexAuthConfig.payloadDeviceKey]", "provider auth configs avoid hardcoded Codex poll body");
assertNotIncludes(providerAuthConfigs, "buildPollBody: (auth) => ({ [copilotAuthConfig.payloadDeviceKey]", "provider auth configs avoid hardcoded Copilot poll body");
assertIncludes(providerAuthActions, "startProviderAuthLoginById,", "provider auth actions expose provider-id auth login action");
assertIncludes(providerAuthActions, "logoutProviderAuthById,", "provider auth actions expose provider-id auth logout action");
assertNotIncludes(providerAuthActions, "async function startProviderAuthLogin(config)", "provider auth actions avoid login action wrapper");
assertNotIncludes(providerAuthActions, "async function logoutProviderAuth(config)", "provider auth actions avoid logout action wrapper");
assertNotIncludes(providerAuthActions, "async function pollProviderAuthLogin(config)", "provider auth actions avoid poll action wrapper");
assertNotIncludes(providerAuthActions, "async function startCodexAuthLogin", "provider auth actions avoid Codex-specific login wrapper");
assertNotIncludes(providerAuthActions, "async function startCopilotAuthLogin", "provider auth actions avoid Copilot-specific login wrapper");
assertNotIncludes(providerAuthActions, "async function logoutCodexAuth", "provider auth actions avoid Codex-specific logout wrapper");
assertNotIncludes(providerAuthActions, "async function logoutCopilotAuth", "provider auth actions avoid Copilot-specific logout wrapper");
assertNotIncludes(providerAuthActions, "async function pollCodexAuthLogin", "provider auth actions avoid unused Codex-specific poll wrapper");
assertNotIncludes(providerAuthActions, "async function pollCopilotAuthLogin", "provider auth actions avoid unused Copilot-specific poll wrapper");
assertIncludes(providerAuthActionRunner, "export function setProviderAuthError", "provider auth action runner centralizes auth error state");
assertIncludes(providerAuthActionRunner, "setProviderAuthError(settingsState, copy, config, fallbackNoticeKey, error)", "provider auth action lifecycle reuses auth error helper");
assertIncludes(providerAuthActionRunner, "export async function runProviderAuthAction", "provider auth action runner centralizes auth action lifecycle");
assertIncludes(providerAuthActionRunner, "await options.after?.();", "provider auth action runner supports shared success follow-up");
assertIncludes(providerAuthActions, "import { runProviderAuthAction, setProviderAuthError } from \"./providerAuthActionRunner\"", "provider auth actions reuse auth action lifecycle helpers");
assertIncludes(providerAuthActions, "await runProviderAuthAction(settingsState, copy, config, config.loadFailedNoticeKey", "provider auth status uses shared action lifecycle");
assertIncludes(providerAuthActions, "await runProviderAuthAction(settingsState, copy, config, config.loginFailedNoticeKey", "provider auth login uses shared action lifecycle");
assertIncludes(providerAuthActions, "await runProviderAuthAction(settingsState, copy, config, config.logoutFailedNoticeKey", "provider auth logout uses shared action lifecycle");
assertIncludes(providerAuthActions, "after: () => loadProviderAuthStatusById(config.providerId)", "provider auth logout refreshes status after logout through provider id");
assertIncludes(providerAuthActions, "setProviderAuthError(settingsState, copy, config, config.loginFailedNoticeKey, error)", "provider auth polling reuses auth error helper");
assertIncludes(providerAuthRequests, "export function requestProviderAuthLogin", "provider auth requests centralize auth login request");
assertIncludes(providerAuthRequests, "export function requestProviderAuthPoll", "provider auth requests centralize auth poll request");
assertIncludes(providerAuthRequests, "export function requestProviderAuthLogout", "provider auth requests centralize auth logout request");
assertIncludes(providerAuthRequests, "requestSettingsJson(config.loginEndpoint, { method: \"POST\" })", "provider auth requests keep shared auth login request");
assertIncludes(providerAuthRequests, "requestSettingsJson(config.logoutEndpoint, { method: \"POST\" })", "provider auth requests keep shared auth logout request");
assertIncludes(providerAuthRequests, "requestSettingsJson(config.pollEndpoint", "provider auth requests keep shared auth poll request");
assertIncludes(providerAuthRequests, "config.buildPollBody(pendingAuth)", "provider auth requests keep provider-specific poll payload");
assertIncludes(providerAuthActions, "requestProviderAuthLogin(requestSettingsJson, config)", "provider auth actions delegate auth login request");
assertIncludes(providerAuthActions, "requestProviderAuthPoll(requestSettingsJson, config, pendingAuth)", "provider auth actions delegate auth poll request");
assertIncludes(providerAuthActions, "requestProviderAuthLogout(requestSettingsJson, config)", "provider auth actions delegate auth logout request");
assertNotIncludes(providerAuthActions, "requestSettingsJson(config.loginEndpoint", "provider auth actions no longer own auth login request");
assertNotIncludes(providerAuthActions, "requestSettingsJson(config.pollEndpoint", "provider auth actions no longer own auth poll request");
assertNotIncludes(providerAuthActions, "requestSettingsJson(config.logoutEndpoint", "provider auth actions no longer own auth logout request");
assertIncludes(providerSettings, "AvailableProvidersSection", "provider settings delegates available providers section");
assertIncludes(providerSettings, "ConnectedProvidersSection", "provider settings delegates connected providers section");
assertIncludes(providerSettings, "ProviderConnectDialog", "provider settings delegates provider connect dialog");
assertIncludes(providerHelpers, "export function selectedConnectProvider", "provider helpers centralize connect dialog provider selection");
assertIncludes(providerSettings, "selectedConnectProvider(providers, state.connectForm.providerId)", "provider settings delegates connect provider selection");
assertNotIncludes(providerSettings, "...(providers.available || []), ...(providers.connected || [])", "provider settings no longer owns connect provider list merge");
assertIncludes(providerAuthSection, "SettingsSectionTitle", "provider auth section keeps section title");
assertIncludes(providerAuthSection, "SettingsStatus message={notice}", "provider auth section keeps notice status");
assertIncludes(providerAuthSection, "SettingsStatus message={error} type=\"error\"", "provider auth section keeps error status");
assertIncludes(providerAuthSection, "AuthProviderCard", "provider auth section renders auth provider card");
assertIncludes(providerAuthSection, "onLogin={onLogin}", "provider auth section keeps login action");
assertIncludes(providerHelpers, "hasConnectedProvider(state, providerId)", "provider auth visibility includes connected provider state");
assertIncludes(providerHelpers, "auth?.userCode || notice || error", "provider auth visibility includes pending auth state");
assertIncludes(authProviderCard, "codex-auth-row", "auth provider card keeps auth row layout");
assertIncludes(authProviderCard, "onClick={onRefresh}", "auth provider card keeps refresh action");
assertIncludes(authProviderCard, "onClick={onLogin}", "auth provider card keeps login action");
assertIncludes(authProviderCard, "onClick={onLogout}", "auth provider card keeps logout action");
assertIncludes(authProviderCard, "auth.userCode", "auth provider card keeps user code display");
assertIncludes(availableProvidersSection, "AvailableProviderRow", "available providers delegates available provider row");
assertIncludes(availableProvidersSection, "ProviderEmptyState", "available providers delegates provider empty state");
assertIncludes(availableProvidersSection, "providerCopy.noAvailableTitle", "available providers keeps empty state title");
assertIncludes(providerEmptyState, "provider-row--empty", "provider empty state keeps row class");
assertIncludes(providerEmptyState, "<strong>{title}</strong>", "provider empty state keeps title");
assertIncludes(providerEmptyState, "<span>{description}</span>", "provider empty state keeps description");
assertIncludes(availableProviderRow, "isOAuthProviderAuthType(provider.auth_type)", "available provider row keeps OAuth detection");
assertIncludes(availableProviderRow, "onConnectOAuth(provider) : onBeginConnect(provider)", "available provider row keeps connect routing");
assertIncludes(availableProviderRow, "providerCopy.builtInBadge", "available provider row keeps built-in badge");
assertIncludes(availableProviderRow, "providerCopy.connectedCount", "available provider row keeps connected count badge");
assertIncludes(connectedProvidersSection, "ConnectedProviderRow", "connected providers delegates connected provider row");
assertIncludes(connectedProvidersSection, "ProviderEmptyState", "connected providers delegates provider empty state");
assertIncludes(connectedProviderRow, "providerCredentials(state, provider)", "connected provider row keeps credential lookup");
assertIncludes(connectedProviderRow, "providerEffectiveCredentialId(provider)", "connected provider row keeps effective credential lookup");
assertIncludes(connectedProviderRow, "providerAuthKey(provider)", "connected provider row keeps provider auth key lookup");
assertIncludes(connectedProviderRow, "providerAuthConfigured(state, provider)", "connected provider row keeps auth configured badge rule");
assertIncludes(connectedProviderRow, "onSetCredential(provider, value)", "connected provider row keeps credential switch action");
assertIncludes(connectedProviderRow, "onDeleteCredential(provider, effectiveCredentialId)", "connected provider row keeps credential deletion action");
assertIncludes(connectedProviderRow, "onDisconnect(provider)", "connected provider row keeps disconnect action");
assertIncludes(connectedProviderRow, "provider-row__credential--missing", "connected provider row keeps missing credential state");
assertIncludes(providerConnectDialog, "role=\"dialog\"", "provider connect dialog keeps dialog role");
assertIncludes(providerConnectDialog, "provider.requires_api_key !== false || provider.api_key_optional === true", "provider connect dialog keeps API key requirement rule");
assertIncludes(providerConnectDialog, "state.connectForm.showAdvanced = !state.connectForm.showAdvanced", "provider connect dialog keeps advanced toggle");
assertIncludes(providerConnectDialog, "state.connectForm.baseUrl", "provider connect dialog keeps base URL field");
assertIncludes(providerConnectDialog, "onFinish={() => onSave()}", "provider connect dialog keeps save action");
assertIncludes(providerConnectDialog, "onClick={onCancel}", "provider connect dialog keeps cancel actions");
assertNotIncludes(providerConstants, "[CODEX_PROVIDER_ID]: CODEX_AUTH_STATE_KEYS.authKey", "provider constants avoid duplicate Codex auth key map");
assertNotIncludes(providerConstants, "[COPILOT_PROVIDER_ID]: COPILOT_AUTH_STATE_KEYS.authKey", "provider constants avoid duplicate Copilot auth key map");
assertIncludes(providerHelpers, "export function providerAuthDescription", "provider helpers centralize provider auth descriptions");
assertIncludes(providerHelpers, "state[config.authKey]", "provider helpers read auth state through section config");
assertIncludes(providerHelpers, "copy.settings.providers?.[config.copyKey]", "provider helpers read auth copy through section config");
assertIncludes(providerAuthSections, "providerAuthDescription(copy, state, config)", "provider auth sections delegate description to config-based helper");
assertNotIncludes(providerAuthSections, "PROVIDER_AUTH_DESCRIPTIONS", "provider auth sections avoid per-provider description maps");
assertNotIncludes(providerHelpers, "CODEX_AUTH_CONFIG", "provider helpers avoid direct Codex auth config ownership");
assertNotIncludes(providerHelpers, "COPILOT_AUTH_CONFIG", "provider helpers avoid direct Copilot auth config ownership");
assertNotIncludes(providerHelpers, "CODEX_AUTH_STATE_KEYS", "provider helpers avoid direct Codex auth state key ownership");
assertNotIncludes(providerHelpers, "COPILOT_AUTH_STATE_KEYS", "provider helpers avoid direct Copilot auth state key ownership");
assertIncludes(modelSettings, "client.saveMediaModel", "model settings keeps media model save action");
assertIncludes(channelSettings, "client.beginChannelConnect", "channel settings keeps add channel flow");
assertIncludes(mcpSettings, "client.toggleMcpAdvanced", "MCP settings keeps advanced editor");
assertIncludes(mcpSettings, "client.toggleMcpJsonInput", "MCP settings keeps JSON editor");
assertIncludes(mcpSettings, "client.applyMcpJson", "MCP settings keeps JSON import action");
assertIncludes(mcpSettings, "form.envJson", "MCP settings keeps environment JSON field");
assertIncludes(mcpSettings, "form.headersJson", "MCP settings keeps headers JSON field");
assertIncludes(scheduleSettings, "state.scheduleForm.defaultTimezone", "schedule settings keeps default timezone field");
assertIncludes(scheduleSettings, "client.saveScheduleSettings", "schedule settings keeps default save action");
assertIncludes(scheduleSettings, "client.saveCronJob", "schedule settings keeps cron editor save");
assertIncludes(scheduleSettings, "client.runCronJobAction(job, job.enabled ? \"pause\" : \"enable\")", "schedule settings keeps pause/enable action");
assertIncludes(scheduleSettings, "client.runCronJobAction(job, \"run\")", "schedule settings keeps run-now action");
assertIncludes(scheduleSettings, "client.runCronJobAction(job, \"remove\")", "schedule settings keeps remove action");
assertIncludes(scheduleSettings, "form.deliver", "schedule settings keeps delivery toggle");
assertIncludes(networkSettings, "form.httpProxy", "network settings keeps HTTP proxy field");
assertIncludes(networkSettings, "form.httpsProxy", "network settings keeps HTTPS proxy field");
assertIncludes(networkSettings, "form.noProxy", "network settings keeps no proxy field");
assertNotIncludes(networkSettings, "state.networkForm.enabled", "network settings does not show unsupported enabled field");
assertIncludes(searchSettings, "client.saveSearchSettings", "search settings keeps save action");
assertIncludes(searchSettings, "client.loadSearxngOptions", "search settings keeps SearXNG option load action");
assertIncludes(searchSettings, "form.jinaApiKey", "search settings keeps Jina API key field");
assertIncludes(searchSettings, "form.searxngEngines", "search settings keeps SearXNG engine selection");
assertIncludes(searchSettings, "form.searxngCategories", "search settings keeps SearXNG category selection");
assertIncludes(logSettings, "client.saveLogSettings", "log settings keeps save action");
assertIncludes(logSettings, "form.retentionDays", "log settings keeps retention field");
assertIncludes(logSettings, "form.logSystemPrompt", "log settings keeps system prompt toggle");
assertIncludes(logSettings, "form.logSystemPromptLines", "log settings keeps system prompt line limit");
assertIncludes(logSettings, "form.logReasoningDetails", "log settings keeps reasoning detail toggle");
assertIncludes(browserSettings, "form.commandTimeout", "browser settings keeps command timeout");
assertIncludes(browserSettings, "form.sessionTimeout", "browser settings keeps session timeout");
assertIncludes(browserSettings, "form.allowPrivateUrls", "browser settings keeps private URL toggle");
assertIncludes(browserSettings, "client.runBrowserDoctor", "browser settings keeps doctor action");
assertIncludes(browserSettings, "client.runBrowserInstall", "browser settings keeps install action");
assertNotIncludes(browserSettings, "sessionTimeoutSeconds", "browser settings avoids stale session timeout field");
assertIncludes(shortcutSettings, "shortcut-keys", "shortcut settings uses parity layout");
assertIncludes(settingsPrimitives, "function SettingsCard", "settings pages use Ant card helper");
assertIncludes(generalSettings, "<SettingsCard className=\"settings-card--form\"", "general settings form cards use Ant card helper");
assertIncludes(generalSettings, "<Select", "general settings uses Ant Select controls");
assertIncludes(generalSettings, "<Switch", "general settings uses Ant Switch controls");
assertIncludes(generalSettings, "<Input", "general settings uses Ant Input controls");
assertNotIncludes(openSpriteShell, "<button", "app shell avoids raw button elements");
assertNotIncludes(openSpriteShell, "<input", "app shell avoids raw input elements");
assertNotIncludes(openSpriteShell, "<select", "app shell avoids raw select elements");
assertNotIncludes(openSpriteShell, "<textarea", "app shell avoids raw textarea elements");
assertIncludes(runInspector, "RunHistorySelector", "run inspector delegates run history selector");
assertIncludes(runInspector, "RunSummaryCard", "run inspector delegates run summary card");
assertIncludes(runInspector, "RunTimeline", "run inspector delegates run timeline");
assertIncludes(runInspector, "RunTraceViewer", "run inspector delegates run trace viewer");
assertIncludes(runInspector, "WorkStateCard", "run inspector delegates work state card");
assertIncludes(settingsModal, "SettingsNav", "settings modal uses the parity sidebar nav");
assertIncludes(settingsModal, "className=\"settings-nav__menu\"", "settings nav uses Ant menu");
assertIncludes(settingsModal, "selectedKeys={[section]}", "settings nav marks active section");
assertIncludes(settingsModal, "selectSection(String(key))", "settings nav changes active section");
assertIncludes(settingsModal, "renderSettingsSection", "settings modal renders only the active section");
assertIncludes(settingsModal, "settings-page--loading", "settings modal defers heavy section content");
assertIncludes(settingsModal, "<GeneralSettings client={pageClient} clearWebSessions={clearWebSessions}", "settings modal wires general settings cleanup prop");
assertIncludes(settingsModal, "<ProviderSettings client={pageClient}", "settings modal wires provider settings");
assertNotIncludes(settingsModal, "const contentBySection", "settings modal should not build a section map during render");
assertIncludes(styles, ".settings-page--loading", "settings deferred loading state is styled");
assertIncludes(styles, ".settings-nav__menu .ant-menu-item-selected", "settings nav selected state is styled through Ant");
assertRegex(runHistorySelector, /className=\"run-history__select\"[\s\S]+<Select[\s\S]+client\.selectRun\(value\)/, "run history selector changes active run");
assertIncludes(runSummaryCard, "className=\"run-summary-card\"", "run summary card keeps card class");
assertIncludes(runSummaryCard, "cleanupWorktreeSandbox(run)", "run summary card keeps cleanup sandbox action");
assertIncludes(runSummaryCard, "summary.status || run.status", "run summary card keeps status fallback");
assertIncludes(runSummaryCard, "summary.result || summary.final_answer", "run summary card keeps result fallback");
assertIncludes(runSummaryCard, "run.summaryError", "run summary card keeps summary error state");
assertIncludes(runTimeline, "className=\"run-timeline\"", "run timeline keeps card class");
assertIncludes(runTimeline, "copy.timeline?.title || copy.runHistory.title", "run timeline keeps fallback title");
assertIncludes(runTimeline, "event.tone === \"error\" ? \"red\"", "run timeline keeps event tone mapping");
assertIncludes(runTimeline, "Empty.PRESENTED_IMAGE_SIMPLE", "run timeline keeps empty state");
assertIncludes(runTraceViewer, "JSON.stringify({ run, exported_at", "trace viewer keeps debug JSON export");
assertIncludes(runTraceViewer, "URL.revokeObjectURL(url)", "trace viewer releases debug JSON URL");
assertIncludes(runTraceViewer, "events.slice(-120)", "trace viewer keeps event limit");
assertIncludes(runTraceViewer, "revertFileChange(run, change)", "trace viewer keeps file revert action");
assertIncludes(runTraceViewer, "cancelRun(run)", "trace viewer keeps cancel action");
assertIncludes(runTraceViewer, "defaultActiveKey={[\"artifacts\"]}", "trace viewer keeps default section");
assertIncludes(workStateCard, "className=\"work-state-card\"", "work state card keeps card class");
assertIncludes(workStateCard, "client.resumeFollowUp", "work state card keeps continue action");
assertIncludes(workStateCard, "client.runVerification", "work state card keeps verify action");
assertIncludes(workStateCard, "next_steps.slice(0, 4)", "work state card keeps next step limit");
assertNotIncludes(openSpriteShell, "BackgroundProcessSidebar", "background process sidebar stays removed");
assertNotIncludes(openSpriteShell, "CuratorSettingsPage", "curator settings page stays removed");

for (const exportName of ["ref", "silentRef", "reactive", "computed", "watch", "onMounted", "onBeforeUnmount", "useReactiveStore"]) {
  assertRegex(reactiveCompat, new RegExp(`export function ${exportName}\\b`), `reactive compat export ${exportName}`);
}

assertIncludes(chatClient, "../lib/reactiveCompat", "chat client uses React-compatible reactivity bridge");
assertNotIncludes(chatClient, "from \"vue\"", "chat client no longer imports Vue runtime");
assertIncludes(chatClient, "silentRef(null)", "DOM refs do not trigger React render loops");
assertIncludes(chatClient, "new WebSocket", "chat WebSocket flow retained");
assertIncludes(chatClient, "activeSocket.send", "chat send flow retained");
assertIncludes(chatClient, "loadCurrentSessionRuns", "run history loading retained");
assertIncludes(chatClient, "maybeLoadRunTraceForSession", "trace loading retained");
assertIncludes(chatClient, "STORAGE_KEYS.showRunHistory", "run history preference retained");
assertIncludes(chatClient, "STORAGE_KEYS.showWorkState", "work state preference retained");
assertIncludes(chatClient, "deferSettingsWork", "settings loads are deferred after opening");
assertIncludes(chatClient, "window.requestAnimationFrame", "settings deferred work yields after user interaction");
assertNotIncludes(chatClient, "/api/background-processes", "background process polling remains removed");
assertNotIncludes(chatClient, "/api/curator/", "curator action fetch remains removed");

console.log("web smoke checks passed");
