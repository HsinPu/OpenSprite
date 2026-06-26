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
  workStateCard,
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
  read("src/components/workStateCard.tsx"),
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
assertIncludes(providerSettings, "client.startCodexAuthLogin", "provider settings keeps OpenAI Codex OAuth login");
assertIncludes(providerSettings, "client.startCopilotAuthLogin", "provider settings keeps Copilot OAuth login");
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
assertIncludes(runInspector, "JSON.stringify({ run, exported_at", "trace debug JSON export");
assertIncludes(runInspector, "RunHistorySelector", "run inspector delegates run history selector");
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
