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
  main,
  styles,
  reactiveCompat,
  chatClient,
  runInspector,
  providerSettings,
  modelSettings,
  settingsPrimitives,
] = await Promise.all([
  read("package.json"),
  read("vite.config.ts"),
  read("tsconfig.json"),
  read("index.html"),
  read("src/App.tsx"),
  read("src/main.tsx"),
  read("styles.css"),
  read("src/lib/reactiveCompat.ts"),
  read("src/composables/useChatClient.js"),
  read("src/components/runInspector.tsx"),
  read("src/settings/providerSettings.tsx"),
  read("src/settings/modelSettings.tsx"),
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
assertIncludes(app, "ConfigProvider", "Ant Design provider");
assertIncludes(app, "useReactiveStore", "React subscription bridge");
assertIncludes(app, "useTransition", "settings modal uses transition for deferred content");
assertIncludes(app, "useChatClient", "existing chat client flow reused");
assertIncludes(app, "SidebarNav", "React sidebar shell");
assertIncludes(app, "ChatPanel", "React chat panel");
assertIncludes(app, "RunInspector", "React trace inspector");
assertIncludes(app, "SettingsModal", "React settings modal");
assertIncludes(app, "MessageList", "React message list");
assertIncludes(app, "MessageTextRenderer", "React message renderer");
assertIncludes(app, "viewTraceForRun", "assistant message trace action");
assertIncludes(app, "client.selectRun(runId)", "trace action selects the requested run");
assertIncludes(app, "client.toggleTraceInspectorCollapsed()", "trace action opens collapsed inspector");
assertIncludes(app, "client.currentRuns.value", "run history uses active session runs");
assertIncludes(app, "client.settingsState", "settings API state remains wired");
assertIncludes(app, "client.saveBrowserSettings", "browser settings save action");
assertIncludes(app, "client.runBrowserTest", "browser manual test action");
assertIncludes(app, "client.saveMcpServer", "MCP settings action");
assertIncludes(modelSettings, "client.selectModel", "model selection action");
assertIncludes(app, "client.clearWebSessions()", "web history cleanup action");
assertIncludes(app, "form.externalChatId", "general settings keeps external chat id control");
assertIncludes(app, "client.runUpdate", "general settings keeps update apply action");
assertIncludes(providerSettings, "client.deleteCredential", "provider settings keeps credential deletion");
assertIncludes(providerSettings, "client.startCodexAuthLogin", "provider settings keeps OpenAI Codex OAuth login");
assertIncludes(providerSettings, "client.startCopilotAuthLogin", "provider settings keeps Copilot OAuth login");
assertIncludes(modelSettings, "client.saveMediaModel", "model settings keeps media model save action");
assertIncludes(app, "client.beginChannelConnect", "channel settings keeps add channel flow");
assertIncludes(app, "client.toggleMcpAdvanced", "MCP settings keeps advanced editor");
assertIncludes(app, "client.toggleMcpJsonInput", "MCP settings keeps JSON editor");
assertIncludes(app, "client.applyMcpJson", "MCP settings keeps JSON import action");
assertIncludes(app, "form.envJson", "MCP settings keeps environment JSON field");
assertIncludes(app, "form.headersJson", "MCP settings keeps headers JSON field");
assertIncludes(app, "state.scheduleForm.defaultTimezone", "schedule settings keeps default timezone field");
assertIncludes(app, "client.saveCronJob", "schedule settings keeps cron editor save");
assertIncludes(app, "client.runCronJobAction(job, job.enabled ? \"pause\" : \"enable\")", "schedule settings keeps pause/enable action");
assertIncludes(app, "form.httpProxy", "network settings keeps HTTP proxy field");
assertIncludes(app, "form.httpsProxy", "network settings keeps HTTPS proxy field");
assertIncludes(app, "form.noProxy", "network settings keeps no proxy field");
assertNotIncludes(app, "state.networkForm.enabled", "network settings does not show unsupported enabled field");
assertIncludes(app, "form.jinaApiKey", "search settings keeps Jina API key field");
assertIncludes(app, "form.searxngEngines", "search settings keeps SearXNG engine selection");
assertIncludes(app, "form.searxngCategories", "search settings keeps SearXNG category selection");
assertIncludes(app, "form.commandTimeout", "browser settings keeps command timeout");
assertIncludes(app, "form.sessionTimeout", "browser settings keeps session timeout");
assertIncludes(app, "form.allowPrivateUrls", "browser settings keeps private URL toggle");
assertNotIncludes(app, "sessionTimeoutSeconds", "browser settings avoids stale session timeout field");
assertIncludes(app, "shortcut-keys", "shortcut settings uses parity layout");
assertIncludes(settingsPrimitives, "function SettingsCard", "settings pages use Ant card helper");
assertIncludes(app, "<SettingsCard className=\"settings-card--form\"", "settings form cards use Ant card helper");
assertIncludes(app, "<Select", "settings pages use Ant Select controls");
assertIncludes(app, "<Switch", "settings pages use Ant Switch controls");
assertIncludes(app, "<Input", "settings pages use Ant Input controls");
assertIncludes(app, "<Checkbox", "sidebar selection uses Ant Checkbox controls");
assertIncludes(app, "<Segmented", "sidebar filters use Ant Segmented controls");
assertNotIncludes(app, "<button", "app shell avoids raw button elements");
assertNotIncludes(app, "<input", "app shell avoids raw input elements");
assertNotIncludes(app, "<select", "app shell avoids raw select elements");
assertNotIncludes(app, "<textarea", "app shell avoids raw textarea elements");
assertIncludes(runInspector, "JSON.stringify({ run, exported_at", "trace debug JSON export");
assertIncludes(app, "SettingsNav", "settings modal uses the parity sidebar nav");
assertIncludes(app, "className=\"settings-nav__menu\"", "settings nav uses Ant menu");
assertIncludes(app, "selectedKeys={[section]}", "settings nav marks active section");
assertIncludes(app, "selectSection(String(key))", "settings nav changes active section");
assertIncludes(app, "renderSettingsSection", "settings modal renders only the active section");
assertIncludes(app, "settings-page--loading", "settings modal defers heavy section content");
assertNotIncludes(app, "const contentBySection", "settings modal should not build a section map during render");
assertIncludes(styles, ".settings-page--loading", "settings deferred loading state is styled");
assertIncludes(styles, ".settings-nav__menu .ant-menu-item-selected", "settings nav selected state is styled through Ant");
assertRegex(runInspector, /className=\"run-history__select\"[\s\S]+<Select[\s\S]+client\.selectRun\(value\)/, "run history selector changes active run");
assertNotIncludes(app, "BackgroundProcessSidebar", "background process sidebar stays removed");
assertNotIncludes(app, "CuratorSettingsPage", "curator settings page stays removed");

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
