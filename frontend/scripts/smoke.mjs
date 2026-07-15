import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import ts from "typescript";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

async function read(relativePath) {
  const content = await readFile(join(root, relativePath), "utf8");
  return content.replace(/\r\n?/g, "\n");
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

function assertOccurrenceCount(content, needle, expected, label) {
  const count = content.split(needle).length - 1;
  if (count !== expected) {
    throw new Error(`${label}: expected ${expected} occurrences of ${needle}, received ${count}`);
  }
}

async function importTypeScriptModule(relativePath) {
  const source = await read(relativePath);
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: relativePath,
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}

async function importReactiveCompatModule() {
  const source = await read("src/lib/reactiveCompat.ts");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: "src/lib/reactiveCompat.ts",
  });
  const smokeSource = outputText.replace(
    /^import \{ useEffect, useRef, useSyncExternalStore \} from "react";\n/m,
    "",
  );
  return import(`data:text/javascript;base64,${Buffer.from(smokeSource).toString("base64")}`);
}

function assertNotRegex(content, pattern, label) {
  if (pattern.test(content)) {
    throw new Error(`${label}: unexpected ${pattern}`);
  }
}

const {
  beginRequestGeneration,
  captureRunTraceWatermark,
  createSessionHistoryRefreshQueue,
  createSessionSnapshotFence,
  enqueueSessionHistoryRefresh,
  fileChangeCommonIdentity,
  isCurrentRequestGeneration,
  mergeFreshSessionSnapshot,
  mergeMonotonicRunStatus,
  mergeRunTraceSnapshot,
  takePendingSessionHistoryRefresh,
} = await importTypeScriptModule("src/composables/chatClientStateMerges.ts");
const { reactive } = await importReactiveCompatModule();

function assertState(condition, label) {
  if (!condition) {
    throw new Error(label);
  }
}

const reactiveRoot = reactive({ sessions: [{ id: "session-1" }] });
const stableSessionProxy = reactiveRoot.sessions[0];
const stateBySession = new WeakMap([[stableSessionProxy, "retained"]]);
reactiveRoot.sessions = [stableSessionProxy];
assertState(
  reactiveRoot.sessions[0] === stableSessionProxy,
  "reactive values written back into the same graph must not be wrapped in a second proxy",
);
assertState(
  stateBySession.get(reactiveRoot.sessions[0]) === "retained",
  "reactive proxy identity must remain stable for WeakMap-backed client state",
);
assertState(
  reactive(stableSessionProxy) === stableSessionProxy,
  "reactive must return an existing proxy from the current lifecycle context",
);

function traceCounts(total) {
  return {
    total,
    returned: total,
    compacted: 0,
    textTotal: 0,
    textReturned: 0,
    maxEvents: 80,
    maxTextEvents: 20,
  };
}

assertState(
  mergeMonotonicRunStatus("completed", "running") === "completed",
  "terminal run status must not reopen from a delayed run_started event",
);
assertState(
  mergeMonotonicRunStatus("failed", "cancelling") === "failed",
  "terminal run status must not reopen from a delayed cancellation snapshot",
);
assertState(
  mergeMonotonicRunStatus("completed", "failed") === "completed",
  "the first durable terminal run status must remain authoritative",
);
assertState(
  mergeMonotonicRunStatus("running", "completed") === "completed",
  "a terminal run event must still close a running run",
);

const initialTrace = {
  rawEvents: [{
    id: "live-old",
    schemaVersion: 0,
    eventType: "tool_started",
    kind: "tool",
    status: "running",
    createdAt: 10,
    payload: { tool_name: "shell" },
    artifact: null,
  }],
  eventCounts: traceCounts(1),
  parts: [{
    partId: "part-1",
    partType: "assistant_message",
    schemaVersion: 0,
    kind: "text",
    state: "running",
    content: "A",
    toolName: "",
    metadata: { streaming: true },
    artifact: null,
    createdAt: 10,
  }],
  artifacts: [{
    artifactId: "tool:call-1",
    artifactType: "tool_call",
    kind: "tool",
    status: "running",
    phase: "started",
    title: "shell",
    detail: "",
    source: "event",
    sourceId: "live-old",
    createdAt: 10,
    toolName: "shell",
    toolCallId: "call-1",
    iteration: "1",
    path: "",
    action: "",
    diffLen: 0,
    diffPreview: "",
    snapshotsAvailable: { before: false, after: false },
    metadata: {},
  }, {
    artifactId: "live-only",
    artifactType: "notice",
    kind: "other",
    status: "completed",
    phase: "",
    title: "live only",
    detail: "",
    source: "event",
    sourceId: "live-only",
    createdAt: 11,
    toolName: "",
    toolCallId: "",
    iteration: "",
    path: "",
    action: "",
    diffLen: 0,
    diffPreview: "",
    snapshotsAvailable: { before: false, after: false },
    metadata: {},
  }],
  fileChanges: [{
    changeId: "change-1",
    sourceId: "change-1",
    schemaVersion: 0,
    kind: "file",
    state: "running",
    status: "running",
    path: "src/app.ts",
    label: "src/app.ts",
    action: "edit",
    toolName: "shell",
    diffLen: 1,
    diff: "",
    diffPreview: "old",
    beforeContent: null,
    afterContent: null,
    snapshotsAvailable: { before: false, after: false },
    artifact: null,
    revertSupported: false,
    createdAt: 10,
  }],
};
const traceWatermark = captureRunTraceWatermark(initialTrace);
const liveTrace = structuredClone(initialTrace);
liveTrace.rawEvents.push({
  id: "live-new",
  schemaVersion: 0,
  eventType: "tool_finished",
  kind: "tool",
  status: "completed",
  createdAt: 20,
  payload: { tool_name: "shell" },
  artifact: null,
});
liveTrace.eventCounts = traceCounts(2);
liveTrace.parts[0].content = "AB";
liveTrace.artifacts[0].status = "completed";
liveTrace.fileChanges[0].state = "completed";
liveTrace.fileChanges[0].status = "completed";
liveTrace.fileChanges[0].diffPreview = "new";

const snapshotTrace = structuredClone(initialTrace);
snapshotTrace.rawEvents[0].id = "stored-old";
snapshotTrace.artifacts = [structuredClone(initialTrace.artifacts[0])];
const mergedTrace = mergeRunTraceSnapshot(snapshotTrace, liveTrace, traceWatermark);
assertState(mergedTrace.rawEvents.length === 2, "trace merge must dedupe the stored/live copy and retain a concurrent event");
assertState(mergedTrace.parts[0].content === "AB", "trace merge must retain a concurrent part delta");
assertState(mergedTrace.artifacts.some((artifact) => artifact.artifactId === "live-only"), "trace merge must retain a live-only artifact missing from the snapshot");
assertState(mergedTrace.artifacts[0].status === "completed", "trace merge must retain a concurrent terminal artifact update");
assertState(mergedTrace.fileChanges[0].diffPreview === "new", "trace merge must retain a concurrent file-change update");

const summaryGenerations = new WeakMap();
const summaryRun = {};
const staleSummaryGeneration = beginRequestGeneration(summaryGenerations, summaryRun);
const currentSummaryGeneration = beginRequestGeneration(summaryGenerations, summaryRun);
assertState(
  !isCurrentRequestGeneration(summaryGenerations, summaryRun, staleSummaryGeneration),
  "a superseded run-summary request must not commit success, failure, or loading state",
);
assertState(
  isCurrentRequestGeneration(summaryGenerations, summaryRun, currentSummaryGeneration),
  "the newest run-summary request generation must remain current",
);

const traceGenerations = new WeakMap();
const traceRun = {};
const staleTraceGeneration = beginRequestGeneration(traceGenerations, traceRun);
beginRequestGeneration(traceGenerations, traceRun);
assertState(
  !isCurrentRequestGeneration(traceGenerations, traceRun, staleTraceGeneration),
  "a superseded run-trace failure must not overwrite the newest trace result",
);

const duplicateLiveEvents = ["live-a", "live-b"].map((id) => ({
  ...structuredClone(initialTrace.rawEvents[0]),
  id,
}));
const duplicateStoredEvents = ["stored-a", "stored-b"].map((id) => ({
  ...structuredClone(initialTrace.rawEvents[0]),
  id,
}));
const duplicateEventLiveTrace = {
  ...structuredClone(initialTrace),
  rawEvents: duplicateLiveEvents,
  eventCounts: traceCounts(2),
  parts: [],
  artifacts: [],
  fileChanges: [],
};
const duplicateEventSnapshotTrace = {
  ...structuredClone(duplicateEventLiveTrace),
  rawEvents: duplicateStoredEvents,
};
const duplicateEventMerge = mergeRunTraceSnapshot(
  duplicateEventSnapshotTrace,
  duplicateEventLiveTrace,
  captureRunTraceWatermark(duplicateEventLiveTrace),
);
assertState(
  duplicateEventMerge.rawEvents.length === 2,
  "raw-event snapshot matching must preserve two distinct IDs with identical payloads",
);
const liveOnlyDuplicateEventMerge = mergeRunTraceSnapshot(
  { ...structuredClone(duplicateEventSnapshotTrace), rawEvents: [], eventCounts: traceCounts(0) },
  duplicateEventLiveTrace,
  captureRunTraceWatermark(duplicateEventLiveTrace),
);
assertState(
  liveOnlyDuplicateEventMerge.rawEvents.length === 2,
  "raw-event identity must retain live multiplicity when event IDs differ",
);

function fileChangeForMerge(id, diffPreview, diffLen, createdAt, durable = false) {
  return {
    ...structuredClone(initialTrace.fileChanges[0]),
    changeId: id,
    sourceId: id,
    path: "src/shared.ts",
    action: "edit",
    diffLen: durable ? 0 : diffLen,
    diff: durable ? diffPreview : "",
    diffPreview: durable ? "" : diffPreview,
    state: "completed",
    status: "completed",
    revertSupported: durable,
    createdAt,
  };
}

const liveFileChanges = [
  fileChangeForMerge("live-alpha", "+ alpha", 7, 1_100),
  fileChangeForMerge("live-beta", "+ beta!", 7, 2_100),
];
const storedFileChanges = [
  fileChangeForMerge("db-alpha", "+ alpha", 7, 1_000, true),
  fileChangeForMerge("db-beta", "+ beta!", 7, 2_000, true),
];
assertState(
  fileChangeCommonIdentity(liveFileChanges[0]) === fileChangeCommonIdentity(storedFileChanges[0]),
  "live and durable file changes must share a timestamp-independent identity",
);
assertState(
  fileChangeCommonIdentity(liveFileChanges[0]) !== fileChangeCommonIdentity(liveFileChanges[1]),
  "different edits on the same path must not share a file-change identity",
);
assertState(
  fileChangeCommonIdentity(fileChangeForMerge("live-empty", "<empty>", 0, 3_100))
    === fileChangeCommonIdentity(fileChangeForMerge("db-empty", "", 0, 3_000, true)),
  "empty durable and live diffs must share the same file-change identity",
);
const fileChangeLiveTrace = {
  ...structuredClone(initialTrace),
  rawEvents: [],
  eventCounts: traceCounts(0),
  parts: [],
  artifacts: [],
  fileChanges: liveFileChanges,
};
const fileChangeSnapshotTrace = {
  ...structuredClone(fileChangeLiveTrace),
  fileChanges: storedFileChanges,
};
const fileChangeMerge = mergeRunTraceSnapshot(
  fileChangeSnapshotTrace,
  fileChangeLiveTrace,
  captureRunTraceWatermark(fileChangeLiveTrace),
);
assertState(fileChangeMerge.fileChanges.length === 2, "durable/live file changes must dedupe one-to-one");
assertState(
  fileChangeMerge.fileChanges.map((change) => change.changeId).join(",") === "db-alpha,db-beta",
  "file-change merge must keep both distinct durable changes on the same path",
);

const historyRefreshQueue = createSessionHistoryRefreshQueue();
enqueueSessionHistoryRefresh(historyRefreshQueue, {
  quiet: false,
  includeHiddenSessions: false,
  pruneMissingHistorySessions: false,
});
assertState(
  takePendingSessionHistoryRefresh(historyRefreshQueue)?.includeHiddenSessions === false,
  "the first history refresh request must start immediately",
);
enqueueSessionHistoryRefresh(historyRefreshQueue, {
  quiet: true,
  includeHiddenSessions: true,
  pruneMissingHistorySessions: true,
});
enqueueSessionHistoryRefresh(historyRefreshQueue, {
  quiet: false,
  includeHiddenSessions: false,
  pruneMissingHistorySessions: false,
});
const pendingHistoryRefresh = takePendingSessionHistoryRefresh(historyRefreshQueue);
assertState(pendingHistoryRefresh?.includeHiddenSessions === false, "pending history refresh must use the latest include_cli choice");
assertState(pendingHistoryRefresh?.quiet === false, "pending history refresh must use the latest quiet choice");
assertState(pendingHistoryRefresh?.pruneMissingHistorySessions === true, "pending history refresh must preserve a requested prune");
assertState(takePendingSessionHistoryRefresh(historyRefreshQueue) === null, "history refresh queue must drain pending work once");

const liveSession = {
  externalChatId: "chat-1",
  transportExternalChatId: "chat-1",
  channel: "web",
  sessionId: "web:chat-1",
  title: "Live title",
  updatedAt: 200,
  messages: [{ id: "live", role: "assistant", text: "live", meta: "", createdAt: 200 }],
  entries: [{ id: "live-entry" }],
  hiddenFromBrowserHistory: false,
  status: { status: "running", updatedAt: 210, metadata: {} },
  activeRunId: null,
  runs: [],
  runsLoaded: true,
  runsLoading: false,
  runsError: "",
};
const staleSession = {
  ...structuredClone(liveSession),
  title: "Stale title",
  updatedAt: 100,
  messages: [{ id: "stale", role: "assistant", text: "stale", meta: "", createdAt: 100 }],
  entries: [{ id: "stale-entry" }],
  status: { status: "idle", updatedAt: 100, metadata: {} },
};
const sessionSnapshotFence = createSessionSnapshotFence();
mergeFreshSessionSnapshot(liveSession, staleSession, {
  changedSinceRequest: true,
  snapshotFence: sessionSnapshotFence,
});
assertState(liveSession.updatedAt === 200, "quiet history must not lower a live session timestamp");
assertState(liveSession.status.status === "running", "quiet history must not replace a newer live status");
assertState(liveSession.messages[0].id === "live", "quiet history must not replace live message details");
assertState(liveSession.entries[0].id === "live-entry", "quiet history must not replace live entry details");
const concurrentNewerSnapshot = {
  ...structuredClone(staleSession),
  updatedAt: 300,
  messages: [{ id: "snapshot-newer", role: "assistant", text: "snapshot", meta: "", createdAt: 300 }],
  status: { status: "idle", updatedAt: 300, metadata: {} },
};
mergeFreshSessionSnapshot(liveSession, concurrentNewerSnapshot, {
  changedSinceRequest: true,
  snapshotFence: sessionSnapshotFence,
});
assertState(liveSession.status.status === "running", "a quiet request watermark must protect live status even from a higher snapshot timestamp");
assertState(liveSession.messages[0].id === "live", "a quiet request watermark must protect live details even from a higher snapshot timestamp");
mergeFreshSessionSnapshot(liveSession, structuredClone(concurrentNewerSnapshot), {
  snapshotFence: sessionSnapshotFence,
});
assertState(liveSession.status.status === "running", "the same rejected history snapshot must stay fenced on later refreshes");
assertState(liveSession.messages[0].id === "live", "a later refresh must not revive previously rejected stale details");
const genuinelyNewerSnapshot = {
  ...structuredClone(concurrentNewerSnapshot),
  updatedAt: 301,
  messages: [{ id: "snapshot-fresh", role: "assistant", text: "fresh", meta: "", createdAt: 301 }],
  entries: [{ id: "snapshot-fresh-entry" }],
  status: { status: "idle", updatedAt: 301, metadata: {} },
};
mergeFreshSessionSnapshot(liveSession, genuinelyNewerSnapshot, { snapshotFence: sessionSnapshotFence });
assertState(liveSession.messages[0].id === "snapshot-fresh", "a snapshot newer than the quiet-history fence must still apply");

const [
  packageJsonRaw,
  viteConfig,
  tsconfigRaw,
  indexHtml,
  app,
  appProviders,
  displayCopy,
  openSpriteShell,
  main,
  styles,
  reactiveCompat,
  payloadBoundary,
  browserDefaults,
  browserSettingsActions,
  chatClient,
  chatClientApiPayloads,
  chatClientCronPayloads,
  chatClientEventPayloads,
  chatClientHistoryPayloads,
  chatClientLiveSocket,
  chatClientMessagePayloads,
  chatClientRunPayloads,
  chatClientCoercion,
  chatClientSessionIds,
  chatClientRunHelpers,
  runSummaryNormalizers,
  runTraceNormalizers,
  chatClientSessions,
  chatClientTokens,
  logDefaults,
  networkDefaults,
  channelSettingsActions,
  logSettingsActions,
  networkSettingsActions,
  modelReasoning,
  modelSettingsActions,
  mcpSettingsActions,
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
  scheduleDefaults,
  scheduleSettingsActions,
  searchDefaults,
  searchSettingsActions,
  updateSettingsActions,
  settingsSectionLoaders,
  useSettingsState,
  settingsApi,
  settingsNormalizers,
  chatClientPaths,
  chatClientPreferences,
  confirmFlow,
  shellLayout,
  authGate,
  chatPanel,
  confirmDialog,
  displayHelpers,
  emptyState,
  messageList,
  messageData,
  messageMarkdown,
  mobileNavControls,
  sidebarNav,
  traceSidebar,
  toastStack,
  browserSettings,
  runInspector,
  runHistorySelector,
  runSummaryCard,
  runTimeline,
  runTraceViewer,
  authProviderCard,
  providerAuthSection,
  providerAuthSections,
  providerAuthInitialState,
  providerAuthMetadata,
  providerEndpoints,
  providerEmptyState,
  providerHelpers,
  providerAuthHelpers,
  providerCredentialHelpers,
  providerModelHelpers,
  providerMediaHelpers,
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
  mcpHelpers,
  networkSettings,
  scheduleSettings,
  scheduleNetworkHelpers,
  searchSettings,
  searchBrowserHelpers,
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
  read("src/i18n/copy.ts"),
  read("src/components/openSpriteShell.tsx"),
  read("src/main.tsx"),
  read("styles.css"),
  read("src/lib/reactiveCompat.ts"),
  read("src/composables/payloadBoundary.ts"),
  read("src/composables/browserDefaults.ts"),
  read("src/composables/useBrowserSettingsActions.ts"),
  read("src/composables/useChatClient.ts"),
  read("src/composables/chatClientApiPayloads.ts"),
  read("src/composables/chatClientCronPayloads.ts"),
  read("src/composables/chatClientEventPayloads.ts"),
  read("src/composables/chatClientHistoryPayloads.ts"),
  read("src/composables/chatClientLiveSocket.ts"),
  read("src/composables/chatClientMessagePayloads.ts"),
  read("src/composables/chatClientRunPayloads.ts"),
  read("src/composables/chatClientCoercion.ts"),
  read("src/composables/chatClientSessionIds.ts"),
  read("src/composables/chatClientRunHelpers.ts"),
  read("src/composables/runSummaryNormalizers.ts"),
  read("src/composables/runTraceNormalizers.ts"),
  read("src/composables/chatClientSessions.ts"),
  read("src/composables/chatClientTokens.ts"),
  read("src/composables/logDefaults.ts"),
  read("src/composables/networkDefaults.ts"),
  read("src/composables/useChannelSettingsActions.ts"),
  read("src/composables/useLogSettingsActions.ts"),
  read("src/composables/useNetworkSettingsActions.ts"),
  read("src/composables/modelReasoning.ts"),
  read("src/composables/useModelSettingsActions.ts"),
  read("src/composables/useMcpSettingsActions.ts"),
  read("src/composables/useProviderSettingsActions.ts"),
  read("src/composables/providerSettingsLoader.ts"),
  read("src/composables/providerSettingsRequests.ts"),
  read("src/composables/useProviderAuthActions.ts"),
  read("src/composables/providerAuthActionRunner.ts"),
  read("src/composables/providerAuthRequests.ts"),
  read("src/composables/providerAuthConfigs.ts"),
  read("src/composables/providerAuthPollTimers.ts"),
  read("src/composables/providerAuthState.ts"),
  read("src/composables/providerConnectForm.ts"),
  read("src/composables/providerMutationRunner.ts"),
  read("src/composables/scheduleDefaults.ts"),
  read("src/composables/useScheduleSettingsActions.ts"),
  read("src/composables/searchDefaults.ts"),
  read("src/composables/useSearchSettingsActions.ts"),
  read("src/composables/useUpdateSettingsActions.ts"),
  read("src/composables/settingsSectionLoaders.ts"),
  read("src/composables/useSettingsState.ts"),
  read("src/composables/settingsApi.ts"),
  read("src/composables/settingsNormalizers.ts"),
  read("src/composables/chatClientPaths.ts"),
  read("src/composables/chatClientPreferences.ts"),
  read("src/composables/useConfirmDialog.ts"),
  read("src/composables/useShellLayout.ts"),
  read("src/components/authGate.tsx"),
  read("src/components/chatPanel.tsx"),
  read("src/components/confirmDialog.tsx"),
  read("src/components/displayHelpers.ts"),
  read("src/components/emptyState.tsx"),
  read("src/components/messageList.tsx"),
  read("src/components/messageData.ts"),
  read("src/components/messageMarkdown.tsx"),
  read("src/components/mobileNavControls.tsx"),
  read("src/components/sidebarNav.tsx"),
  read("src/components/traceSidebar.tsx"),
  read("src/components/toastStack.tsx"),
  read("src/settings/browserSettings.tsx"),
  read("src/components/runInspector.tsx"),
  read("src/components/runHistorySelector.tsx"),
  read("src/components/runSummaryCard.tsx"),
  read("src/components/runTimeline.tsx"),
  read("src/components/runTraceViewer.tsx"),
  read("src/settings/authProviderCard.tsx"),
  read("src/settings/providerAuthSection.tsx"),
  read("src/settings/providerAuthSections.ts"),
  read("src/settings/providerAuthInitialState.ts"),
  read("src/settings/providerAuthMetadata.ts"),
  read("src/settings/providerEndpoints.ts"),
  read("src/settings/providerEmptyState.tsx"),
  read("src/settings/providerHelpers.ts"),
  read("src/settings/providerAuthHelpers.ts"),
  read("src/settings/providerCredentialHelpers.ts"),
  read("src/settings/providerModelHelpers.ts"),
  read("src/settings/providerMediaHelpers.ts"),
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
  read("src/settings/mcpHelpers.ts"),
  read("src/settings/networkSettings.tsx"),
  read("src/settings/scheduleSettings.tsx"),
  read("src/settings/scheduleNetworkHelpers.ts"),
  read("src/settings/searchSettings.tsx"),
  read("src/settings/searchBrowserHelpers.ts"),
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
assertIncludes(displayCopy, "const DEFAULT_LANGUAGE = \"zh-TW\";", "display copy keeps default language");
assertIncludes(displayCopy, "export const DISPLAY_COPY", "display copy table remains exported");
assertIncludes(displayCopy, "export function getDisplayCopy(language: string)", "display copy lookup remains typed and exported");
assertIncludes(openSpriteShell, "useReactiveStore", "React subscription bridge");
assertIncludes(openSpriteShell, "useConfirmDialog(client)", "app shell delegates confirm dialog flow");
assertIncludes(openSpriteShell, "useShellLayout(client)", "app shell delegates resize layout logic");
assertIncludes(confirmFlow, "import type { ChatSession } from \"./chatClientSessions\";", "confirm flow imports typed chat session model");
assertIncludes(confirmFlow, "type ConfirmDialogAction = () => void | Promise<void>;", "confirm flow types deferred dialog actions");
assertIncludes(confirmFlow, "interface ConfirmDialogState", "confirm flow uses typed dialog state");
assertIncludes(confirmFlow, "interface ConfirmDialogCopy", "confirm flow uses typed copy props");
assertIncludes(confirmFlow, "type ConfirmDialogClient = {", "confirm flow uses typed client boundary");
assertIncludes(confirmFlow, "const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>", "confirm flow stores typed dialog state");
assertIncludes(confirmFlow, "function deleteSessions(sessions: ChatSession[])", "confirm flow deletes typed chat sessions");
assertIncludes(confirmFlow, "action: () => client.deleteSessions(targets)", "confirm flow keeps session delete action");
assertIncludes(confirmFlow, "action: () => client.clearWebSessions()", "confirm flow keeps web history cleanup action");
assertIncludes(confirmFlow, "setConfirmDialog((dialog) => ({ ...dialog, busy: true }))", "confirm flow keeps busy state");
assertIncludes(confirmFlow, "copy.sidebar.confirmDeleteChat(client.getSessionTitle(targets[0]))", "confirm flow keeps single-session delete copy");
assertNotIncludes(confirmFlow, "type AnyRecord", "confirm flow no longer relies on dynamic AnyRecord props");
assertIncludes(shellLayout, "SIDEBAR_WIDTH_DEFAULT = 268", "shell layout keeps sidebar default width");
assertIncludes(shellLayout, "TRACE_WIDTH_MIN = 440", "shell layout keeps trace minimum width");
assertIncludes(shellLayout, "type ShellStyle = CSSProperties & {", "shell layout names its custom CSS property boundary");
assertIncludes(shellLayout, "const appShellStyle: ShellStyle = {", "shell layout assigns custom properties through the typed style view");
assertNotIncludes(shellLayout, "as CSSProperties", "shell layout avoids asserting custom properties as generic React styles");
assertIncludes(shellLayout, "window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY", "shell layout persists sidebar width");
assertIncludes(shellLayout, "setSidebarWidth(clampSidebarWidth(moveEvent.clientX))", "shell layout keeps sidebar drag math");
assertIncludes(shellLayout, "setTraceInspectorWidth(clampTraceWidth(window.innerWidth - moveEvent.clientX))", "shell layout keeps trace drag math");
assertIncludes(settingsModal, "useTransition", "settings modal uses transition for deferred content");
assertIncludes(openSpriteShell, "useChatClient", "existing chat client flow reused");
assertIncludes(openSpriteShell, "SidebarNav", "React sidebar shell");
assertIncludes(sidebarNav, "<Checkbox", "sidebar selection uses Ant Checkbox controls");
assertIncludes(sidebarNav, "<Segmented", "sidebar filters use Ant Segmented controls");
assertIncludes(sidebarNav, "import { normalizeSessionChannelFilter, type ChatSession, type SessionChannelFilter } from \"../composables/chatClientSessions\";", "sidebar imports typed session filter helpers");
assertIncludes(sidebarNav, "import type { SettingsSectionId } from \"../composables/settingsSectionLoaders\";", "sidebar imports typed settings section id");
assertIncludes(sidebarNav, "type ValueRef<T> = { value: T };", "sidebar uses a typed value ref boundary");
assertIncludes(sidebarNav, "interface SidebarCopy", "sidebar exposes typed copy props");
assertIncludes(sidebarNav, "interface SidebarState", "sidebar exposes typed active session state");
assertIncludes(sidebarNav, "sidebarSessions: ValueRef<ChatSession[]>;", "sidebar reads typed session list");
assertIncludes(sidebarNav, "sessionChannelFilter: ValueRef<SessionChannelFilter>;", "sidebar reads typed session channel filter");
assertIncludes(sidebarNav, "state: SidebarState;", "sidebar reads typed active session state");
assertIncludes(sidebarNav, "deleteSessions: (sessions: ChatSession[]) => void;", "sidebar bulk delete uses typed sessions");
assertIncludes(sidebarNav, "setSessionChannelFilter: (value: SessionChannelFilter) => void;", "sidebar sets typed session channel filter");
assertIncludes(sidebarNav, "openSettings: (section: SettingsSectionId) => void;", "sidebar opens typed settings sections");
assertIncludes(sidebarNav, "function sessionSelectionKey(session: ChatSession)", "sidebar selection key uses typed sessions");
assertIncludes(sidebarNav, "function toggleSelected(session: ChatSession, checked: boolean)", "sidebar selection updates typed sessions");
assertNotIncludes(sidebarNav, "type AnyRecord", "sidebar no longer relies on dynamic AnyRecord props");
assertIncludes(sidebarNav, "client.setSessionChannelFilter(normalizeSessionChannelFilter(value))", "sidebar normalizes filter values before updating client");
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
assertIncludes(openSpriteShell, "ToastStack", "React toast stack");
assertIncludes(toastStack, "import type { ToastNotice } from \"../composables/useChatClient\";", "toast stack imports typed toast notice");
assertIncludes(toastStack, "type ValueRef<T> = { value: T };", "toast stack uses a typed value ref boundary");
assertIncludes(toastStack, "toasts: ValueRef<ToastNotice[]>;", "toast stack reads typed toast notices");
assertIncludes(toastStack, "dismissToast: (id: string) => void;", "toast stack dismisses typed toast ids");
assertIncludes(toastStack, "toasts.map((toast: ToastNotice)", "toast stack renders typed toast notices");
assertNotIncludes(toastStack, "type AnyRecord", "toast stack no longer relies on dynamic AnyRecord props");
assertIncludes(authGate, "auth-gate", "auth gate component keeps auth overlay layout");
assertIncludes(authGate, "client.submitAccessToken", "auth gate keeps token submit flow");
assertIncludes(authGate, "client.settingsForm.accessToken", "auth gate keeps access token field");
assertIncludes(authGate, "client.openSettings(\"general\")", "auth gate keeps settings fallback action");
assertIncludes(authGate, "import type { SettingsSectionId } from \"../composables/settingsSectionLoaders\";", "auth gate imports typed settings section id");
assertIncludes(authGate, "type ValueRef<T> = { value: T };", "auth gate uses a typed value ref boundary");
assertIncludes(authGate, "interface AuthGateCopy", "auth gate exposes typed auth copy props");
assertIncludes(authGate, "interface AuthGateState", "auth gate exposes typed auth state");
assertIncludes(authGate, "interface AuthGateSettingsForm", "auth gate exposes typed settings form slice");
assertIncludes(authGate, "copy: ValueRef<AuthGateCopy>;", "auth gate reads typed auth copy");
assertIncludes(authGate, "state: AuthGateState;", "auth gate reads typed auth state");
assertIncludes(authGate, "settingsForm: AuthGateSettingsForm;", "auth gate reads typed settings form");
assertIncludes(authGate, "openSettings: (section: SettingsSectionId) => void;", "auth gate opens typed settings sections");
assertNotIncludes(authGate, "type AnyRecord", "auth gate no longer relies on dynamic AnyRecord props");
assertIncludes(emptyState, "empty-state", "empty state component keeps starter screen layout");
assertIncludes(emptyState, "prompt-card", "empty state keeps prompt card layout");
assertIncludes(emptyState, "applyPrompt(prompt.text)", "empty state keeps prompt application flow");
assertIncludes(emptyState, "interface EmptyStateCopy", "empty state uses typed copy props");
assertIncludes(emptyState, "interface PromptOption", "empty state uses typed prompt options");
assertNotIncludes(emptyState, "type AnyRecord", "empty state no longer relies on dynamic AnyRecord props");
assertIncludes(chatPanel, "MessageList", "React message list");
assertIncludes(chatPanel, "type ChatPanelCopy = EmptyStateCopy &", "chat panel composes typed copy boundary");
assertIncludes(chatPanel, "type ChatPanelState = {", "chat panel types local state boundary");
assertIncludes(chatPanel, "setMessageInputRef: (element: HTMLTextAreaElement | null) => void;", "chat panel types composer input ref");
assertNotIncludes(chatPanel, "type AnyRecord", "chat panel no longer relies on dynamic AnyRecord props");
assertNotIncludes(chatPanel, "Record<string, any>", "chat panel avoids broad dynamic records");
assertIncludes(chatPanel, "import type { RunViewState } from \"../composables/chatClientRunHelpers\";", "chat panel imports typed run view state");
assertIncludes(chatPanel, "import type { ChatMessage, LiveEntry } from \"../composables/chatClientSessions\";", "chat panel imports typed chat session models");
assertIncludes(chatPanel, "import type { MessageCopy } from \"./messageMarkdown\";", "chat panel imports typed message copy boundary");
assertIncludes(chatPanel, "type ValueRef<T> = { value: T };", "chat panel uses a typed value ref boundary");
assertIncludes(chatPanel, "prompts: ValueRef<PromptOption[]>;", "chat panel exposes typed prompt options");
assertIncludes(chatPanel, "import type { CommandCatalogItem, NoticeState } from \"../composables/useChatClient\";", "chat panel imports typed command catalog and notice state");
assertIncludes(chatPanel, "notice: NoticeState;", "chat panel receives typed notice state");
assertIncludes(chatPanel, "commandHints: ValueRef<CommandCatalogItem[]>;", "chat panel exposes typed command hints");
assertIncludes(chatPanel, "currentEntries: ValueRef<LiveEntry[]>;", "chat panel exposes typed live entry refs");
assertIncludes(chatPanel, "currentMessages: ValueRef<ChatMessage[]>;", "chat panel exposes typed chat message refs");
assertIncludes(chatPanel, "currentRuns: ValueRef<RunViewState[]>;", "chat panel exposes typed run refs");
assertIncludes(chatPanel, "applyCommandHint: (command: CommandCatalogItem) => void;", "chat panel applies typed command hints");
assertIncludes(chatPanel, "client.commandHints.value.map((command: CommandCatalogItem)", "chat panel renders typed command hints");
assertIncludes(messageList, "MessageTextRenderer", "React message renderer");
assertIncludes(messageList, "import type { MessageCopy } from \"./messageMarkdown\";", "message list imports typed message copy boundary");
assertIncludes(messageList, "import type { RunViewState } from \"../composables/chatClientRunHelpers\";", "message list imports typed run view state");
assertIncludes(messageList, "import type { ChatMessage, LiveEntry } from \"../composables/chatClientSessions\";", "message list imports typed chat session models");
assertIncludes(messageList, "entries: LiveEntry[];", "message list accepts typed live entries");
assertIncludes(messageList, "messages: ChatMessage[];", "message list accepts typed chat messages");
assertIncludes(messageList, "runs: RunViewState[];", "message list accepts typed runs");
assertIncludes(messageList, "message__trace-button", "message list keeps trace action button");
assertIncludes(messageList, "viewTraceForRun(message.traceRunId)", "message list keeps trace run selection callback");
assertIncludes(messageList, "normalizeMessages", "message list keeps message normalization");
assertIncludes(messageList, "message.content.map((part: NormalizedMessagePart)", "message list renders typed normalized parts");
assertIncludes(messageList, "message__artifact", "message list keeps artifact cards");
assertNotIncludes(messageList, "type AnyRecord", "message list no longer relies on dynamic AnyRecord props");
assertNotIncludes(messageList, "Record<string, any>", "message list avoids broad dynamic records");
assertIncludes(messageMarkdown, "export type MessageBlock =", "message markdown exports typed block union");
assertIncludes(messageMarkdown, "export function buildMessageBlocks(copy: MessageCopy, value: unknown", "message markdown narrows raw message input");
assertNotIncludes(messageMarkdown, "type AnyRecord", "message markdown avoids dynamic AnyRecord alias");
assertNotIncludes(messageMarkdown, "Record<string, any>", "message markdown avoids broad dynamic records");
assertIncludes(displayHelpers, "export type ConnectionCopy = {", "display helpers type connection copy boundary");
assertIncludes(displayHelpers, "export type RunOptionCopy = {", "display helpers type run option copy boundary");
assertIncludes(displayHelpers, "import type { ConnectionState, NoticeTone } from \"../composables/useChatClient\";", "display helpers imports typed connection and notice tone");
assertIncludes(displayHelpers, "export function connectionLabel(copy: ConnectionCopy, state: ConnectionState)", "display helpers labels typed connection states");
assertIncludes(displayHelpers, "export function noticeTone(tone: NoticeTone | string | null | undefined): NoticeTone", "display helpers normalizes notice tones to typed values");
assertIncludes(displayHelpers, "[\"cancelled\", \"cancelling\", \"stopped\"]", "display helpers renders stopped runs with warning color");
assertNotIncludes(displayHelpers, "type AnyRecord", "display helpers avoid dynamic AnyRecord alias");
assertNotIncludes(displayHelpers, "Record<string, any>", "display helpers avoid broad dynamic records");
assertIncludes(messageData, "import type { MessageBlock, MessageCopy } from \"./messageMarkdown\";", "message data imports typed message block boundary");
assertIncludes(messageData, "import { normalizeChatMessageRole, type ChatMessage, type ChatMessageRole, type LiveEntry } from \"../composables/chatClientSessions\";", "message data imports typed message role helpers");
assertIncludes(messageData, "import { toPayloadSource } from \"../composables/payloadBoundary\";", "message data reuses the shared finite payload guard");
assertNotIncludes(messageData, "type PayloadSource<Payload extends object>", "message data avoids a duplicate payload source type");
assertNotIncludes(messageData, "function toPayloadSource<Payload extends object>", "message data avoids a duplicate payload source guard");
assertIncludes(messageData, "role: ChatMessageRole;", "message data exposes typed normalized message roles");
assertIncludes(messageData, "textBlocks: MessageBlock[];", "message data exposes typed message blocks");
assertIncludes(messageData, "entries: LiveEntry[];", "message data normalizes typed live entries");
assertIncludes(messageData, "messages: ChatMessage[];", "message data normalizes typed chat messages");
assertIncludes(messageData, "runs: RunViewState[];", "message data normalizes typed runs");
assertIncludes(messageData, "type RunReferenceMetadataSource = {", "message data names the finite trace metadata boundary");
assertIncludes(messageData, "metadata?: unknown;", "message data keeps extensible trace metadata unknown at the input boundary");
assertIncludes(messageData, "const metadata = toPayloadSource<RunReferenceMetadataSource>(entry.metadata);", "message data limits trace metadata reads to known run id aliases");
assertNotIncludes(messageData, "metadata?: Record<string, unknown> | null;", "message data avoids an open trace metadata record");
assertIncludes(messageData, "function findTraceRunIdForEntry(entry: RunReferenceSource", "message data narrows trace matching inputs");
assertIncludes(messageData, "function findTraceRunIdForEntry(entry: RunReferenceSource, role: ChatMessageRole", "message data accepts typed roles for trace matching");
assertIncludes(messageData, "type MessageContentPartPayload = {", "message data types live entry content part payloads");
assertIncludes(messageData, "function toMessageContentPartPayload(value: unknown): MessageContentPartPayload | null", "message data narrows content parts through a named payload boundary");
assertIncludes(messageData, "const payload = toPayloadSource<MessageContentPartPayload>(value);", "message data limits content part reads to known payload fields");
assertIncludes(messageData, "id: payload.id,\n        text: payload.text,\n        detail: payload.detail,", "message data projects live entry content parts onto named fields");
assertNotIncludes(messageData, "value as Record<string, unknown>", "message data avoids casting finite content parts to open records");
assertNotIncludes(messageData, "type JsonRecord", "message data avoids dynamic JsonRecord alias");
assertNotIncludes(messageData, "const record = toJsonRecord(part);", "message data avoids raw content part records");
assertNotIncludes(messageData, "value as JsonRecord", "message data avoids casting content parts to generic JSON records");
assertNotIncludes(messageData, "type AnyRecord", "message data avoids dynamic AnyRecord alias");
assertNotIncludes(messageData, "Record<string, any>", "message data avoids broad dynamic records");
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
assertIncludes(mobileNavControls, "interface MobileNavCopy", "mobile nav uses typed copy props");
assertIncludes(mobileNavControls, "copy: { value: MobileNavCopy }", "mobile nav client exposes typed copy value");
assertNotIncludes(mobileNavControls, "type AnyRecord", "mobile nav no longer relies on dynamic AnyRecord props");
assertIncludes(confirmDialog, "okButtonProps={{ danger: true, loading: dialog.busy }}", "confirm dialog keeps destructive loading state");
assertIncludes(confirmDialog, "cancelButtonProps={{ disabled: dialog.busy }}", "confirm dialog disables cancel while busy");
assertIncludes(confirmDialog, "onCancel={dialog.busy ? undefined : onCancel}", "confirm dialog blocks cancel while busy");
assertIncludes(confirmDialog, "Alert type=\"warning\"", "confirm dialog keeps warning detail");
assertIncludes(generalSettings, "client.settingsState", "settings API state remains wired through settings modules");
assertIncludes(browserSettings, "client.saveBrowserSettings", "browser settings save action");
assertIncludes(browserSettings, "client.runBrowserTest", "browser manual test action");
assertIncludes(mcpSettings, "client.saveMcpServer", "MCP settings action");
assertIncludes(mcpSettings, "import { MCP_TRANSPORT_TYPES, normalizeMcpTransport } from \"../composables/settingsNormalizers\";", "MCP settings imports typed transport options");
assertIncludes(mcpSettings, "options={MCP_TRANSPORT_TYPES.map((transport) => ({ value: transport, label: transport }))}", "MCP settings renders transport options from typed constants");
assertIncludes(mcpSettings, "onChange={(value) => (form.type = normalizeMcpTransport(value))}", "MCP settings normalizes transport selection");
assertIncludes(modelSettings, "client.selectModel", "model selection action");
assertIncludes(modelSettings, "MODEL_REASONING_EFFORTS.map((effort)", "model settings renders reasoning options from typed constants");
assertIncludes(modelSettings, "normalizeModelReasoningEffort(value)", "model settings normalizes selected reasoning effort");
assertIncludes(modelSettings, "reasoningSelections: Record<string, ModelReasoningEffort>", "model settings narrows reasoning selection state");
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
assertIncludes(providerSettings, "providerAuthSections(copy, state, client)", "provider settings passes its finite auth state directly to section assembly");
assertIncludes(providerAuthMetadata, "providerId: \"openai-codex\"", "provider auth metadata keep Codex provider id in section metadata");
assertIncludes(providerAuthMetadata, "providerId: \"copilot\"", "provider auth metadata keep Copilot provider id in section metadata");
assertNotIncludes(providerAuthMetadata, "CODEX_PROVIDER_ID", "provider auth metadata avoid Codex provider id middle constant");
assertNotIncludes(providerAuthMetadata, "COPILOT_PROVIDER_ID", "provider auth metadata avoid Copilot provider id middle constant");
assertIncludes(providerAuthMetadata, "PROVIDER_AUTH_PROVIDER_IDS = PROVIDER_AUTH_SECTION_CONFIGS.map((config) => config.providerId)", "provider auth metadata derive auth provider ids from section metadata");
assertIncludes(providerAuthMetadata, "export type ProviderAuthSectionConfig = (typeof PROVIDER_AUTH_SECTION_CONFIGS)[number];", "provider auth metadata exports its finite section config union");
assertIncludes(providerAuthMetadata, "export function providerAuthSectionForId", "provider auth metadata centralize provider auth section lookup");
assertIncludes(providerAuthMetadata, "providerAuthSectionForId(providerId: string): ProviderAuthSectionConfig | undefined", "provider auth metadata types missing section lookups without assertions");
assertIncludes(providerAuthMetadata, "PROVIDER_AUTH_SECTION_CONFIGS.find((config) => config.providerId === providerId)", "provider auth metadata looks up directly from the finite config list");
assertNotIncludes(providerAuthMetadata, "PROVIDER_AUTH_SECTIONS", "provider auth metadata avoids a dynamic section index");
assertNotIncludes(providerAuthMetadata, "function providerAuthKeyForId", "provider auth metadata keep auth key derivation out of exported constants");
assertNotIncludes(providerAuthMetadata, "PROVIDER_AUTH_KEYS", "provider auth metadata avoid duplicate auth key map ownership");
assertIncludes(providerAuthMetadata, "providerName: \"OpenAI Codex\"", "provider auth metadata keep Codex provider name in section metadata");
assertIncludes(providerAuthMetadata, "providerName: \"GitHub Copilot\"", "provider auth metadata keep Copilot provider name in section metadata");
assertNotIncludes(providerAuthMetadata, "CODEX_PROVIDER_NAME", "provider auth metadata avoid Codex provider name middle constant");
assertNotIncludes(providerAuthMetadata, "COPILOT_PROVIDER_NAME", "provider auth metadata avoid Copilot provider name middle constant");
assertIncludes(providerAuthMetadata, "providerAuthSectionKeys(\"codexAuth\")", "provider auth metadata keep Codex auth key in provider metadata");
assertIncludes(providerAuthMetadata, "providerAuthSectionKeys(\"copilotAuth\")", "provider auth metadata keep Copilot auth key in provider metadata");
assertNotIncludes(providerAuthMetadata, "    authKey,\n", "provider auth metadata avoid exposing auth key as runtime metadata");
assertNotIncludes(providerAuthMetadata, "export const CODEX_AUTH_KEY", "provider auth metadata keep Codex auth key internal");
assertNotIncludes(providerAuthMetadata, "export const COPILOT_AUTH_KEY", "provider auth metadata keep Copilot auth key internal");
assertIncludes(providerAuthMetadata, "function providerAuthStateKeys", "provider auth metadata expose auth state key factory");
assertIncludes(providerAuthMetadata, "providerAuthStateKeys<const AuthKey extends string>", "provider auth metadata preserves literal auth state keys");
assertIncludes(providerAuthMetadata, "loadingKey: `${authKey}Loading` as const", "provider auth metadata preserves literal loading keys");
assertIncludes(providerAuthMetadata, "function providerAuthSectionKeys", "provider auth metadata keep UI copy key ownership in section metadata");
assertIncludes(providerAuthMetadata, "return { copyKey: authKey, ...providerAuthStateKeys(authKey) };", "provider auth metadata keep copy key out of auth state key factory");
assertNotIncludes(providerAuthMetadata, "function providerAuthInitialState", "provider auth metadata keep auth initial state assembly separate");
assertNotIncludes(providerAuthMetadata, "function createProviderAuthInitialStates", "provider auth metadata keep auth initial state assembly separate");
assertNotIncludes(providerAuthInitialState, "function providerAuthInitialState", "provider auth initial state avoids an open entry factory");
assertIncludes(providerAuthInitialState, "const [openaiCodexConfig, copilotConfig] = PROVIDER_AUTH_SECTION_CONFIGS;", "provider auth initial state binds every finite metadata entry");
assertNotIncludes(providerAuthInitialState, "[keys.authKey]: auth", "provider auth initial state avoids auth key ownership for writes");
assertIncludes(providerAuthInitialState, "function createProviderAuthInitialStates", "provider auth initial state centralizes provider auth initial states");
assertIncludes(providerAuthInitialState, "import type { ProviderAuthStatePayload }", "provider auth initial state reuses typed auth state payloads");
assertIncludes(providerAuthInitialState, "export type ProviderAuthStateKey =", "provider auth initial state exports finite auth payload keys");
assertIncludes(providerAuthInitialState, "export type ProviderAuthLoadingKey =", "provider auth initial state exports finite loading keys");
assertIncludes(providerAuthInitialState, "export type ProviderAuthMessageKey =", "provider auth initial state exports finite message keys");
assertIncludes(providerAuthInitialState, "export type ProviderAuthInitialStates =", "provider auth initial state exports finite provider slots");
assertIncludes(providerAuthInitialState, "{ [Key in ProviderAuthStateKey]: ProviderAuthStatePayload }", "provider auth initial state maps auth payload slots");
assertIncludes(providerAuthInitialState, "{ [Key in ProviderAuthLoadingKey]: boolean }", "provider auth initial state maps loading slots");
assertIncludes(providerAuthInitialState, "{ [Key in ProviderAuthMessageKey]: string }", "provider auth initial state maps message slots");
assertNotIncludes(providerAuthInitialState, "type ProviderAuthInitialStates = Record<string", "provider auth initial state avoids open-ended exported slots");
assertIncludes(providerAuthInitialState, "createProviderAuthInitialStates(): ProviderAuthInitialStates", "provider auth initial state exposes typed initial state map");
assertNotIncludes(providerAuthInitialState, "as ProviderAuthInitialStates", "provider auth initial state avoids asserting its assembled state");
assertNotIncludes(providerAuthInitialState, "ProviderAuthInitialStateEntry", "provider auth initial state avoids an open intermediate entry map");
assertIncludes(providerAuthMetadata, "function providerDeviceAuthInitialState", "provider auth metadata share device auth initial state defaults");
assertIncludes(providerAuthMetadata, "ProviderAuthDeviceKey,\n  ProviderAuthStatePayload,", "provider auth metadata reuses finite device keys and typed auth state payloads");
assertIncludes(providerAuthMetadata, "extra: ProviderAuthStatePayload = {}", "provider auth metadata types device auth initial extras");
assertIncludes(providerAuthMetadata, "): ProviderAuthStatePayload", "provider auth metadata returns typed device auth initial state");
assertIncludes(providerAuthMetadata, "deviceKey: ProviderAuthDeviceKey", "provider auth metadata restricts device state keys to known providers");
assertIncludes(providerAuthMetadata, "deviceKey === \"deviceAuthId\"\n    ? { deviceAuthId: \"\" }\n    : { deviceCode: \"\" }", "provider auth metadata initializes finite device state fields");
assertNotIncludes(providerAuthMetadata, "[deviceKey]: \"\"", "provider auth metadata avoids open computed initial state fields");
assertIncludes(providerAuthMetadata, "PROVIDER_AUTH_SECTION_CONFIGS", "provider auth metadata centralize provider auth section metadata");
assertNotIncludes(providerAuthMetadata, "const CODEX_AUTH_KEY", "provider auth metadata avoid Codex auth key middle constant");
assertNotIncludes(providerAuthMetadata, "const COPILOT_AUTH_KEY", "provider auth metadata avoid Copilot auth key middle constant");
assertIncludes(providerAuthMetadata, "connectedNoticeKey: authKey.replace(/Auth$/, \"ProviderConnected\")", "provider auth metadata derive provider connected notices from auth keys");
assertNotIncludes(providerAuthMetadata, "export const CODEX_AUTH_STATE_KEYS", "provider auth metadata keep Codex auth state keys internal");
assertNotIncludes(providerAuthMetadata, "export const COPILOT_AUTH_STATE_KEYS", "provider auth metadata keep Copilot auth state keys internal");
assertIncludes(providerAuthMetadata, "DEFAULT_PROVIDER_AUTH_PROVIDER_ID = PROVIDER_AUTH_SECTION_CONFIGS[0].providerId", "provider auth metadata derive default auth provider from metadata");
assertIncludes(providerAuthHelpers, "function providerAuthSection", "provider auth helpers centralize provider section lookup");
assertIncludes(providerAuthHelpers, "return providerAuthSection(provider)?.copyKey || \"\"", "provider auth helpers derive auth copy keys through section metadata");
assertIncludes(providerAuthMetadata, "initialAuth: providerDeviceAuthInitialState(", "provider auth metadata keep auth initial payloads in provider metadata");
assertIncludes(providerAuthMetadata, "deviceKey: \"deviceAuthId\"", "provider auth metadata keep Codex device auth key in metadata");
assertIncludes(providerAuthMetadata, "payloadDeviceKey: \"device_auth_id\"", "provider auth metadata keep Codex device auth payload key in metadata");
assertIncludes(providerAuthMetadata, "pollRequiresUserCode: true", "provider auth metadata keep Codex poll user code requirement in metadata");
assertIncludes(providerAuthMetadata, "includeAccountStatus: true", "provider auth metadata keep Codex account status support in metadata");
assertIncludes(providerAuthMetadata, "loginExtra: { command: \"\" }", "provider auth metadata keep Codex login extras in metadata");
assertIncludes(providerAuthMetadata, "logoutReset: { expired: false, expires_at: null, account_id: \"\", command: \"\" }", "provider auth metadata keep Codex logout reset state in metadata");
assertIncludes(providerAuthMetadata, "deviceKey: \"deviceCode\"", "provider auth metadata keep Copilot device auth key in metadata");
assertIncludes(providerAuthMetadata, "payloadDeviceKey: \"device_code\"", "provider auth metadata keep Copilot device auth payload key in metadata");
assertIncludes(providerAuthMetadata, "logoutReset: { path: \"\" }", "provider auth metadata keep Copilot logout reset state in metadata");
assertIncludes(providerAuthInitialState, "[openaiCodexConfig.stateKey]: openaiCodexConfig.initialAuth", "provider auth initial state initializes Codex through finite metadata");
assertIncludes(providerAuthInitialState, "[copilotConfig.stateKey]: copilotConfig.initialAuth", "provider auth initial state initializes Copilot through finite metadata");
assertNotIncludes(providerAuthInitialState, "providerAuthInitialState(CODEX_AUTH_STATE_KEYS", "provider auth initial state avoids Codex-specific auth initial state assembly");
assertNotIncludes(providerAuthInitialState, "providerAuthInitialState(COPILOT_AUTH_STATE_KEYS", "provider auth initial state avoids Copilot-specific auth initial state assembly");
assertIncludes(providerAuthHelpers, "return providerAuthSectionForId(providerCatalogKey(provider))", "provider auth helpers delegate provider section lookup through shared provider key resolver");
assertIncludes(providerAuthHelpers, "authState(state, config).configured", "provider auth configured reads state through typed helper");
assertIncludes(providerAuthHelpers, "authCopyForConfig(copy, config)", "provider description reads login copy through typed helper");
assertNotIncludes(providerAuthMetadata, "function providerAuthEndpoint", "provider auth metadata keep endpoint builders in provider endpoints");
assertNotIncludes(providerAuthMetadata, "function providerSettingsEndpoint", "provider auth metadata keep provider endpoint builders separate");
assertNotIncludes(providerAuthMetadata, "function providerCredentialEndpoint", "provider auth metadata keep credential endpoint builders separate");
assertIncludes(providerEndpoints, "function providerAuthEndpoint", "provider endpoints expose auth endpoint builder");
assertIncludes(providerEndpoints, "`/api/settings/auth/${providerId}${action ? `/${action}` : \"\"}`", "provider endpoints keep auth endpoint path shape");
assertIncludes(providerEndpoints, "function providerSettingsEndpoint", "provider endpoints expose provider settings endpoint builder");
assertIncludes(providerEndpoints, "function providerCredentialEndpoint", "provider endpoints expose provider credential endpoint builder");
assertNotIncludes(providerAuthMetadata, "function providerAuthActionConfig", "provider auth metadata keep auth action metadata out of settings constants");
assertNotIncludes(providerAuthMetadata, "function providerAuthRequestConfig", "provider auth metadata avoid request-only naming for auth action metadata");
assertIncludes(providerAuthConfigs, "function providerAuthActionConfig", "provider auth configs own auth action metadata factory");
assertIncludes(providerAuthConfigs, "loginEndpoint: providerAuthEndpoint(providerId, \"login\")", "provider auth configs keep auth login endpoint metadata");
assertIncludes(providerAuthConfigs, "logoutEndpoint: providerAuthEndpoint(providerId, \"logout\")", "provider auth configs keep auth logout endpoint metadata");
assertIncludes(providerAuthConfigs, "pollEndpoint: providerAuthEndpoint(providerId, \"poll\")", "provider auth configs keep auth poll endpoint metadata");
assertIncludes(providerAuthConfigs, "type ProviderAuthStateKeys = Omit<", "provider auth configs retain shared notice metadata while narrowing state keys");
assertIncludes(providerAuthConfigs, "stateKey: ProviderAuthStateKey;\n  loadingKey: ProviderAuthLoadingKey;\n  errorKey: ProviderAuthMessageKey;\n  noticeKey: ProviderAuthMessageKey;", "provider auth configs bind action slots to finite metadata-derived keys");
assertIncludes(providerAuthConfigs, "const actionKeys: ProviderAuthStateKeys = {", "provider auth configs project action metadata through an explicit typed object");
assertNotIncludes(providerAuthConfigs, "Object.keys(providerAuthStateKeys(\"\"))", "provider auth configs avoid asserting Object.keys results");
assertNotIncludes(providerAuthConfigs, "as ProviderAuthActionKey[]", "provider auth configs avoid casting dynamic action key arrays");
assertNotIncludes(providerAuthConfigs, "as ProviderAuthStateKeys", "provider auth configs avoid casting projected action metadata");
assertIncludes(providerAuthMetadata, "oauthAuthType: \"openai_codex_oauth\"", "provider auth metadata keep Codex OAuth auth type in section metadata");
assertIncludes(providerAuthMetadata, "oauthAuthType: \"github_copilot_oauth\"", "provider auth metadata keep Copilot OAuth auth type in section metadata");
assertNotIncludes(providerAuthMetadata, "OPENAI_CODEX_OAUTH_AUTH_TYPE", "provider auth metadata avoid Codex OAuth auth type middle constant");
assertNotIncludes(providerAuthMetadata, "GITHUB_COPILOT_OAUTH_AUTH_TYPE", "provider auth metadata avoid Copilot OAuth auth type middle constant");
assertNotIncludes(providerAuthMetadata, "function isOAuthProviderAuthType", "provider auth metadata keep OAuth auth type helper out of metadata constants");
assertIncludes(providerAuthHelpers, "function isOAuthProviderAuthType", "provider auth helpers expose OAuth auth type helper");
assertNotIncludes(providerHelpers, "function isOAuthProviderAuthType", "provider helpers keep OAuth auth type helper out of generic helpers");
assertIncludes(providerAuthMetadata, "oauthAuthType: \"openai_codex_oauth\"", "provider auth metadata keep Codex OAuth auth type in provider metadata");
assertIncludes(providerAuthMetadata, "oauthAuthType: \"github_copilot_oauth\"", "provider auth metadata keep Copilot OAuth auth type in provider metadata");
assertIncludes(providerAuthHelpers, "PROVIDER_AUTH_SECTION_CONFIGS.some((config) => config.oauthAuthType === authType)", "provider auth helpers resolve OAuth auth types from provider metadata");
assertNotIncludes(providerAuthHelpers, "authType === OPENAI_CODEX_OAUTH_AUTH_TYPE || authType === GITHUB_COPILOT_OAUTH_AUTH_TYPE", "provider auth helpers avoid hardcoded OAuth auth type branch");
assertIncludes(providerAuthSections, "providerAuthVisible(state, config)", "provider auth sections delegate visibility through typed provider metadata");
assertIncludes(providerAuthMetadata, "providerId: \"openai-codex\"", "provider auth metadata keep Codex auth provider section");
assertIncludes(providerAuthMetadata, "providerId: \"copilot\"", "provider auth metadata keep Copilot auth provider section");
assertIncludes(providerAuthSections, "PROVIDER_AUTH_SECTION_CONFIGS.map", "provider auth sections consume provider section metadata");
assertIncludes(providerAuthSections, "key: config.providerId", "provider auth sections derive section key from provider id");
assertNotIncludes(providerAuthMetadata, "CODEX_AUTH_STATE_KEYS", "provider auth metadata avoid Codex auth state key middle constant");
assertNotIncludes(providerAuthMetadata, "COPILOT_AUTH_STATE_KEYS", "provider auth metadata avoid Copilot auth state key middle constant");
assertIncludes(providerAuthSections, "const auth = authState(state, config)", "provider auth sections read auth state through shared typed helper");
assertIncludes(providerAuthSections, "const copyForAuth = authCopyForConfig(copy, config);", "provider auth sections read copy through shared typed helper");
assertNotIncludes(providerAuthSections, "const auth = state[config.copyKey]", "provider auth sections keep copy key separate from state key");
assertIncludes(providerAuthMetadata, "providerName: \"OpenAI Codex\"", "provider auth metadata keep Codex provider name in section metadata");
assertIncludes(providerAuthMetadata, "providerName: \"GitHub Copilot\"", "provider auth metadata keep Copilot provider name in section metadata");
assertNotIncludes(providerAuthSections, "CODEX_AUTH_STATE_KEYS", "provider auth sections avoid owning Codex auth state metadata");
assertNotIncludes(providerAuthSections, "COPILOT_AUTH_STATE_KEYS", "provider auth sections avoid owning Copilot auth state metadata");
assertIncludes(providerAuthSections, "text(copyForAuth.title, `${config.providerName} auth`)", "provider auth sections derive default title from provider name");
assertIncludes(providerAuthSections, "text(copyForAuth.name, config.providerName)", "provider auth sections derive default name from provider name");
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
assertNotIncludes(providerAuthConfigs, "resolveProviderAuthConfigId", "provider auth configs avoid fallback wrapper helper");
assertIncludes(providerAuthConfigs, "export function getProviderAuthConfig", "provider auth configs centralize provider config lookup");
assertIncludes(providerAuthConfigs, "const section = providerAuthSectionForId(providerId);", "provider auth configs narrow provider ids through shared metadata");
assertIncludes(providerAuthConfigs, "providerAuthConfigs[section?.providerId ?? DEFAULT_PROVIDER_AUTH_PROVIDER_ID]", "provider auth configs keep provider id fallback inside lookup helper");
assertIncludes(providerAuthConfigs, "DEFAULT_PROVIDER_AUTH_PROVIDER_ID", "provider auth configs use metadata-derived default provider");
assertNotIncludes(providerAuthConfigs, ": CODEX_PROVIDER_ID;", "provider auth configs avoid direct Codex fallback");
assertIncludes(providerAuthActions, "getProviderAuthConfig(providerAuthConfigs, providerId)", "provider auth actions reuse provider config lookup helper");
assertIncludes(providerAuthConfigs, "PROVIDER_AUTH_SECTION_CONFIGS", "provider auth configs build configs directly from provider section metadata");
assertIncludes(providerAuthConfigs, "export type ProviderAuthConfigMap = {\n  [ProviderId in ProviderAuthProviderId]: ProviderAuthConfig;\n};", "provider auth configs expose a finite provider-id map");
assertIncludes(providerAuthConfigs, "createProviderAuthConfigs(): ProviderAuthConfigMap", "provider auth configs return the finite provider-id map");
assertIncludes(providerAuthConfigs, "const [openaiCodexConfig, copilotConfig] = PROVIDER_AUTH_SECTION_CONFIGS;", "provider auth configs assemble every finite metadata entry");
assertIncludes(providerAuthConfigs, "[openaiCodexConfig.providerId]: deviceAuthBaseConfig(openaiCodexConfig)", "provider auth configs assemble Codex through finite metadata");
assertIncludes(providerAuthConfigs, "[copilotConfig.providerId]: deviceAuthBaseConfig(copilotConfig)", "provider auth configs assemble Copilot through finite metadata");
assertNotIncludes(providerAuthConfigs, "Object.fromEntries", "provider auth configs avoid widening finite provider ids through Object.fromEntries");
assertNotIncludes(providerAuthConfigs, "CODEX_PROVIDER_ID", "provider auth configs avoid hardcoded Codex config entry");
assertNotIncludes(providerAuthConfigs, "COPILOT_PROVIDER_ID", "provider auth configs avoid hardcoded Copilot config entry");
assertIncludes(providerAuthConfigs, "function deviceAuthBaseConfig", "provider auth configs share device auth base config helper");
assertIncludes(providerAuthConfigs, "deviceAuthBaseConfig(openaiCodexConfig)", "provider auth configs reuse shared base config for Codex metadata");
assertIncludes(providerAuthConfigs, "deviceAuthBaseConfig(copilotConfig)", "provider auth configs reuse shared base config for Copilot metadata");
assertIncludes(providerAuthConfigs, "function deviceAuthPollConfig", "provider auth configs share device auth poll config helper");
assertIncludes(providerAuthConfigs, "...deviceAuthPollConfig(config)", "provider auth configs reuse shared poll config inside base config");
assertIncludes(providerAuthConfigs, "auth[config.deviceKey]", "provider auth configs read device key from metadata");
assertIncludes(providerAuthConfigs, "config.payloadDeviceKey", "provider auth configs read payload key from metadata");
assertNotIncludes(providerAuthConfigs, "\"deviceAuthId\"", "provider auth configs avoid hardcoded Codex device auth key");
assertNotIncludes(providerAuthConfigs, "payloadDeviceKey: \"device_auth_id\"", "provider auth configs avoid hardcoded Codex device auth payload metadata");
assertNotIncludes(providerAuthConfigs, "\"deviceCode\"", "provider auth configs avoid hardcoded Copilot device auth key");
assertNotIncludes(providerAuthConfigs, "payloadDeviceKey: \"device_code\"", "provider auth configs avoid hardcoded Copilot device auth payload metadata");
assertIncludes(providerAuthActions, "loadProviderAuthStatusById,", "provider auth actions expose provider-id auth status action");
assertNotIncludes(providerAuthActions, "async function loadProviderAuthStatus(config)", "provider auth actions avoid status loader wrapper");
assertNotIncludes(providerAuthActions, "async function loadCodexAuthStatus", "provider auth actions avoid Codex-specific status wrapper");
assertNotIncludes(providerAuthActions, "async function loadCopilotAuthStatus", "provider auth actions avoid Copilot-specific status wrapper");
assertIncludes(providerAuthConfigs, "function normalizeConfiguredPathStatus", "provider auth configs share configured/path status normalization");
assertIncludes(providerAuthConfigs, "function normalizeProviderAccountStatus", "provider auth configs share provider account status normalization");
assertIncludes(providerAuthConfigs, "export type ProviderAuthConfig", "provider auth configs expose typed provider auth config");
assertIncludes(providerAuthState, "export type ProviderDeviceAuthPayloadDeviceKey = \"device_auth_id\" | \"device_code\";", "provider auth state types device login payload keys");
assertIncludes(providerAuthState, "export type ProviderDeviceAuthLoginPayload = {", "provider auth state types fixed device login API payload");
assertIncludes(providerAuthState, "verification_uri?: unknown;", "provider auth device login payload names verification URI field");
assertIncludes(providerAuthState, "user_code?: unknown;", "provider auth device login payload names user code field");
assertIncludes(providerAuthState, "interval?: unknown;", "provider auth device login payload names poll interval field");
assertIncludes(providerAuthState, "device_auth_id?: unknown;", "provider auth device login payload names Codex device auth id field");
assertIncludes(providerAuthState, "device_code?: unknown;", "provider auth device login payload names Copilot device code field");
assertNotIncludes(providerAuthState, "export type ProviderDeviceAuthLoginPayload = JsonRecord & {", "provider auth state avoids broad device login API payload records");
assertIncludes(providerAuthState, "export type ProviderAuthDeviceKey = \"deviceAuthId\" | \"deviceCode\";", "provider auth state restricts device fields to known keys");
assertIncludes(providerAuthState, "export type ProviderAuthPendingPayload = {", "provider auth state types a finite pending auth payload");
assertIncludes(providerAuthState, "deviceAuthId?: string;", "provider auth pending payload names Codex device state field");
assertIncludes(providerAuthState, "deviceCode?: string;", "provider auth pending payload names Copilot device state field");
assertIncludes(providerAuthState, "command?: string;", "provider auth pending payload names Codex command state field");
assertNotIncludes(providerAuthState, "ProviderAuthStateFields", "provider auth state avoids open-ended provider-specific fields");
assertNotIncludes(providerAuthState, "ProviderAuthStateValue", "provider auth state avoids a generic primitive value bucket");
assertNotIncludes(providerAuthState, "normalizeProviderAuthStatePayload", "provider auth state avoids normalizing trusted internal state as an open payload");
assertIncludes(providerAuthState, "verificationUri?: string;", "provider auth pending payload names verification URI state field");
assertIncludes(providerAuthState, "userCode?: string;", "provider auth pending payload names user code state field");
assertIncludes(providerAuthState, "pollIntervalSeconds?: number;", "provider auth pending payload names poll interval state field");
assertIncludes(providerAuthState, "export type ProviderAuthStatusPayload = {", "provider auth state names fixed status API payload boundary");
assertIncludes(providerAuthState, "configured?: unknown;", "provider auth status payload names configured field");
assertIncludes(providerAuthState, "path?: unknown;", "provider auth status payload names path field");
assertIncludes(providerAuthState, "expired?: unknown;", "provider auth status payload names expiry field");
assertIncludes(providerAuthState, "expires_at?: unknown;", "provider auth status payload names expiry timestamp field");
assertIncludes(providerAuthState, "account_id?: unknown;", "provider auth status payload names account id field");
assertNotIncludes(providerAuthState, "export type ProviderAuthStatusPayload = JsonRecord & {", "provider auth state avoids broad status API payload records");
assertIncludes(providerAuthState, "export type ProviderAuthStatePayload = ProviderAuthPendingPayload & {", "provider auth state types stored auth state payload");
assertIncludes(providerAuthState, "configured?: boolean;", "provider auth state narrows configured state field");
assertIncludes(providerAuthState, "path?: string;", "provider auth state narrows path state field");
assertIncludes(providerAuthState, "expired?: boolean;", "provider auth state narrows expired state field");
assertIncludes(providerAuthState, "expires_at?: string | null;", "provider auth state narrows expiry timestamp state field");
assertIncludes(providerAuthState, "account_id?: string;", "provider auth state narrows account id state field");
assertIncludes(providerAuthState, "payload: ProviderDeviceAuthLoginPayload,", "provider auth state narrows device login payload input");
assertIncludes(providerAuthState, "payloadDeviceKey: ProviderDeviceAuthPayloadDeviceKey,", "provider auth state narrows device login payload key input");
assertIncludes(providerAuthState, "function deviceAuthPayloadValue(", "provider auth state centralizes typed device payload key reads");
assertNotIncludes(providerAuthState, "payload[payloadDeviceKey]", "provider auth state avoids dynamic device login payload reads");
assertIncludes(providerAuthState, "function deviceAuthState(", "provider auth state centralizes finite device state construction");
assertIncludes(providerAuthState, "deviceKey: ProviderAuthDeviceKey", "provider auth state restricts device state writes to finite keys");
assertIncludes(providerAuthState, "extra: ProviderAuthPendingPayload = {}", "provider auth state types device login extra state values");
assertIncludes(providerAuthState, "): ProviderAuthPendingPayload {", "provider auth state returns typed pending auth payload");
assertIncludes(providerAuthState, "...deviceAuthState(deviceKey, String(deviceAuthPayloadValue(payload, payloadDeviceKey) || \"\"))", "provider auth state writes normalized login device values through finite fields");
assertIncludes(providerAuthState, "export function clearedDeviceAuthState(deviceKey: ProviderAuthDeviceKey): ProviderAuthPendingPayload", "provider auth state clears typed pending auth payload");
assertIncludes(providerAuthState, "...deviceAuthState(deviceKey, \"\")", "provider auth state clears finite device state fields");
assertIncludes(providerAuthConfigs, "type ProviderAuthPendingPayload", "provider auth configs import pending auth payload type");
assertIncludes(providerAuthConfigs, "type ProviderAuthStatePayload", "provider auth configs import stored auth state payload type");
assertIncludes(providerAuthConfigs, "type ProviderAuthDeviceKey", "provider auth configs import finite device state keys");
assertNotIncludes(providerAuthConfigs, "ProviderAuthStateValue", "provider auth configs avoid generic primitive auth values");
assertIncludes(providerAuthConfigs, "type ProviderAuthStatusPayload", "provider auth configs import status payload type");
assertIncludes(providerAuthConfigs, "type ProviderDeviceAuthPayloadDeviceKey", "provider auth configs import typed device auth payload key");
assertIncludes(providerAuthConfigs, "type ProviderDeviceAuthLoginPayload", "provider auth configs import device login payload type");
assertIncludes(providerAuthConfigs, "hasPendingPoll: (auth: ProviderAuthPendingPayload) => boolean;", "provider auth configs use typed pending auth for poll checks");
assertIncludes(providerAuthConfigs, "type ProviderAuthPollRequestPayload = {", "provider auth configs type fixed poll request payloads");
assertIncludes(providerAuthConfigs, "device_auth_id?: string;", "provider auth configs type Codex poll device auth id field");
assertIncludes(providerAuthConfigs, "device_code?: string;", "provider auth configs type Copilot poll device code field");
assertIncludes(providerAuthConfigs, "user_code?: string;", "provider auth configs type optional poll user code field");
assertIncludes(providerAuthConfigs, "buildPollBody: (auth: ProviderAuthPendingPayload) => ProviderAuthPollRequestPayload;", "provider auth configs use typed pending auth for fixed poll payloads");
assertIncludes(providerAuthConfigs, "normalizeLogin: (payload: ProviderDeviceAuthLoginPayload) => ProviderAuthPendingPayload;", "provider auth configs type device login normalizer boundary");
assertIncludes(providerAuthConfigs, "normalizeStatus: (payload: ProviderAuthStatusPayload) => ProviderAuthStatePayload;", "provider auth configs type status normalizer boundary");
assertIncludes(providerAuthConfigs, "normalizeAuthorized: (auth: ProviderAuthStatusPayload, currentAuth: ProviderAuthStatePayload) => ProviderAuthStatePayload;", "provider auth configs type authorized normalizer boundary");
assertIncludes(providerAuthConfigs, "resetLogout: (auth: ProviderAuthStatePayload) => ProviderAuthStatePayload;", "provider auth configs type logout state reset boundary");
assertIncludes(providerAuthConfigs, "hasPendingPoll: (auth: ProviderAuthPendingPayload) => Boolean", "provider auth poll config checks typed pending auth payload");
assertIncludes(providerAuthConfigs, "function deviceAuthPollBody(config: ProviderAuthSectionConfig, auth: ProviderAuthPendingPayload): ProviderAuthPollRequestPayload", "provider auth configs centralize typed poll body construction");
assertIncludes(providerAuthConfigs, "body.device_auth_id = auth[config.deviceKey];", "provider auth configs write Codex poll body through fixed field");
assertIncludes(providerAuthConfigs, "body.device_code = auth[config.deviceKey];", "provider auth configs write Copilot poll body through fixed field");
assertIncludes(providerAuthConfigs, "body.user_code = auth.userCode;", "provider auth configs write optional poll user code through fixed field");
assertIncludes(providerAuthConfigs, "buildPollBody: (auth: ProviderAuthPendingPayload) => deviceAuthPollBody(config, auth),", "provider auth poll config builds typed fixed poll payloads");
assertIncludes(providerAuthConfigs, "type ProviderAuthSectionConfig = ProviderAuthStateKeys & {", "provider auth configs type provider section metadata without a generic record boundary");
assertIncludes(providerAuthConfigs, "deviceKey: ProviderAuthDeviceKey;", "provider auth configs restrict metadata device keys to finite state fields");
assertIncludes(providerAuthConfigs, "payloadDeviceKey: ProviderDeviceAuthPayloadDeviceKey;", "provider auth configs narrow provider section device payload keys");
assertNotIncludes(providerAuthConfigs, "type JsonRecord = Record<string, unknown>;", "provider auth configs avoid generic JSON records for poll bodies");
assertIncludes(providerAuthConfigs, "function optionalText(value: unknown): string", "provider auth configs normalize raw status text values");
assertIncludes(providerAuthConfigs, "function optionalNullableText(value: unknown): string | null", "provider auth configs normalize nullable status text values");
assertIncludes(providerAuthConfigs, "normalizeStatus: (payload: ProviderAuthStatusPayload) => normalizeConfiguredPathStatus(payload, normalizeProviderAccountStatus(config, payload))", "provider auth configs normalize status through shared provider metadata");
assertIncludes(providerAuthConfigs, "normalizeProviderAccountStatus(config, payload)", "provider auth configs read account status from provider metadata");
assertIncludes(providerAuthConfigs, "path: optionalText(payload.path)", "provider auth configs store normalized auth status path");
assertIncludes(providerAuthConfigs, "expires_at: optionalNullableText(payload.expires_at)", "provider auth configs store normalized auth expiry timestamp");
assertIncludes(providerAuthConfigs, "account_id: optionalText(payload.account_id)", "provider auth configs store normalized auth account id");
assertNotIncludes(providerAuthConfigs, "type ProviderAuthSectionConfig = ProviderAuthStateKeys & JsonRecord & {", "provider auth configs keep generic record inheritance out of provider section metadata");
assertNotIncludes(providerAuthConfigs, "ProviderAuthConfigPayload", "provider auth configs avoid broad config payload aliases");
assertNotIncludes(providerAuthConfigs, "Record<string, any>", "provider auth configs avoid broad dynamic records");
assertIncludes(providerAuthRequests, "export async function requestProviderAuthStatus", "provider auth requests centralize auth status request");
for (const [providerRequestModule, moduleName] of [
  [providerSettingsLoader, "provider settings loader"],
  [providerSettingsRequests, "provider settings requests"],
  [providerAuthRequests, "provider auth requests"],
]) {
  assertIncludes(providerRequestModule, "import { toPayloadSource } from \"./payloadBoundary\";", `${moduleName} reuse the shared finite payload guard`);
  assertIncludes(providerRequestModule, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", `${moduleName} keep API responses unknown until conversion`);
  assertNotIncludes(providerRequestModule, "type PayloadSource<Payload extends object>", `${moduleName} avoid a duplicate payload source type`);
  assertNotIncludes(providerRequestModule, "function toPayloadSource<Payload extends object>", `${moduleName} avoid a duplicate payload source guard`);
  assertNotIncludes(providerRequestModule, "requestSettingsJson<", `${moduleName} avoid trusting unchecked API response generics`);
}
assertIncludes(providerAuthRequests, "import type { ProviderAuthConfig } from \"./providerAuthConfigs\";", "provider auth requests reuse provider auth config type");
assertIncludes(providerAuthRequests, "type ProviderAuthPendingPayload,", "provider auth requests reuse pending auth payload type");
assertIncludes(providerAuthRequests, "type ProviderAuthStatusPayload,", "provider auth requests reuse status auth payload type");
assertIncludes(providerAuthRequests, "type ProviderDeviceAuthLoginPayload,", "provider auth requests reuse device login payload type");
assertIncludes(providerAuthRequests, "type ProviderAuthRequestConfig = ProviderOAuthConnectOptions & Pick<", "provider auth requests narrow request config to provider auth config fields");
assertIncludes(providerConnectForm, "providerName?: string;", "provider connect form narrows OAuth provider name fallback");
assertNotIncludes(providerConnectForm, "export type ProviderOAuthConnectOptions = {\n  providerName?: unknown;", "provider connect form avoids unknown OAuth provider name fallback");
assertIncludes(providerAuthRequests, "ProviderAuthConfig,", "provider auth requests derive request config from provider auth config");
assertIncludes(providerAuthRequests, "\"providerId\" | \"endpoint\" | \"loginEndpoint\" | \"pollEndpoint\" | \"logoutEndpoint\" | \"buildPollBody\"", "provider auth requests require typed endpoint and poll config fields");
assertIncludes(providerAuthRequests, "export type ProviderAuthPollPayload = {", "provider auth requests expose typed auth poll payload");
assertNotIncludes(providerAuthRequests, "export type ProviderAuthPayload", "provider auth requests split shared auth payload into per-endpoint payloads");
assertNotIncludes(providerAuthRequests, "export type ProviderAuthPayload = JsonRecord & ProviderAuthStatusPayload & {", "provider auth requests keep dynamic login payloads out of status and poll responses");
assertIncludes(providerAuthRequests, "export type ProviderAuthMutationPayload = {", "provider auth requests name fixed auth mutation payload boundary");
assertIncludes(providerAuthRequests, "auth?: ProviderAuthStatusPayload;", "provider auth requests type nested auth status payload");
assertIncludes(providerAuthRequests, "status?: string;", "provider auth requests type auth status string");
assertNotIncludes(providerAuthRequests, "function toJsonRecord(value: unknown): JsonRecord", "provider auth requests avoid a generic record converter for finite responses");
for (const payloadType of ["ProviderAuthStatusPayload", "ProviderDeviceAuthLoginPayload", "ProviderAuthPollPayload", "ProviderAuthMutationPayload"]) {
  assertIncludes(providerAuthRequests, `toPayloadSource<${payloadType}>(value)`, `provider auth requests limit ${payloadType} source reads to known fields`);
}
assertIncludes(providerAuthRequests, "function toProviderAuthStatusPayload(value: unknown): ProviderAuthStatusPayload", "provider auth requests project auth status payloads onto named fields");
assertIncludes(providerAuthRequests, "function toProviderAuthStatusPayload(value: unknown): ProviderAuthStatusPayload {\n  const payload = toPayloadSource<ProviderAuthStatusPayload>(value);\n  if (!payload) {\n    return {};\n  }", "provider auth requests handles non-object status responses before field projection");
assertNotIncludes(providerAuthRequests, "const payload = toJsonRecord(value) as ProviderAuthStatusPayload;", "provider auth requests avoid casting raw status records through");
assertIncludes(providerAuthRequests, "function toProviderDeviceAuthLoginPayload(value: unknown): ProviderDeviceAuthLoginPayload", "provider auth requests keep device login dynamic payload conversion isolated");
assertIncludes(providerAuthRequests, "function toProviderDeviceAuthLoginPayload(value: unknown): ProviderDeviceAuthLoginPayload {\n  const payload = toPayloadSource<ProviderDeviceAuthLoginPayload>(value);\n  if (!payload) {\n    return {};\n  }", "provider auth requests handles non-object device login responses before field projection");
assertIncludes(providerAuthRequests, "device_auth_id: payload.device_auth_id,\n    device_code: payload.device_code,", "provider auth requests project device login payloads onto named fields");
assertNotIncludes(providerAuthRequests, "return toJsonRecord(value) as ProviderDeviceAuthLoginPayload;", "provider auth requests avoid casting raw device login records through");
assertIncludes(providerAuthRequests, "function toProviderAuthPollPayload(value: unknown): ProviderAuthPollPayload", "provider auth requests project auth poll payloads onto named fields");
assertIncludes(providerAuthRequests, "function toProviderAuthPollPayload(value: unknown): ProviderAuthPollPayload {\n  const payload = toPayloadSource<ProviderAuthPollPayload>(value);\n  if (!payload) {\n    return {};\n  }", "provider auth requests handles non-object poll responses before field projection");
assertNotIncludes(providerAuthRequests, "const payload = toJsonRecord(value) as ProviderAuthPollPayload;", "provider auth requests avoid casting raw poll records through");
assertIncludes(providerAuthRequests, "function toProviderAuthMutationPayload(value: unknown): ProviderAuthMutationPayload", "provider auth requests narrow auth mutation responses");
assertIncludes(providerAuthRequests, "function toProviderAuthMutationPayload(value: unknown): ProviderAuthMutationPayload {\n  const payload = toPayloadSource<ProviderAuthMutationPayload>(value);\n  if (!payload) {\n    return {};\n  }", "provider auth requests handles non-object mutation responses before field projection");
assertNotIncludes(providerAuthRequests, "const payload = toJsonRecord(value) as ProviderAuthMutationPayload;", "provider auth requests avoid casting raw mutation records through");
assertIncludes(providerAuthRequests, "restart_required: payload.restart_required,", "provider auth requests projects auth mutation payloads onto named fields");
assertIncludes(providerAuthRequests, "pendingAuth: ProviderAuthPendingPayload,", "provider auth requests type pending auth poll input");
assertIncludes(providerAuthRequests, "return toProviderAuthStatusPayload(await requestSettingsJson(optionalText(config.endpoint)))", "provider auth requests convert unknown auth status responses through the named payload boundary");
assertIncludes(providerAuthRequests, "return toProviderAuthMutationPayload(await requestSettingsJson(providerSettingsEndpoint(providerId, \"connect\")", "provider auth requests convert unknown OAuth connect responses through the named payload boundary");
assertIncludes(providerAuthRequests, "return toProviderDeviceAuthLoginPayload(await requestSettingsJson(optionalText(config.loginEndpoint)", "provider auth requests convert unknown auth login responses through the device login payload boundary");
assertIncludes(providerAuthRequests, "return toProviderAuthPollPayload(await requestSettingsJson(optionalText(config.pollEndpoint)", "provider auth requests convert unknown auth poll responses through the named payload boundary");
assertIncludes(providerAuthRequests, "requestSettingsJson(optionalText(config.logoutEndpoint)", "provider auth requests convert unknown auth logout responses");
assertNotIncludes(providerAuthRequests, "requestSettingsJson<ProviderAuthPayload>(providerSettingsEndpoint(providerId, \"connect\")", "provider auth requests avoids direct raw OAuth connect payloads");
assertNotIncludes(providerAuthRequests, "requestSettingsJson<ProviderAuthPayload>(optionalText(config.logoutEndpoint)", "provider auth requests avoids direct raw auth logout payloads");
assertNotIncludes(providerAuthRequests, "Promise<any>", "provider auth requests avoid any response promises");
assertNotIncludes(providerAuthRequests, "Record<string, any>", "provider auth requests avoid broad dynamic records");
assertIncludes(providerAuthActions, "requestProviderAuthStatus(requestSettingsJson, config)", "provider auth actions delegate auth status request");
assertIncludes(providerAuthActions, "type ProviderMutationState = {", "provider auth actions type shared provider mutation state");
assertIncludes(providerAuthActions, "catch (error: unknown)", "provider auth actions narrow poll errors");
assertIncludes(providerAuthActionRunner, "function errorMessage(error: unknown): string", "provider auth action runner narrows unknown errors");
assertIncludes(providerAuthActionRunner, "error: unknown", "provider auth action runner accepts unknown errors");
assertNotIncludes(providerAuthActionRunner, "catch (error: any)", "provider auth action runner avoids any catch boundaries");
assertIncludes(providerSettingsLoader, "export async function loadProviderSettingsState", "provider settings loader centralizes provider list loading");
assertIncludes(providerSettingsLoader, "type ProviderSettingsPayload = {", "provider settings loader types provider settings payload boundary");
assertIncludes(providerSettingsLoader, "providers?: unknown;", "provider settings loader names providers payload field");
assertIncludes(providerSettingsLoader, "default_provider?: unknown;", "provider settings loader names default provider payload field");
assertIncludes(providerSettingsLoader, "connected?: unknown;", "provider settings loader names connected providers payload field");
assertIncludes(providerSettingsLoader, "available?: unknown;", "provider settings loader names available providers payload field");
assertNotIncludes(providerSettingsLoader, "type ProviderSettingsPayload = JsonRecord & {", "provider settings loader avoids open-ended provider settings payload records");
assertIncludes(providerSettingsLoader, "type ProviderCredentialsPayload = {", "provider settings loader types provider credentials payload boundary");
assertIncludes(providerSettingsLoader, "credentials?: unknown;", "provider settings loader names credentials payload field");
assertNotIncludes(providerSettingsLoader, "type ProviderCredentialsPayload = JsonRecord & {", "provider settings loader avoids open-ended provider credentials payload records");
assertIncludes(providerSettingsLoader, "type ProviderCredentialMapPayload = {\n  [providerKey: string]: unknown;\n};", "provider settings loader names dynamic credential map boundary");
assertIncludes(providerSettingsLoader, "type ProviderCredentialEntry = [string, unknown];", "provider settings loader names credential map entry boundary");
assertIncludes(providerSettingsLoader, "type ProviderViewPayload = {", "provider settings loader names provider view payload boundary");
assertIncludes(providerSettingsLoader, "type ProviderCredentialViewPayload = {", "provider settings loader names provider credential view payload boundary");
assertIncludes(providerSettingsLoader, "interface ProviderSettingsLoaderState", "provider settings loader types provider state boundary");
assertNotIncludes(providerSettingsLoader, "type JsonRecord = Record<string, unknown>;", "provider settings loader avoids a shared generic JSON record alias");
assertNotIncludes(providerSettingsLoader, "function toJsonRecord(value: unknown): JsonRecord", "provider settings loader avoids a shared generic JSON record converter");
for (const payloadType of ["ProviderSettingsPayload", "ProviderCredentialsPayload", "ProviderViewPayload", "ProviderCredentialViewPayload", "ProviderCredentialMapPayload"]) {
  assertIncludes(providerSettingsLoader, `toPayloadSource<${payloadType}>(value)`, `provider settings loader limits ${payloadType} source reads to known fields`);
}
assertIncludes(providerSettingsLoader, "function toProviderSettingsPayload(value: unknown): ProviderSettingsPayload", "provider settings loader narrows provider settings before state writes");
assertIncludes(providerSettingsLoader, "function toProviderSettingsPayload(value: unknown): ProviderSettingsPayload {\n  const payload = toPayloadSource<ProviderSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "provider settings loader handles non-object provider settings responses before field projection");
assertIncludes(providerSettingsLoader, "providers: payload.providers,\n    default_provider: payload.default_provider,\n    connected: payload.connected,\n    available: payload.available,", "provider settings loader projects provider settings payloads onto named fields");
assertNotIncludes(providerSettingsLoader, "function toProviderSettingsPayload(value: unknown): ProviderSettingsPayload {\n  return toJsonRecord(value);\n}", "provider settings loader avoids passing raw provider settings records through converter");
assertIncludes(providerSettingsLoader, "function toProviderCredentialsPayload(value: unknown): ProviderCredentialsPayload", "provider settings loader narrows provider credentials before state writes");
assertIncludes(providerSettingsLoader, "function toProviderCredentialsPayload(value: unknown): ProviderCredentialsPayload {\n  const payload = toPayloadSource<ProviderCredentialsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "provider settings loader handles non-object provider credentials responses before field projection");
assertIncludes(providerSettingsLoader, "credentials: payload.credentials,", "provider settings loader projects provider credentials payloads onto named fields");
assertNotIncludes(providerSettingsLoader, "function toProviderCredentialsPayload(value: unknown): ProviderCredentialsPayload {\n  return toJsonRecord(value);\n}", "provider settings loader avoids passing raw provider credential records through converter");
assertIncludes(providerSettingsLoader, "function toProviderViewPayload(value: unknown): ProviderViewPayload", "provider settings loader narrows provider item payloads before view normalization");
assertIncludes(providerSettingsLoader, "function toProviderViewPayload(value: unknown): ProviderViewPayload {\n  const payload = toPayloadSource<ProviderViewPayload>(value);\n  if (!payload) {\n    return {};\n  }", "provider settings loader handles non-object provider item records before field projection");
assertIncludes(providerSettingsLoader, "id: payload.id,\n    name: payload.name,\n    provider: payload.provider,\n    providerName: payload.providerName,", "provider settings loader projects provider item identity fields");
assertIncludes(providerSettingsLoader, "credential_effective_id: payload.credential_effective_id,\n    effective_credential_id: payload.effective_credential_id,", "provider settings loader projects provider credential aliases");
assertIncludes(providerSettingsLoader, "function toProviderCredentialViewPayload(value: unknown): ProviderCredentialViewPayload", "provider settings loader narrows provider credential item payloads before view normalization");
assertIncludes(providerSettingsLoader, "function toProviderCredentialViewPayload(value: unknown): ProviderCredentialViewPayload {\n  const payload = toPayloadSource<ProviderCredentialViewPayload>(value);\n  if (!payload) {\n    return {};\n  }", "provider settings loader handles non-object provider credential records before field projection");
assertIncludes(providerSettingsLoader, "id: payload.id,\n    label: payload.label,\n    name: payload.name,\n    secret_preview: payload.secret_preview,", "provider settings loader projects provider credential item fields");
assertNotIncludes(providerSettingsLoader, "function toProviderViewPayload(value: unknown): ProviderViewPayload {\n  return toJsonRecord(value);\n}", "provider settings loader avoids passing raw provider item records through converter");
assertNotIncludes(providerSettingsLoader, "function toProviderCredentialViewPayload(value: unknown): ProviderCredentialViewPayload {\n  return toJsonRecord(value);\n}", "provider settings loader avoids passing raw provider credential item records through converter");
assertIncludes(providerSettingsLoader, "requestSettingsJson(\"/api/settings/providers\")", "provider settings loader receives an unknown provider catalog response before normalization");
assertIncludes(providerSettingsLoader, "requestSettingsJson(\"/api/settings/credentials\")", "provider settings loader receives an unknown credential catalog response before normalization");
assertIncludes(providerSettingsLoader, "ProviderCredentialView,", "provider settings loader reuses typed provider credential views");
assertIncludes(providerSettingsLoader, "ProviderCredentialsState,", "provider settings loader reuses typed provider credential state");
assertIncludes(providerSettingsLoader, "function toProviderView(value: unknown): ProviderView | null", "provider settings loader normalizes provider records to typed views");
assertIncludes(providerSettingsLoader, "const payload = toProviderViewPayload(value);\n  const id = optionalText(payload.id);", "provider settings loader normalizes provider views through item payload boundary");
assertIncludes(providerSettingsLoader, "function toProviderCredentialView(value: unknown): ProviderCredentialView | null", "provider settings loader normalizes provider credential records to typed views");
assertIncludes(providerSettingsLoader, "const payload = toProviderCredentialViewPayload(value);\n  const id = optionalText(payload.id);", "provider settings loader normalizes provider credential views through item payload boundary");
assertIncludes(providerSettingsLoader, "function toProviderCredentialEntries(value: unknown): ProviderCredentialEntry[]", "provider settings loader narrows provider credential maps into entries");
assertIncludes(providerSettingsLoader, "function toProviderCredentialEntries(value: unknown): ProviderCredentialEntry[] {\n  const payload = toPayloadSource<ProviderCredentialMapPayload>(value);", "provider settings loader preserves dynamic provider credential map keys behind a named payload source");
assertIncludes(providerSettingsLoader, "return payload ? Object.entries(payload) : [];", "provider settings loader handles non-object credential maps before entry projection");
assertIncludes(providerSettingsLoader, "function normalizeProviderSettings(payload: unknown): ProviderSettings", "provider settings loader normalizes provider settings state");
assertIncludes(providerSettingsLoader, "default_provider: optionalText(settings.default_provider) || \"\",", "provider settings loader normalizes default provider before state writes");
assertNotIncludes(providerSettingsLoader, "default_provider: settings.default_provider,", "provider settings loader avoids raw default provider state writes");
assertIncludes(providerSettingsLoader, "function normalizeProviderCredentials(value: unknown): ProviderCredentialsState", "provider settings loader normalizes provider credentials state");
assertIncludes(providerSettingsLoader, "toProviderCredentialEntries(value)", "provider settings loader normalizes provider credential entries through the named boundary");
assertIncludes(providerSettingsLoader, "const providers = normalizeProviderSettings(providersPayload);", "provider settings loader stores typed provider settings state");
assertIncludes(providerSettingsLoader, "const credentials = toProviderCredentialsPayload(credentialsPayload);", "provider settings loader stores typed provider credentials payload");
assertIncludes(providerSettingsLoader, "settingsState.credentials = normalizeProviderCredentials(credentials.credentials);", "provider settings loader stores normalized provider credential state");
assertNotIncludes(providerSettingsLoader, "Object.entries(toJsonRecord(value))", "provider settings loader avoids inline provider credential map records");
assertNotIncludes(providerSettingsLoader, "const record = toJsonRecord(value);", "provider settings loader avoids inline provider item records in view normalizers");
assertNotIncludes(providerSettingsLoader, "settingsState.credentials = toJsonRecord(credentials.credentials);", "provider settings loader avoids raw credential records in state");
assertIncludes(providerSettingsLoader, "function errorMessage(error: unknown): string", "provider settings loader narrows unknown errors");
assertNotIncludes(providerSettingsLoader, "Promise<any>", "provider settings loader avoids any request promises");
assertNotIncludes(providerSettingsLoader, "catch (error: any)", "provider settings loader avoids any catch boundaries");
assertNotIncludes(providerSettingsLoader, "Record<string, any>", "provider settings loader avoids broad dynamic records");
assertIncludes(providerSettingsActions, "loadProviderSettingsState(settingsState, requestSettingsJson, copy)", "provider settings actions delegate provider list loading");
assertNotIncludes(providerSettingsActions, "requestSettingsJson(\"/api/settings/providers\")", "provider settings actions no longer own provider catalog request");
assertNotIncludes(providerSettingsActions, "const oauthProviderConfigs", "provider settings actions no longer own OAuth provider configs");
assertNotIncludes(providerAuthActions, "const oauthProviderConfigs", "provider auth actions fold OAuth metadata into auth provider configs");
assertIncludes(providerSettingsRequests, "export async function requestProviderConnect", "provider settings requests centralize provider connect request");
assertIncludes(providerSettingsRequests, "type ProviderIdentityPayload = Pick<ProviderPayload, \"id\">;", "provider settings requests narrow provider identity input");
assertIncludes(providerSettingsRequests, "export type ProviderMutationPayload", "provider settings requests expose typed mutation payload");
assertIncludes(providerSettingsRequests, "export type ProviderMutationPayload = {", "provider settings requests name fixed provider mutation payload boundary");
assertIncludes(providerSettingsRequests, "function toProviderMutationPayload(value: unknown): ProviderMutationPayload", "provider settings requests narrow provider mutation responses");
assertIncludes(providerSettingsRequests, "restart_required: payload.restart_required,", "provider settings requests project provider mutation payloads onto named fields");
assertIncludes(providerSettingsRequests, "function providerId(provider: ProviderIdentityPayload): string", "provider settings requests derive endpoint ids from typed identity payloads");
assertIncludes(providerSettingsRequests, "providerSettingsEndpoint(form.providerId, \"connect\")", "provider settings requests keep provider connect endpoint helper");
assertIncludes(providerSettingsRequests, "return toProviderMutationPayload(await requestSettingsJson(providerSettingsEndpoint(form.providerId, \"connect\")", "provider settings requests convert unknown provider connect responses through the named payload boundary");
assertIncludes(providerSettingsActions, "requestProviderConnect(requestSettingsJson, settingsState.connectForm)", "provider settings actions delegate provider connect request");
assertNotIncludes(providerSettingsActions, "providerSettingsEndpoint(", "provider settings actions no longer own provider endpoint assembly");
assertIncludes(providerSettingsActions, "createProviderConnectForm(provider)", "provider settings actions reuse provider connect form helper");
assertIncludes(providerSettingsActions, "interface ProviderSettingsState", "provider settings actions type provider state boundary");
assertIncludes(providerSettingsActions, "import type { ProviderCredentialsState, ProviderSettings } from \"./useSettingsState\";", "provider settings actions reuse typed provider settings state");
assertIncludes(providerSettingsActions, "providers: ProviderSettings;", "provider settings actions narrow provider state boundary");
assertIncludes(providerSettingsActions, "credentials: ProviderCredentialsState;", "provider settings actions narrow credential state boundary");
assertIncludes(providerSettingsActions, "interface ProviderSettingsCopy", "provider settings actions type provider copy boundary");
assertIncludes(providerSettingsActions, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", "provider settings actions keep API responses unknown until request adapters convert them");
assertNotIncludes(providerSettingsActions, "type RequestSettingsJson = <", "provider settings actions avoid caller-selected response types");
assertIncludes(providerSettingsActions, "function providerDisplayName(provider: ProviderPayload): string", "provider settings actions normalize provider display name");
assertNotIncludes(providerSettingsActions, "Promise<any>", "provider settings actions avoid any request promises");
assertNotIncludes(providerSettingsActions, "Record<string, any>", "provider settings actions avoid broad dynamic records");
assertIncludes(providerConnectForm, "export function createEmptyProviderConnectForm", "provider connect form centralizes empty form state");
assertIncludes(providerConnectForm, "export function createProviderConnectForm", "provider connect form centralizes provider-derived form state");
assertIncludes(providerConnectForm, "export function resetProviderConnectForm", "provider connect form centralizes connect form reset");
assertIncludes(providerConnectForm, "export type ProviderPayload = {", "provider connect form exposes typed provider payload without a generic index signature");
assertIncludes(providerConnectForm, "export type ProviderConnectPayload = {", "provider connect form types fixed connect request payload");
assertIncludes(providerConnectForm, "export type ProviderOAuthConnectPayload = {", "provider connect form types fixed OAuth connect request payload");
assertIncludes(providerConnectForm, "export type ProviderCredentialPayload = {", "provider connect form types fixed credential request payload");
assertIncludes(providerConnectForm, "export function providerConnectPayloadFromForm(form: ProviderConnectForm): ProviderConnectPayload", "provider connect form narrows connect payload helper return");
assertIncludes(providerConnectForm, "function optionalText(value: unknown): string", "provider connect form narrows optional text values");
assertNotIncludes(providerConnectForm, "Record<string, any>", "provider connect form avoids broad any records");
assertNotIncludes(providerConnectForm, "export type ProviderPayload = JsonRecord & {", "provider connect form keeps generic record inheritance out of provider view payloads");
assertNotIncludes(providerConnectForm, "export type ProviderConnectPayload = JsonRecord & {", "provider connect form keeps generic record inheritance out of connect request payloads");
assertNotIncludes(providerConnectForm, "export type ProviderOAuthConnectPayload = JsonRecord & {", "provider connect form keeps generic record inheritance out of OAuth request payloads");
assertNotIncludes(providerConnectForm, "export type ProviderCredentialPayload = JsonRecord & {", "provider connect form keeps generic record inheritance out of credential request payloads");
assertIncludes(providerSettingsRequests, "providerConnectPayloadFromForm(form)", "provider settings requests reuse connect payload helper");
assertIncludes(providerConnectForm, "): ProviderOAuthConnectPayload", "provider connect form narrows OAuth payload helper return");
assertIncludes(providerAuthRequests, "providerOAuthConnectPayload(provider, options)", "provider auth requests reuse OAuth connect payload helper");
assertIncludes(providerConnectForm, "export function providerCredentialPayload(credentialId: string): ProviderCredentialPayload", "provider connect form narrows credential payload helper return");
assertIncludes(providerSettingsRequests, "providerCredentialPayload(credentialId)", "provider settings requests reuse credential payload helper");
assertIncludes(providerHelpers, "export function providerCatalogKey", "provider helpers centralize provider key resolution");
assertIncludes(providerHelpers, "export type ProviderLike = {", "provider helpers expose typed provider-like boundary");
assertIncludes(providerHelpers, "export type ProviderMarkSource = Pick<ProviderLike, \"id\" | \"name\" | \"type\">;", "provider helpers derive the minimal display mark input");
assertIncludes(providerHelpers, "export function providerMark(value: ProviderMarkSource | null | undefined): string", "provider helpers accept provider and channel mark sources without assertions");
assertIncludes(providerHelpers, "function providerList(value: unknown): ProviderLike[]", "provider helpers normalize provider lists at boundary");
assertIncludes(providerHelpers, "providerCatalogKey(provider) === presetId", "provider helpers reuse provider key resolution for connected providers");
assertNotIncludes(providerHelpers, "AnyRecord", "provider helpers avoid dynamic AnyRecord alias");
assertNotIncludes(providerHelpers, "Record<string, any>", "provider helpers avoid broad dynamic records");
assertNotIncludes(providerHelpers, "export type ProviderLike = Record<string, unknown>", "provider helpers keep generic record inheritance out of provider-like views");
assertNotIncludes(providerHelpers, "provider: AnyRecord", "provider helpers avoid AnyRecord in helper parameters");
assertIncludes(providerCredentialHelpers, "const providerKey = providerCatalogKey(provider)", "provider credential helpers reuse provider key resolution for credentials");
assertIncludes(providerCredentialHelpers, "type CredentialProvider = ProviderLike & {", "provider credential helpers type credential provider view");
assertIncludes(providerCredentialHelpers, "import type { ProviderCredentialView, ProviderCredentialsState }", "provider credential helpers reuse typed credential state");
assertIncludes(providerCredentialHelpers, "function credentialList(value: unknown): ProviderCredentialView[]", "provider credential helpers normalize typed credential lists");
assertIncludes(providerCredentialHelpers, "export function providerCredentials(state: CredentialSettingsState, provider: CredentialProvider | null | undefined): ProviderCredentialView[]", "provider credential helpers return typed credential views");
assertIncludes(providerCredentialHelpers, "type CredentialCopyRootPayload = {", "provider credential helpers name root copy boundary");
assertIncludes(providerCredentialHelpers, "type CredentialSettingsCopyPayload = {", "provider credential helpers name settings copy boundary");
assertIncludes(providerCredentialHelpers, "type CredentialProvidersCopyPayload = {", "provider credential helpers name provider copy boundary");
assertIncludes(providerCredentialHelpers, "const CREDENTIAL_SOURCES = [\"explicit\", \"provider_default\", \"priority\"] as const;", "provider credential helpers define finite credential sources");
assertIncludes(providerCredentialHelpers, "type CredentialSource = (typeof CREDENTIAL_SOURCES)[number];", "provider credential helpers derive credential source keys from finite metadata");
assertIncludes(providerCredentialHelpers, "type CredentialSourceMapPayload = {\n  [Source in CredentialSource]?: unknown;\n};", "provider credential helpers narrow credential source copy keys");
assertIncludes(providerCredentialHelpers, "function credentialSource(value: unknown): CredentialSource | null", "provider credential helpers validate provider credential source values");
assertNotIncludes(providerCredentialHelpers, "[source: string]: unknown;", "provider credential helpers avoid open credential source copy keys");
assertIncludes(providerCredentialHelpers, "export function credentialSourceLabel(copy: unknown, provider: CredentialProvider | null | undefined): string", "provider credential helpers narrow unknown copy input internally");
assertIncludes(providerCredentialHelpers, "const sources = toPayloadSource<CredentialSourceMapPayload>(providers?.credentialSources) || {};", "provider credential helpers route credential sources through the named map");
assertIncludes(providerCredentialHelpers, "return source ? String(sources[source] || \"\") : \"\";", "provider credential helpers read labels only through validated source keys");
for (const [providerViewModule, moduleName] of [
  [providerSettings, "provider settings component"],
  [providerAuthHelpers, "provider auth helpers"],
  [providerCredentialHelpers, "provider credential helpers"],
]) {
  assertIncludes(providerViewModule, "import { toPayloadSource } from \"../composables/payloadBoundary\";", `${moduleName} reuse the shared finite payload guard`);
  assertNotIncludes(providerViewModule, "type PayloadSource<Payload extends object>", `${moduleName} avoid a duplicate payload source type`);
  assertNotIncludes(providerViewModule, "function toPayloadSource<Payload extends object>", `${moduleName} avoid a duplicate payload source guard`);
}
assertNotIncludes(providerCredentialHelpers, "type JsonRecord = Record<string, unknown>;", "provider credential helpers avoid a shared generic record alias");
assertNotIncludes(providerCredentialHelpers, "function toRecord", "provider credential helpers avoid a shared generic record converter");
assertNotIncludes(providerCredentialHelpers, "AnyRecord", "provider credential helpers avoid dynamic AnyRecord import");
assertNotIncludes(providerCredentialHelpers, "Record<string, any>", "provider credential helpers avoid broad dynamic records");
assertNotIncludes(providerHelpers, "function providerCredentials", "provider helpers keep credential lookup out of generic helpers");
assertIncludes(providerModelHelpers, "function modelOptionsForProvider", "provider model helpers expose text model options");
assertIncludes(providerModelHelpers, "function textModelOptionLabel", "provider model helpers expose text model labels");
assertIncludes(providerModelHelpers, "import type { ModelProviderView as SettingsModelProviderView } from \"../composables/useSettingsState\";", "provider model helpers reuse normalized settings provider type");
assertIncludes(providerModelHelpers, "type ModelCopyRootPayload = {", "provider model helpers name the root copy payload");
assertIncludes(providerModelHelpers, "type ModelMetadataCopyView = {", "provider model helpers name model metadata copy fields");
assertIncludes(providerModelHelpers, "export function textModelOptionLabel(copy: unknown", "provider model helpers narrow copy input internally");
assertIncludes(providerModelHelpers, "const modelsCopy = toPayloadSource<ModelCopyView>(settings?.models) || {};", "provider model helpers narrow model copy fields before reading them");
assertNotIncludes(providerModelHelpers, "type JsonRecord", "provider model helpers avoid dynamic JsonRecord aliases");
assertNotIncludes(providerModelHelpers, "function toRecord", "provider model helpers avoid generic record conversion");
assertNotIncludes(providerModelHelpers, "type ModelMetadataEntryView = {", "provider model helpers rely on normalized settings metadata entry type");
assertIncludes(providerModelHelpers, "type ModelProviderView = Pick<SettingsModelProviderView, \"is_default\" | \"model_metadata\" | \"models\" | \"selected_model\">;", "provider model helpers narrow provider shape from normalized state");
assertIncludes(providerModelHelpers, "const modelMetadataEntry = provider?.model_metadata?.[model] ?? {};", "provider model helpers read typed metadata entries directly");
assertNotIncludes(providerModelHelpers, "const modelMetadata = toRecord(provider?.model_metadata);", "provider model helpers avoid reopening typed metadata maps");
assertNotIncludes(providerModelHelpers, "const modelMetadataEntry = toRecord(modelMetadata[model]);", "provider model helpers avoid reopening typed metadata entries");
assertNotIncludes(providerModelHelpers, "type ModelProviderView = JsonRecord & {", "provider model helpers avoid dynamic provider view boundary");
assertNotIncludes(providerModelHelpers, "is_default?: unknown;", "provider model helpers avoid unknown default provider flag");
assertNotIncludes(providerModelHelpers, "type ModelProviderView = {", "provider model helpers avoid reopening normalized providers as unknown field bags");
assertNotIncludes(providerModelHelpers, "selected_model?: unknown;", "provider model helpers avoid unknown selected model");
assertIncludes(providerModelHelpers, "const models = [...(provider?.models ?? [])];", "provider model helpers read typed model lists without mutating state");
assertNotIncludes(providerModelHelpers, "function stringList(value: unknown): string[]", "provider model helpers no longer need model list coercion");
assertIncludes(providerModelHelpers, "function formatCompactTokenCount(value: unknown): string", "provider model helpers narrow token count input");
assertNotIncludes(providerModelHelpers, "AnyRecord", "provider model helpers avoid dynamic AnyRecord import");
assertNotIncludes(providerModelHelpers, "Record<string, any>", "provider model helpers avoid broad dynamic records");
assertNotIncludes(providerHelpers, "function modelOptionsForProvider", "provider helpers keep text model options out of generic helpers");
assertIncludes(providerMediaHelpers, "function mediaModelCategories", "provider media helpers expose media categories");
assertIncludes(providerMediaHelpers, "function mediaModelsForProvider", "provider media helpers expose media model lookup");
assertIncludes(providerMediaHelpers, "MediaCategory,\n  MediaSettings as SettingsMediaSettings,", "provider media helpers reuse the canonical media category and normalized settings types");
assertIncludes(providerMediaHelpers, "type MediaCategoriesCopyPayload = {\n  [Category in MediaCategory]?: unknown;\n};", "provider media helpers derive fixed copy keys from the canonical media categories");
assertIncludes(providerMediaHelpers, "type MediaModelCategory = {", "provider media helpers name normalized category output");
assertIncludes(providerMediaHelpers, "key: MediaCategory;", "provider media helpers retain canonical category keys after normalization");
assertIncludes(providerMediaHelpers, "export function mediaModelCategories(copy: unknown): MediaModelCategory[]", "provider media helpers narrow copy input into typed categories");
assertIncludes(providerMediaHelpers, "const categories = toPayloadSource<MediaCategoriesCopyPayload>(models?.mediaCategories);", "provider media helpers narrow media category copy before reading entries");
assertNotIncludes(providerMediaHelpers, "type JsonRecord", "provider media helpers avoid dynamic JsonRecord aliases");
assertNotIncludes(providerMediaHelpers, "function toRecord", "provider media helpers avoid generic record conversion");
assertIncludes(providerMediaHelpers, "type MediaProviderView = Pick<SettingsModelProviderView, \"id\" | \"media_models\" | \"models\">;", "provider media helpers narrow provider shape from normalized state");
assertIncludes(providerMediaHelpers, "media?: Pick<SettingsMediaSettings, \"providers\">;", "provider media helpers read typed media provider state");
assertNotIncludes(providerMediaHelpers, "type MediaProviderView = JsonRecord & {", "provider media helpers avoid dynamic media provider view boundary");
assertNotIncludes(providerMediaHelpers, "type MediaStateView = JsonRecord & {", "provider media helpers avoid dynamic media state view boundary");
assertNotIncludes(providerMediaHelpers, "id?: unknown;", "provider media helpers avoid unknown provider ids");
assertNotIncludes(providerMediaHelpers, "media_models?: unknown;", "provider media helpers avoid unknown media model maps");
assertNotIncludes(providerMediaHelpers, "type MediaProviderView = {", "provider media helpers avoid reopening normalized providers as unknown field bags");
assertNotIncludes(providerMediaHelpers, "media?: unknown;", "provider media helpers avoid unknown media state");
assertNotIncludes(providerMediaHelpers, "function mediaProviders(value: unknown): MediaProviderView[]", "provider media helpers no longer need provider list coercion");
assertNotIncludes(providerMediaHelpers, "function stringList(value: unknown): string[]", "provider media helpers no longer need model list coercion");
assertIncludes(providerMediaHelpers, "const provider = (state.media?.providers ?? []).find((entry: MediaProviderView) => entry.id === providerId);", "provider media helpers find typed providers by id");
assertIncludes(providerMediaHelpers, "const models = [...(provider?.media_models?.[category] ?? provider?.models ?? [])];", "provider media helpers read typed media model arrays without mutating state");
assertIncludes(providerMediaHelpers, "category: MediaCategory", "provider media helpers restrict model lookup to canonical media categories");
assertNotIncludes(providerMediaHelpers, "AnyRecord", "provider media helpers avoid dynamic AnyRecord import");
assertNotIncludes(providerMediaHelpers, "Record<string, any>", "provider media helpers avoid broad dynamic records");
assertNotIncludes(providerHelpers, "function mediaModelCategories", "provider helpers keep media model categories out of generic helpers");
for (const [settingsHelper, moduleName] of [
  [modelSettings, "model settings component"],
  [providerModelHelpers, "provider model helpers"],
  [providerMediaHelpers, "provider media helpers"],
]) {
  assertIncludes(settingsHelper, "import { toPayloadSource } from \"../composables/payloadBoundary\";", `${moduleName} reuse the shared finite payload guard`);
  assertNotIncludes(settingsHelper, "type PayloadSource<Payload extends object>", `${moduleName} avoid a duplicate payload source type`);
  assertNotIncludes(settingsHelper, "function toPayloadSource<Payload extends object>", `${moduleName} avoid a duplicate payload source guard`);
}
assertIncludes(providerSettingsActions, "providerCatalogKey(provider)", "provider settings actions reuse shared provider key helper");
assertNotIncludes(providerConnectForm, "providerCredentialKey", "provider connect form no longer owns provider key resolution");
assertNotIncludes(providerSettingsActions, "providerCredentialKey", "provider settings actions avoid form-owned provider key helper");
assertIncludes(useSettingsState, "export interface SettingsForm", "settings state exposes typed settings form");
assertIncludes(useSettingsState, "import type { ColorSchemePreference, LanguagePreference } from \"./chatClientPreferences\";", "settings state imports typed display preferences");
assertIncludes(useSettingsState, "language: LanguagePreference;", "settings form types language preference");
assertIncludes(useSettingsState, "colorScheme: ColorSchemePreference;", "settings form types color scheme preference");
assertIncludes(useSettingsState, "import { createProviderAuthInitialStates, type ProviderAuthInitialStates }", "settings state imports finite provider auth slots");
assertIncludes(useSettingsState, "export type SettingsState = ProviderAuthInitialStates & {", "settings state composes finite provider auth slots");
assertNotIncludes(useSettingsState, "type JsonRecord", "settings state avoids unused generic JSON aliases");
assertNotIncludes(useSettingsState, "export type SettingsState = Record<string, unknown> & {", "settings state avoids an open-ended index signature");
assertNotIncludes(useSettingsState, "Record<string, any>", "settings state avoids broad any index signature");
assertIncludes(useSettingsState, "export interface ChannelSettings", "settings state exposes typed channel settings model");
assertIncludes(useSettingsState, "export interface ChannelSettings {\n  connected: ChannelView[];\n  available: ChannelView[];\n  channels: ChannelView[];\n}", "settings state keeps channel settings state fixed");
assertNotIncludes(useSettingsState, "export interface ChannelSettings {\n  connected: ChannelView[];\n  available: ChannelView[];\n  channels: ChannelView[];\n  [key: string]: unknown;\n}", "settings state avoids open-ended channel settings state");
assertIncludes(useSettingsState, "export interface ChannelView {", "settings state exposes typed channel view boundary");
assertIncludes(useSettingsState, "enabled?: boolean;", "settings state types channel enabled flag");
assertIncludes(useSettingsState, "description?: string;", "settings state types channel description");
assertIncludes(useSettingsState, "status?: string;", "settings state types channel status");
assertNotIncludes(useSettingsState, "export interface ChannelView extends JsonRecord", "settings state keeps channel views off generic JSON inheritance");
assertIncludes(useSettingsState, "channels: ChannelSettings;", "settings state exposes typed channel state boundary");
assertIncludes(useSettingsState, "channelConnectForm: ChannelConnectForm;", "settings state exposes typed channel connect form boundary");
assertIncludes(useSettingsState, "export interface ProviderSettings", "settings state exposes typed provider settings model");
assertIncludes(useSettingsState, "export interface ProviderView {", "settings state exposes typed provider view boundary");
assertIncludes(useSettingsState, "auth_type?: string;", "settings state types provider auth type");
assertIncludes(useSettingsState, "credential_preview?: string;", "settings state types provider credential preview");
assertIncludes(useSettingsState, "requires_api_key?: boolean;", "settings state types provider API-key requirement");
assertIncludes(useSettingsState, "export interface ProviderSettings {\n  default_provider: string;", "settings state narrows provider default provider id");
assertIncludes(useSettingsState, "export interface ProviderSettings {", "settings state keeps provider settings off generic JSON inheritance");
assertNotIncludes(useSettingsState, "export interface ProviderSettings {\n  default_provider: unknown;", "settings state avoids unknown provider default provider ids");
assertIncludes(useSettingsState, "export interface ProviderCredentialView {", "settings state exposes typed provider credential view boundary");
assertIncludes(useSettingsState, "export type ProviderCredentialsState = Record<string, ProviderCredentialView[]>;", "settings state exposes typed provider credentials map");
assertNotIncludes(useSettingsState, "export interface ProviderView extends JsonRecord", "settings state keeps provider views off generic JSON inheritance");
assertNotIncludes(useSettingsState, "export interface ProviderSettings extends JsonRecord", "settings state keeps provider settings off generic JSON inheritance");
assertIncludes(useSettingsState, "providers: ProviderSettings;", "settings state exposes typed provider state boundary");
assertIncludes(useSettingsState, "credentials: ProviderCredentialsState;", "settings state exposes typed credentials boundary");
assertNotIncludes(useSettingsState, "credentials: JsonRecord;", "settings state keeps credentials off generic JSON records");
assertIncludes(useSettingsState, "connectForm: createEmptyProviderConnectForm()", "settings state reuses provider connect form defaults");
assertIncludes(useSettingsState, "export interface UpdateStatusView {", "settings state exposes typed update status view");
assertIncludes(useSettingsState, "supported: boolean;", "settings state narrows update supported flag");
assertIncludes(useSettingsState, "commits_behind: number;", "settings state narrows update commit count");
assertIncludes(useSettingsState, "updateStatus: UpdateStatusView;", "settings state exposes typed update status boundary");
assertNotIncludes(useSettingsState, "updateStatus: JsonRecord;", "settings state keeps update status off generic JSON records");
assertIncludes(useSettingsState, "schedule: ScheduleState;", "settings state exposes typed schedule state boundary");
assertIncludes(useSettingsState, "scheduleForm: ScheduleForm;", "settings state exposes typed schedule form boundary");
assertIncludes(useSettingsState, "networkForm: NetworkForm;", "settings state exposes typed network form boundary");
assertIncludes(useSettingsState, "log: LogState;", "settings state exposes typed log state boundary");
assertIncludes(useSettingsState, "logForm: LogForm;", "settings state exposes typed log form boundary");
assertIncludes(useSettingsState, "search: SearchState;", "settings state exposes typed search state boundary");
assertIncludes(useSettingsState, "searchForm: SearchForm;", "settings state exposes typed search form boundary");
assertIncludes(useSettingsState, "export interface CronJobScheduleView {", "settings state exposes typed cron job schedule view boundary");
assertIncludes(useSettingsState, "export interface CronJobPayloadView {", "settings state exposes typed cron job payload view boundary");
assertIncludes(useSettingsState, "export interface CronJobStateView {", "settings state exposes typed cron job state view boundary");
assertIncludes(useSettingsState, "export interface CronJobView {", "settings state exposes typed cron job view boundary");
assertNotIncludes(useSettingsState, "export interface CronJobScheduleView extends JsonRecord", "settings state keeps cron job schedules off generic JSON inheritance");
assertNotIncludes(useSettingsState, "export interface CronJobPayloadView extends JsonRecord", "settings state keeps cron job payloads off generic JSON inheritance");
assertNotIncludes(useSettingsState, "export interface CronJobStateView extends JsonRecord", "settings state keeps cron job state off generic JSON inheritance");
assertNotIncludes(useSettingsState, "export interface CronJobView extends JsonRecord", "settings state keeps cron job views off generic JSON inheritance");
assertIncludes(useSettingsState, "id: string;", "settings state normalizes cron job ids to strings");
assertIncludes(useSettingsState, "enabled: boolean;", "settings state normalizes cron job enabled flags");
assertIncludes(useSettingsState, "schedule: CronJobScheduleView;", "settings state nests typed cron job schedules");
assertIncludes(useSettingsState, "payload: CronJobPayloadView;", "settings state nests typed cron job payloads");
assertIncludes(useSettingsState, "cronJobs: CronJobView[];", "settings state exposes typed cron jobs list boundary");
assertIncludes(useSettingsState, "cronJobForm: CronJobForm;", "settings state exposes typed cron job form boundary");
assertIncludes(useSettingsState, "type CronJobMode", "settings state imports typed cron job mode");
assertIncludes(useSettingsState, "mode: CronJobMode;", "settings state narrows cron job form mode");
assertIncludes(chatClient, "resetProviderConnectForm(settingsState.connectForm)", "chat client reuses provider connect form reset helper");
assertNotIncludes(chatClient, "Object.assign(settingsState.connectForm, createEmptyProviderConnectForm())", "chat client no longer owns provider connect form reset fields");
assertIncludes(chatClient, "const loadSettingsSection = createSettingsSectionLoader({", "chat client delegates settings section loading");
assertNotIncludes(chatClient, "function loadSettingsSection(sectionName)", "chat client no longer owns settings section loader dispatch");
assertIncludes(settingsSectionLoaders, "export function createSettingsSectionLoader", "settings section loaders centralize section dispatch");
assertIncludes(settingsSectionLoaders, "type SettingsLoaderResult = void | Promise<void>;", "settings section loaders keep typed loader result");
assertIncludes(settingsSectionLoaders, "interface SettingsLoaders", "settings section loaders use an explicit loader contract");
assertIncludes(settingsSectionLoaders, "loadProviderAuthStatusById: (providerId: string) => SettingsLoaderResult;", "settings section loaders type provider auth refresh input");
assertIncludes(settingsSectionLoaders, "export type SettingsSectionId = (typeof SETTINGS_SECTION_IDS)[number];", "settings section loaders export typed section ids");
assertIncludes(settingsSectionLoaders, "export function normalizeSettingsSectionId(value: unknown): SettingsSectionId", "settings section loaders normalize unknown section ids");
assertIncludes(settingsSectionLoaders, "const sectionLoaders: Record<SettingsSectionId, SettingsSectionLoader>", "settings section loaders type section dispatch table");
assertIncludes(settingsSectionLoaders, "shortcuts: () => undefined,", "settings section loaders keep shortcuts as a no-op section");
assertNotIncludes(settingsSectionLoaders, "any[]", "settings section loaders avoid dynamic args");
assertNotIncludes(settingsSectionLoaders, "Record<string, (...args:", "settings section loaders avoid broad dynamic loader contracts");
assertIncludes(settingsSectionLoaders, "providers: () => {", "settings section loaders keep provider section loader");
assertIncludes(settingsSectionLoaders, "loadProviderSettings();", "settings section loaders keep provider settings refresh");
assertIncludes(settingsSectionLoaders, "PROVIDER_AUTH_PROVIDER_IDS", "settings section loaders use shared provider auth refresh list");
assertIncludes(settingsSectionLoaders, "loadProviderAuthStatusById(providerId)", "settings section loaders refresh auth through provider id");
assertIncludes(settingsSectionLoaders, "loadScheduleSettings();", "settings section loaders keep schedule settings refresh");
assertIncludes(settingsSectionLoaders, "loadCronJobs();", "settings section loaders keep cron jobs refresh");
assertIncludes(providerSettingsRequests, "export async function requestProviderDisconnect", "provider settings requests centralize provider disconnect request");
assertIncludes(providerSettingsRequests, "export async function requestProviderCredentialUpdate", "provider settings requests centralize provider credential update request");
assertIncludes(providerSettingsRequests, "export async function requestProviderCredentialDelete", "provider settings requests centralize provider credential delete request");
assertIncludes(providerSettingsRequests, "providerSettingsEndpoint(providerId(provider), \"disconnect\")", "provider settings requests keep provider disconnect endpoint helper");
assertIncludes(providerSettingsRequests, "providerSettingsEndpoint(providerId(provider), \"credential\")", "provider settings requests keep provider credential endpoint helper");
assertIncludes(providerSettingsRequests, "return toProviderMutationPayload(await requestSettingsJson(providerSettingsEndpoint(providerId(provider), \"disconnect\")", "provider settings requests convert unknown provider disconnect responses through the named payload boundary");
assertIncludes(providerSettingsRequests, "return toProviderMutationPayload(await requestSettingsJson(providerSettingsEndpoint(providerId(provider), \"credential\")", "provider settings requests convert unknown credential update responses through the named payload boundary");
assertIncludes(providerSettingsRequests, "providerCredentialEndpoint(providerKey, credentialId)", "provider settings requests keep credential endpoint helper");
assertIncludes(providerSettingsRequests, "return toProviderMutationPayload(await requestSettingsJson(", "provider settings requests convert unknown provider mutation responses");
assertIncludes(providerSettingsRequests, "const payload = toPayloadSource<ProviderMutationPayload>(value);", "provider settings requests narrow responses to known mutation fields");
assertNotIncludes(providerSettingsRequests, "function toRecord", "provider settings requests avoid generic record conversion");
assertNotIncludes(providerSettingsRequests, "Record<string, unknown>", "provider settings requests avoid open-ended response records");
assertNotIncludes(providerSettingsRequests, "export type ProviderMutationPayload = JsonRecord & {", "provider settings requests avoids broad provider mutation payload records");
assertNotIncludes(providerSettingsRequests, "value as ProviderMutationPayload", "provider settings requests avoid casting raw mutation records through");
assertNotIncludes(providerSettingsRequests, "Promise<any>", "provider settings requests avoid any response promises");
assertNotIncludes(providerSettingsRequests, "Record<string, any>", "provider settings requests avoid broad dynamic records");
assertIncludes(providerSettingsActions, "requestProviderDisconnect(requestSettingsJson, provider)", "provider settings actions delegate provider disconnect request");
assertIncludes(providerSettingsActions, "requestProviderCredentialUpdate(requestSettingsJson, provider, credentialId)", "provider settings actions delegate provider credential update request");
assertIncludes(providerSettingsActions, "requestProviderCredentialDelete(requestSettingsJson, providerKey, credentialId)", "provider settings actions delegate provider credential delete request");
assertIncludes(providerMutationRunner, "export async function runProviderMutation", "provider mutation runner centralizes provider mutation lifecycle");
assertIncludes(providerMutationRunner, "interface ProviderMutationState", "provider mutation runner types provider mutation state");
assertIncludes(providerMutationRunner, "function errorMessage(error: unknown): string", "provider mutation runner narrows unknown errors");
assertIncludes(providerMutationRunner, "settingsState.providersLoading = true", "provider mutation runner sets provider loading");
assertIncludes(providerMutationRunner, "settingsState.providersNotice = \"\"", "provider mutation runner clears provider notice");
assertIncludes(providerMutationRunner, "await options.after?.();", "provider mutation runner supports shared success follow-up");
assertNotIncludes(providerMutationRunner, "catch (error: any)", "provider mutation runner avoids any catch boundaries");
assertNotIncludes(providerMutationRunner, "Record<string, any>", "provider mutation runner avoids broad dynamic records");
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
assertIncludes(providerAuthActions, "authNotice(copy, config.connectedNoticeKey)", "provider auth OAuth connect resolves provider notice through helper");
assertIncludes(providerAuthRequests, "export async function requestProviderOAuthConnect", "provider auth requests centralize OAuth connect request");
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
assertIncludes(providerAuthConfigs, "normalizeAuthorized: (auth: ProviderAuthStatusPayload, currentAuth: ProviderAuthStatePayload) => normalizeAuthorizedDeviceAuth(auth, currentAuth, config.deviceKey, normalizeProviderAccountStatus(config, auth))", "provider auth configs normalize authorized auth through shared provider metadata");
assertIncludes(providerAuthConfigs, "normalizeProviderAccountStatus(config, auth)", "provider auth configs read authorized account status from provider metadata");
assertIncludes(providerAuthActions, "settingsState[config.noticeKey] = notice;", "provider auth actions write provider auth notices through finite keys");
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
assertIncludes(providerAuthPollTimers, "export interface ProviderAuthPollState", "provider auth poll timers expose typed poll state");
assertIncludes(providerAuthPollTimers, "const providerAuthPollTimers = new Map<string, number>()", "provider auth poll timers centralize typed provider auth poll timers");
assertIncludes(providerAuthPollTimers, "providerAuthPollTimers.set(providerId", "provider auth poll timers store auth poll timers by provider id");
assertIncludes(providerAuthPollTimers, "window.setTimeout", "provider auth poll timers keep browser timer scheduling");
assertNotIncludes(providerAuthConfigs, "clearPoll", "provider auth configs avoid auth poll clearing closure");
assertIncludes(providerAuthActions, "clearProviderAuthPollTimer(config.providerId)", "provider auth actions clear polling through provider id");
assertNotIncludes(providerAuthConfigs, "schedulePoll", "provider auth configs avoid auth poll scheduling closure");
assertIncludes(providerAuthActions, "scheduleProviderAuthPoll(config.providerId, authStateForConfig(settingsState, config)", "provider auth actions schedule polling through typed state helper");
assertIncludes(providerAuthActions, "scheduleProviderAuthPollById(config.providerId)", "provider auth actions reschedule polling through provider id");
assertNotIncludes(chatClient, "let codexAuthPollTimer", "chat client removes split Codex auth timer state");
assertNotIncludes(chatClient, "let copilotAuthPollTimer", "chat client removes split Copilot auth timer state");
assertNotIncludes(providerAuthActions, "const providerAuthFlowConfigs", "provider auth actions no longer split auth flow configs");
assertNotIncludes(providerAuthConfigs, "deviceAuthBaseConfig(providerAuthSectionForId", "provider auth configs avoid id lookup while building configs");
assertIncludes(providerAuthConfigs, "providerAuthActionConfig(config)", "provider auth configs build action metadata from provider section metadata");
assertNotIncludes(providerAuthConfigs, "providerAuthRequestConfig(config)", "provider auth configs avoid request-only naming for action metadata");
assertNotIncludes(providerAuthConfigs, "PROVIDER_AUTH_SECTIONS", "provider auth configs avoid local auth section indexes");
assertNotIncludes(providerAuthConfigs, "CODEX_AUTH_STATE_KEYS", "provider auth configs avoid direct Codex auth state key ownership");
assertNotIncludes(providerAuthConfigs, "COPILOT_AUTH_STATE_KEYS", "provider auth configs avoid direct Copilot auth state key ownership");
assertNotIncludes(providerAuthConfigs, "[config.payloadDeviceKey]: auth[config.deviceKey]", "provider auth configs avoid computed-key poll body records");
assertNotIncludes(providerAuthConfigs, "config.pollRequiresUserCode ? { user_code: auth.userCode } : {}", "provider auth configs avoid inline optional poll body spreads");
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
assertIncludes(providerAuthActionRunner, "ProviderAuthInitialStates,\n  ProviderAuthLoadingKey,\n  ProviderAuthMessageKey,", "provider auth action runner imports finite provider auth slot types");
assertIncludes(providerAuthActionRunner, "export type ProviderAuthActionState = ProviderAuthInitialStates;", "provider auth action runner reuses the finite settings state boundary");
assertIncludes(providerAuthActionRunner, "type ProviderAuthActionCopy", "provider auth action runner types auth copy boundary");
assertIncludes(providerAuthActionRunner, "loadingKey: ProviderAuthLoadingKey;", "provider auth action runner restricts loading writes to finite keys");
assertIncludes(providerAuthActionRunner, "errorKey: ProviderAuthMessageKey;\n  noticeKey: ProviderAuthMessageKey;", "provider auth action runner restricts message writes to finite keys");
assertIncludes(providerAuthActionRunner, "function setProviderAuthLoading(", "provider auth action runner centralizes boolean loading writes");
assertIncludes(providerAuthActionRunner, "function setProviderAuthMessage(", "provider auth action runner centralizes string message writes");
assertIncludes(providerAuthActionRunner, "setProviderAuthMessage(settingsState, config.errorKey, errorMessage(error) || copy.value.notices[fallbackNoticeKey]);", "provider auth action runner writes typed error slot values");
assertIncludes(providerAuthActionRunner, "setProviderAuthError(settingsState, copy, config, fallbackNoticeKey, error)", "provider auth action lifecycle reuses auth error helper");
assertIncludes(providerAuthActionRunner, "export async function runProviderAuthAction(", "provider auth action runner centralizes finite auth action lifecycle");
assertIncludes(providerAuthActionRunner, "setProviderAuthLoading(settingsState, config.loadingKey, true);", "provider auth action runner writes typed loading start values");
assertIncludes(providerAuthActionRunner, "setProviderAuthMessage(settingsState, config.errorKey, \"\");", "provider auth action runner clears error through typed message helper");
assertIncludes(providerAuthActionRunner, "setProviderAuthMessage(settingsState, config.noticeKey, \"\");", "provider auth action runner clears notice through typed message helper");
assertIncludes(providerAuthActionRunner, "setProviderAuthLoading(settingsState, config.loadingKey, false);", "provider auth action runner writes typed loading finish values");
assertIncludes(providerAuthActionRunner, "await options.after?.();", "provider auth action runner supports shared success follow-up");
assertNotIncludes(providerAuthActionRunner, "settingsState[config.loadingKey] = true;", "provider auth action runner avoids inline loading start writes");
assertNotIncludes(providerAuthActionRunner, "settingsState[config.loadingKey] = false;", "provider auth action runner avoids inline loading finish writes");
assertNotIncludes(providerAuthActionRunner, "settingsState[config.errorKey] = \"\";", "provider auth action runner avoids inline error clear writes");
assertNotIncludes(providerAuthActionRunner, "ProviderAuthActionState<TAuthState>", "provider auth action runner avoids generic open-ended auth slot state");
assertNotIncludes(providerAuthActionRunner, "setProviderAuthActionSlot", "provider auth action runner avoids mixed boolean/string slot writes");
assertNotIncludes(providerAuthActionRunner, "Record<string, ProviderAuthActionSlotValue", "provider auth action runner avoids open-ended action state records");
assertNotIncludes(providerAuthActionRunner, "Record<string, any>", "provider auth action runner avoids broad dynamic records");
assertIncludes(providerAuthActions, "type ProviderAuthActionState,", "provider auth actions reuse typed auth action state");
assertIncludes(providerAuthActions, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", "provider auth actions keep API responses unknown until request adapters convert them");
assertNotIncludes(providerAuthActions, "type RequestSettingsJson = <", "provider auth actions avoid caller-selected response types");
assertIncludes(providerAuthActions, "function authStateForConfig", "provider auth actions centralize dynamic auth state reads");
assertIncludes(providerAuthActions, "function setAuthStateForConfig", "provider auth actions centralize dynamic auth state writes");
assertIncludes(providerAuthActions, "import type { ProviderAuthStatePayload } from \"./providerAuthState\";", "provider auth actions import the finite internal auth state payload");
assertIncludes(providerAuthActions, "type ProviderAuthActionsState = ProviderMutationState & ProviderAuthActionState;", "provider auth actions compose mutation state with finite auth slots");
assertNotIncludes(providerAuthActions, "type ProviderAuthActionsState = Record<string, unknown> & ProviderMutationState;", "provider auth actions avoid broad unknown state records at context boundary");
assertNotIncludes(providerAuthActions, "function providerAuthSlotState", "provider auth actions no longer cast settings state through a slot adapter");
assertNotIncludes(providerAuthActions, "as ProviderAuthSlotState", "provider auth actions avoid asserting provider auth state slots");
assertIncludes(providerAuthActions, "runProviderAuthAction(settingsState, copy, config", "provider auth actions pass finite auth state directly to the action runner");
assertIncludes(providerAuthActions, "setProviderAuthError(settingsState, copy, config", "provider auth actions pass finite auth state directly to the error helper");
assertIncludes(providerAuthActions, "return settingsState[config.stateKey];", "provider auth actions read finite stored auth state directly");
assertNotIncludes(providerAuthActions, "normalizeProviderAuthStatePayload", "provider auth actions avoid re-normalizing trusted internal state");
assertNotIncludes(providerAuthActions, "type JsonRecord = Record<string, unknown>;", "provider auth actions avoid local JSON record aliases");
assertNotIncludes(providerAuthActions, "function toJsonRecord(value: unknown): JsonRecord", "provider auth actions avoid local raw record converters");
assertNotIncludes(providerAuthActions, "function toProviderAuthStatePayload(value: unknown): ProviderAuthStatePayload", "provider auth actions delegate stored auth state normalization");
assertIncludes(providerAuthActions, "function authStateForConfig(settingsState: ProviderAuthActionsState, config: ProviderAuthConfig): ProviderAuthStatePayload", "provider auth actions return typed auth state payloads");
assertIncludes(providerAuthActions, "function setAuthStateForConfig(settingsState: ProviderAuthActionsState, config: ProviderAuthConfig, auth: ProviderAuthStatePayload): void", "provider auth actions write typed auth state payloads");
assertIncludes(providerAuthActions, "type ProviderAuthNoticeValue = string;", "provider auth actions type auth notice slot values");
assertIncludes(providerAuthActions, "function setAuthNoticeForConfig(settingsState: ProviderAuthActionsState, config: ProviderAuthConfig, notice: ProviderAuthNoticeValue): void", "provider auth actions centralize auth notice writes");
assertIncludes(providerAuthActions, "settingsState[config.noticeKey] = notice;", "provider auth actions write typed auth notice values");
assertIncludes(providerAuthActions, "setAuthNoticeForConfig(settingsState, config, \"\");", "provider auth actions clear auth notices through typed helper");
assertNotIncludes(providerAuthActions, "settingsState[config.noticeKey] = \"\";", "provider auth actions avoid inline auth notice clear writes");
assertIncludes(providerAuthActions, "const auth = payload.auth || {};", "provider auth actions consume typed authorized auth payload");
assertNotIncludes(providerAuthActions, "function toProviderAuthStatusPayload", "provider auth actions avoid re-narrowing typed auth response payloads");
assertIncludes(providerAuthActions, "function authNotice", "provider auth actions centralize dynamic auth notices");
assertNotIncludes(providerAuthActions, "Record<string, any>", "provider auth actions avoid broad dynamic records");
assertIncludes(providerAuthActions, "await runProviderAuthAction(settingsState, copy, config, config.loadFailedNoticeKey", "provider auth status uses shared action lifecycle");
assertIncludes(providerAuthActions, "await runProviderAuthAction(settingsState, copy, config, config.loginFailedNoticeKey", "provider auth login uses shared action lifecycle");
assertIncludes(providerAuthActions, "await runProviderAuthAction(settingsState, copy, config, config.logoutFailedNoticeKey", "provider auth logout uses shared action lifecycle");
assertIncludes(providerAuthActions, "after: () => loadProviderAuthStatusById(config.providerId)", "provider auth logout refreshes status after logout through provider id");
assertIncludes(providerAuthActions, "setProviderAuthError(settingsState, copy, config, config.loginFailedNoticeKey, error)", "provider auth polling reuses auth error helper");
assertIncludes(providerAuthRequests, "export async function requestProviderAuthLogin", "provider auth requests centralize auth login request");
assertIncludes(providerAuthRequests, "export async function requestProviderAuthPoll", "provider auth requests centralize auth poll request");
assertIncludes(providerAuthRequests, "export async function requestProviderAuthLogout", "provider auth requests centralize auth logout request");
assertIncludes(providerAuthRequests, "requestSettingsJson(optionalText(config.loginEndpoint), { method: \"POST\" })", "provider auth requests keep auth login conversion at the response boundary");
assertIncludes(providerAuthRequests, "requestSettingsJson(optionalText(config.logoutEndpoint), { method: \"POST\" })", "provider auth requests keep auth logout conversion at the response boundary");
assertIncludes(providerAuthRequests, "requestSettingsJson(optionalText(config.pollEndpoint)", "provider auth requests keep auth poll conversion at the response boundary");
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
assertIncludes(providerSettings, "builtInBadge?: unknown;", "provider settings copy view names available badge copy field");
assertIncludes(providerSettings, "connectOAuth?: unknown;", "provider settings copy view names OAuth copy field");
assertIncludes(providerSettings, "connectedCount?: unknown;", "provider settings copy view names connected count copy field");
assertIncludes(providerSettings, "connectedTitle?: unknown;", "provider settings copy view names connected title copy field");
assertIncludes(providerSettings, "credentialLabel?: unknown;", "provider settings copy view names credential label copy field");
assertIncludes(providerSettings, "disconnect?: unknown;", "provider settings copy view names disconnect copy field");
assertIncludes(providerSettings, "missingCredential?: unknown;", "provider settings copy view names missing credential copy field");
assertIncludes(providerSettings, "noConnectedTitle?: unknown;", "provider settings copy view names connected empty title copy field");
assertIncludes(providerSettings, "popularTitle?: unknown;", "provider settings copy view names available title copy field");
assertIncludes(providerHelpers, "export function selectedConnectProvider", "provider helpers centralize connect dialog provider selection");
assertIncludes(providerSettings, "selectedConnectProvider(providers, state.connectForm.providerId)", "provider settings delegates connect provider selection");
assertNotIncludes(providerSettings, "...(providers.available || []), ...(providers.connected || [])", "provider settings no longer owns connect provider list merge");
assertIncludes(providerSettings, "type ProviderSettingsStateView = ProviderAuthSlotState & {", "provider settings component carries finite provider auth state");
assertNotIncludes(providerSettings, "type ProviderSettingsStateView = JsonRecord & {", "provider settings component avoids dynamic provider state view boundary");
assertIncludes(providerSettings, "ProviderCredentialsState,", "provider settings component reuses typed credential state");
assertIncludes(providerSettings, "credentials?: ProviderCredentialsState;", "provider settings component types credential state field");
assertIncludes(providerSettings, "type ProviderSettingsCopyView = {", "provider settings component uses fixed provider copy view boundary");
assertNotIncludes(providerSettings, "type ProviderSettingsCopyView = JsonRecord & {", "provider settings component avoids dynamic provider copy view boundary");
assertIncludes(providerSettings, "function providerSettingsCopy(copy: ProviderSettingsCopy): ProviderSettingsCopyView", "provider settings component centralizes provider copy narrowing");
assertIncludes(providerSettings, "const settings = toPayloadSource<ProviderSettingsContainerPayload>(copy.settings);", "provider settings narrows its copy container before reading providers");
assertNotIncludes(providerSettings, "toProviderAuthSlotMap", "provider settings avoids downgrading typed auth state into an open map");
assertNotIncludes(providerSettings, "type JsonRecord", "provider settings component avoids dynamic JsonRecord alias");
assertNotIncludes(providerSettings, "function toRecord", "provider settings component avoids generic record conversion");
assertNotIncludes(providerSettings, "type AnyRecord", "provider settings component avoids dynamic AnyRecord alias");
assertNotIncludes(providerSettings, "Record<string, any>", "provider settings component avoids broad dynamic records");
assertIncludes(providerAuthSection, "SettingsSectionTitle", "provider auth section keeps section title");
assertIncludes(providerAuthSection, "SettingsStatus message={notice}", "provider auth section keeps notice status");
assertIncludes(providerAuthSection, "SettingsStatus message={error} type=\"error\"", "provider auth section keeps error status");
assertIncludes(providerAuthSection, "AuthProviderCard", "provider auth section renders auth provider card");
assertIncludes(providerAuthSections, "export type ProviderAuthSectionView", "provider auth sections expose typed section view");
assertNotIncludes(providerAuthSections, "ProviderAuthSectionConfigView", "provider auth sections consume metadata configs without an asserted adapter view");
assertIncludes(providerAuthSections, "type ProviderAuthStateView,", "provider auth sections import shared auth state view boundary");
assertIncludes(providerAuthSections, "type ProviderAuthCopyView,", "provider auth sections import shared auth copy view boundary");
assertIncludes(providerAuthSections, "export function providerAuthSections(copy: unknown, state: ProviderAuthSlotState", "provider auth sections consume finite metadata-derived state");
assertNotIncludes(providerAuthSections, "type JsonRecord = Record<string, unknown>;", "provider auth sections avoid a shared generic record alias");
assertNotIncludes(providerAuthSections, "function toRecord", "provider auth sections avoid a shared generic record converter");
assertNotIncludes(providerAuthSections, "type ProviderAuthSectionConfigView = JsonRecord & {", "provider auth sections avoid dynamic config view boundary");
assertNotIncludes(providerAuthSections, "type ProviderAuthStateView = JsonRecord & {", "provider auth sections avoid dynamic auth state view boundary");
assertNotIncludes(providerAuthSections, "type ProviderAuthCopyView = JsonRecord & {", "provider auth sections avoid dynamic auth copy view boundary");
assertNotIncludes(providerAuthSections, "AnyRecord", "provider auth sections avoid dynamic AnyRecord import");
assertNotIncludes(providerAuthSections, "Record<string, any>", "provider auth sections avoid broad dynamic records");
assertIncludes(providerAuthSection, "Omit<ProviderAuthSectionView, \"key\" | \"visible\">", "provider auth section consumes typed section view props");
assertNotIncludes(providerAuthSection, "AnyRecord", "provider auth section avoids dynamic AnyRecord import");
assertNotIncludes(providerAuthSection, "Record<string, any>", "provider auth section avoids broad dynamic records");
assertIncludes(providerAuthSection, "onLogin={onLogin}", "provider auth section keeps login action");
assertIncludes(providerAuthHelpers, "hasConnectedProvider(state, config.providerId)", "provider auth visibility reads connected provider state through metadata");
assertIncludes(providerAuthHelpers, "state[config.noticeKey]", "provider auth visibility reads notice state through metadata");
assertIncludes(providerAuthHelpers, "state[config.errorKey]", "provider auth visibility reads error state through metadata");
assertIncludes(authProviderCard, "codex-auth-row", "auth provider card keeps auth row layout");
assertIncludes(authProviderCard, "type AuthProviderCardCopy = {", "auth provider card uses fixed copy view boundary");
assertIncludes(authProviderCard, "type AuthProviderCardState = {", "auth provider card uses fixed auth state boundary");
assertIncludes(authProviderCard, "type AuthProviderCardProps = {", "auth provider card uses typed props");
assertIncludes(authProviderCard, "userCode?: unknown;", "auth provider card names user code auth state field");
assertIncludes(authProviderCard, "verificationUri?: unknown;", "auth provider card names verification URI auth state field");
assertNotIncludes(authProviderCard, "type AuthProviderCardCopy = JsonRecord & {", "auth provider card avoids dynamic copy view boundary");
assertNotIncludes(authProviderCard, "type AuthProviderCardState = JsonRecord & {", "auth provider card avoids dynamic auth state boundary");
assertNotIncludes(authProviderCard, "AnyRecord", "auth provider card avoids dynamic AnyRecord import");
assertNotIncludes(authProviderCard, "type JsonRecord", "auth provider card avoids dynamic JsonRecord alias");
assertNotIncludes(authProviderCard, "Record<string, any>", "auth provider card avoids broad dynamic records");
assertIncludes(authProviderCard, "onClick={onRefresh}", "auth provider card keeps refresh action");
assertIncludes(authProviderCard, "onClick={onLogin}", "auth provider card keeps login action");
assertIncludes(authProviderCard, "onClick={onLogout}", "auth provider card keeps logout action");
assertIncludes(authProviderCard, "auth.userCode", "auth provider card keeps user code display");
assertIncludes(availableProvidersSection, "AvailableProviderRow", "available providers delegates available provider row");
assertIncludes(availableProvidersSection, "ProviderEmptyState", "available providers delegates provider empty state");
assertIncludes(availableProvidersSection, "type AvailableProviderCopyView = {", "available providers section uses fixed copy view boundary");
assertIncludes(availableProvidersSection, "builtInBadge?: unknown;", "available providers section carries row badge copy field");
assertIncludes(availableProvidersSection, "connectOAuth?: unknown;", "available providers section carries OAuth copy field");
assertIncludes(availableProvidersSection, "connectedCount?: unknown;", "available providers section carries connected count copy field");
assertIncludes(availableProvidersSection, "providerCopy.noAvailableTitle", "available providers keeps empty state title");
assertIncludes(availableProvidersSection, "providers: ProviderLike[]", "available providers section types provider list");
assertNotIncludes(availableProvidersSection, "type AvailableProviderCopyView = JsonRecord & {", "available providers section avoids dynamic copy view boundary");
assertNotIncludes(availableProvidersSection, "AnyRecord", "available providers section avoids dynamic AnyRecord import");
assertNotIncludes(availableProvidersSection, "type JsonRecord", "available providers section avoids dynamic JsonRecord alias");
assertNotIncludes(availableProvidersSection, "Record<string, any>", "available providers section avoids broad dynamic records");
assertIncludes(providerEmptyState, "provider-row--empty", "provider empty state keeps row class");
assertIncludes(providerEmptyState, "<strong>{title}</strong>", "provider empty state keeps title");
assertIncludes(providerEmptyState, "<span>{description}</span>", "provider empty state keeps description");
assertIncludes(availableProviderRow, "type AvailableProviderView = ProviderLike & {", "available provider row types available provider view");
assertIncludes(availableProviderRow, "type AvailableProviderCopyView = {", "available provider row uses fixed copy view boundary");
assertIncludes(availableProviderRow, "builtInBadge?: unknown;", "available provider row names built-in badge copy field");
assertIncludes(availableProviderRow, "connect?: unknown;", "available provider row names connect copy field");
assertIncludes(availableProviderRow, "connectOAuth?: unknown;", "available provider row names OAuth connect copy field");
assertIncludes(availableProviderRow, "connectedCount?: unknown;", "available provider row names connected count copy field");
assertIncludes(availableProviderRow, "isOAuthProviderAuthType(text(provider.auth_type))", "available provider row keeps typed OAuth detection");
assertIncludes(availableProviderRow, "onConnectOAuth(provider) : onBeginConnect(provider)", "available provider row keeps connect routing");
assertIncludes(availableProviderRow, "providerCopy.builtInBadge", "available provider row keeps built-in badge");
assertIncludes(availableProviderRow, "function connectedCountLabel(copy: AvailableProviderCopyView, count: unknown): string", "available provider row centralizes connected count badge label");
assertNotIncludes(availableProviderRow, "type AvailableProviderCopyView = JsonRecord & {", "available provider row avoids dynamic copy view boundary");
assertNotIncludes(availableProviderRow, "AnyRecord", "available provider row avoids dynamic AnyRecord import");
assertNotIncludes(availableProviderRow, "type JsonRecord", "available provider row avoids dynamic JsonRecord alias");
assertNotIncludes(availableProviderRow, "Record<string, any>", "available provider row avoids broad dynamic records");
assertIncludes(connectedProvidersSection, "ConnectedProviderRow", "connected providers delegates connected provider row");
assertIncludes(connectedProvidersSection, "ProviderEmptyState", "connected providers delegates provider empty state");
assertIncludes(connectedProvidersSection, "type ConnectedProviderCopyView = {", "connected providers section uses fixed copy view boundary");
assertIncludes(connectedProvidersSection, "type ConnectedProvidersStateView = ProviderAuthSlotState & {", "connected providers section preserves finite auth state for provider rows");
assertIncludes(connectedProvidersSection, "credentialLabel?: unknown;", "connected providers section carries row credential label copy field");
assertIncludes(connectedProvidersSection, "credentialSelect?: unknown;", "connected providers section carries row credential select copy field");
assertIncludes(connectedProvidersSection, "deleteCredential?: unknown;", "connected providers section carries row delete credential copy field");
assertIncludes(connectedProvidersSection, "disconnect?: unknown;", "connected providers section carries row disconnect copy field");
assertIncludes(connectedProvidersSection, "missingCredential?: unknown;", "connected providers section carries row missing credential copy field");
assertIncludes(connectedProvidersSection, "providers: ProviderLike[]", "connected providers section types provider list");
assertIncludes(connectedProvidersSection, "import type { ProviderCredentialsState }", "connected providers section reuses typed credential state");
assertIncludes(connectedProvidersSection, "credentials?: ProviderCredentialsState;", "connected providers section types credential state field");
assertNotIncludes(connectedProvidersSection, "type ConnectedProviderCopyView = JsonRecord & {", "connected providers section avoids dynamic copy view boundary");
assertNotIncludes(connectedProvidersSection, "type ConnectedProvidersStateView = JsonRecord & {", "connected providers section avoids dynamic state view boundary");
assertIncludes(connectedProvidersSection, "copy: unknown;", "connected providers section preserves an unknown copy boundary for row normalization");
assertNotIncludes(connectedProvidersSection, "type JsonRecord", "connected providers section avoids dynamic JsonRecord alias");
assertNotIncludes(connectedProvidersSection, "AnyRecord", "connected providers section avoids dynamic AnyRecord import");
assertNotIncludes(connectedProvidersSection, "Record<string, any>", "connected providers section avoids broad dynamic records");
assertIncludes(connectedProviderRow, "providerCredentials(state, provider)", "connected provider row keeps credential lookup");
assertIncludes(connectedProviderRow, "providerEffectiveCredentialId(provider)", "connected provider row keeps effective credential lookup");
assertIncludes(connectedProviderRow, "type ConnectedProviderView = ProviderLike & {", "connected provider row types connected provider view");
assertIncludes(connectedProviderRow, "type ProviderCopyView = {", "connected provider row uses fixed provider copy view boundary");
assertIncludes(connectedProviderRow, "type ConnectedProviderStateView = ProviderAuthSlotState & {", "connected provider row uses finite auth state boundary");
assertIncludes(connectedProviderRow, "credentialLabel?: unknown;", "connected provider row names credential label copy field");
assertIncludes(connectedProviderRow, "credentialSelect?: unknown;", "connected provider row names credential select copy field");
assertIncludes(connectedProviderRow, "currentBadge?: unknown;", "connected provider row names current badge copy field");
assertIncludes(connectedProviderRow, "deleteCredential?: unknown;", "connected provider row names delete credential copy field");
assertIncludes(connectedProviderRow, "disconnect?: unknown;", "connected provider row names disconnect copy field");
assertIncludes(connectedProviderRow, "missingCredential?: unknown;", "connected provider row names missing credential copy field");
assertIncludes(connectedProviderRow, "import type { ProviderCredentialView, ProviderCredentialsState }", "connected provider row reuses typed credential state");
assertIncludes(connectedProviderRow, "credentials?: ProviderCredentialsState;", "connected provider row types credential state field");
assertIncludes(connectedProviderRow, "function credentialOption(credential: ProviderCredentialView): { value: string; label: string }", "connected provider row normalizes typed credential options");
assertIncludes(connectedProviderRow, "function credentialPreviewLabel(copy: unknown, providerCopy: ProviderCopyView, provider: ConnectedProviderView): string", "connected provider row centralizes credential preview labels from an unknown copy boundary");
assertIncludes(connectedProviderRow, "const authCopy = providerAuthCopyForProvider(copy, provider);", "connected provider row delegates auth copy narrowing to provider auth helpers");
assertNotIncludes(connectedProviderRow, "toProviderAuthSlotMap", "connected provider row avoids downgrading typed auth state into an open map");
assertNotIncludes(connectedProviderRow, "type JsonRecord", "connected provider row avoids dynamic JsonRecord alias");
assertNotIncludes(connectedProviderRow, "function toRecord", "connected provider row avoids generic record conversion");
assertNotIncludes(connectedProviderRow, "type ProviderCopyView = JsonRecord & {", "connected provider row avoids dynamic provider copy view boundary");
assertNotIncludes(connectedProviderRow, "type ConnectedProviderStateView = JsonRecord & {", "connected provider row avoids dynamic state view boundary");
assertNotIncludes(connectedProviderRow, "type AnyRecord", "connected provider row avoids dynamic AnyRecord alias");
assertNotIncludes(connectedProviderRow, "Record<string, any>", "connected provider row avoids broad dynamic records");
assertIncludes(providerCredentialHelpers, "export function providerCredentials", "provider credential helpers expose credential lookup");
assertIncludes(providerCredentialHelpers, "export function providerEffectiveCredentialId", "provider credential helpers expose effective credential id lookup");
assertIncludes(providerCredentialHelpers, "export function credentialSourceLabel", "provider credential helpers expose credential source labels");
assertIncludes(connectedProviderRow, "providerAuthCopyKey(provider)", "connected provider row keeps provider auth copy lookup");
assertIncludes(providerAuthHelpers, "export function providerAuthCopyKey", "provider auth helpers expose provider auth copy key helper");
assertIncludes(providerAuthHelpers, "export function providerAuthCopyForProvider", "provider auth helpers expose provider-scoped auth copy narrowing");
assertIncludes(providerAuthHelpers, "return config ? authCopyForConfig(copy, config) : {};", "provider auth helpers reuse config-scoped copy narrowing for provider rows");
assertIncludes(connectedProviderRow, "providerAuthConfigured(state, provider)", "connected provider row keeps auth configured badge rule through finite state");
assertIncludes(connectedProviderRow, "providerDescription(copy, state, provider)", "connected provider row keeps provider description through finite state");
assertIncludes(connectedProviderRow, "onSetCredential(provider, String(value || \"\"))", "connected provider row keeps typed credential switch action");
assertIncludes(connectedProviderRow, "onDeleteCredential(provider, effectiveCredentialId)", "connected provider row keeps credential deletion action");
assertIncludes(connectedProviderRow, "onDisconnect(provider)", "connected provider row keeps disconnect action");
assertIncludes(connectedProviderRow, "provider-row__credential--missing", "connected provider row keeps missing credential state");
assertIncludes(providerConnectDialog, "role=\"dialog\"", "provider connect dialog keeps dialog role");
assertIncludes(providerConnectDialog, "type ProviderConnectProviderView = ProviderLike & {", "provider connect dialog types provider view");
assertIncludes(providerConnectDialog, "type ProviderConnectCopyView = {", "provider connect dialog uses fixed copy view boundary");
assertIncludes(providerConnectDialog, "loading?: unknown;", "provider connect dialog names shared provider loading copy field");
assertIncludes(providerConnectDialog, "type ProviderConnectStateView = {", "provider connect dialog uses fixed state view boundary");
assertNotIncludes(providerConnectDialog, "type ProviderConnectCopyView = JsonRecord & {", "provider connect dialog avoids dynamic copy view boundary");
assertNotIncludes(providerConnectDialog, "type ProviderConnectStateView = JsonRecord & {", "provider connect dialog avoids dynamic state view boundary");
assertIncludes(providerConnectDialog, "function formatCopy(copyValue: unknown, providerName: string, fallback = \"\"): string", "provider connect dialog centralizes function copy formatting");
assertNotIncludes(providerConnectDialog, "type AnyRecord", "provider connect dialog avoids dynamic AnyRecord alias");
assertNotIncludes(providerConnectDialog, "type JsonRecord", "provider connect dialog avoids dynamic JsonRecord alias");
assertNotIncludes(providerConnectDialog, "Record<string, any>", "provider connect dialog avoids broad dynamic records");
assertIncludes(providerConnectDialog, "provider.requires_api_key !== false || provider.api_key_optional === true", "provider connect dialog keeps API key requirement rule");
assertIncludes(providerConnectDialog, "form.showAdvanced = !form.showAdvanced", "provider connect dialog keeps advanced toggle");
assertIncludes(providerConnectDialog, "form.baseUrl", "provider connect dialog keeps base URL field");
assertIncludes(providerConnectDialog, "onFinish={() => onSave()}", "provider connect dialog keeps save action");
assertIncludes(providerConnectDialog, "onClick={onCancel}", "provider connect dialog keeps cancel actions");
assertNotIncludes(providerAuthMetadata, "[CODEX_PROVIDER_ID]: CODEX_AUTH_STATE_KEYS.authKey", "provider auth metadata avoid duplicate Codex auth key map");
assertNotIncludes(providerAuthMetadata, "[COPILOT_PROVIDER_ID]: COPILOT_AUTH_STATE_KEYS.authKey", "provider auth metadata avoid duplicate Copilot auth key map");
assertIncludes(providerAuthHelpers, "export function providerAuthDescription", "provider auth helpers centralize provider auth descriptions");
assertIncludes(providerAuthHelpers, "export type ProviderAuthConfigView = Pick<", "provider auth helpers derive config reads from metadata");
assertIncludes(providerAuthHelpers, "export type ProviderAuthStateView = Pick<", "provider auth helpers derive shared auth state view from finite internal state");
assertIncludes(providerAuthHelpers, "export type ProviderAuthCopyView = {", "provider auth helpers own shared auth copy view boundary");
assertIncludes(providerAuthHelpers, "export type ProviderAuthSlotState = ProviderAuthInitialStates & {", "provider auth helpers preserve finite auth state slots");
assertIncludes(providerAuthHelpers, "export function authState(state: ProviderAuthSlotState, config: ProviderAuthConfigView): ProviderAuthStateView", "provider auth helpers centralize finite auth state reads");
assertIncludes(providerAuthHelpers, "return state[config.stateKey];", "provider auth helpers read trusted finite auth state directly");
assertNotIncludes(providerAuthHelpers, "toPayloadSource<ProviderAuthStateView>", "provider auth helpers avoid re-normalizing trusted internal auth state");
assertNotIncludes(providerAuthHelpers, "ProviderAuthSlotMap", "provider auth helpers avoid an open auth slot map");
assertNotIncludes(providerAuthHelpers, "as ProviderAuthConfigView", "provider auth helpers avoid asserting metadata configs");
assertIncludes(providerAuthHelpers, "export function authCopyForConfig(copy: unknown, config: ProviderAuthConfigView): ProviderAuthCopyView", "provider auth helpers centralize auth copy reads");
assertIncludes(providerAuthHelpers, "type ProviderAuthCopyKey = ProviderAuthSectionConfig[\"copyKey\"];", "provider auth helpers derive finite copy keys from provider metadata");
assertIncludes(providerAuthHelpers, "[CopyKey in ProviderAuthCopyKey]?: unknown;", "provider auth helpers restrict provider copy lookup to finite keys");
assertNotIncludes(providerAuthHelpers, "[copyKey: string]: unknown;", "provider auth helpers avoid open provider auth copy keys");
assertIncludes(providerAuthHelpers, "return toPayloadSource<ProviderAuthCopyView>(providers?.[config.copyKey]) || {};", "provider auth helpers project finite copy keys into the fixed copy view");
assertNotIncludes(providerAuthHelpers, "type JsonRecord = Record<string, unknown>;", "provider auth helpers avoid a shared generic record alias");
assertNotIncludes(providerAuthHelpers, "function toRecord", "provider auth helpers avoid a shared generic record converter");
assertNotIncludes(providerAuthHelpers, "type ProviderAuthConfigView = JsonRecord & {", "provider auth helpers avoid dynamic config view boundary");
assertNotIncludes(providerAuthHelpers, "type ProviderAuthStateView = JsonRecord & {", "provider auth helpers avoid dynamic auth state view boundary");
assertNotIncludes(providerAuthHelpers, "type ProviderAuthCopyView = JsonRecord & {", "provider auth helpers avoid dynamic auth copy view boundary");
assertNotIncludes(providerAuthHelpers, "type AnyRecord", "provider auth helpers avoid dynamic AnyRecord alias");
assertNotIncludes(providerAuthHelpers, "Record<string, any>", "provider auth helpers avoid broad dynamic records");
assertIncludes(providerAuthSections, "providerAuthDescription(copy, state, config)", "provider auth sections delegate description to metadata-typed helper");
assertNotIncludes(providerAuthSections, "PROVIDER_AUTH_DESCRIPTIONS", "provider auth sections avoid per-provider description maps");
assertNotIncludes(providerHelpers, "CODEX_AUTH_CONFIG", "provider helpers avoid direct Codex auth config ownership");
assertNotIncludes(providerHelpers, "COPILOT_AUTH_CONFIG", "provider helpers avoid direct Copilot auth config ownership");
assertNotIncludes(providerHelpers, "CODEX_AUTH_STATE_KEYS", "provider helpers avoid direct Codex auth state key ownership");
assertNotIncludes(providerHelpers, "COPILOT_AUTH_STATE_KEYS", "provider helpers avoid direct Copilot auth state key ownership");
assertIncludes(modelSettings, "client.saveMediaModel", "model settings keeps media model save action");
assertIncludes(modelSettings, "type ModelSettingsStateView = {", "model settings component uses fixed settings state view boundary");
assertNotIncludes(modelSettings, "type ModelSettingsStateView = JsonRecord & {", "model settings component avoids dynamic settings state view boundary");
assertIncludes(modelSettings, "type ModelSettingsCopyView = {", "model settings component uses fixed copy view boundary");
assertNotIncludes(modelSettings, "type ModelSettingsCopyView = JsonRecord & {", "model settings component avoids dynamic copy view boundary");
assertIncludes(modelSettings, "function modelSettingsCopy(copy: ModelSettingsCopy): ModelSettingsCopyView", "model settings component centralizes copy narrowing");
assertIncludes(modelSettings, "const settings = toPayloadSource<ModelSettingsContainerPayload>(copy.settings);", "model settings narrows its copy container before reading models");
assertNotIncludes(modelSettings, "type JsonRecord", "model settings component avoids dynamic JsonRecord aliases");
assertNotIncludes(modelSettings, "function toRecord", "model settings component avoids generic record conversion");
assertIncludes(modelSettings, "function emptyMediaSelection(): MediaSelection", "model settings component uses typed media selection fallback");
assertNotIncludes(modelSettings, "type AnyRecord", "model settings component avoids dynamic AnyRecord alias");
assertNotIncludes(modelSettings, "Record<string, any>", "model settings component avoids broad dynamic records");
assertIncludes(modelSettings, "modelOptionsForProvider(selectedProvider, selectedModel)", "model settings keeps text model option helper");
assertIncludes(modelSettings, "textModelOptionLabel(copy, selectedProvider, model)", "model settings keeps text model label helper");
assertIncludes(modelSettings, "mediaModelCategories(copy).map", "model settings keeps media category helper");
assertIncludes(modelSettings, "mediaModelsForProvider(state, category.key, selection.providerId, selection.model)", "model settings keeps media model lookup helper");
assertIncludes(channelSettings, "type ChannelSettingsCopyView = {", "channel settings types copy view");
assertIncludes(channelSettings, "type ChannelSettingsStateView = {", "channel settings types state view");
assertIncludes(channelSettings, "client.beginChannelConnect", "channel settings keeps add channel flow");
assertIncludes(channelSettings, "function channelName(channel: ChannelView): string", "channel settings centralizes channel label formatting");
assertIncludes(channelSettings, "providerMark(channel)", "channel settings renders channel marks through the shared minimal view");
assertIncludes(channelSettings, "providerMark(selectedConnectChannel)", "channel settings renders selected channel marks without conversion");
assertNotIncludes(channelSettings, "as ProviderLike", "channel settings avoids asserting channels as providers");
assertNotIncludes(channelSettings, "type AnyRecord", "channel settings avoids dynamic AnyRecord alias");
assertNotIncludes(channelSettings, "Record<string, any>", "channel settings avoids broad dynamic records");
assertIncludes(mcpSettings, "type McpSettingsCopyView = {", "MCP settings types copy view");
assertIncludes(mcpSettings, "type McpSettingsCopy = {", "MCP settings uses a finite page copy envelope");
assertNotIncludes(mcpSettings, "type JsonRecord", "MCP settings avoids dynamic JsonRecord aliases");
assertNotIncludes(mcpSettings, "McpSettingsCopy = JsonRecord &", "MCP settings avoids open-ended page copy inheritance");
assertIncludes(mcpSettings, "import type { McpForm, McpServerView, McpSettings as McpSettingsValue } from \"../composables/useSettingsState\";", "MCP settings reuses typed MCP state views");
assertIncludes(mcpSettings, "type McpSettingsStateView = {", "MCP settings types state view without a generic index signature");
assertIncludes(mcpSettings, "mcp: McpSettingsValue;", "MCP settings reads typed MCP state");
assertIncludes(mcpSettings, "function stringList(value: unknown): string[]", "MCP settings narrows dynamic list values");
assertIncludes(mcpSettings, "client.toggleMcpAdvanced", "MCP settings keeps advanced editor");
assertIncludes(mcpSettings, "client.toggleMcpJsonInput", "MCP settings keeps JSON editor");
assertIncludes(mcpSettings, "client.applyMcpJson", "MCP settings keeps JSON import action");
assertIncludes(mcpSettings, "form.envJson", "MCP settings keeps environment JSON field");
assertIncludes(mcpSettings, "form.headersJson", "MCP settings keeps headers JSON field");
assertNotIncludes(mcpSettings, "type AnyRecord", "MCP settings avoids dynamic AnyRecord alias");
assertNotIncludes(mcpSettings, "Record<string, any>", "MCP settings avoids broad dynamic records");
assertIncludes(scheduleSettings, "state.scheduleForm.defaultTimezone", "schedule settings keeps default timezone field");
assertIncludes(scheduleSettings, "client.saveScheduleSettings", "schedule settings keeps default save action");
assertIncludes(scheduleSettings, "client.saveCronJob", "schedule settings keeps cron editor save");
assertIncludes(scheduleSettings, "client.runCronJobAction(job, job.enabled ? \"pause\" : \"enable\")", "schedule settings keeps pause/enable action");
assertIncludes(scheduleSettings, "client.runCronJobAction(job, \"run\")", "schedule settings keeps run-now action");
assertIncludes(scheduleSettings, "client.runCronJobAction(job, \"remove\")", "schedule settings keeps remove action");
assertIncludes(scheduleSettings, "form.deliver", "schedule settings keeps delivery toggle");
assertIncludes(scheduleSettings, "type ScheduleSettingsCopyView = {", "schedule settings types copy view");
assertIncludes(scheduleSettings, "type ScheduleSettingsStateView = {", "schedule settings types state view");
assertIncludes(scheduleSettings, "import { CRON_JOB_MODES, normalizeCronJobMode, type CronJobAction, type CronJobMode, type ScheduleForm, type ScheduleState } from \"../composables/scheduleDefaults\";", "schedule settings imports typed cron job modes");
assertIncludes(scheduleSettings, "import type { CronJobForm, CronJobView } from \"../composables/useSettingsState\";", "schedule settings reuses typed cron job view from settings state");
assertIncludes(scheduleSettings, "runCronJobAction: (job: CronJobView, action: CronJobAction) => void;", "schedule settings narrows cron job actions");
assertIncludes(scheduleSettings, "function jobScheduleSummary(job: CronJobView): string", "schedule settings centralizes job schedule formatting");
assertIncludes(scheduleSettings, "function cronJobModeLabel(copy: ScheduleSettingsCopyView, mode: CronJobMode): string", "schedule settings labels typed cron job modes");
assertIncludes(scheduleSettings, "options={CRON_JOB_MODES.map((mode) => ({ value: mode, label: cronJobModeLabel(scheduleCopy, mode) }))}", "schedule settings renders job modes from typed constants");
assertIncludes(scheduleSettings, "onChange={(value) => (form.mode = normalizeCronJobMode(value))}", "schedule settings normalizes selected cron job mode");
assertNotIncludes(scheduleSettings, "type ScheduleJobView", "schedule settings no longer duplicates cron job record shape");
assertNotIncludes(scheduleSettings, "function toRecord", "schedule settings relies on normalized cron job records");
assertNotIncludes(scheduleSettings, "type AnyRecord", "schedule settings avoids dynamic AnyRecord alias");
assertNotIncludes(scheduleSettings, "Record<string, any>", "schedule settings avoids broad dynamic records");
assertIncludes(scheduleNetworkHelpers, "type ScheduleTimezoneState = {", "schedule network helper types timezone state");
assertNotIncludes(scheduleNetworkHelpers, "type AnyRecord", "schedule network helper avoids dynamic AnyRecord alias");
assertNotIncludes(scheduleNetworkHelpers, "Record<string, any>", "schedule network helper avoids broad dynamic records");
assertIncludes(networkSettings, "type NetworkSettingsCopyView = {", "network settings types copy view");
assertIncludes(networkSettings, "type NetworkSettingsStateView = {", "network settings types state view");
assertIncludes(networkSettings, "form.httpProxy", "network settings keeps HTTP proxy field");
assertIncludes(networkSettings, "form.httpsProxy", "network settings keeps HTTPS proxy field");
assertIncludes(networkSettings, "form.noProxy", "network settings keeps no proxy field");
assertNotIncludes(networkSettings, "state.networkForm.enabled", "network settings does not show unsupported enabled field");
assertNotIncludes(networkSettings, "type AnyRecord", "network settings avoids dynamic AnyRecord alias");
assertNotIncludes(networkSettings, "Record<string, any>", "network settings avoids broad dynamic records");
assertIncludes(searchSettings, "client.saveSearchSettings", "search settings keeps save action");
assertIncludes(searchSettings, "client.loadSearxngOptions", "search settings keeps SearXNG option load action");
assertIncludes(searchSettings, "type SearchSettingsStateView = SearchSettingsStateLike & {", "search settings types state view");
assertIncludes(searchSettings, "const searchCopy: SearchSettingsCopyView = copy.settings.search ?? {};", "search settings types copy view");
assertIncludes(searchSettings, "form.jinaApiKey", "search settings keeps Jina API key field");
assertIncludes(searchSettings, "form.searxngEngines", "search settings keeps SearXNG engine selection");
assertIncludes(searchSettings, "form.searxngCategories", "search settings keeps SearXNG category selection");
assertNotIncludes(searchSettings, "type AnyRecord", "search settings avoids dynamic AnyRecord alias");
assertNotIncludes(searchSettings, "Record<string, any>", "search settings avoids broad dynamic records");
assertIncludes(searchBrowserHelpers, "export type SearchSettingsCopyView = {", "search helper types search copy view");
assertIncludes(searchBrowserHelpers, "export type SearchSettingsStateLike = {", "search helper types search state view");
assertIncludes(searchBrowserHelpers, "search?: Partial<SearchState>;", "search helper accepts typed search state without dynamic index signature");
assertIncludes(searchBrowserHelpers, "export function mergeSelectedSearchOptions(options: SearxngOptionEntry[] = [], selected: string[] = []): SearchOptionEntry[]", "search helper types SearXNG option merge");
assertIncludes(searchBrowserHelpers, "export type SearchOptionEntry = SearxngOptionEntry;", "search helper preserves normalized SearXNG option entries without generic record intersections");
assertIncludes(searchBrowserHelpers, "export type BrowserSettingsCopyView = {", "browser helper types browser copy view");
assertIncludes(searchBrowserHelpers, "export type BrowserSettingsStateLike = {", "browser helper types browser state view");
assertIncludes(searchBrowserHelpers, "import { normalizeBrowserResultCheck, type BrowserForm, type BrowserOperationResult, type BrowserResultCheck, type BrowserRuntimeState, type BrowserState } from \"../composables/browserDefaults\";", "browser helper reuses browser result view types");
assertIncludes(searchBrowserHelpers, "import { toPayloadSource } from \"../composables/payloadBoundary\";", "search/browser helper reuses the shared finite payload guard");
assertNotIncludes(searchBrowserHelpers, "type PayloadSource<Payload extends object>", "search/browser helper avoids a duplicate payload source type");
assertNotIncludes(searchBrowserHelpers, "function toPayloadSource<Payload extends object>", "search/browser helper avoids a duplicate payload source guard");
assertIncludes(searchBrowserHelpers, "browser?: Partial<BrowserState>;", "browser helper keeps normalized browser state at the helper boundary");
assertIncludes(searchBrowserHelpers, "type BrowserCloudBackendPayload = {", "browser helper names the dynamic cloud backend payload");
assertIncludes(searchBrowserHelpers, "const cloud = toPayloadSource<BrowserCloudBackendPayload>(state.browser?.cloud?.[backend]) || {};", "browser helper narrows cloud backend status to configured state");
assertIncludes(searchBrowserHelpers, "result.open?.error", "browser helper reads normalized browser test checks directly");
assertIncludes(searchBrowserHelpers, "export function browserDoctorChecks(value: BrowserOperationResult | null | undefined): BrowserResultCheck[]", "browser helper consumes normalized doctor results");
assertIncludes(searchBrowserHelpers, "checks.map(normalizeBrowserResultCheck)", "browser helper preserves defensive doctor check normalization");
assertNotIncludes(searchBrowserHelpers, "type JsonRecord", "search/browser helper avoids dynamic JsonRecord aliases");
assertNotIncludes(searchBrowserHelpers, "function toRecord", "search/browser helper avoids generic record conversion");
assertNotIncludes(searchBrowserHelpers, "export type BrowserOperationResult = JsonRecord & {", "browser helper no longer owns generic browser operation result records");
assertNotIncludes(searchBrowserHelpers, "export type BrowserResultCheck = JsonRecord & {", "browser helper no longer owns generic browser check records");
assertIncludes(settingsModal, "type SettingsModalCopy = {", "settings modal types copy boundary");
assertIncludes(settingsModal, "type SettingsPageClient =", "settings modal composes typed settings page clients");
assertNotIncludes(settingsModal, "type AnyRecord", "settings modal avoids dynamic AnyRecord alias");
assertNotIncludes(settingsModal, "Record<string, any>", "settings modal avoids broad dynamic records");
assertNotIncludes(settingsModal, "as any", "settings modal avoids untyped page client casts");
assertIncludes(logSettings, "type LogSettingsCopyView = {", "log settings types copy view");
assertIncludes(logSettings, "type LogSettingsStateView = {", "log settings types state view");
assertIncludes(logSettings, "client.saveLogSettings", "log settings keeps save action");
assertIncludes(logSettings, "form.retentionDays", "log settings keeps retention field");
assertIncludes(logSettings, "form.logSystemPrompt", "log settings keeps system prompt toggle");
assertIncludes(logSettings, "form.logSystemPromptLines", "log settings keeps system prompt line limit");
assertIncludes(logSettings, "form.logReasoningDetails", "log settings keeps reasoning detail toggle");
assertNotIncludes(logSettings, "type AnyRecord", "log settings avoids dynamic AnyRecord alias");
assertNotIncludes(logSettings, "Record<string, any>", "log settings avoids broad dynamic records");
assertIncludes(browserSettings, "type BrowserSettingsStateView = BrowserSettingsStateLike & {", "browser settings types state view");
assertIncludes(browserSettings, "const browserCopy: BrowserSettingsCopyView = copy.settings.browser ?? {};", "browser settings types copy view");
assertIncludes(browserSettings, "form.commandTimeout", "browser settings keeps command timeout");
assertIncludes(browserSettings, "form.sessionTimeout", "browser settings keeps session timeout");
assertIncludes(browserSettings, "form.allowPrivateUrls", "browser settings keeps private URL toggle");
assertIncludes(browserSettings, "client.runBrowserDoctor", "browser settings keeps doctor action");
assertIncludes(browserSettings, "client.runBrowserInstall", "browser settings keeps install action");
assertNotIncludes(browserSettings, "sessionTimeoutSeconds", "browser settings avoids stale session timeout field");
assertNotIncludes(browserSettings, "type AnyRecord", "browser settings avoids dynamic AnyRecord alias");
assertNotIncludes(browserSettings, "Record<string, any>", "browser settings avoids broad dynamic records");
assertNotIncludes(searchBrowserHelpers, "type AnyRecord", "search/browser helper avoids dynamic AnyRecord alias");
assertNotIncludes(searchBrowserHelpers, "Record<string, any>", "search/browser helper avoids broad dynamic records");
assertIncludes(shortcutSettings, "shortcut-keys", "shortcut settings uses parity layout");
assertIncludes(settingsPrimitives, "function SettingsCard", "settings pages use Ant card helper");
assertIncludes(generalSettings, "type GeneralSettingsCopyView = {", "general settings types copy view");
assertIncludes(generalSettings, "type GeneralSettingsCopy = {", "general settings uses a finite page copy envelope");
assertNotIncludes(generalSettings, "type JsonRecord", "general settings avoids dynamic JsonRecord aliases");
assertNotIncludes(generalSettings, "GeneralSettingsCopy = JsonRecord &", "general settings avoids open-ended page copy inheritance");
assertIncludes(generalSettings, "type GeneralSettingsStateView = {", "general settings types update state view");
assertIncludes(generalSettings, "import type { ConnectionState } from \"../composables/useChatClient\";", "general settings imports typed connection state");
assertIncludes(generalSettings, "import type { SettingsForm, UpdateStatusView } from \"../composables/useSettingsState\";", "general settings reuses typed update status view");
assertIncludes(generalSettings, "connectionState: ConnectionState;", "general settings reads typed connection state");
assertIncludes(generalSettings, "updateStatus: UpdateStatusView;", "general settings requires normalized update status");
assertIncludes(generalSettings, "const commitsBehind = updateStatus.commits_behind;", "general settings reads typed update commit count");
assertNotIncludes(generalSettings, "type UpdateStatusView = JsonRecord & {", "general settings avoids local raw update status view");
assertNotIncludes(generalSettings, "const updateStatus: UpdateStatusView = state.updateStatus || {};", "general settings avoids empty raw update status fallback");
assertIncludes(generalSettings, "normalizeChoice(value, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES)", "general settings normalizes language selections");
assertIncludes(generalSettings, "normalizeChoice(value, DEFAULT_COLOR_SCHEME, SUPPORTED_COLOR_SCHEMES)", "general settings normalizes color scheme selections");
assertIncludes(generalSettings, "<SettingsCard className=\"settings-card--form\"", "general settings form cards use Ant card helper");
assertIncludes(generalSettings, "<Select", "general settings uses Ant Select controls");
assertIncludes(generalSettings, "<Switch", "general settings uses Ant Switch controls");
assertNotIncludes(generalSettings, "type AnyRecord", "general settings avoids dynamic AnyRecord alias");
assertNotIncludes(generalSettings, "Record<string, any>", "general settings avoids broad dynamic records");
assertIncludes(generalSettings, "<Input", "general settings uses Ant Input controls");
assertNotIncludes(openSpriteShell, "<button", "app shell avoids raw button elements");
assertNotIncludes(openSpriteShell, "<input", "app shell avoids raw input elements");
assertNotIncludes(openSpriteShell, "<select", "app shell avoids raw select elements");
assertNotIncludes(openSpriteShell, "<textarea", "app shell avoids raw textarea elements");
assertIncludes(runInspector, "RunHistorySelector", "run inspector delegates run history selector");
assertIncludes(runInspector, "RunSummaryCard", "run inspector delegates run summary card");
assertIncludes(runInspector, "RunTimeline", "run inspector delegates run timeline");
assertIncludes(runInspector, "RunTraceViewer", "run inspector delegates run trace viewer");
assertIncludes(runInspector, "currentRunTimeline: ValueRef<RunTimelineEventView[]>;", "run inspector types timeline events");
assertIncludes(settingsModal, "SettingsNav", "settings modal uses the parity sidebar nav");
assertIncludes(settingsModal, "className=\"settings-nav__menu\"", "settings nav uses Ant menu");
assertIncludes(settingsModal, "selectedKeys={[section]}", "settings nav marks active section");
assertIncludes(settingsModal, "import { normalizeSettingsSectionId, type SettingsSectionId } from \"../composables/settingsSectionLoaders\";", "settings modal imports typed settings section ids");
assertIncludes(settingsModal, "settingsSection: { value: SettingsSectionId };", "settings modal reads typed section state");
assertIncludes(settingsModal, "selectSection(normalizeSettingsSectionId(key))", "settings nav normalizes menu keys before changing section");
assertIncludes(settingsModal, "renderSettingsSection", "settings modal renders only the active section");
assertIncludes(settingsModal, "settings-page--loading", "settings modal defers heavy section content");
assertIncludes(settingsModal, "<GeneralSettings client={client} clearWebSessions={clearWebSessions}", "settings modal wires general settings cleanup prop");
assertIncludes(settingsModal, "<ProviderSettings client={client}", "settings modal wires provider settings");
assertNotIncludes(settingsModal, "const contentBySection", "settings modal should not build a section map during render");
assertNotIncludes(settingsModal, "pageClient", "settings modal should route the typed client directly");
assertIncludes(shortcutSettings, "type ShortcutSettingsCopy = {", "shortcut settings types copy boundary");
assertNotIncludes(shortcutSettings, "type AnyRecord", "shortcut settings avoids dynamic AnyRecord alias");
assertNotIncludes(shortcutSettings, "Record<string, any>", "shortcut settings avoids broad dynamic records");
assertIncludes(styles, ".settings-page--loading", "settings deferred loading state is styled");
assertIncludes(styles, ".settings-nav__menu .ant-menu-item-selected", "settings nav selected state is styled through Ant");
assertRegex(runHistorySelector, /className=\"run-history__select\"[\s\S]+<Select[\s\S]+client\.selectRun\(value\)/, "run history selector changes active run");
assertIncludes(runSummaryCard, "className=\"run-summary-card\"", "run summary card keeps card class");
const runInspectorClassPattern = /(?:run-(?:history|summary-card|timeline|trace)|trace-sidebar)(?:__[a-z0-9-]+)?/g;
const runInspectorRuntimeClasses = new Set([
  ...(runHistorySelector.match(runInspectorClassPattern) || []),
  ...(runSummaryCard.match(runInspectorClassPattern) || []),
  ...(runTimeline.match(runInspectorClassPattern) || []),
  ...(runTraceViewer.match(runInspectorClassPattern) || []),
  ...(runInspector.match(runInspectorClassPattern) || []),
  ...(traceSidebar.match(runInspectorClassPattern) || []),
]);
const runInspectorStyleClasses = new Set(styles.match(runInspectorClassPattern) || []);
for (const className of runInspectorStyleClasses) {
  if (!runInspectorRuntimeClasses.has(className)) {
    throw new Error(`run inspector styles exclude orphaned selectors: ${className}`);
  }
}
for (const className of runInspectorRuntimeClasses) {
  if (!runInspectorStyleClasses.has(className)) {
    throw new Error(`run inspector runtime classes remain styled: ${className}`);
  }
}
assertIncludes(runSummaryCard, "const statusText = text(summary?.status, run.status);", "run summary card keeps typed status fallback");
assertIncludes(runSummaryCard, "copy.runSummary.durationSeconds(summary.durationSeconds)", "run summary card formats backend duration seconds");
assertIncludes(runSummaryCard, "<strong>{copy.runSummary.headline}</strong>", "run summary card uses a static main-run headline");
assertIncludes(runSummaryCard, "children: summary.toolCount,", "run summary card renders the normalized tool count");
assertIncludes(runSummaryCard, "run.summaryError", "run summary card keeps summary error state");
assertIncludes(runTimeline, "className=\"run-timeline\"", "run timeline keeps card class");
assertIncludes(runTimeline, "copy.timeline?.title || copy.runHistory.title", "run timeline keeps fallback title");
assertIncludes(runTimeline, "type RunTimelineCopy = {", "run timeline types copy boundary");
assertIncludes(runTimeline, "import type { RunTimelineEventView } from \"../composables/chatClientRunHelpers\";", "run timeline imports typed event view");
assertIncludes(runTimeline, "const tone = text(event.tone);", "run timeline centralizes event tone reads");
assertNotIncludes(runTimeline, "type AnyRecord", "run timeline avoids dynamic AnyRecord alias");
assertNotIncludes(runTimeline, "Record<string, any>", "run timeline avoids broad dynamic records");
assertIncludes(runTimeline, "Empty.PRESENTED_IMAGE_SIMPLE", "run timeline keeps empty state");
assertIncludes(runTraceViewer, "JSON.stringify({ run, exported_at", "trace viewer keeps debug JSON export");
assertIncludes(runTraceViewer, "URL.revokeObjectURL(url)", "trace viewer releases debug JSON URL");
assertIncludes(runTraceViewer, "events.slice(-120)", "trace viewer keeps event limit");
assertIncludes(runTraceViewer, "const events = run.rawEvents || [];", "trace viewer reads typed raw events");
assertIncludes(runTraceViewer, "import type { RunArtifactView, TraceEventView, TraceFileChangeView, TracePartView } from \"../composables/runTraceNormalizers\";", "trace viewer imports typed trace views");
assertIncludes(runTraceViewer, "renderItem={(artifact: RunArtifactView) => (", "trace viewer renders typed artifacts");
assertIncludes(runTraceViewer, "avatar={<Tag color={runStatusColor(artifact.status)}>{artifact.status || artifact.kind}</Tag>}", "trace viewer reads typed artifact status");
assertIncludes(runTraceViewer, "title={artifact.title || artifact.toolName || artifact.kind || artifact.artifactType}", "trace viewer reads typed artifact titles");
assertIncludes(runTraceViewer, "description={artifact.detail || artifact.path || artifact.diffPreview}", "trace viewer reads typed artifact descriptions");
assertNotIncludes(runTraceViewer, "renderItem={(artifact: RunJsonObject) => (", "trace viewer avoids generic artifact rendering");
assertNotIncludes(runTraceViewer, "import type { RunJsonObject, RunViewState }", "trace viewer avoids generic run JSON imports");
assertNotIncludes(runTraceViewer, "function fieldText(record: RunJsonObject", "trace viewer avoids dynamic run JSON field reads");
assertIncludes(runTraceViewer, "items={events.slice(-120).map((event: TraceEventView) => ({", "trace viewer renders typed raw events");
assertIncludes(runTraceViewer, "color: event.status === \"failed\" ? \"red\" : \"blue\",", "trace viewer reads typed event status");
assertIncludes(runTraceViewer, "key: event.id || event.eventType || \"event\",", "trace viewer keys typed raw events");
assertIncludes(runTraceViewer, "label: event.eventType || \"event\",", "trace viewer labels typed raw events");
assertIncludes(runTraceViewer, "children: <pre>{JSON.stringify(event.payload, null, 2)}</pre>,", "trace viewer renders typed event payloads");
assertNotIncludes(runTraceViewer, "events.slice(-120).map((event: RunJsonObject", "trace viewer avoids generic raw event rendering");
assertNotIncludes(runTraceViewer, "run.rawEvents || run.events || []", "trace viewer avoids mixing raw events with timeline events");
assertIncludes(runTraceViewer, "revertFileChange(run, change)", "trace viewer keeps file revert action");
assertIncludes(runTraceViewer, "copy.runFileInspector?.revertAction || \"Revert\"", "trace viewer uses the localized file revert label");
assertIncludes(runTraceViewer, "cancelRun(run)", "trace viewer keeps cancel action");
assertIncludes(runTraceViewer, "defaultActiveKey={[\"artifacts\"]}", "trace viewer keeps default section");
assertIncludes(runTraceViewer, "run: RunViewState;", "trace viewer accepts typed run view state");
assertIncludes(runTraceViewer, "revertFileChange: (run: RunViewState, change: TraceFileChangeView) => void;", "trace viewer types file revert action");
assertIncludes(runTraceViewer, "items={parts.map((part: TracePartView, index: number) => ({", "trace viewer renders typed trace parts");
assertIncludes(runTraceViewer, "key: part.partId || String(index),", "trace viewer keys typed trace parts");
assertIncludes(runTraceViewer, "label: part.partType || `${copy.trace.parts} ${index + 1}`", "trace viewer labels typed trace parts");
assertIncludes(runTraceViewer, "children: <pre>{part.content || JSON.stringify(part, null, 2)}</pre>", "trace viewer reads typed trace part content");
assertNotIncludes(runTraceViewer, "parts.map((part: RunJsonObject", "trace viewer avoids generic trace part rendering");
assertIncludes(runTraceViewer, "renderItem={(change: TraceFileChangeView) => (", "trace viewer renders typed file changes");
assertIncludes(runTraceViewer, "Boolean(change.revertSupported)", "trace viewer reads typed revert support");
assertIncludes(runTraceViewer, "title={change.path || change.label} description={change.status || change.kind}", "trace viewer reads typed file change labels");
assertNotIncludes(runTraceViewer, "revertFileChange: (run: RunViewState, change: RunJsonObject) => void;", "trace viewer avoids generic file revert input");
assertIncludes(runTraceViewer, "type RunTraceCopy = {", "trace viewer types copy boundary");
assertNotIncludes(runTraceViewer, "type AnyRecord", "trace viewer avoids dynamic AnyRecord alias");
assertNotIncludes(runTraceViewer, "Record<string, any>", "trace viewer avoids broad dynamic records");
assertIncludes(runInspector, "currentRun: ValueRef<RunViewState | null>;", "run inspector client exposes typed current run");
assertIncludes(runInspector, "import type { RunTimelineEventView, RunViewState } from \"../composables/chatClientRunHelpers\";", "run inspector imports typed timeline event view");
assertIncludes(runInspector, "import type { TraceFileChangeView } from \"../composables/runTraceNormalizers\";", "run inspector imports typed trace file change view");
assertIncludes(runInspector, "export type RunInspectorStateView = {", "run inspector names its required state view");
assertIncludes(runInspector, "showRunHistory: boolean;\n  showRunSummary: boolean;\n  showRunTimeline: boolean;\n  showRunTrace: boolean;", "run inspector state view contains only consumed visibility flags");
assertIncludes(runHistorySelector, "client.state.showRunHistory", "run history selector consumes the typed run history visibility flag");
assertIncludes(runInspector, "state: RunInspectorStateView;", "run inspector client uses the typed state view");
assertNotIncludes(runInspector, "type UiRecord", "run inspector avoids a dynamic UI state record");
assertNotIncludes(runInspector, "state: Record<string, unknown>", "run inspector avoids inline dynamic state records");
assertIncludes(runInspector, "revertRunFileChange: (run: RunViewState, change: TraceFileChangeView) => void;", "run inspector client types file revert action");
assertNotIncludes(runInspector, "revertRunFileChange: (run: RunViewState, change: RunJsonObject) => void;", "run inspector avoids generic file revert input");
assertIncludes(runInspector, "export type RunInspectorCopy = RunSummaryCopy &", "run inspector types shared copy boundary");
assertNotIncludes(runInspector, "Record<string, any>", "run inspector avoids broad dynamic records");
assertIncludes(displayCopy, "stopped: \"已停止\"", "Traditional Chinese copy labels stopped runs");
assertIncludes(displayCopy, "stopped: \"Stopped\"", "English copy labels stopped runs");
assertIncludes(runHistorySelector, "run: RunViewState | null;", "run history selector accepts typed selected run");
assertIncludes(runHistorySelector, "runs: RunViewState[];", "run history selector accepts typed run list");
assertIncludes(runSummaryCard, "run: RunViewState;", "run summary card accepts typed run view state");
assertIncludes(runSummaryCard, "type RunSummaryCopy = {", "run summary card types copy boundary");
assertNotIncludes(runSummaryCard, "type RunSummary =", "run summary card excludes the unused summary helper type");
assertNotIncludes(runSummaryCard, "fieldText(summary,", "run summary card avoids dynamic summary field reads");
assertNotIncludes(runSummaryCard, "RunJsonObject, RunViewState", "run summary card avoids generic run JSON summary import");
assertNotIncludes(runSummaryCard, "type AnyRecord", "run summary card avoids dynamic AnyRecord alias");
assertNotIncludes(runSummaryCard, "Record<string, any>", "run summary card avoids broad dynamic records");
assertIncludes(runTimeline, "events: RunTimelineEventView[]", "run timeline accepts typed run timeline event records");
assertNotIncludes(openSpriteShell, "BackgroundProcessSidebar", "background process sidebar stays removed");
assertNotIncludes(openSpriteShell, "CuratorSettingsPage", "curator settings page stays removed");

for (const exportName of ["ref", "reactive", "computed", "watch", "onMounted", "onBeforeUnmount", "useReactiveStore"]) {
  assertRegex(reactiveCompat, new RegExp(`export function ${exportName}\\b`), `reactive compat export ${exportName}`);
}

assertIncludes(chatClient, "../lib/reactiveCompat", "chat client uses React-compatible reactivity bridge");
assertNotIncludes(chatClient, "from \"vue\"", "chat client no longer imports Vue runtime");
assertIncludes(chatClient, "let messageInput: HTMLTextAreaElement | null = null;", "message input DOM handle stays private and typed");
assertIncludes(chatClient, "let messageStage: HTMLElement | null = null;", "message stage DOM handle stays private and typed");
assertIncludes(chatClient, "let messageStagePinnedToBottom = true;", "message stage pin state stays private and render-silent");
assertNotIncludes(chatClient, "silentRef", "chat client avoids a compatibility helper for private mutable cells");
assertNotIncludes(reactiveCompat, "export function silentRef", "reactive compat avoids an app-specific silent cell API");
assertIncludes(chatClient, "function runAfterCurrentMicrotask(callback: () => void): void", "chat client keeps private microtask scheduling local");
assertIncludes(chatClient, "void Promise.resolve().then(callback);", "chat client preserves microtask callback timing");
assertNotIncludes(chatClient, "nextTick", "chat client avoids an app-specific compatibility scheduling API");
assertNotIncludes(reactiveCompat, "export function nextTick", "reactive compat only exposes store reactivity and lifecycle APIs");
assertIncludes(chatClient, "let activeSocket: WebSocket | null = null;", "chat client stores typed websocket handle");
assertIncludes(chatClient, "let gatewayReconnectTimer: number | null = null;", "chat client stores typed gateway reconnect timer");
assertIncludes(chatClient, "let sessionHistoryRefreshTimer: number | null = null;", "chat client stores typed session history timer");
assertIncludes(chatClient, "let boundMessageStage: HTMLElement | null = null;", "chat client stores typed message stage listener target");
assertIncludes(chatClient, "const runSummaryTimers = new Map<string, number>();", "chat client tracks typed run summary timers");
assertIncludes(chatClient, "const runBackfillTimes = new Map<string, number>();", "chat client tracks typed run backfill timestamps");
assertIncludes(chatClient, "const runSummaryRequestGenerations = new WeakMap<RunViewState, number>();", "chat client tracks per-run summary request generations");
assertIncludes(chatClient, "const runTraceRequestGenerations = new WeakMap<RunViewState, number>();", "chat client tracks per-run trace request generations");
assertIncludes(chatClient, "snapshotFence: snapshotFenceForSession(existing)", "chat history merges reuse a persistent per-session freshness fence");
assertIncludes(chatClient, "fileChangesRepresentSameOccurrence(change, preview)", "live file changes use the shared durable/live occurrence identity");
assertNotIncludes(chatClient, "return String(change.path || \"\").trim() === normalizedPath", "live file changes no longer collapse every change with the same path and action");
assertIncludes(chatClient, "while (request) {\n        await performSessionHistoryRefresh(request);", "history refresh drains a pending rerun after the active request");
assertIncludes(chatClient, "includeHiddenSessions: showHiddenSessions.value", "history refresh snapshots the latest include_cli choice when queued");
assertIncludes(chatClient, "pruneMissingHistorySessions: request.pruneMissingHistorySessions", "history refresh applies the coalesced prune request");
assertIncludes(chatClient, "const deletedSessionTombstones = new Map<string, number>();", "chat client tracks typed deleted-session tombstone timers");
assertIncludes(chatClient, "function applyDocumentPreferences(): void", "chat client types document preference side effects");
assertIncludes(chatClient, "function addColorSchemeListener(): void", "chat client types color scheme listener setup");
assertIncludes(chatClient, "function removeColorSchemeListener(): void", "chat client types color scheme listener teardown");
assertIncludes(chatClient, "function setMessageInputRef(element: HTMLTextAreaElement | null): void", "chat client types message input ref setter");
assertIncludes(chatClient, "function handleMessageStageScroll(event: Event): void", "chat client types message stage scroll events");
assertIncludes(chatClient, "function setMessageStageRef(element: HTMLElement | null): void", "chat client types message stage ref setter");
assertIncludes(chatClient, "function setMessageText(value: string): void", "chat client types composer text setter");
assertIncludes(chatClient, "event.currentTarget instanceof HTMLElement", "chat client narrows scroll event target before DOM reads");
assertIncludes(chatClient, "function saveRunPanelVisibilitySettings(\n    showRunHistory: boolean,\n    showRunTimeline: boolean,\n    showRunSummary: boolean,\n    showRunTrace: boolean,\n  ): void", "chat client types run panel visibility persistence");
assertIncludes(chatClient, "type RunTimelineEventView,", "chat client imports typed run timeline event view");
assertIncludes(chatClient, "type RunTimelineTone,", "chat client imports typed run timeline tone");
assertIncludes(chatClient, "type RunEventDescription = { label: string; detail: string; tone: RunTimelineTone };", "chat client types run event descriptions with timeline tone");
assertIncludes(chatClient, "const TERMINAL_PART_STATES = [\"completed\", \"failed\", \"cancelled\", \"error\"] as const;", "chat client keeps terminal part states as a typed array");
assertIncludes(chatClient, "type TerminalPartState = (typeof TERMINAL_PART_STATES)[number];", "chat client derives terminal part state union");
assertIncludes(chatClient, "const TERMINAL_PART_STATE_SET: ReadonlySet<string> = new Set<string>(TERMINAL_PART_STATES);", "chat client validates terminal part states through a readonly set");
assertIncludes(chatClient, "function isTerminalPartState(state: string): state is TerminalPartState", "chat client narrows terminal part states with a type guard");
assertIncludes(chatClient, "!isTerminalPartState(artifactStatus)", "chat client uses typed terminal part state guard for tool artifacts");
assertIncludes(chatClient, "streaming: !isTerminalPartState(state)", "chat client uses typed terminal part state guard for streaming metadata");
assertNotIncludes(chatClient, "const TERMINAL_PART_STATES = new Set([", "chat client avoids untyped terminal part state sets");
assertIncludes(chatClient, "const TIMELINE_EVENT_TYPES = [", "chat client keeps timeline event allow-list as a typed array");
assertIncludes(chatClient, "type TimelineEventType = (typeof TIMELINE_EVENT_TYPES)[number];", "chat client derives timeline event type union");
assertIncludes(chatClient, "const TIMELINE_EVENT_TYPE_SET: ReadonlySet<string> = new Set<string>(TIMELINE_EVENT_TYPES);", "chat client validates timeline event types through a readonly set");
assertIncludes(chatClient, "function isTimelineEventType(eventType: string): eventType is TimelineEventType", "chat client narrows timeline event types with a named type guard");
assertIncludes(chatClient, "function normalizeTimelineEventType(eventType: string): TimelineEventType | null", "chat client normalizes timeline event types at the UI boundary");
assertIncludes(chatClient, "return isTimelineEventType(eventType) ? eventType : null;", "chat client normalizes timeline event types without assertion");
assertNotIncludes(chatClient, "eventType as TimelineEventType", "chat client avoids asserting timeline event types after validation");
assertIncludes(chatClient, "if (!normalizeTimelineEventType(eventType)) {", "chat client filters timeline events through typed normalizer");
assertNotIncludes(chatClient, "const TIMELINE_EVENT_TYPES = new Set([", "chat client avoids untyped timeline event sets");
assertIncludes(chatClient, "type CurrentRunSummaryView = {", "chat client types current run summary view");
assertIncludes(chatClient, "tone: RunTimelineTone;", "chat client current run summary tone is typed");
assertNotIncludes(chatClient, "function runEventDetail", "chat client avoids duplicating scalar text coercion for run events");
assertIncludes(chatClient, "tone: runTone(run.status, latestEvent.tone),", "chat client keeps current run summary tone typed");
assertIncludes(chatClient, "run.status = mergeMonotonicRunStatus(run.status, nextStatus || \"running\");", "chat client applies the executable monotonic status merge to live events");
assertIncludes(chatClient, "const incomingIsCurrent = incomingUpdatedAt >= existingUpdatedAt;", "run history only applies status snapshots that are at least as current as live state");
assertIncludes(chatClient, "existing.status = mergeMonotonicRunStatus(existing.status, run.status);", "run history applies the same executable monotonic status merge");
assertIncludes(chatClient, "isRunSummaryTriggerEventType,", "chat client imports typed summary trigger event guard");
assertIncludes(chatClient, "isTerminalRunStatus(run.status) || isRunSummaryTriggerEventType(liveEvent.eventType)", "chat client schedules run summaries through typed summary trigger guard");
assertNotIncludes(chatClient, "[\"completed\", \"failed\", \"cancelled\"].includes(run.status)", "chat client avoids hard-coded terminal run status arrays");
assertNotIncludes(chatClient, "eventType === \"run_finished\" || eventType === \"run_failed\"", "chat client avoids hard-coded summary trigger event checks");
assertIncludes(chatClient, "if (eventType === \"execution.stopped\")", "chat client renders explicit execution-stopped events");
assertIncludes(chatClient, "if (eventDetail.status === \"stopped\")", "chat client does not render stopped run-finished events as success");
assertIncludes(chatClient, "if (eventDetail.status === \"failed\")", "chat client does not render failed run-finished events as success");
assertIncludes(chatClient, "if (eventDetail.status === \"cancelled\")", "chat client does not render cancelled run-finished events as success");
assertIncludes(chatClient, "function normalizeLocalizedRawRunEvent(event: TraceEventView): RunTimelineEventView | null", "chat client normalizes raw run events before timeline localization");
assertIncludes(chatClient, "function localizeRawRunEvents(rawEvents: TraceEventView[]): RunTimelineEventView[]", "chat client localizes typed run timeline events");
assertIncludes(chatClient, ".map(normalizeLocalizedRawRunEvent)", "chat client maps raw run events through localized event normalizer");
assertIncludes(chatClient, ".filter((event): event is RunTimelineEventView => Boolean(event))", "chat client filters localized run events with typed predicate");
assertIncludes(chatClient, "function clearAllRunSummaryTimers(): void", "chat client types summary timer clearing");
assertIncludes(chatClient, "function saveDisplaySettings(language: LanguagePreference, colorScheme: ColorSchemePreference): void", "chat client types display settings persistence");
assertIncludes(chatClient, "() => [settingsForm.language, settingsForm.colorScheme] as const", "chat client watches display preferences as a typed tuple");
assertIncludes(chatClient, "function rebuildLocalizedRunEvents(): void", "chat client types localized run event rebuild side effect");
assertIncludes(chatClient, "run.events = (run.rawEvents || [])\n          .map(normalizeLocalizedRawRunEvent)", "chat client rebuilds localized run events through shared normalizer");
assertNotIncludes(chatClient, ".map((event): RunTimelineEventView | null => {", "chat client avoids inline raw run event localization maps");
assertIncludes(chatClient, "function sortSessions(): void", "chat client types session sorting side effect");
assertIncludes(chatClient, "function persistLocalDraftSessions(): void", "chat client types local draft persistence side effect");
assertIncludes(chatClient, "function setNotice(text: string, tone: NoticeTone): void", "chat client types notice state updates");
assertIncludes(chatClient, "function showToast(text: unknown, tone: NoticeTone = \"info\"): void", "chat client types toast display helper");
assertIncludes(chatClient, "function dismissToast(id: string): void", "chat client types toast dismissal");
assertIncludes(chatClient, "function isNonEmptyString(value: string | null | undefined): value is string", "chat client narrows actual nullable session id inputs to strings");
assertIncludes(chatClient, "async function deleteSessions(sessions: ChatSession[]): Promise<void>", "chat client bulk delete accepts typed chat sessions");
assertIncludes(chatClient, "if (settingsErrorStatus(error) === 404)", "chat client narrows delete session missing errors by status");
assertIncludes(chatClient, "lastError = settingsErrorMessage(error, copy.value.notices.sessionDeleteFailed);", "chat client narrows delete session errors");
assertIncludes(chatClient, "type SessionChannelFilter,", "chat client imports typed sidebar session filter values");
assertIncludes(chatClient, "const sessionChannelFilter = ref<SessionChannelFilter>(\"all\");", "chat client stores typed sidebar session filter");
assertIncludes(chatClient, "function getSessionDisplayId(session: ChatSession | null | undefined): string", "chat client types session display id helper");
assertIncludes(chatClient, "function getSessionOwnerId(session: ChatSession | null | undefined): string", "chat client types session owner id helper");
assertIncludes(chatClient, "function ensureSession(externalChatId: string | null | undefined, sessionId = \"\", options: EnsureSessionOptions = {}): ChatSession | null", "chat client types session creation helper result");
assertIncludes(chatClient, "function setActiveSession(externalChatId: string): void", "chat client types active session setter");
assertIncludes(chatClient, "function setSessionChannelFilter(value: SessionChannelFilter): void", "chat client types session channel filter setter");
assertIncludes(chatClient, "sessionChannelFilter.value = normalizeSessionChannelFilter(value);", "chat client normalizes session channel filters");
assertIncludes(chatClient, "function ensureActiveSessionVisibleInSidebar(): void", "chat client types active sidebar session repair");
assertIncludes(chatClient, "async function setShowHiddenSessions(value: boolean): Promise<void>", "chat client types hidden session toggle action");
assertIncludes(chatClient, "function selectRun(runId: string | null | undefined): void", "chat client types active run selection");
assertIncludes(chatClient, "function persistActiveSession(): void", "chat client types active session persistence");
assertIncludes(chatClient, "const settingsSection = ref<SettingsSectionId>(\"general\");", "chat client stores typed settings section id");
assertIncludes(chatClient, "function normalizeSettingsSection(sectionName: unknown): SettingsSectionId", "chat client normalizes settings sections at the boundary");
assertIncludes(chatClient, "function deferSettingsWork(callback: () => void): void", "chat client types deferred settings callbacks");
assertIncludes(chatClient, "function selectSettingsSection(sectionName: SettingsSectionId): void", "chat client types settings section selection");
assertIncludes(chatClient, "function syncSettingsForm(): void", "chat client types settings form sync");
assertIncludes(chatClient, "function openSettings(sectionName: SettingsSectionId = \"general\"): void", "chat client types settings opener section");
assertIncludes(chatClient, "function closeSettings(): void", "chat client types settings closer side effect");
assertIncludes(chatClient, "function openSidebar(): void", "chat client types sidebar opener");
assertIncludes(chatClient, "function closeSidebar(): void", "chat client types sidebar closer");
assertIncludes(chatClient, "function toggleSidebar(): void", "chat client types sidebar toggle");
assertIncludes(chatClient, "function toggleSidebarCollapsed(): void", "chat client types sidebar collapsed toggle");
assertIncludes(chatClient, "function toggleTraceInspectorCollapsed(): void", "chat client types trace inspector collapsed toggle");
assertIncludes(chatClient, "function removeSessionsFromState(\n    predicate: (session: ChatSession) => boolean,\n    { preferWeb = false }: { preferWeb?: boolean } = {},\n  ): number", "chat client types removed session count");
assertIncludes(chatClient, "function clearSessionRunTimers(session: ChatSession | null | undefined): void", "chat client types session run timer cleanup");
assertIncludes(chatClient, "async function deleteSession(session: ChatSession | null | undefined): Promise<void>", "chat client types single session delete action");
assertIncludes(chatClient, "type DisplayCopy = ReturnType<typeof getDisplayCopy>;", "chat client derives display copy boundary from copy module");
assertIncludes(chatClient, "type RunEventDescription = { label: string; detail: string; tone: RunTimelineTone };", "chat client types localized run event descriptions");
assertIncludes(chatClient, "function buildRunCancelUrl(wsUrl: string, runId: string, sessionId: string): string", "chat client types run cancel URL helper");
assertIncludes(chatClient, "function getActiveRun(session: ChatSession | null | undefined): RunViewState | null", "chat client types active run lookup");
assertIncludes(chatClient, "function shouldLoadRunSummary({ showRunSummary }: { showRunSummary: boolean }, run: RunViewState | null | undefined): boolean", "chat client types run summary load predicate");
assertIncludes(chatClient, "function shouldLoadRunTrace(run: RunViewState | null | undefined): boolean", "chat client types run trace load predicate");
assertIncludes(chatClient, "function runSummaryTimerKey(sessionId: string, runId: string): string", "chat client types run summary timer keys");
assertIncludes(chatClient, "function clearRunSummaryTimer(sessionId: string, runId: string): void", "chat client types run summary timer clearing");
assertIncludes(chatClient, "function maybeLoadRunSummaryForSession(session: ChatSession | null | undefined): void", "chat client types summary load entrypoint side effect");
assertIncludes(chatClient, "function maybeLoadRunTraceForSession(session: ChatSession | null | undefined): void", "chat client types trace load entrypoint side effect");
assertIncludes(chatClient, "const summaryHasFileChanges = Boolean(run.summary?.fileChangeCount);", "chat client reads the normalized summary file-change count");
assertIncludes(chatClient, "const hasNeededFileChanges = (run.fileChanges || []).length > 0 || !summaryHasFileChanges;", "chat client uses the summary count only to decide whether trace details are needed");
assertIncludes(chatClientEventPayloads, "export type RunEventPayloadInput = {", "event payload adapter owns the run event input boundary");
assertIncludes(chatClient, "type RunEventPayloadView = {", "chat client gives core run event payloads a typed view");
assertIncludes(chatClientEventPayloads, "export function toRunEventPayloadInput(value: unknown): RunEventPayloadInput", "event payload adapter narrows run event timeline inputs");
assertIncludes(chatClient, "function describeRunEvent(eventType: string, payload: RunTimelinePayload, copy: DisplayCopy): RunEventDescription | null", "chat client describes only finite normalized timeline payloads");
assertIncludes(chatClient, "function normalizeRunEventPayload(payload: RunEventPayloadInput): RunEventPayloadView", "chat client normalizes core run event payloads before timeline formatting");
assertNotIncludes(chatClientEventPayloads, "type RunEventPayloadInput = {\n  [key: string]: unknown;", "event payload adapter avoids open-ended run event input indexes");
assertNotIncludes(chatClient, "function describeRunEvent(eventType: string, payload: RunJsonObject, copy: DisplayCopy): RunEventDescription | null", "chat client avoids generic run event description payloads");
assertNotIncludes(chatClient, "function normalizeRunEventPayload(payload: RunJsonObject): RunEventPayloadView", "chat client avoids generic run event payload normalization inputs");
assertIncludes(chatClient, "const eventDetail = normalizeRunEventPayload(payload);", "chat client describes run events from normalized payload view state");
assertIncludes(chatClient, "if (eventDetail.toolName === \"verify\")", "chat client filters verify tool events from normalized payload view state");
assertIncludes(chatClient, "label: eventDetail.verificationOk ? copy.run.verificationPassed : copy.run.verificationFailed", "chat client derives verification labels from normalized payload view state");
assertIncludes(chatClient, "label: eventDetail.backgroundSucceeded", "chat client derives background process status from normalized payload view state");
assertIncludes(chatClient, "label: eventDetail.hadToolError ? copy.run.completedWithWarnings : copy.run.completed", "chat client derives run finished warning labels from normalized payload view state");
assertIncludes(chatClient, "normalizeSubagentDetail,", "chat client imports normalized subagent detail helper");
assertIncludes(chatClient, "normalizeWorkflowDetail,", "chat client imports normalized workflow detail helper");
assertNotIncludes(chatClient, "normalizeRunLifecycleEventPayload,", "chat client does not own lifecycle payload projection");
assertIncludes(chatClient, "normalizeRunFinishDetail,", "chat client imports normalized run finish detail helper");
assertIncludes(chatClient, "const lifecyclePayload = payload;", "chat client reuses the already-projected timeline lifecycle fields for detail formatting");
assertIncludes(chatClient, "const detail = normalizeSubagentDetail(lifecyclePayload);", "chat client normalizes subagent payloads before detail formatting");
assertIncludes(chatClient, "const detail = normalizeWorkflowDetail(lifecyclePayload);", "chat client normalizes workflow payloads before detail formatting");
assertIncludes(chatClient, "const detail = normalizeRunFinishDetail(lifecyclePayload);", "chat client normalizes run finish payloads before detail formatting");
assertNotIncludes(chatClient, "const detail = normalizeSubagentDetail(payload);", "chat client avoids broad run event payloads in subagent detail normalization");
assertNotIncludes(chatClient, "const detail = normalizeWorkflowDetail(payload);", "chat client avoids broad run event payloads in workflow detail normalization");
assertNotIncludes(chatClient, "const detail = normalizeRunFinishDetail(payload);", "chat client avoids broad run event payloads in run finish detail normalization");
assertNotIncludes(chatClient, "formatSubagentGroupDetail(payload)", "chat client avoids raw subagent group payload formatting");
assertNotIncludes(chatClient, "formatSubagentDetail(payload)", "chat client avoids raw subagent payload formatting");
assertNotIncludes(chatClient, "formatWorkflowDetail(payload)", "chat client avoids raw workflow payload formatting");
assertNotIncludes(chatClient, "formatWorkflowStepDetail(payload)", "chat client avoids raw workflow step payload formatting");
assertNotIncludes(chatClient, "formatRunFinishDetail(payload, copy)", "chat client avoids raw run finish payload formatting");
assertNotIncludes(chatClient, "const message = String(payload.message || copy.run.thinking);", "chat client avoids raw llm status message reads inside event formatter");
assertNotIncludes(chatClient, "if (payload.tool_name === \"verify\")", "chat client avoids raw tool name checks inside event formatter");
assertNotIncludes(chatClient, "const ok = payload.ok !== false;", "chat client avoids raw verification result checks inside event formatter");
assertNotIncludes(chatClient, "const exitCode = payload.exit_code ?? payload.exitCode;", "chat client avoids raw background exit code reads inside event formatter");
assertNotIncludes(chatClient, "label: payload.had_tool_error ? copy.run.completedWithWarnings : copy.run.completed,", "chat client avoids raw run finished warning labels inside event formatter");
assertNotIncludes(chatClient, "const cancelled = payload.status === \"cancelled\";", "chat client avoids raw run failed status checks inside event formatter");
assertIncludes(chatClient, "tone: runTone(run.status, latestEvent.tone),", "chat client narrows timeline event tone before status styling");
assertIncludes(chatClient, "const eventPayload = normalizeRunTimelinePayload(event.payload);", "chat client narrows raw run event payloads through the timeline payload boundary");
assertIncludes(chatClient, "describeRunEvent(eventType, eventPayload, copy.value)", "chat client passes already-normalized timeline payloads into event descriptions");
assertNotIncludes(chatClient, "describeRunEvent(eventType, event.payload, copy.value)", "chat client avoids passing raw trace payloads directly into event descriptions");
assertNotIncludes(chatClient, "const eventPayload = toJsonRecord(event.payload) || {};", "chat client avoids inline raw run event payload records");
assertIncludes(chatClient, "function formatReconnectNotice(notice: ReconnectNotice, delayMs: number): string", "chat client types reconnect notice formatter");
assertIncludes(chatClient, "function addMessage(externalChatId: string, message: ChatMessage): ChatSession | null", "chat client types message mutation helper");
assertIncludes(chatClient, "const role = normalizeChatMessageRole(payload.role);", "chat client normalizes history message roles");
assertIncludes(chatClient, "function findOrCreateRun(session: ChatSession, runId: string, createdAt: number): RunViewState", "chat client types run lookup and creation helper");
assertIncludes(chatClient, "function upsertRunArtifact(run: RunViewState, artifact: unknown): RunArtifactView | null", "chat client treats run artifact input as typed normalized artifact boundary");
assertIncludes(chatClient, "const artifacts: RunArtifactView[] = run.artifacts || [];", "chat client keeps run artifacts list typed");
assertIncludes(chatClient, "function applyToolArtifactToParts(run: RunViewState, artifact: RunArtifactView | null | undefined): void", "chat client types tool artifact part mutation");
assertIncludes(chatClient, "const partArtifact = part.artifact;", "chat client reads typed part artifacts before field reads");
assertIncludes(chatClient, "const artifactMetadata: RunArtifactMetadata = normalizeRunArtifactMetadata(artifact.metadata);", "chat client narrows artifact metadata through the run artifact boundary");
assertIncludes(chatClient, "const metadata = normalizeTracePartMetadata(part.metadata);", "chat client narrows existing tool part metadata through the trace part boundary");
assertIncludes(chatClient, "const nextMetadata: TracePartMetadata = { ...metadata, state: artifactStatus };", "chat client keeps tool artifact metadata merge behind the trace part metadata boundary");
assertNotIncludes(chatClient, "type RunJsonObject,", "chat client does not import generic run JSON into useChatClient");
assertNotIncludes(chatClient, "const nextMetadata: RunJsonObject", "chat client avoids generic run JSON metadata merges");
assertIncludes(chatClient, "function applyRunEventArtifact(run: RunViewState, artifact: unknown): void", "chat client treats event artifact input as unknown boundary");
assertIncludes(chatClient, "const normalizedSourceId = String(normalized.sourceId || \"\").trim();", "chat client narrows file artifact source ids before matching");
assertIncludes(chatClient, "const previewChangeId = normalized.sourceId || normalized.artifactId;", "chat client normalizes live file preview change ids");
assertIncludes(chatClient, "const previewStatus = normalized.status || \"completed\";", "chat client normalizes live file preview status");
assertIncludes(chatClient, "const preview: TraceFileChangeView = {", "chat client types file artifact preview records");
assertIncludes(chatClient, "sourceId: normalized.sourceId || previewChangeId,", "chat client types live file preview source ids");
assertIncludes(chatClient, "revertSupported: false,", "chat client disables live preview revert until trace load");
assertIncludes(chatClient, "type RunPartDeltaView = {", "chat client keeps normalized streaming run part delta boundary");
assertIncludes(chatClient, "existing: TracePartView | null;", "chat client types existing streaming run part state");
assertIncludes(chatClient, "kind: RunEventKind;\n  toolName: string;\n  metadata: TracePartMetadata;\n  createdAt: number;", "chat client routes streaming run part delta metadata through trace part metadata");
assertIncludes(chatClientEventPayloads, "export type RunPartDeltaPayload = {", "event payload adapter owns the streaming run part boundary");
assertNotIncludes(chatClientEventPayloads, "type RunPartDeltaPayload = {\n  [key: string]: unknown;", "event payload adapter avoids open-ended streaming run part indexes");
assertNotIncludes(chatClientEventPayloads, "type RunPartDeltaPayload = TraceEventPayload & {", "event payload adapter avoids routing streaming parts through trace records");
assertNotIncludes(chatClientEventPayloads, "type RunPartDeltaPayload = JsonRecord & {", "event payload adapter avoids generic JSON streaming part records");
assertIncludes(chatClientEventPayloads, "export function toRunPartDeltaPayload(value: unknown): RunPartDeltaPayload", "event payload adapter narrows streaming run part payloads");
assertIncludes(chatClient, "function applyRunPartDelta(run: RunViewState, payload: RunPartDeltaPayload, createdAt: number): void", "chat client types streaming run part deltas");
assertIncludes(chatClient, "function normalizeRunPartDelta(run: RunViewState, payload: RunPartDeltaPayload, createdAt: number): RunPartDeltaView", "chat client normalizes streaming run part deltas before applying them");
assertNotIncludes(chatClient, "function applyRunPartDelta(run: RunViewState, payload: RunJsonObject, createdAt: number): void", "chat client avoids generic streaming run part delta inputs");
assertNotIncludes(chatClient, "function normalizeRunPartDelta(run: RunViewState, payload: RunJsonObject, createdAt: number): RunPartDeltaView", "chat client avoids generic streaming run part delta normalizer inputs");
assertIncludes(chatClient, "const partDelta = normalizeRunPartDelta(run, payload, createdAt);", "chat client applies streaming run part deltas from normalized view state");
assertIncludes(chatClient, "content: `${partDelta.existing?.content || \"\"}${partDelta.delta}`", "chat client builds streaming part content from normalized delta state");
assertNotIncludes(chatClient, "const nextState = String(payload.state || payload.status || existing?.state || \"running\").trim() || \"running\";", "chat client avoids raw streaming part state reads inside the applier");
assertIncludes(chatClient, "const metadata = normalizeTracePartMetadata(payload.metadata);", "chat client normalizes streaming part metadata through the trace part boundary");
assertIncludes(chatClient, "const existingMetadata = normalizeTracePartMetadata(existing?.metadata);", "chat client normalizes existing part metadata through the trace part boundary");
assertIncludes(chatClient, "const existingCreatedAt = Number(existing?.createdAt);", "chat client narrows existing streaming part timestamps before reuse");
assertIncludes(chatClient, "kind: normalizeRunKind(payload.kind || existing?.kind, \"text\"),", "chat client narrows streaming part kind before applying deltas");
assertIncludes(chatClient, "toolName: textField(payload.tool_name || payload.toolName || existing?.toolName),", "chat client narrows streaming part tool name before applying deltas");
assertIncludes(chatClient, "createdAt: Number.isFinite(existingCreatedAt) && existingCreatedAt > 0 ? existingCreatedAt : createdAt,", "chat client stores typed streaming part timestamps");
assertNotIncludes(chatClient, "kind: unknown;\n  toolName: unknown;", "chat client avoids unknown streaming part delta kind/tool names");
assertNotIncludes(chatClient, "createdAt: unknown;", "chat client avoids unknown streaming part delta timestamps");
assertIncludes(chatClient, "function normalizeLocalizedRawRunEvent(event: TraceEventView): RunTimelineEventView | null", "chat client normalizes single raw run events before localization");
assertIncludes(chatClient, "function localizeRawRunEvents(rawEvents: TraceEventView[]): RunTimelineEventView[]", "chat client types raw run event localization");
assertIncludes(chatClient, ".map(normalizeLocalizedRawRunEvent)", "chat client keeps localized run event map delegated to typed helper");
assertNotIncludes(chatClient, "SettingsApiError", "chat client avoids asserting settings API error shapes");
assertIncludes(chatClient, "./chatClientApiPayloads", "chat client imports the dedicated API payload boundary");
assertIncludes(chatClientApiPayloads, "export type SettingsErrorPayload = {", "API payload adapter types settings error response fields");
assertNotIncludes(chatClient, "type SettingsErrorPayload = {", "chat client delegates settings error payload ownership to the adapter");
assertNotIncludes(chatClientApiPayloads, "type SettingsErrorApiPayload = {", "API payload adapter avoids redundant settings error aliases");
assertNotIncludes(chatClientApiPayloads, "type SettingsErrorPayload = SettingsErrorApiPayload;", "API payload adapter keeps one settings error boundary");
assertNotIncludes(chatClientApiPayloads, "JsonRecord", "API payload adapter avoids open-ended JSON records");
assertIncludes(chatClientApiPayloads, "export function toSettingsErrorPayload(value: unknown): SettingsErrorPayload | null", "API payload adapter narrows settings errors through a typed converter");
assertIncludes(chatClientApiPayloads, "status: payload.status,\n    message: payload.message,", "API payload adapter projects settings error fields");
assertNotIncludes(chatClient, "function toSettingsErrorPayload", "chat client delegates settings error projection to the adapter");
assertIncludes(chatClient, "function settingsErrorStatus(error: unknown): number | null", "chat client narrows settings API error status");
assertIncludes(chatClient, "function settingsErrorStatus(error: unknown): number | null {\n  const record = toSettingsErrorPayload(error);", "chat client routes every settings error status through the finite payload boundary");
assertIncludes(chatClient, "function settingsErrorMessage(error: unknown, fallback: string): string", "chat client narrows settings API error messages");
assertIncludes(chatClient, "const record = toSettingsErrorPayload(error);", "chat client routes settings error records through the named boundary");
assertNotIncludes(chatClient, "error instanceof Error && \"status\" in error", "chat client avoids a parallel asserted settings error path");
assertNotIncludes(chatClient, "const record = toJsonRecord(error);", "chat client avoids inline settings error records");
assertIncludes(chatClient, "} catch (error: unknown) {\n      if (settingsErrorStatus(error) === 401)", "chat client narrows auth settings request errors");
assertIncludes(chatClient, "async function loadCommandCatalog(): Promise<void>", "chat client types command catalog loader");
assertIncludes(chatClient, "state.commandCatalog.error = settingsErrorMessage(error, \"Command catalog unavailable\");", "chat client narrows command catalog load errors");
assertNotIncludes(chatClient, "type RunSummaryPayload,", "chat client no longer imports the canonical raw run summary payload");
assertNotIncludes(chatClient, "function toRunSummaryPayload", "chat client delegates raw run summary projection to the canonical normalizer");
assertNotIncludes(chatClient, "function normalizeRunSummaryPayload", "chat client avoids a redundant run summary wrapper");
assertIncludes(chatClient, "const summary = normalizeRunSummary(await requestSettingsJson(buildRunSummaryPath(run.runId, sessionId)));", "chat client sends unknown run summary responses directly through the canonical normalizer");
assertNotIncludes(chatClient, "requestSettingsJson<RunSummaryPayload>", "chat client avoids trusting an unchecked run summary response generic");
assertNotIncludes(chatClient, "const payload = toRunSummaryPayload", "chat client avoids duplicating run summary projection before normalization");
assertIncludes(chatClient, "function loadRunSummary(\n    session: ChatSession | null | undefined,\n    run: RunViewState | null | undefined,\n  ): Promise<void>", "chat client types run summary loading helper");
assertIncludes(chatClient, "if (settingsErrorStatus(error) === 404)", "chat client narrows run summary missing errors by status");
assertIncludes(chatClient, "run.summaryError = settingsErrorMessage(error, copy.value.notices.runSummaryLoadFailed);", "chat client narrows run summary error messages");
assertOccurrenceCount(
  chatClient,
  "isCurrentRequestGeneration(runSummaryRequestGenerations, run, requestGeneration)",
  3,
  "run summary success, catch, and finally all use the same generation guard",
);
assertIncludes(chatClient, "function loadRunTrace(\n    session: ChatSession | null | undefined,\n    run: RunViewState | null | undefined,\n  ): Promise<void>", "chat client types run trace loading helper");
assertIncludes(chatClient, "run.traceError = settingsErrorMessage(error, copy.value.notices.runTraceLoadFailed);", "chat client narrows run trace error messages");
assertOccurrenceCount(
  chatClient,
  "isCurrentRequestGeneration(runTraceRequestGenerations, run, requestGeneration)",
  3,
  "run trace success, catch, and finally all use the same generation guard",
);
assertIncludes(chatClient, "function maybeLoadRunSummaryForSession(session: ChatSession | null | undefined)", "chat client types summary loading entrypoint");
assertIncludes(chatClient, "function maybeLoadRunTraceForSession(session: ChatSession | null | undefined)", "chat client types trace loading entrypoint");
assertIncludes(reactiveCompat, "type WatchCallback<T> = (value: T, previousValue: T | undefined) => void;", "reactive compat watch callback is generic");
assertIncludes(reactiveCompat, "type WatchOptions = { immediate?: boolean };", "reactive compat names watch options");
assertIncludes(reactiveCompat, "type WatchStopHandle = () => void;", "reactive compat names watch cleanup handles");
assertIncludes(reactiveCompat, "type WatchRunner = () => void;", "reactive compat names scheduled watch runners");
assertIncludes(reactiveCompat, "type StoreListener = () => void;", "reactive compat names external store listeners");
assertIncludes(reactiveCompat, "type StoreSubscription = () => void;", "reactive compat names external store unsubscribe handles");
assertIncludes(reactiveCompat, "type Scheduler = (callback: StoreListener) => void;", "reactive compat types notification scheduling");
assertIncludes(reactiveCompat, "type ReactiveStoreEntry<T extends object> = {", "reactive compat types lifecycle store ownership");
assertIncludes(reactiveCompat, "readonly context: LifecycleContext;\n  readonly store: T;", "reactive compat prevents replacing stable store ownership");
assertIncludes(reactiveCompat, "cleanups: RegisteredCleanup[];", "reactive compat stores callable mounted cleanups");
assertIncludes(reactiveCompat, "type ProxyCache = WeakMap<object, object>;", "reactive compat types proxy cache values");
assertIncludes(reactiveCompat, "proxyCache: ProxyCache;", "reactive compat assigns proxy cache ownership to lifecycle contexts");
assertIncludes(reactiveCompat, "proxyCache: new WeakMap(),", "reactive compat creates an isolated proxy cache per lifecycle context");
assertIncludes(reactiveCompat, "const cached = context.proxyCache.get(target);", "reactive compat reads proxies from the active lifecycle cache");
assertIncludes(reactiveCompat, "context.proxyCache.set(target, proxy);", "reactive compat stores proxies in the active lifecycle cache");
assertIncludes(reactiveCompat, "function toComparable<T>(value: T): T;", "reactive compat exposes a same-type watch snapshot overload");
assertIncludes(reactiveCompat, "function toComparable(value: unknown): unknown", "reactive compat implements watch snapshots at the unknown boundary");
assertIncludes(reactiveCompat, "function proxied<T extends object>(target: T, context: LifecycleContext): T;", "reactive compat exposes a same-target proxy overload");
assertIncludes(reactiveCompat, "function proxied(target: object, context: LifecycleContext): object", "reactive compat implements proxy caching at the object boundary");
assertNotIncludes(reactiveCompat, "as T", "reactive compat avoids generic assertions in clone and cache internals");
assertNotIncludes(reactiveCompat, "const proxyCache = new WeakMap", "reactive compat avoids a module-global proxy cache");
assertIncludes(reactiveCompat, "readonly watchers: Set<WatchRunner>;\n  readonly listeners: Set<StoreListener>;", "reactive compat separates lifecycle watcher and listener contracts");
assertIncludes(reactiveCompat, "readonly subscribe: (listener: StoreListener) => StoreSubscription;", "reactive compat types store subscription boundaries");
assertIncludes(reactiveCompat, "function currentContext(): LifecycleContext", "reactive compat exposes an explicit lifecycle context return contract internally");
assertIncludes(reactiveCompat, "function hasChanged(left: unknown, right: unknown): boolean", "reactive compat types watch change detection results");
assertIncludes(reactiveCompat, "const schedule: Scheduler =", "reactive compat keeps notification scheduling behind a named contract");
assertIncludes(reactiveCompat, "const read: () => T =", "reactive compat keeps watch source reads generic and explicit");
assertIncludes(reactiveCompat, "const runner: WatchRunner = () => {", "reactive compat registers named watch runner contracts");
assertIncludes(reactiveCompat, "export function watch<T>(source: WatchSource<T>, callback: WatchCallback<T>, options: WatchOptions = {}): WatchStopHandle", "reactive compat watch source and stop handle are typed");
assertIncludes(reactiveCompat, "function isRegisteredCleanup(value: Cleanup): value is RegisteredCleanup", "reactive compat narrows mounted cleanup callbacks");
assertIncludes(reactiveCompat, "const entry = storeRef.current;", "reactive compat captures stable store ownership");
assertIncludes(reactiveCompat, "entry.cleanups = context.mounted.map((callback) => callback()).filter(isRegisteredCleanup);", "reactive compat stores narrowed mounted cleanups");
assertNotIncludes(reactiveCompat, "storeRef.current!", "reactive compat avoids nullable store non-null assertions");
assertNotIncludes(reactiveCompat, "storeRef.current?.cleanups", "reactive compat avoids dynamic cleanup owner lookup");
assertNotIncludes(reactiveCompat, "any", "reactive compat avoids any in bridge internals");
assertIncludes(chatClient, "new WebSocket", "chat WebSocket flow retained");
assertIncludes(chatClient, "activeSocket.send", "chat send flow retained");
assertIncludes(chatClient, "loadCurrentSessionRuns", "run history loading retained");
assertIncludes(chatClient, "maybeLoadRunTraceForSession", "trace loading retained");
assertIncludes(chatClient, "./chatClientRunPayloads", "chat client imports the dedicated run API payload boundary");
assertIncludes(chatClientRunPayloads, "export type RunTracePayload = {", "run payload adapter owns the run trace response boundary");
assertIncludes(chatClientRunPayloads, "rawEvents: TraceEventView[];\n  fileChanges: TraceFileChangeView[];\n  parts: TracePartView[];\n  artifacts: RunArtifactView[];\n  eventCounts: TraceEventCountsView;\n  diffSummary: DiffSummaryView | null;", "run payload adapter exposes fully typed normalized trace fields");
assertNotIncludes(chatClient, "type NormalizedRunTracePayload", "chat client avoids duplicating the normalized run trace shape");
assertNotIncludes(chatClientRunPayloads, "type RunTraceApiPayload", "run payload adapter avoids redundant trace aliases");
assertNotIncludes(chatClientRunPayloads, "JsonRecord", "run payload adapter avoids open-ended JSON records");
assertIncludes(chatClientRunPayloads, "export function toRunTracePayload(value: unknown): RunTracePayload | null", "run payload adapter projects run trace responses");
assertIncludes(chatClientRunPayloads, "const payload = toPayloadSource<RunTraceSourcePayload>(value);\n  if (!payload) {\n    return null;\n  }", "run payload adapter rejects non-object trace responses");
assertIncludes(chatClientRunPayloads, "const rawEvents = normalizeRunTraceEvents(payload.events);", "run payload adapter normalizes trace events before exposing them");
assertIncludes(chatClientRunPayloads, "fileChanges: normalizeRunTraceFileChanges(payload.file_changes || payload.fileChanges),\n    parts: normalizeRunTraceParts(payload.parts),\n    artifacts: normalizeRunTraceArtifacts(payload.artifacts),\n    eventCounts: normalizeTraceEventCounts(payload.event_counts || payload.eventCounts, rawEvents),\n    diffSummary: normalizeDiffSummary(payload.diff_summary || payload.diffSummary),", "run payload adapter resolves aliases and normalizes nested trace fields");
assertNotIncludes(chatClient, "function toRunTracePayload", "chat client delegates run trace projection to the adapter");
assertIncludes(chatClientRunPayloads, "events?: unknown;", "run payload adapter treats trace events as unknown input");
assertIncludes(chatClientRunPayloads, "file_changes?: unknown;", "run payload adapter treats trace file changes as unknown input");
assertIncludes(chatClientRunPayloads, "parts?: unknown;", "run payload adapter treats trace parts as unknown input");
assertIncludes(chatClientRunPayloads, "artifacts?: unknown;", "run payload adapter treats trace artifacts as unknown input");
assertIncludes(chatClientRunPayloads, "export type RunsPayload = {\n  runs?: unknown;\n};", "run payload adapter owns the run list response boundary");
assertNotIncludes(chatClientRunPayloads, "type RunsListPayload", "run payload adapter avoids a duplicate run list wrapper");
assertNotIncludes(chatClientRunPayloads, "type RunsApiPayload", "run payload adapter avoids redundant run list aliases");
assertIncludes(chatClientRunPayloads, "export function toRunsPayload(value: unknown): RunsPayload | null", "run payload adapter projects run list responses");
assertIncludes(chatClientRunPayloads, "return {\n    runs: payload.runs,\n  };", "run payload adapter projects the run list field");
assertIncludes(chatClientRunPayloads, "const payload = toPayloadSource<RunsPayload>(value);\n  if (!payload) {\n    return null;\n  }", "run payload adapter rejects non-object run list responses");
assertNotIncludes(chatClient, "function toRunsPayload", "chat client delegates run list projection to the adapter");
assertIncludes(chatClientHistoryPayloads, "export type SessionHistoryPayload = {", "history payload adapter owns the field-aware session history response boundary");
assertIncludes(chatClient, "type NormalizedSessionHistoryPayload = {", "chat client names the normalized session history state boundary");
assertIncludes(chatClient, "sessions: ChatSession[];\n  total: number;\n  limit: number;\n  channelTotals: SessionHistoryChannelTotals;", "chat client keeps normalized session history fields typed");
assertNotIncludes(chatClient, "type SessionHistorySessionsPayload", "chat client avoids a duplicate session history sessions wrapper");
assertNotIncludes(chatClient, "type SessionHistoryCountsPayload", "chat client avoids a duplicate session history counts wrapper");
assertNotIncludes(chatClient, "type SessionHistoryChannelTotalsResponsePayload", "chat client avoids a duplicate session history channel totals wrapper");
assertIncludes(chatClient, "./chatClientHistoryPayloads", "chat client imports the dedicated session history API boundary");
assertIncludes(chatClientHistoryPayloads, "export type SessionHistoryPayload = {", "history payload adapter owns the session history response shape");
assertNotIncludes(chatClientHistoryPayloads, "type SessionHistoryApiPayload", "history payload adapter avoids redundant API payload aliases");
assertNotIncludes(chatClientHistoryPayloads, "JsonRecord", "history payload adapter avoids open-ended JSON records");
assertIncludes(chatClientHistoryPayloads, "export function toSessionHistoryPayload(value: unknown): SessionHistoryPayload | null", "history payload adapter projects session history responses through a nullable converter");
assertIncludes(chatClientHistoryPayloads, "sessions: toHistorySessionPayloadList(payload.sessions),\n    total: payload.total,\n    limit: payload.limit,\n    channel_totals: payload.channel_totals,\n    channelTotals: payload.channelTotals,", "history payload adapter projects nested sessions before exposing the response boundary");
assertIncludes(chatClientHistoryPayloads, "const payload = toPayloadSource<SessionHistoryPayload>(value);\n  if (!payload) {\n    return null;\n  }", "history payload adapter rejects non-object session history responses");
assertNotIncludes(chatClient, "function toSessionHistoryPayload", "chat client delegates session history response projection to the adapter");
assertNotIncludes(chatClientHistoryPayloads, "function toSessionHistorySessionsPayload", "history payload adapter avoids a redundant sessions converter");
assertNotIncludes(chatClientHistoryPayloads, "function toSessionHistoryCountsPayload", "history payload adapter avoids a redundant counts converter");
assertNotIncludes(chatClientHistoryPayloads, "function toSessionHistoryChannelTotalsResponsePayload", "history payload adapter avoids a redundant channel totals converter");
assertIncludes(chatClientHistoryPayloads, "export type SessionHistoryChannelTotals = Record<string, number>;", "history payload adapter owns typed numeric session history channel totals");
assertNotIncludes(chatClient, "type SessionHistoryChannelTotals =", "chat client imports rather than duplicates session history channel totals");
assertIncludes(chatClientHistoryPayloads, "messages?: HistoryMessagePayload[];", "history payload adapter exposes projected history messages");
assertIncludes(chatClientHistoryPayloads, "entries?: Array<HistoryEntryPayload | null>;", "history payload adapter preserves projected entry positions with nullable placeholders");
assertIncludes(chatClientHistoryPayloads, "runs?: Array<HistoryRunPayload | null>;", "history payload adapter preserves projected run positions with nullable placeholders");
assertIncludes(chatClientHistoryPayloads, "export type HistorySessionPayload = {", "history payload adapter owns the field-aware session boundary");
assertNotIncludes(chatClientHistoryPayloads, "HistorySessionMessagesPayload", "history payload adapter avoids redundant projected message slices");
assertNotIncludes(chatClientHistoryPayloads, "HistorySessionEntriesPayload", "history payload adapter avoids redundant projected entry slices");
assertNotIncludes(chatClientHistoryPayloads, "HistorySessionRunsPayload", "history payload adapter avoids redundant projected run slices");
assertIncludes(chatClientHistoryPayloads, "export type HistorySessionStatusPayload = {", "history payload adapter owns the field-aware session status boundary");
assertNotIncludes(chatClientHistoryPayloads, "type HistorySessionApiRecord", "history payload adapter keeps one session payload boundary");
assertNotIncludes(chatClientHistoryPayloads, "Record<string, unknown> &", "history payload adapter avoids generic payload intersections");
assertIncludes(chatClientHistoryPayloads, "function toHistorySessionPayload(value: unknown): HistorySessionPayload | null", "history payload adapter privately narrows history sessions");
assertNotIncludes(chatClientHistoryPayloads, "export function toHistorySessionPayload", "history payload adapter exposes only collection-level session parsing");
assertIncludes(chatClientHistoryPayloads, "session_id: payload.session_id,\n    channel: payload.channel,\n    external_chat_id: payload.external_chat_id,\n    hidden_from_browser_history: payload.hidden_from_browser_history,\n    hiddenFromBrowserHistory: payload.hiddenFromBrowserHistory,\n    title: payload.title,\n    updated_at: payload.updated_at,\n    messages: toHistoryMessagePayloadList(payload.messages),\n    entries: toHistoryEntryPayloadList(payload.entries),\n    runs: toHistoryRunPayloadList(payload.runs),\n    status: toHistorySessionStatusPayload(payload.status),", "history payload adapter projects every nested session collection before returning it");
assertNotIncludes(chatClientHistoryPayloads, "return payload;", "history payload adapter never forwards a whole session envelope");
assertIncludes(chatClientHistoryPayloads, "function toHistorySessionStatusPayload(value: unknown): HistorySessionStatusPayload", "history payload adapter privately narrows history session status");
assertNotIncludes(chatClientHistoryPayloads, "export function toHistorySessionStatusPayload", "history payload adapter keeps nested status conversion private");
assertIncludes(chatClientHistoryPayloads, "status: payload.status,\n    updated_at: payload.updated_at,\n    updatedAt: payload.updatedAt,\n    metadata: payload.metadata,", "history payload adapter projects session status fields onto named fields");
assertNotIncludes(chatClient, "function toHistorySessionPayload", "chat client delegates history session projection to the adapter");
assertNotIncludes(chatClient, "function toHistorySessionStatusPayload", "chat client delegates history status projection to the adapter");
assertIncludes(chatClient, "function normalizeHistorySessionStatus(status: HistorySessionStatusPayload): ChatSessionStatus", "chat client receives projected history session status");
assertIncludes(chatClient, "function normalizeHistorySessionStatus(status: HistorySessionStatusPayload): ChatSessionStatus {\n  return {\n    status: textField(status.status) || \"idle\",\n    updatedAt: normalizeEventTimestamp(status.updated_at ?? status.updatedAt),\n    metadata: {},", "chat client keeps history session status metadata finite");
assertIncludes(chatClient, "function normalizeLiveSessionStatus(payload: LiveSessionStatusPayload): ChatSessionStatus {\n  return {\n    status: textField(payload.status) || \"idle\",\n    updatedAt: normalizeEventTimestamp(payload.updated_at ?? payload.updatedAt),\n    metadata: {},", "chat client keeps live session status metadata finite");
assertNotIncludes(chatClient, "function isNonArrayObject", "chat client removes the redundant object presence guard");
assertNotIncludes(chatClient, "function toChatSessionStatusMetadata", "chat client no longer routes discarded status metadata through a helper");
assertNotIncludes(chatClient, "const status = toJsonRecord(payload.status) || {};", "chat client avoids inline history session status payload records");
assertIncludes(chatClient, "type CronJobPayload = {", "chat client keeps typed cron job payload boundary");
assertNotIncludes(chatClient, "type JsonRecord = Record<string, unknown>;", "chat client avoids a shared unknown record boundary");
assertNotIncludes(chatClient, "type PayloadSource<Payload extends object>", "chat client delegates finite payload source ownership to adapters");
assertNotIncludes(chatClient, "function toPayloadSource<Payload extends object>", "chat client no longer owns a generic payload source guard");
for (const [payloadAdapter, moduleName, payloadTypes] of [
  [chatClientApiPayloads, "API payload adapter", ["SettingsErrorPayload", "CommandCatalogPayload", "CommandCatalogItemPayload"]],
  [chatClientMessagePayloads, "message payload adapter", ["LiveEntryMetadataPayload", "OutgoingMessageMetadata", "OutgoingMessageInputPayload"]],
]) {
  assertIncludes(payloadAdapter, "import { toPayloadSource } from \"./payloadBoundary\";", `${moduleName} reuses the shared finite object guard`);
  assertNotIncludes(payloadAdapter, "type PayloadSource<Payload extends object>", `${moduleName} avoids another local payload source type`);
  assertNotIncludes(payloadAdapter, "function toPayloadSource<Payload extends object>", `${moduleName} avoids another local payload source guard`);
  for (const payloadType of payloadTypes) {
    assertIncludes(payloadAdapter, `toPayloadSource<${payloadType}>(value)`, `${moduleName} limits ${payloadType} source reads to known fields`);
  }
}
for (const payloadType of [
  "RunEventPayloadInput",
  "RunPartDeltaPayload",
]) {
  assertIncludes(chatClientEventPayloads, `toPayloadSource<${payloadType}>(value)`, `event payload adapter limits ${payloadType} source reads to known fields`);
}
assertIncludes(chatClient, "./chatClientEventPayloads", "chat client imports the dedicated event payload boundary");
assertIncludes(chatClientEventPayloads, "import { toPayloadSource } from \"./payloadBoundary\";", "event payload adapter reuses the shared finite object guard");
assertNotIncludes(chatClientEventPayloads, "type PayloadSource<Payload extends object>", "event payload adapter avoids another local payload source type");
assertNotIncludes(chatClientEventPayloads, "function toPayloadSource<Payload extends object>", "event payload adapter avoids another local payload source guard");
for (const payloadType of [
  "RunEventPayloadInput",
  "RunPartDeltaPayload",
  "LiveRunEventPayloadSource",
]) {
  assertNotIncludes(chatClient, `type ${payloadType} =`, `chat client delegates ${payloadType} ownership to the event adapter`);
}
for (const converterName of [
  "toRunEventPayloadInput",
  "toRunPartDeltaPayload",
  "toLiveRunEventPayloadSource",
]) {
  assertNotIncludes(chatClient, `function ${converterName}`, `chat client delegates ${converterName} to the event adapter`);
}
for (const payloadType of [
  "RunsPayload",
  "RunTraceSourcePayload",
  "RunFileChangeRevertSourcePayload",
  "RunFileChangeRevertRecordSourcePayload",
]) {
  assertIncludes(chatClientRunPayloads, `toPayloadSource<${payloadType}>(value)`, `run payload adapter limits ${payloadType} source reads to known fields`);
}
for (const payloadType of [
  "HistorySessionPayload",
  "HistorySessionStatusPayload",
  "SessionHistoryPayload",
  "SessionClearPayload",
  "HistoryRunPayload",
  "HistoryMessagePayload",
  "HistoryMessageMetadata",
  "HistoryEntryContentPayload",
  "HistoryEntryPayload",
]) {
  assertIncludes(chatClientHistoryPayloads, `toPayloadSource<${payloadType}>(value)`, `history payload adapter limits ${payloadType} source reads to known fields`);
}
assertIncludes(chatClientCronPayloads, "toPayloadSource<CronJobScheduleSourcePayload>(value)", "cron payload adapter limits schedule source reads to known fields");
assertIncludes(chatClientCronPayloads, "toPayloadSource<CronJobMessageSourcePayload>(value)", "cron payload adapter limits message source reads to known fields");
assertIncludes(chatClientCronPayloads, "toPayloadSource<CronJobStateSourcePayload>(value)", "cron payload adapter limits state source reads to known fields");
assertIncludes(chatClientCronPayloads, "toPayloadSource<CronJobSourcePayload>(value)", "cron payload adapter limits job source reads to known fields");
assertIncludes(chatClientHistoryPayloads, "type SessionHistoryChannelTotalsSource = Record<string, unknown>;", "history payload adapter isolates dynamic channel names at the raw boundary");
assertIncludes(chatClientMessagePayloads, "export function toLiveEntryMetadata(value: unknown): LiveEntryMetadata", "message payload adapter normalizes finite live entry metadata");
assertIncludes(chatClientApiPayloads, "export type CommandCatalogPayload = { commands?: unknown };", "API payload adapter types command catalog response fields");
assertNotIncludes(chatClient, "type CommandCatalogPayload = { commands?: unknown };", "chat client delegates command catalog payload ownership to the adapter");
assertNotIncludes(chatClientApiPayloads, "type CommandCatalogItemsPayload", "API payload adapter avoids a duplicate command list wrapper");
assertNotIncludes(chatClientApiPayloads, "type CommandCatalogApiPayload", "API payload adapter avoids redundant command catalog aliases");
assertIncludes(chatClientApiPayloads, "export function toCommandCatalogPayload(value: unknown): CommandCatalogPayload | null", "API payload adapter projects command catalog responses");
assertIncludes(chatClientApiPayloads, "return {\n    commands: payload.commands,\n  };", "API payload adapter projects the command list field");
assertIncludes(chatClientApiPayloads, "if (!payload) {\n    return null;\n  }", "API payload adapter rejects non-object command catalog responses");
assertNotIncludes(chatClient, "function toCommandCatalogPayload", "chat client delegates command catalog projection to the adapter");
assertNotIncludes(chatClient, "function toCommandCatalogItemsPayload", "chat client avoids a redundant command catalog item-list converter");
assertIncludes(chatClient, "export type ConnectionState = \"disconnected\" | \"connecting\" | \"connected\";", "chat client exports typed connection state union");
assertIncludes(chatClient, "connectionState: \"disconnected\",", "chat client initializes connection state through contextual typing");
assertNotIncludes(chatClient, "connectionState: \"disconnected\" as ConnectionState,", "chat client avoids asserting its reactive connection state initializer");
assertIncludes(chatClient, "export interface CommandCatalogItem", "chat client exports typed command catalog item");
assertIncludes(chatClient, "type CommandCatalogState = {", "chat client types command catalog reactive state");
assertIncludes(chatClient, "commands: CommandCatalogItem[];", "chat client command catalog state stores typed commands");
assertIncludes(chatClient, "export type NoticeTone = \"info\" | \"success\" | \"warning\" | \"error\";", "chat client exports typed notice tone union");
assertIncludes(chatClient, "export type NoticeState = {", "chat client exports typed notice state");
assertIncludes(chatClient, "const initialNotice: NoticeState = {", "chat client initializes notice with typed state");
assertIncludes(chatClient, "export interface ToastNotice", "chat client exports typed toast notice item");
assertIncludes(chatClient, "type SessionHistoryState = {", "chat client types session history reactive state");
assertIncludes(chatClient, "channelTotals: SessionHistoryChannelTotals;", "chat client session history state stores typed channel totals");
assertIncludes(chatClient, "type ChatClientState = {", "chat client types root reactive state");
assertIncludes(chatClient, "sessions: ChatSession[];", "chat client root state stores typed sessions");
assertIncludes(chatClient, "commandCatalog: CommandCatalogState;", "chat client root state stores typed command catalog");
assertIncludes(chatClient, "sessionHistory: SessionHistoryState;", "chat client root state stores typed session history");
assertIncludes(chatClient, "const state = reactive<ChatClientState>({", "chat client initializes root state through typed reactive boundary");
assertNotIncludes(chatClient, "const state = reactive({", "chat client avoids anonymous root reactive state");
assertIncludes(chatClient, "const toasts = ref<ToastNotice[]>([]);", "chat client stores typed toast notices");
assertIncludes(chatClient, "const toastTimers = new Map<string, number>();", "chat client tracks typed toast timers");
assertIncludes(chatClient, "function showToast(text: unknown, tone: NoticeTone = \"info\")", "chat client narrows toast text before display");
assertIncludes(chatClient, "function dismissToast(id: string)", "chat client dismisses typed toast ids");
assertIncludes(chatClientHistoryPayloads, "export type SessionClearPayload = {", "history payload adapter types session clear response fields");
assertNotIncludes(chatClientHistoryPayloads, "type SessionClearApiPayload", "history payload adapter keeps a single session clear boundary");
assertNotIncludes(chatClientHistoryPayloads, "type SessionClearPayload = SessionClearApiPayload;", "history payload adapter avoids session clear aliases");
assertNotIncludes(chatClientHistoryPayloads, "type SessionClearPayload = JsonRecord", "history payload adapter avoids open-ended session clear records");
assertIncludes(chatClient, "type SessionClearResult = { deleted: number };", "chat client stores normalized session clear results");
assertIncludes(chatClientRunPayloads, "export type RunFileChangeRevertPayload = {", "run payload adapter owns the file revert response boundary");
assertNotIncludes(chatClientRunPayloads, "type RunFileChangeRevertApiPayload", "run payload adapter keeps one file revert boundary");
assertNotIncludes(chatClientRunPayloads, "JsonRecord", "run payload adapter avoids open-ended file revert records");
assertIncludes(chatClientRunPayloads, "export type RunFileChangeRevertRecord = {", "run payload adapter owns normalized file revert records");
assertNotIncludes(chatClient, "type RunFileChangeRevertResult = {", "chat client reuses the normalized file revert payload");
assertNotRegex(
  chatClient,
  /^\s*(?:export\s+)?(?:async\s+)?function\s+\w+\([^)]*(?:value|payload): unknown/m,
  "chat client delegates unknown value and payload boundaries to adapters",
);
assertIncludes(chatClient, "type ComposerSubmitEvent = { preventDefault: () => void };", "chat client types composer submit events structurally");
assertIncludes(chatClient, "type ComposerKeyboardEvent = ComposerSubmitEvent & {", "chat client types composer key events structurally");
assertIncludes(chatClient, "./chatClientMessagePayloads", "chat client imports the dedicated message payload boundary");
assertIncludes(chatClientMessagePayloads, "export type OutgoingMessageMetadata = {", "message payload adapter types outgoing metadata input fields");
assertNotIncludes(chatClient, "type OutgoingMessageMetadata = {", "chat client delegates outgoing metadata ownership to the adapter");
assertNotIncludes(chatClientMessagePayloads, "type OutgoingMessageMetadataPayload", "message payload adapter keeps one outgoing metadata boundary");
assertIncludes(chatClientMessagePayloads, "overlay_profile_id?: string;", "message payload adapter narrows outgoing overlay profile ids");
assertNotIncludes(chatClientMessagePayloads, "overlay_profile_id?: unknown;", "message payload adapter avoids unknown outgoing overlay profile ids");
assertNotIncludes(chatClientMessagePayloads, "JsonRecord", "message payload adapter avoids open-ended JSON records");
assertIncludes(chatClientMessagePayloads, "export type OutgoingMessageInputPayload = {", "message payload adapter types outgoing message input fields");
assertIncludes(chatClientMessagePayloads, "text: string;\n  metadata: OutgoingMessageMetadata;", "message payload adapter stores normalized outgoing text and metadata");
assertNotIncludes(chatClientMessagePayloads, "type OutgoingMessageInputPayload = {\n  text?: unknown;\n  metadata?: unknown;", "message payload adapter avoids raw outgoing message input fields");
assertNotIncludes(chatClientMessagePayloads, "type OutgoingMessageInputRecord", "message payload adapter keeps one outgoing message input boundary");
assertIncludes(chatClient, "type OutgoingMessagePayload = {\n  text: string;\n  metadata: OutgoingMessageMetadata;\n};", "chat client routes outgoing message payload metadata through the named boundary");
assertIncludes(chatClient, "./chatClientLiveSocket", "chat client imports the dedicated live socket boundary");
assertIncludes(chatClientLiveSocket, "type LiveSocketPayload = {", "live socket adapter types envelope fields inside the API boundary");
assertNotIncludes(chatClientLiveSocket, "export type LiveSocketPayload", "live socket adapter keeps the broad raw envelope private");
assertNotIncludes(chatClientLiveSocket, "type LiveSocketApiPayload", "live socket adapter keeps a single envelope payload boundary");
assertIncludes(chatClientLiveSocket, "export type LiveSessionIdentityPayload = Pick<", "live socket adapter routes identity through the field-aware envelope");
assertIncludes(chatClientLiveSocket, "\"session_id\" | \"sessionId\" | \"channel\" | \"external_chat_id\" | \"externalChatId\"", "live socket adapter identity payload lists only identity aliases");
assertIncludes(chatClient, "type LiveSessionIdentity = {", "chat client keeps normalized live session identity boundary");
assertIncludes(chatClient, "type ChatSessionStatus,", "chat client imports shared normalized session status boundary");
assertNotIncludes(chatClient, "type ChatSessionStatusMetadata,", "chat client no longer imports an unused status metadata alias");
assertNotIncludes(chatClient, "type LiveEntryMetadata,", "chat client delegates live entry metadata output typing to the adapter");
assertIncludes(chatClientMessagePayloads, "import type { LiveEntryMetadata, LiveEntryMetadataPayload } from \"./chatClientSessions\";", "message payload adapter imports raw and normalized live entry metadata boundaries");
assertNotIncludes(chatClient, "type LiveEntryMetadataPayload,", "chat client delegates raw live entry metadata projection to the adapter");
assertIncludes(chatClientLiveSocket, "export type LiveSessionStatusPayload = LiveSessionIdentityPayload & Pick<", "live socket adapter routes status through the field-aware envelope");
assertIncludes(chatClientLiveSocket, "\"status\" | \"updated_at\" | \"updatedAt\" | \"metadata\"", "live socket adapter status payload lists only status aliases");
assertIncludes(chatClientLiveSocket, "export type LiveAssistantMessagePayload = LiveSessionIdentityPayload & Pick<LiveSocketPayload, \"text\">;", "live socket adapter routes messages through a text plus identity boundary");
assertIncludes(chatClientLiveSocket, "export type LiveSocketErrorPayload = Pick<LiveSocketPayload, \"error\" | \"text\">;", "live socket adapter routes errors through a narrow boundary");
assertIncludes(chatClientLiveSocket, "export type LiveRunEventPayload = LiveSessionIdentityPayload & Pick<", "live socket adapter routes run events through the field-aware envelope");
assertIncludes(chatClientLiveSocket, "\"run_id\" | \"runId\" | \"event_type\" | \"eventType\" | \"payload\" | \"artifact\" | \"kind\" | \"status\" | \"created_at\" | \"createdAt\"", "live socket adapter run event payload lists only run event aliases");
assertIncludes(chatClient, "type LiveRunEventView = TraceEventView & {", "chat client keeps normalized live run event boundary aligned with trace events");
assertIncludes(chatClient, "type LiveAssistantMessageView = LiveSessionIdentity & {", "chat client keeps normalized live assistant message boundary");
assertNotIncludes(chatClientLiveSocket, "type LiveSocketPayload = LiveSocketApiPayload;", "live socket adapter avoids envelope alias wrappers");
assertNotIncludes(chatClientLiveSocket, "type LiveSocketPayload = JsonRecord;", "live socket adapter avoids pure JSON records");
assertNotIncludes(chatClientLiveSocket, "type LiveSocketPayload = JsonRecord & {", "live socket adapter avoids open-ended JSON records");
assertNotIncludes(chatClientLiveSocket, "type LiveSessionIdentityPayload = LiveSocketPayload;", "live socket adapter avoids passing whole envelopes into identity normalization");
assertNotIncludes(chatClientLiveSocket, "type LiveAssistantMessagePayload = LiveSocketPayload;", "live socket adapter avoids passing whole envelopes into message normalization");
assertNotIncludes(chatClientLiveSocket, "type LiveSocketErrorPayload = LiveSocketPayload;", "live socket adapter avoids passing whole envelopes into error normalization");
assertNotIncludes(chatClientLiveSocket, "type LiveRunEventPayload = LiveSocketPayload;", "live socket adapter avoids passing whole envelopes into run event normalization");
assertNotIncludes(chatClientLiveSocket, "type LiveSessionIdentityPayload = JsonRecord & {", "live socket adapter routes identity through the finite envelope");
assertNotIncludes(chatClientLiveSocket, "type LiveSocketErrorPayload = JsonRecord & {", "live socket adapter routes errors through the finite envelope");
assertNotIncludes(chatClientLiveSocket, "type LiveSocketPayload = LiveSessionStatusPayload & LiveRunEventPayload & {", "live socket adapter avoids broad live event intersections");
assertNotIncludes(chatClientLiveSocket, "type LiveSessionIdentityPayload = {", "live socket adapter avoids duplicate bare identity records");
assertNotIncludes(chatClientLiveSocket, "type LiveSocketErrorPayload = {", "live socket adapter avoids duplicate bare error records");
assertIncludes(chatClientLiveSocket, "event_type?: unknown;", "live socket adapter lists event type aliases");
assertIncludes(chatClientLiveSocket, "updated_at?: unknown;", "live socket adapter lists session status aliases");
assertIncludes(chatClientLiveSocket, "const LIVE_SOCKET_TYPES = [\"session\", \"message\", \"run_event\", \"session_status\", \"error\"] as const;", "live socket adapter owns typed event names");
assertIncludes(chatClientLiveSocket, "type LiveSocketType = (typeof LIVE_SOCKET_TYPES)[number];", "live socket adapter derives its private event type union from constants");
assertNotIncludes(chatClientLiveSocket, "export type LiveSocketType", "live socket adapter exposes the routed event union instead of its internal type guard union");
assertIncludes(chatClientLiveSocket, "export type LiveSocketMessageParseResult =\n  | { kind: \"invalid\" }\n  | { kind: \"unsupported\" }\n  | { kind: \"event\"; event: LiveSocketEvent };", "live socket adapter exposes a finite parse result boundary");
assertNotIncludes(chatClient, "type JsonRecord = Record<string, unknown>;", "chat client avoids a shared generic JSON record alias");
assertNotIncludes(chatClient, "function toJsonRecord(value: unknown): JsonRecord | null", "chat client avoids a shared generic JSON record converter");
assertNotIncludes(chatClientEventPayloads, "[key: string]: unknown;", "event payload adapter avoids open-ended event payload indexes");
assertNotIncludes(chatClientEventPayloads, "TraceEventPayload & {", "event payload adapter avoids trace event inheritance");
assertNotIncludes(chatClientEventPayloads, "JsonRecord", "event payload adapter avoids open-ended JSON records");
assertNotIncludes(chatClient, "normalizeRunLifecycleEventPayload,", "chat client leaves live lifecycle payload projection inside the event adapter");
assertNotIncludes(chatClient, "type TraceEventPayload,", "chat client no longer imports trace event payloads for live run event records");
assertIncludes(chatClientEventPayloads, "import {\n  normalizeRunTimelinePayload,\n  type RunTimelinePayload,\n} from \"./chatClientRunHelpers\";", "event payload adapter reuses the finite timeline payload projection");
assertIncludes(chatClientEventPayloads, "export type LiveRunEventPayloadSource =\n  RunTimelinePayload\n  & RunPartDeltaPayload;", "event payload adapter composes one finite live run event source");
assertNotIncludes(chatClientEventPayloads, "type LiveRunEventPayloadSource = {\n  [key: string]: unknown;\n};", "event payload adapter avoids open-ended live run event indexes");
assertNotIncludes(chatClient, "type LiveRunEventPayloadRecord", "chat client delegates live run event source composition to the adapter");
assertNotIncludes(chatClient, "type LivePayloadRecord = JsonRecord;", "chat client avoids one broad live payload alias");
assertNotIncludes(chatClient, "type LiveSocketPayloadRecord = JsonRecord;", "chat client avoids a separate broad socket payload alias");
assertNotIncludes(chatClientEventPayloads, "type LiveRunEventPayloadSource = JsonRecord", "event payload adapter avoids generic JSON live run event sources");
assertNotIncludes(chatClient, "type LiveSessionStatusView = {", "chat client avoids duplicating the shared session status view");
assertNotIncludes(chatClient, "type LiveSessionMetadata = JsonRecord;", "chat client avoids duplicating the shared session status metadata");
assertNotIncludes(chatClient, "type RunLifecycleEventPayload = {", "chat client avoids duplicating the shared run lifecycle payload shape");
assertNotIncludes(chatClient, "type BackgroundProcessEventPayload = {", "chat client avoids duplicating the shared background process payload shape");
assertIncludes(chatClient, "payload: LiveRunEventPayloadSource;", "chat client keeps run event payloads behind the adapter-owned finite boundary");
assertIncludes(chatClientLiveSocket, "const payload = toPayloadSource<LiveSocketPayload>(value);", "live socket adapter guards parsed envelope objects");
assertIncludes(chatClientLiveSocket, "function toLiveSocketPayload(value: unknown): LiveSocketPayload | null", "live socket adapter narrows parsed payloads through a named private boundary");
assertNotIncludes(chatClientLiveSocket, "export function toLiveSocketPayload", "live socket adapter does not expose raw envelope conversion");
assertIncludes(chatClientLiveSocket, "export type LiveSocketEvent =\n  | { type: \"session\"; payload: LiveSessionIdentityPayload }\n  | { type: \"message\"; payload: LiveAssistantMessagePayload }\n  | { type: \"run_event\"; payload: LiveRunEventPayload }\n  | { type: \"session_status\"; payload: LiveSessionStatusPayload }\n  | { type: \"error\"; payload: LiveSocketErrorPayload };", "live socket adapter exposes one discriminated union for known events");
assertIncludes(chatClientLiveSocket, "type: payload.type,\n    text: payload.text,\n    error: payload.error,\n    session_id: payload.session_id,\n    sessionId: payload.sessionId,\n    channel: payload.channel,\n    external_chat_id: payload.external_chat_id,\n    externalChatId: payload.externalChatId,\n    status: payload.status,\n    updated_at: payload.updated_at,\n    updatedAt: payload.updatedAt,\n    metadata: payload.metadata,\n    run_id: payload.run_id,\n    runId: payload.runId,\n    event_type: payload.event_type,\n    eventType: payload.eventType,\n    payload: payload.payload,\n    artifact: payload.artifact,\n    kind: payload.kind,\n    created_at: payload.created_at,\n    createdAt: payload.createdAt,", "live socket adapter projects raw envelopes onto named fields");
assertNotIncludes(chatClientLiveSocket, "function toLiveSocketPayload(value: unknown): LiveSocketPayload | null {\n  return toJsonRecord(value);\n}", "live socket adapter avoids passing raw records through a generic converter");
assertIncludes(chatClientLiveSocket, "function toLiveSessionIdentityPayload(payload: LiveSocketPayload): LiveSessionIdentityPayload", "live socket adapter projects envelopes before session handling");
assertIncludes(chatClientLiveSocket, "function toLiveRunEventPayload(payload: LiveSocketPayload): LiveRunEventPayload", "live socket adapter projects envelopes before run event handling");
assertIncludes(chatClientLiveSocket, "session_id: payload.session_id,\n    sessionId: payload.sessionId,\n    channel: payload.channel,\n    external_chat_id: payload.external_chat_id,\n    externalChatId: payload.externalChatId,\n    run_id: payload.run_id,\n    runId: payload.runId,\n    event_type: payload.event_type,\n    eventType: payload.eventType,\n    payload: payload.payload,\n    artifact: payload.artifact,\n    kind: payload.kind,\n    status: payload.status,\n    created_at: payload.created_at,\n    createdAt: payload.createdAt,", "live socket adapter projects run event fields onto named fields");
assertNotIncludes(chatClientLiveSocket, "function toLiveRunEventPayload(payload: LiveSocketPayload): LiveRunEventPayload {\n  return payload;\n}", "live socket adapter avoids passing whole envelopes through the run event converter");
assertIncludes(chatClientLiveSocket, "function toLiveSessionStatusPayload(payload: LiveSocketPayload): LiveSessionStatusPayload", "live socket adapter projects envelopes before status handling");
assertIncludes(chatClientLiveSocket, "session_id: payload.session_id,\n    sessionId: payload.sessionId,\n    channel: payload.channel,\n    external_chat_id: payload.external_chat_id,\n    externalChatId: payload.externalChatId,\n    status: payload.status,\n    updated_at: payload.updated_at,\n    updatedAt: payload.updatedAt,\n    metadata: payload.metadata,", "live socket adapter projects status fields onto named fields");
assertNotIncludes(chatClientLiveSocket, "function toLiveSessionStatusPayload(payload: LiveSocketPayload): LiveSessionStatusPayload {\n  return payload;\n}", "live socket adapter avoids passing whole envelopes through the status converter");
assertIncludes(chatClientLiveSocket, "function isLiveSocketType(value: string): value is LiveSocketType", "live socket adapter narrows event names with a type guard");
assertIncludes(chatClientLiveSocket, "function normalizeLiveSocketType(value: unknown): LiveSocketType | \"\"", "live socket adapter normalizes event types before routing");
assertIncludes(chatClientLiveSocket, "function toLiveSocketEvent(payload: LiveSocketPayload): LiveSocketEvent | null", "live socket adapter routes known events through a private discriminated union boundary");
assertNotIncludes(chatClientLiveSocket, "export function toLiveSocketEvent", "live socket adapter does not expose intermediate event conversion");
assertIncludes(chatClientLiveSocket, "return { type, payload: toLiveSessionIdentityPayload(payload) };", "live socket adapter narrows session events before dispatch");
assertIncludes(chatClientLiveSocket, "return { type, payload: toLiveAssistantMessagePayload(payload) };", "live socket adapter narrows message events before dispatch");
assertIncludes(chatClientLiveSocket, "return { type, payload: toLiveRunEventPayload(payload) };", "live socket adapter narrows run events before dispatch");
assertIncludes(chatClientLiveSocket, "return { type, payload: toLiveSessionStatusPayload(payload) };", "live socket adapter narrows status events before dispatch");
assertIncludes(chatClientLiveSocket, "return { type, payload: toLiveSocketErrorPayload(payload) };", "live socket adapter narrows error events before dispatch");
assertIncludes(chatClientLiveSocket, "return null;", "live socket adapter ignores unsupported event types");
assertIncludes(chatClientLiveSocket, "export function parseLiveSocketMessage(rawData: string): LiveSocketMessageParseResult", "live socket adapter owns raw websocket JSON parsing");
assertIncludes(chatClientLiveSocket, "parsedPayload = JSON.parse(rawData);", "live socket adapter parses websocket JSON inside the boundary");
assertIncludes(chatClientLiveSocket, "return { kind: \"invalid\" };", "live socket adapter reports malformed or non-object messages");
assertIncludes(chatClientLiveSocket, "return event ? { kind: \"event\", event } : { kind: \"unsupported\" };", "live socket adapter distinguishes supported and unknown event types");
assertNotIncludes(chatClientLiveSocket, "export function toLiveRunEventPayload", "live socket adapter keeps branch projectors private");
assertNotIncludes(chatClientLiveSocket, "export function normalizeLiveSocketType", "live socket adapter keeps type normalization private");
assertNotIncludes(chatClient, "function toLiveSocketPayload", "chat client delegates raw socket parsing to the adapter");
assertNotIncludes(chatClient, "toLiveSocketPayload", "chat client does not depend on the raw live socket envelope converter");
assertNotIncludes(chatClient, "toLiveSocketEvent", "chat client does not depend on the intermediate live socket event converter");
assertNotIncludes(chatClient, "function toLiveRunEventPayload", "chat client delegates run event projection to the adapter");
assertNotIncludes(chatClient, "function toLiveSessionStatusPayload", "chat client delegates status projection to the adapter");
assertIncludes(chatClient, "function normalizeLiveSocketErrorMessage(payload: LiveSocketErrorPayload, fallback: string): string", "chat client normalizes live socket errors through a narrow payload boundary");
assertNotIncludes(chatClient, "function normalizeLiveSocketErrorMessage(payload: LiveSocketPayload, fallback: string): string", "chat client avoids passing the whole socket envelope into error normalization");
assertIncludes(chatClientMessagePayloads, "export function toLiveEntryMetadata(value: unknown): LiveEntryMetadata", "message payload adapter narrows raw live entry metadata before normalization");
assertIncludes(chatClientMessagePayloads, "const payload = toPayloadSource<LiveEntryMetadataPayload>(value);", "message payload adapter projects live entry metadata through the finite payload boundary");
assertIncludes(chatClientMessagePayloads, "metadata.sender_name = senderName;", "message payload adapter normalizes live entry sender name to string state");
assertIncludes(chatClientMessagePayloads, "metadata.sender_id = senderId;", "message payload adapter normalizes live entry sender id to string state");
assertIncludes(chatClientMessagePayloads, "metadata.runId = runId;", "message payload adapter preserves the camel-case run reference");
assertIncludes(chatClientMessagePayloads, "metadata.run_id = legacyRunId;", "message payload adapter preserves the legacy run reference");
assertNotIncludes(chatClientMessagePayloads, "Object.entries(payload)", "message payload adapter drops unconsumed dynamic metadata keys");
assertNotIncludes(chatClient, "function toLiveEntryMetadata", "chat client delegates live entry metadata normalization");
assertIncludes(chatClientMessagePayloads, "export function toOutgoingMessageMetadata(value: unknown): OutgoingMessageMetadata", "message payload adapter narrows outgoing metadata before sending");
assertIncludes(chatClientMessagePayloads, "overlay_profile_id: String(payload.overlay_profile_id ?? \"\").trim(),", "message payload adapter normalizes outgoing overlay profile ids");
assertNotIncludes(chatClient, "function toOutgoingMessageMetadata", "chat client delegates outgoing metadata projection to the adapter");
assertIncludes(chatClientMessagePayloads, "export function toOutgoingMessageInputPayload(value: unknown): OutgoingMessageInputPayload | null", "message payload adapter narrows outgoing message inputs");
assertIncludes(chatClientMessagePayloads, "text: String(payload.text || \"\").trim(),\n    metadata: toOutgoingMessageMetadata(payload.metadata),", "message payload adapter normalizes outgoing message fields");
assertNotIncludes(chatClient, "function toOutgoingMessageInputPayload", "chat client delegates outgoing message input projection to the adapter");
assertIncludes(chatClientEventPayloads, "export function toLiveRunEventPayloadSource(value: unknown): LiveRunEventPayloadSource", "event payload adapter owns the nested live run event boundary");
assertIncludes(chatClientEventPayloads, "...normalizeRunTimelinePayload(value),\n    ...toRunPartDeltaPayload(value),", "event payload adapter preserves timeline and streaming fields");
assertNotIncludes(chatClient, "function toLiveEventPayload", "chat client does not project unknown nested live event payloads");
assertNotIncludes(chatClient, "const payload = coerceEventPayload(value);", "chat client avoids routing live run events through open trace payload records");
assertNotIncludes(chatClient, "  coerceEventPayload,", "chat client avoids importing open trace payload coercion");
assertIncludes(chatClient, "function normalizeLiveSessionIdentity(payload: LiveSessionIdentityPayload): LiveSessionIdentity", "chat client normalizes live session identity fields at the socket boundary");
assertIncludes(chatClient, "function normalizeLiveSessionStatus(payload: LiveSessionStatusPayload): ChatSessionStatus", "chat client normalizes live session status fields into the shared session status boundary");
assertIncludes(chatClient, "function normalizeLiveRunEvent(payload: LiveRunEventPayload): LiveRunEventView", "chat client normalizes live run event fields at the socket boundary");
assertIncludes(chatClient, "function traceEventFromLiveRunEvent(event: LiveRunEventView): TraceEventView", "chat client projects live run events into typed trace events");
assertIncludes(chatClient, "function normalizeLiveAssistantMessage(\n  payload: LiveAssistantMessagePayload,\n  fallbackExternalChatId: string | null | undefined,\n): LiveAssistantMessageView", "chat client normalizes live assistant messages through a narrow payload boundary");
assertNotIncludes(chatClient, "function normalizeLiveAssistantMessage(\n  payload: LiveSocketPayload,\n  fallbackExternalChatId: string | null | undefined,\n): LiveAssistantMessageView", "chat client avoids passing the whole socket envelope into message normalization");
assertIncludes(chatClientLiveSocket, "function toLiveAssistantMessagePayload(payload: LiveSocketPayload): LiveAssistantMessagePayload", "live socket adapter projects envelopes before assistant message handling");
assertIncludes(chatClientLiveSocket, "session_id: payload.session_id,\n    sessionId: payload.sessionId,\n    channel: payload.channel,\n    external_chat_id: payload.external_chat_id,\n    externalChatId: payload.externalChatId,\n    text: payload.text,", "live socket adapter projects assistant message fields onto named fields");
assertNotIncludes(chatClientLiveSocket, "function toLiveAssistantMessagePayload(payload: LiveSocketPayload): LiveAssistantMessagePayload {\n  return payload;\n}", "live socket adapter avoids passing whole envelopes through the message converter");
assertIncludes(chatClientLiveSocket, "function toLiveSocketErrorPayload(payload: LiveSocketPayload): LiveSocketErrorPayload", "live socket adapter projects envelopes before error handling");
assertIncludes(chatClientLiveSocket, "error: payload.error,\n    text: payload.text,", "live socket adapter projects error fields onto named fields");
assertNotIncludes(chatClientLiveSocket, "function toLiveSocketErrorPayload(payload: LiveSocketPayload): LiveSocketErrorPayload {\n  return payload;\n}", "live socket adapter avoids passing whole envelopes through the error converter");
assertNotIncludes(chatClient, "function toLiveAssistantMessagePayload", "chat client delegates message projection to the adapter");
assertNotIncludes(chatClient, "function toLiveSocketErrorPayload", "chat client delegates error projection to the adapter");
assertIncludes(chatClient, "function resolveDefaultWsUrl(): string", "chat client types default websocket URL resolution");
assertIncludes(chatClient, "function applySessionStatus(payload: LiveSessionStatusPayload): void", "chat client session status accepts typed live payloads");
assertIncludes(chatClient, "const identity = normalizeLiveSessionIdentity(payload);\n    const { sessionId, channel } = identity;", "chat client applies session status from normalized live identity");
assertIncludes(chatClient, "const nextStatus = normalizeLiveSessionStatus(payload);\n    if (nextStatus.updatedAt >= Number(session.status.updatedAt || 0)) {\n      session.status = nextStatus;\n    }", "chat client applies normalized live session status without accepting an older status snapshot");
assertNotIncludes(chatClient, "status: String(payload?.status || \"idle\").trim() || \"idle\"", "chat client avoids raw live status reads in session status assignment");
assertIncludes(chatClient, "function handleRunEvent(payload: LiveRunEventPayload): void", "chat client run events accept typed live payloads");
assertIncludes(chatClient, "const session = ensureSession(externalChatId, identity.sessionId);", "chat client creates run event sessions from normalized live identity");
assertIncludes(chatClient, "const liveEvent = normalizeLiveRunEvent(payload);", "chat client normalizes live run events before state updates");
assertIncludes(chatClient, "const run = findOrCreateRun(session, liveEvent.runId, liveEvent.createdAt);", "chat client finds runs through normalized live event state");
assertIncludes(chatClient, "const eventPayload = toLiveRunEventPayloadSource(payload.payload);", "chat client converts nested live run event data through the adapter-owned source boundary");
assertIncludes(chatClient, "statusFromRunEvent(\n      liveEvent.eventType,\n      liveEvent.payload,\n      liveEvent.status,", "chat client passes the finite lifecycle source directly to status mapping");
assertIncludes(chatClient, "applyRunPartDelta(run, toRunPartDeltaPayload(liveEvent.payload), liveEvent.createdAt);", "chat client narrows live streaming run part payloads before applying deltas");
assertNotIncludes(chatClient, "applyRunPartDelta(run, liveEvent.payload, liveEvent.createdAt);", "chat client avoids passing broad live payloads directly to streaming part deltas");
assertIncludes(chatClient, "describeRunEvent(liveEvent.eventType, liveEvent.payload, copy.value)", "chat client describes the already-projected finite live event payload");
assertNotIncludes(chatClient, "const runId = String(payload.run_id || payload.runId || `run-${Date.now().toString(36)}-${randomToken()}`);", "chat client avoids raw run id reads inside handleRunEvent");
assertNotIncludes(chatClient, "const eventType = String(payload.event_type || payload.eventType", "chat client avoids raw event type reads inside handleRunEvent");
assertNotIncludes(chatClient, "const eventStatus = String(payload.status || inferRunEventStatus", "chat client avoids raw event status reads inside handleRunEvent");
assertIncludes(chatClient, "function clearGatewayReconnectTimer(): void", "chat client types gateway reconnect timer clearing");
assertIncludes(chatClient, "function clearSessionHistoryRefreshTimer(): void", "chat client types session history timer clearing");
assertIncludes(chatClient, "function scheduleSessionHistoryRefresh(delayMs: number = SESSION_HISTORY_REFRESH_INTERVAL_MS): void", "chat client types session history refresh scheduling");
assertIncludes(chatClient, "function scheduleGatewayReconnect(reason: ReconnectNotice, tone: NoticeTone = \"warning\"): void", "chat client types gateway reconnect scheduling");
assertIncludes(chatClient, "function disconnectSocket(reason: string, tone: NoticeTone = \"warning\", { manual = true }: DisconnectSocketOptions = {}): void", "chat client types socket disconnect helper");
assertIncludes(chatClient, "function buildSocketUrl(baseUrl: string, externalChatId: string, accessToken = \"\"): string", "chat client types websocket URL builder");
assertIncludes(chatClient, "function authorizedHeaders(headers?: HeadersInit): Headers", "chat client accepts every standard fetch header input");
assertIncludes(chatClient, "const authorized = new Headers(headers);", "chat client normalizes settings headers through the platform API");
assertIncludes(chatClient, "authorized.set(\"Authorization\", `Bearer ${token}`);", "chat client applies the current access token after normalizing headers");
assertIncludes(chatClient, "headers: authorizedHeaders(options.headers),", "chat client forwards typed request headers without casting them");
assertNotIncludes(chatClient, "type HeaderRecord = Record<string, string>;", "chat client avoids narrowing valid fetch header inputs to plain records");
assertNotIncludes(chatClient, "as HeaderRecord", "chat client avoids casting settings request headers");
assertIncludes(chatClient, "function handleSocketMessage(rawData: string): void", "chat client socket handler narrows raw websocket data");
assertIncludes(chatClient, "const result = parseLiveSocketMessage(rawData);", "chat client delegates raw websocket parsing to the live socket adapter");
assertIncludes(chatClient, "if (result.kind === \"invalid\") {\n      setNotice(copy.value.notices.parseError, \"error\");\n      return;\n    }", "chat client preserves malformed websocket error notices");
assertIncludes(chatClient, "if (result.kind === \"unsupported\") {\n      return;\n    }\n    const { event } = result;", "chat client silently ignores unsupported events before dispatching the finite union");
assertNotIncludes(chatClient, "JSON.parse(rawData)", "chat client keeps raw JSON parsing outside the orchestrator");
assertIncludes(chatClient, "if (event.type === \"session\") {\n      const identity = normalizeLiveSessionIdentity(event.payload);", "chat client narrows session events before handling identity");
assertIncludes(chatClient, "const { sessionId, transportExternalChatId } = identity;", "chat client opens live sessions from normalized identity");
assertIncludes(chatClient, "const liveMessage = normalizeLiveAssistantMessage(\n        event.payload,\n        currentSession.value?.externalChatId,\n      );", "chat client receives a narrowed assistant message payload");
assertNotIncludes(chatClient, "const liveMessage = normalizeLiveAssistantMessage(payload, currentSession.value?.externalChatId);", "chat client avoids passing whole socket envelopes into assistant message handling");
assertIncludes(chatClient, "if (!shouldAcceptLivePayload(event.payload, liveMessage.externalChatId))", "chat client checks message routing against the narrowed event payload");
assertIncludes(chatClient, "const session = ensureSession(liveMessage.externalChatId, liveMessage.sessionId);", "chat client opens live message sessions from normalized message identity");
assertIncludes(chatClient, "if (event.type === \"run_event\") {\n      handleRunEvent(event.payload);", "chat client dispatches narrowed run event payloads");
assertNotIncludes(chatClient, "handleRunEvent(payload);", "chat client avoids passing whole socket envelopes into run event handling");
assertIncludes(chatClient, "if (event.type === \"session_status\") {\n      applySessionStatus(event.payload);", "chat client dispatches narrowed session status payloads");
assertNotIncludes(chatClient, "applySessionStatus(payload);", "chat client avoids passing whole socket envelopes into session status handling");
assertIncludes(chatClient, "addMessage(session.externalChatId, makeMessage(\"assistant\", liveMessage.text, \"OpenSprite\"));", "chat client appends live messages from normalized message text");
assertNotIncludes(chatClient, "addMessage(session.externalChatId, makeMessage(\"assistant\", String(payload.text || \"\"), \"OpenSprite\"));", "chat client avoids raw live message text reads in socket handler");
assertIncludes(chatClient, "setNotice(normalizeLiveSocketErrorMessage(event.payload, copy.value.notices.gatewayError), \"error\");", "chat client dispatches narrowed socket error payloads");
assertNotIncludes(chatClient, "setNotice(normalizeLiveSocketErrorMessage(payload, copy.value.notices.gatewayError), \"error\");", "chat client avoids passing whole socket envelopes into error handling");
assertNotIncludes(chatClient, "const payloadType = normalizeLiveSocketType(payload.type);", "chat client delegates event type routing to the live socket adapter");
assertNotIncludes(chatClient, "toLiveAssistantMessagePayload(payload)", "chat client delegates message projection to the live socket adapter");
assertNotIncludes(chatClient, "toLiveRunEventPayload(payload)", "chat client delegates run event projection to the live socket adapter");
assertNotIncludes(chatClient, "toLiveSessionStatusPayload(payload)", "chat client delegates status projection to the live socket adapter");
assertNotIncludes(chatClient, "toLiveSocketErrorPayload(payload)", "chat client delegates error projection to the live socket adapter");
assertNotIncludes(chatClient, "const payloadType = String(payload.type || \"\").trim();", "chat client avoids raw live socket type reads in socket handler");
assertNotIncludes(chatClient, "setNotice(String(payload.error || copy.value.notices.gatewayError), \"error\");", "chat client avoids raw live socket error reads in socket handler");
assertNotIncludes(chatClient, "const sessionId = liveSessionId(payload);\n    const channel = liveChannel(payload, sessionId);", "chat client avoids repeated raw live identity reads in socket handlers");
assertIncludes(chatClient, "function connectSocket(): void", "chat client types socket connection helper");
assertIncludes(chatClient, "let socketUrl: string;", "chat client avoids implicit any socket URL state");
assertIncludes(chatClient, "socket.addEventListener(\"message\", (event: MessageEvent) => {", "chat client types websocket message events");
assertIncludes(chatClient, "if (typeof event.data !== \"string\") {", "chat client guards websocket message data before JSON parsing");
assertIncludes(chatClient, "function resizeComposer(): void", "chat client types composer resize helper");
assertIncludes(chatClient, "function scrollMessagesToBottom(options: ScrollOptions = {}): void", "chat client types message scroll helper");
assertIncludes(chatClient, "function createNewChat(): void", "chat client types new chat creation helper");
assertIncludes(chatClient, "type DeletedSessionIdentity = {\n  sessionId?: unknown;\n  externalChatId?: unknown;\n  transportExternalChatId?: unknown;\n};", "chat client keeps deleted session identity as an explicit tombstone boundary");
assertNotIncludes(chatClient, "type DeletedSessionIdentity = SessionIdentity;", "chat client avoids aliasing deleted session identities to live session identities");
assertIncludes(chatClient, "function isDeletedSessionIdentity(identity: DeletedSessionIdentity = {}): boolean", "chat client types deleted session identity guard");
assertIncludes(chatClient, "function reconnectSocketSoon(): void", "chat client types deferred reconnect helper");
assertIncludes(chatClient, "function ensureActiveAfterSessionRemoval(preferWeb = false): void", "chat client types active-session repair helper");
assertIncludes(chatClient, "async function clearWebSessions(): Promise<void>", "chat client types web session cleanup helper");
assertIncludes(chatClient, "setNotice(settingsErrorMessage(error, copy.value.notices.sessionDeleteFailed), \"warning\");", "chat client narrows web session cleanup errors");
assertIncludes(chatClient, "function normalizeCommandCatalog(payload: CommandCatalogPayload | null): CommandCatalogItem[]", "chat client normalizes nullable command catalog payloads at one typed boundary");
assertIncludes(chatClient, "const commands = Array.isArray(payload?.commands) ? payload.commands : [];", "chat client keeps malformed and missing command lists empty");
assertNotIncludes(chatClient, "function normalizeCommandCatalogItems", "chat client avoids a redundant command catalog list normalizer");
assertIncludes(chatClientApiPayloads, "export type CommandCatalogItemPayload = {", "API payload adapter types command catalog item fields");
assertIncludes(chatClientApiPayloads, "name: string;\n  command: string;\n  usage: string;\n  description: string;\n  category: string;\n  subcommands: string[];", "API payload adapter stores normalized command item fields");
assertNotIncludes(chatClient, "type CommandCatalogItemPayload = {", "chat client delegates command item payload ownership to the adapter");
assertNotIncludes(chatClientApiPayloads, "type CommandCatalogApiItem", "API payload adapter avoids redundant command item aliases");
assertIncludes(chatClientApiPayloads, "export function toCommandCatalogItemPayload(value: unknown): CommandCatalogItemPayload | null", "API payload adapter narrows command catalog items");
assertIncludes(chatClientApiPayloads, "const payload = toPayloadSource<CommandCatalogItemPayload>(value);", "API payload adapter limits command item reads to known fields");
assertIncludes(chatClientApiPayloads, "const name = String(payload.name || \"\").trim();\n  const command = String(payload.command || (name ? `/${name}` : \"\")).trim();", "API payload adapter normalizes command item identity fields");
assertIncludes(chatClientApiPayloads, "usage: String(payload.usage || command).trim() || command,\n    description: String(payload.description || \"\").trim(),\n    category: String(payload.category || \"\").trim(),\n    subcommands: coerceStringList(payload.subcommands),", "API payload adapter normalizes command item detail fields");
assertNotIncludes(chatClient, "function toCommandCatalogItemPayload", "chat client delegates command item projection to the adapter");
assertIncludes(chatClient, "const commandItem = toCommandCatalogItemPayload(item);", "chat client routes command catalog items through the named boundary");
assertIncludes(chatClient, "if (!commandItem || !commandItem.name || !commandItem.command.startsWith(\"/\"))", "chat client validates normalized command catalog items before state storage");
assertIncludes(chatClient, "return commandItem;", "chat client stores normalized command catalog items directly");
assertNotIncludes(chatClient, "const commandItem = toJsonRecord(item);", "chat client avoids inline command catalog item records");
assertIncludes(chatClientHistoryPayloads, "function normalizeSessionHistoryCount(value: unknown, fallback: number): number", "history payload adapter normalizes count scalars at the API boundary");
assertIncludes(chatClientHistoryPayloads, "function normalizeSessionHistoryChannelTotals(value: unknown, fallbackTotal: number): SessionHistoryChannelTotals", "history payload adapter normalizes dynamic channel totals before output");
assertIncludes(chatClientHistoryPayloads, "export function normalizeSessionHistoryMetrics(\n  payload: SessionHistoryPayload | null,\n  fallbackCount: number,\n): SessionHistoryMetrics", "history payload adapter exposes normalized session history metrics");
assertNotIncludes(chatClient, "function normalizeSessionHistoryCount", "chat client delegates history count normalization");
assertNotIncludes(chatClient, "function normalizeSessionHistoryCounts", "chat client delegates history metric normalization");
assertNotIncludes(chatClient, "function normalizeSessionHistoryChannelTotals", "chat client delegates channel total normalization");
assertNotIncludes(chatClient, "function normalizeSessionHistoryChannelTotalsPayload", "chat client avoids a redundant channel totals normalizer wrapper");
assertIncludes(chatClientHistoryPayloads, "type SessionHistoryChannelTotalsSource = Record<string, unknown>;", "history payload adapter names the legitimate dynamic source map");
assertIncludes(chatClientHistoryPayloads, "export type SessionHistoryMetrics = {\n  total: number;\n  limit: number;\n  channelTotals: SessionHistoryChannelTotals;\n};", "history payload adapter exposes finite numeric metrics");
assertNotIncludes(chatClientHistoryPayloads, "export type SessionHistoryChannelTotalsSource", "history payload adapter keeps the raw dynamic map private");
assertIncludes(chatClientHistoryPayloads, "const source = toPayloadSource<SessionHistoryChannelTotalsSource>(value);", "history payload adapter guards dynamic channel totals at one boundary");
assertNotIncludes(chatClient, "const record = toJsonRecord(value);", "chat client avoids inline session history channel total records");
assertIncludes(chatClient, "function normalizeSessionHistorySessions(sessions: Array<HistorySessionPayload | null>): ChatSession[]", "chat client receives projected session history items with position-preserving nulls");
assertIncludes(chatClient, "function normalizeSessionHistoryPayload(payload: SessionHistoryPayload | null): NormalizedSessionHistoryPayload", "chat client centralizes session history response normalization");
assertIncludes(chatClient, "const sessions = normalizeSessionHistorySessions(payload?.sessions || []);", "chat client consumes the adapter-projected session list directly");
assertIncludes(chatClient, "const metrics = normalizeSessionHistoryMetrics(payload, sessions.length);", "chat client derives session history metric fallbacks through the adapter");
assertIncludes(chatClient, "sessions,\n      ...metrics,", "chat client consumes only normalized history metrics");
assertIncludes(chatClientHistoryPayloads, "payload?.channel_totals ?? payload?.channelTotals,", "history payload adapter resolves channel total aliases");
assertIncludes(chatClientHistoryPayloads, "export function toSessionClearPayload(value: unknown): SessionClearPayload | null", "history payload adapter narrows session clear payloads");
assertIncludes(chatClientHistoryPayloads, "deleted: payload.deleted,\n    deleted_count: payload.deleted_count,\n    deletedCount: payload.deletedCount,", "history payload adapter projects session clear fields");
assertIncludes(chatClientHistoryPayloads, "const payload = toPayloadSource<SessionClearPayload>(value);\n  if (!payload) {\n    return null;\n  }", "history payload adapter rejects non-object session clear responses");
assertIncludes(chatClient, "function normalizeSessionClearPayload(payload: SessionClearPayload | null): SessionClearResult", "chat client normalizes nullable session clear payloads after API projection");
assertIncludes(chatClient, "deleted: coerceNonNegativeInteger(payload?.deleted ?? payload?.deleted_count ?? payload?.deletedCount),", "chat client keeps malformed session clear responses at zero deleted sessions");
assertIncludes(chatClientRunPayloads, "export function toRunFileChangeRevertPayload(value: unknown): RunFileChangeRevertPayload | null", "run payload adapter narrows file revert payloads");
assertIncludes(chatClient, "function normalizeRunFileChangeRevertPayload(payload: RunFileChangeRevertPayload | null): RunFileChangeRevertPayload", "chat client only supplies a typed fallback for invalid file revert roots");
assertIncludes(chatClient, "channelTotals: {},", "chat client initializes session history channel totals through typed root state");
assertNotIncludes(chatClient, "channelTotals: {} as SessionHistoryChannelTotals,", "chat client avoids assertion-based session history channel totals initialization");
assertIncludes(chatClient, "const total = state.sessionHistory.channelTotals[key] ?? state.sessionHistory.total;", "chat client reads numeric session history totals without late coercion");
assertIncludes(chatClient, "./chatClientCronPayloads", "chat client imports the dedicated cron API payload boundary");
assertIncludes(chatClientCronPayloads, "import { toPayloadSource } from \"./payloadBoundary\";", "cron payload adapter reuses the shared finite object guard");
assertNotIncludes(chatClientCronPayloads, "type PayloadSource<Payload extends object>", "cron payload adapter avoids another local payload source type");
assertNotIncludes(chatClientCronPayloads, "function toPayloadSource<Payload extends object>", "cron payload adapter avoids another local payload source guard");
assertIncludes(chatClientCronPayloads, "import type { CronJobView } from \"./useSettingsState\";", "cron payload adapter targets the finite settings-state job view");
assertIncludes(chatClientCronPayloads, "type CronJobsSourcePayload = { jobs?: unknown };", "cron payload adapter owns the raw jobs response boundary");
assertIncludes(chatClientCronPayloads, "type CronJobScheduleSourcePayload = {", "cron payload adapter owns finite raw schedule fields");
assertIncludes(chatClientCronPayloads, "type CronJobMessageSourcePayload = {", "cron payload adapter owns finite raw message fields");
assertIncludes(chatClientCronPayloads, "type CronJobStateSourcePayload = {", "cron payload adapter owns finite raw state fields");
assertIncludes(chatClientCronPayloads, "type CronJobSourcePayload = {", "cron payload adapter owns finite raw job fields");
assertIncludes(chatClientCronPayloads, "export type CronJobsPayload = {\n  jobs: CronJobView[];\n};", "cron payload adapter exposes only normalized job views");
assertNotIncludes(chatClientCronPayloads, "export type CronJobScheduleSourcePayload", "cron payload adapter keeps raw schedule sources private");
assertNotIncludes(chatClientCronPayloads, "export type CronJobMessageSourcePayload", "cron payload adapter keeps raw message sources private");
assertNotIncludes(chatClientCronPayloads, "export type CronJobStateSourcePayload", "cron payload adapter keeps raw state sources private");
assertNotIncludes(chatClientCronPayloads, "export type CronJobSourcePayload", "cron payload adapter keeps raw job sources private");
assertNotIncludes(chatClient, "function toCronJobsPayload", "chat client delegates cron response projection to the adapter");
assertNotIncludes(chatClientCronPayloads, "JsonRecord", "cron payload adapter avoids open-ended JSON records");
assertNotIncludes(chatClientCronPayloads, "type CronJobsListPayload", "cron payload adapter avoids duplicate jobs wrappers");
assertNotIncludes(chatClientCronPayloads, "type CronJobsApiPayload", "cron payload adapter avoids redundant jobs API aliases");
assertNotIncludes(chatClientCronPayloads, "type CronJobApiRecord", "cron payload adapter avoids redundant job record aliases");
assertIncludes(chatClientCronPayloads, "export function toCronJobsPayload(value: unknown): CronJobsPayload | null", "cron payload adapter projects jobs responses");
assertIncludes(chatClientCronPayloads, "const payload = toPayloadSource<CronJobsSourcePayload>(value);\n  if (!payload) {\n    return null;\n  }", "cron payload adapter rejects non-object jobs responses");
assertIncludes(chatClientCronPayloads, "function normalizeCronJobSchedule(value: unknown): CronJobView[\"schedule\"]", "cron payload adapter normalizes finite schedule sources");
assertIncludes(chatClientCronPayloads, "function normalizeCronJobMessage(value: unknown): CronJobView[\"payload\"]", "cron payload adapter normalizes finite message sources");
assertIncludes(chatClientCronPayloads, "function normalizeCronJobState(value: unknown): CronJobView[\"state\"]", "cron payload adapter normalizes finite state sources");
assertIncludes(chatClientCronPayloads, "function normalizeCronJob(value: unknown): CronJobView | null", "cron payload adapter normalizes individual job records");
assertIncludes(chatClientCronPayloads, "const schedule = normalizeCronJobSchedule(job.schedule);\n  const payload = normalizeCronJobMessage(job.payload);", "cron payload adapter normalizes nested job fields before output");
assertIncludes(chatClientCronPayloads, "id: textField(job.id),\n    name: textField(job.name),\n    enabled: coerceBoolean(job.enabled),", "cron payload adapter normalizes job identity fields");
assertIncludes(chatClientCronPayloads, "session_id: textField(job.session_id || job.sessionId),", "cron payload adapter resolves session id aliases");
assertIncludes(chatClientCronPayloads, "state: normalizeCronJobState(job.state),", "cron payload adapter normalizes nested job state");
assertIncludes(chatClientCronPayloads, "const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];\n  return {\n    jobs: jobs.map(normalizeCronJob).filter((job): job is CronJobView => job !== null),\n  };", "cron payload adapter filters and exposes only normalized jobs");
assertNotIncludes(chatClientCronPayloads, "...job", "cron payload adapter does not leak raw job aliases into settings state");
assertNotIncludes(chatClient, "function normalizeCronJobSchedule", "chat client delegates cron schedule normalization");
assertNotIncludes(chatClient, "function normalizeCronJobPayload", "chat client delegates cron message normalization");
assertNotIncludes(chatClient, "function normalizeCronJobState", "chat client delegates cron state normalization");
assertNotIncludes(chatClient, "function normalizeCronJob(value", "chat client delegates cron job normalization");
assertNotIncludes(chatClient, "function normalizeCronJobs", "chat client delegates cron job collection normalization");
assertIncludes(chatClient, "function applyCommandHint(command: CommandCatalogItem)", "chat client applies typed command hints");
assertNotIncludes(chatClient, "state.commandCatalog.commands = Array.isArray(payload.commands)", "chat client avoids raw command catalog array checks in loader");
assertIncludes(chatClient, "async function requestSettingsJson(pathname: string, options: RequestInit = {}): Promise<unknown>", "chat client settings request helper exposes unknown payloads");
assertIncludes(chatClient, "const payload = await requestSettingsJsonFromApi(state.wsUrl, pathname, {", "chat client delegates settings requests without selecting a response type");
assertNotIncludes(chatClient, "requestSettingsJsonFromApi<T>", "chat client avoids trusting unchecked settings response generics");
assertNotIncludes(chatClient, "type AnyRecord", "chat client no longer exposes AnyRecord as the default settings response");
assertNotIncludes(chatClient, "type CommandCatalogPayload = { commands?: unknown[] };", "chat client avoids typed-array assumptions for command catalog responses");
assertIncludes(chatClient, "const payload = toCommandCatalogPayload(await requestSettingsJson(\"/api/commands\"));", "chat client keeps command catalog API data unknown until projection");
assertNotIncludes(chatClient, "requestSettingsJson<CommandCatalogPayload>(\"/api/commands\")", "chat client avoids trusting an unchecked command catalog response generic");
assertNotIncludes(chatClient, "const payload = await requestSettingsJson<CommandCatalogPayload>(\"/api/commands\");", "chat client avoids direct command catalog response field reads");
assertIncludes(chatClient, "state.commandCatalog.commands = normalizeCommandCatalog(payload);", "chat client assigns only normalized command catalog items to state");
assertIncludes(chatClient, "toRunTracePayload(await requestSettingsJson(buildRunTracePath(run.runId, sessionId)))", "chat client keeps run trace API data unknown until projection");
assertNotIncludes(chatClient, "requestSettingsJson<RunTracePayload>(buildRunTracePath(run.runId, sessionId))", "chat client avoids trusting an unchecked run trace response generic");
assertNotIncludes(chatClient, "const payload = await requestSettingsJson<RunTracePayload>(buildRunTracePath(run.runId, sessionId));", "chat client avoids direct run trace response field reads");
assertIncludes(chatClientRunPayloads, "function normalizeRunTraceEvents(value: unknown): TraceEventView[]", "run payload adapter narrows trace events at the field boundary");
assertNotIncludes(chatClient, "function normalizeRunTraceEvents", "chat client delegates trace event collection normalization");
assertIncludes(chatClient, "id: `${runId}-raw-${eventType}-${createdAt}-${randomToken()}`", "chat client assigns typed live raw run event ids at normalization");
assertIncludes(chatClient, "const rawEvent = traceEventFromLiveRunEvent(liveEvent);", "chat client stores live raw run events through typed trace event projection");
assertNotIncludes(chatClient, "const rawEvent: TraceEventView = {", "chat client avoids rebuilding raw trace events inline in the handler");
assertIncludes(chatClientRunPayloads, "function normalizeRunTraceFileChanges(value: unknown): TraceFileChangeView[]", "run payload adapter narrows trace file changes at the field boundary");
assertNotIncludes(chatClient, "function normalizeRunTraceFileChanges", "chat client delegates trace file-change collection normalization");
assertIncludes(chatClient, "const preview: TraceFileChangeView = {", "chat client keeps live artifact file change previews typed");
assertIncludes(chatClient, "schemaVersion: 0,\n      kind: \"file\",\n      state: previewStatus,\n      status: previewStatus,", "chat client fills typed file change preview fields");
assertIncludes(chatClient, "normalizeRunArtifactMetadata,", "chat client imports run artifact metadata normalizer");
assertIncludes(chatClient, "type RunArtifactMetadata,", "chat client imports typed run artifact metadata");
assertIncludes(chatClient, "normalizeTracePartMetadata,", "chat client imports trace part metadata normalizer");
assertIncludes(chatClient, "type TracePartMetadata,", "chat client imports typed trace part metadata");
assertIncludes(chatClientRunPayloads, "function normalizeRunTraceParts(value: unknown): TracePartView[]", "run payload adapter narrows trace parts at the field boundary");
assertIncludes(chatClientRunPayloads, "function normalizeRunTraceArtifacts(value: unknown): RunArtifactView[]", "run payload adapter narrows trace artifacts at the field boundary");
assertNotIncludes(chatClient, "function normalizeRunTraceParts", "chat client delegates trace part collection normalization");
assertNotIncludes(chatClient, "function normalizeRunTraceArtifacts", "chat client delegates trace artifact collection normalization");
assertIncludes(chatClient, "type RunTraceFallbackArtifactSource = {\n  artifact: RunArtifactView | null;\n};", "chat client types fallback artifact sources explicitly");
assertIncludes(chatClient, "function collectRunTraceFallbackArtifacts(...sources: RunTraceFallbackArtifactSource[][]): RunArtifactView[]", "chat client keeps fallback run trace artifacts typed");
assertNotIncludes(chatClient, "function normalizeRunTraceEventCountsPayload", "chat client delegates trace event-count normalization");
assertNotIncludes(chatClient, "function normalizeRunTraceDiffSummaryPayload", "chat client delegates trace diff-summary normalization");
assertIncludes(chatClient, "function normalizeRunTracePayload(payload: RunTracePayload | null): RunTracePayload", "chat client limits run trace handling to a typed empty fallback");
assertIncludes(chatClient, "return payload || {\n    rawEvents: [],\n    fileChanges: [],\n    parts: [],\n    artifacts: [],", "chat client preserves empty trace behavior for invalid root responses");
assertIncludes(chatClientRunPayloads, "fileChanges: normalizeRunTraceFileChanges(payload.file_changes || payload.fileChanges),", "run payload adapter resolves run trace file-change aliases");
assertIncludes(chatClientRunPayloads, "eventCounts: normalizeTraceEventCounts(payload.event_counts || payload.eventCounts, rawEvents),", "run payload adapter resolves run trace event-count aliases");
assertIncludes(chatClientRunPayloads, "diffSummary: normalizeDiffSummary(payload.diff_summary || payload.diffSummary),", "run payload adapter resolves run trace diff-summary aliases");
assertNotIncludes(chatClient, "function collectRunTraceFallbackArtifacts(...sources: RunJsonObject[][]): RunArtifactView[]", "chat client avoids generic fallback run trace artifact sources");
assertNotIncludes(chatClient, "function collectRunTraceFallbackArtifacts(...sources: RunJsonObject[][]): RunJsonObject[]", "chat client avoids generic fallback run trace artifact state");
assertIncludes(chatClient, "const trace = normalizeRunTracePayload(", "chat client normalizes the complete run trace before state assignment");
assertIncludes(chatClient, "const { rawEvents, fileChanges, parts, artifacts } = trace;", "chat client consumes typed normalized run trace collections");
assertIncludes(chatClient, "const traceWatermark = captureRunTraceWatermark(run);", "chat client captures a run trace watermark before the request");
assertIncludes(chatClient, "const mergedTrace = mergeRunTraceSnapshot(", "chat client merges normalized trace snapshots with concurrent live state");
assertIncludes(chatClient, "run.diffSummary = trace.diffSummary;", "chat client assigns the normalized run trace diff summary");
assertNotIncludes(chatClient, "toRunTraceEventsPayload(payload)", "chat client no longer projects run trace events in the loader");
assertNotIncludes(chatClient, "toRunTraceFileChangesPayload(payload)", "chat client no longer projects run trace file changes in the loader");
assertNotIncludes(chatClient, "toRunTracePartsPayload(payload)", "chat client no longer projects run trace parts in the loader");
assertNotIncludes(chatClient, "toRunTraceArtifactsPayload(payload)", "chat client no longer projects run trace artifacts in the loader");
assertIncludes(chatClient, ": collectRunTraceFallbackArtifacts(rawEvents, parts, fileChanges).slice(-MAX_RUN_ARTIFACTS);", "chat client uses narrowed fallback run trace artifacts");
assertNotIncludes(chatClient, "run.eventCounts = normalizeTraceEventCounts(payload.event_counts || payload.eventCounts, rawEvents);", "chat client avoids raw run trace event count reads in loader");
assertNotIncludes(chatClient, "run.diffSummary = normalizeDiffSummary(payload.diff_summary || payload.diffSummary);", "chat client avoids raw run trace diff summary reads in loader");
assertNotIncludes(chatClient, "Array.isArray(payload?.events)", "chat client avoids direct run trace event array checks in loader");
assertNotIncludes(chatClient, "Array.isArray(payload?.file_changes || payload?.fileChanges)", "chat client avoids direct run trace file change array checks in loader");
assertNotIncludes(chatClient, "Array.isArray(payload?.parts)", "chat client avoids direct run trace part array checks in loader");
assertNotIncludes(chatClient, "Array.isArray(payload?.artifacts)", "chat client avoids direct run trace artifact array checks in loader");
assertIncludes(chatClient, "toSessionHistoryPayload(await requestSettingsJson(`/api/sessions?${params.toString()}`))", "chat client keeps session history API data unknown until projection");
assertNotIncludes(chatClient, "requestSettingsJson<SessionHistoryPayload>(`/api/sessions?${params.toString()}`)", "chat client avoids trusting an unchecked session history response generic");
assertNotIncludes(chatClient, "const payload = await requestSettingsJson<SessionHistoryPayload>(`/api/sessions?${params.toString()}`);", "chat client avoids direct session history response field reads");
assertIncludes(chatClient, "const history = normalizeSessionHistoryPayload(", "chat client normalizes the complete session history before state assignment");
assertIncludes(chatClient, "state.sessionHistory.total = history.total;", "chat client assigns normalized session history totals");
assertIncludes(chatClient, "state.sessionHistory.limit = history.limit;", "chat client assigns normalized session history limits");
assertIncludes(chatClient, "state.sessionHistory.channelTotals = history.channelTotals;", "chat client assigns normalized session history channel totals");
assertIncludes(chatClient, "mergeHistorySessions(history.sessions, {", "chat client merges typed normalized session history sessions");
assertNotIncludes(chatClient, "state.sessionHistory.total = normalizeSessionHistoryCount(payload.total, historySessions.length);", "chat client avoids direct session history total field reads in loader");
assertNotIncludes(chatClient, "state.sessionHistory.limit = normalizeSessionHistoryCount(payload.limit, historySessions.length);", "chat client avoids direct session history limit field reads in loader");
assertNotIncludes(chatClient, "state.sessionHistory.channelTotals = normalizeSessionHistoryChannelTotals(\n        payload.channel_totals ?? payload.channelTotals,\n        state.sessionHistory.total,\n      );", "chat client avoids direct session history channel-total field reads in loader");
assertNotIncludes(chatClient, "toSessionHistorySessionsPayload(payload)", "chat client no longer projects session history sessions in the loader");
assertNotIncludes(chatClient, "toSessionHistoryCountsPayload(payload)", "chat client no longer projects session history counts in the loader");
assertNotIncludes(chatClient, "toSessionHistoryChannelTotalsResponsePayload(payload)", "chat client no longer projects session history channel totals in the loader");
assertNotIncludes(chatClient, "const historySessions = Array.isArray(payload.sessions)", "chat client avoids direct session history array checks in loader");
assertIncludes(chatClient, "const payload = toCronJobsPayload(await requestSettingsJson(\"/api/cron/jobs\"));", "chat client keeps cron jobs API data unknown until projection");
assertNotIncludes(chatClient, "requestSettingsJson<CronJobsPayload>(\"/api/cron/jobs\")", "chat client avoids trusting an unchecked cron jobs response generic");
assertNotIncludes(chatClient, "const payload = await requestSettingsJson<CronJobsPayload>(\"/api/cron/jobs\");", "chat client avoids direct cron jobs response field reads");
assertIncludes(chatClient, "settingsState.cronJobs = payload?.jobs || [];", "chat client assigns only adapter-normalized cron jobs to state");
assertIncludes(chatClient, "const payload = toSessionClearPayload(\n        await requestSettingsJson(buildSessionsClearPath(\"web\"), { method: \"DELETE\" }),\n      );", "chat client keeps session clear API data unknown until projection");
assertNotIncludes(chatClient, "requestSettingsJson<SessionClearPayload>(buildSessionsClearPath(\"web\")", "chat client avoids trusting an unchecked session clear response generic");
assertNotIncludes(chatClient, "const payload = await requestSettingsJson<SessionClearPayload>(buildSessionsClearPath(\"web\"), { method: \"DELETE\" });", "chat client avoids direct session clear response normalization");
assertIncludes(chatClient, "const clearResult = normalizeSessionClearPayload(payload);", "chat client normalizes session clear response before notices");
assertIncludes(chatClient, "copy.value.notices.sessionsCleared(clearResult.deleted)", "chat client uses normalized session clear deleted count");
assertNotIncludes(chatClient, "Number(payload?.deleted || 0)", "chat client avoids late coercion of session clear deleted count");
assertIncludes(chatClient, "const payload = toRunFileChangeRevertPayload(\n        await requestSettingsJson(buildRunFileChangeRevertPath(run.runId, sessionId, changeId), {", "chat client keeps file revert API data unknown until projection");
assertNotIncludes(chatClient, "requestSettingsJson<RunFileChangeRevertPayload>(buildRunFileChangeRevertPath", "chat client avoids trusting an unchecked file revert response generic");
assertNotIncludes(chatClient, "const payload = await requestSettingsJson<RunFileChangeRevertPayload>(buildRunFileChangeRevertPath(run.runId, sessionId, changeId), {", "chat client avoids direct file revert response normalization");
assertIncludes(chatClientRunPayloads, "const payload = toPayloadSource<RunFileChangeRevertSourcePayload>(value);\n  if (!payload) {\n    return null;\n  }", "run payload adapter rejects non-object file revert responses");
assertIncludes(chatClientRunPayloads, "const revert = normalizeRunFileChangeRevertRecord(payload.revert, payload);", "run payload adapter normalizes nested revert records before output");
assertIncludes(chatClientRunPayloads, "revert,\n    applied: revert.applied,\n    reason: revert.reason || textField(payload.reason),", "run payload adapter exposes a fully normalized file revert result");
assertIncludes(chatClientRunPayloads, "type RunFileChangeRevertRecordSourcePayload = {", "run payload adapter owns the raw nested file revert boundary");
assertNotIncludes(chatClientRunPayloads, "type RunFileChangeRevertApiRecord", "run payload adapter keeps one nested file revert boundary");
assertIncludes(chatClientRunPayloads, "export type RunFileChangeRevertRecord = {\n  applied: boolean;\n  reason: string;\n};", "run payload adapter exposes the normalized file revert record");
assertNotIncludes(chatClient, "type RunFileChangeRevertRecord = {", "chat client reuses the adapter-owned file revert record");
assertIncludes(chatClientRunPayloads, "function normalizeRunFileChangeRevertRecord(\n  value: unknown,\n  fallback: RunFileChangeRevertRecordSourcePayload,\n): RunFileChangeRevertRecord", "run payload adapter narrows and normalizes nested file revert records");
assertIncludes(chatClientRunPayloads, "applied: coerceBoolean(source.applied),\n    reason: textField(source.reason),", "run payload adapter normalizes nested file revert scalar fields");
assertNotIncludes(chatClient, "function toRunFileChangeRevertRecordPayload", "chat client delegates nested file revert projection to the adapter");
assertNotIncludes(chatClient, "function normalizeRunFileChangeRevertRecord", "chat client delegates nested file revert normalization to the run adapter");
assertIncludes(chatClient, "return payload || {\n    revert: null,\n    applied: false,\n    reason: \"\",", "chat client keeps malformed file revert roots unsuccessful");
assertNotIncludes(chatClient, "type RunFileChangeRevertRecord = RunJsonObject & {", "chat client avoids generic file revert result intersections");
assertNotIncludes(chatClient, "const revertRecord = toJsonRecord(payload.revert);", "chat client avoids inline nested file revert payload records");
assertNotIncludes(chatClient, "function normalizeSessionClearPayload(value: unknown): SessionClearResult {\n  const payload = toJsonRecord(value) || {};", "chat client avoids inline session clear payload records");
assertNotIncludes(chatClient, "function normalizeRunFileChangeRevertPayload(value: unknown)", "chat client avoids unknown file revert normalization");
assertNotIncludes(chatClient, "...(revertRecord || {}),", "chat client avoids carrying raw file revert fields into UI state");
assertIncludes(chatClient, "function toggleSettingsConnection(shouldConnect: boolean)", "chat client types settings connection toggle input");
assertIncludes(chatClient, "async function cancelRun(run: RunViewState | null | undefined): Promise<void>", "chat client types run cancellation input");
assertIncludes(chatClient, "setNotice(settingsErrorMessage(error, copy.value.notices.cancelFailed), \"error\");", "chat client narrows cancel run errors");
assertIncludes(chatClient, "async function revertRunFileChange(\n    run: RunViewState | null | undefined,\n    change: TraceFileChangeView | null | undefined,\n  ): Promise<RunFileChangeRevertRecord | null>", "chat client types file revert action inputs");
assertNotIncludes(chatClient, "change: RunJsonObject | null | undefined,\n  ): Promise<RunJsonObject | null>", "chat client avoids generic file revert input");
assertIncludes(chatClient, "const changeId = String(change?.changeId || change?.sourceId || \"\").trim();", "chat client narrows file revert change ids");
assertIncludes(chatClient, "const revertResult = normalizeRunFileChangeRevertPayload(payload);", "chat client normalizes file revert response before notices");
assertIncludes(chatClient, "if (!revertResult.applied) {", "chat client checks normalized file revert result");
assertIncludes(chatClient, "setNotice(revertResult.reason || copy.value.runFileInspector.revertUnavailable, \"warning\");", "chat client uses normalized file revert reason");
assertNotIncludes(chatClient, "const revert = payload.revert || null;", "chat client avoids raw file revert result reads");
assertNotIncludes(chatClient, "if (!revert?.applied)", "chat client avoids late coercion of file revert applied flag");
assertIncludes(chatClient, "setNotice(settingsErrorMessage(error, copy.value.runFileInspector.revertFailed), \"error\");", "chat client narrows file revert errors");
assertIncludes(chatClient, "function normalizeOutgoingMessage(rawValue: unknown): OutgoingMessagePayload", "chat client types outgoing message normalization boundary");
assertIncludes(chatClient, "const rawRecord = toOutgoingMessageInputPayload(rawValue);", "chat client routes outgoing message inputs through the named boundary");
assertNotIncludes(chatClient, "const rawRecord = toJsonRecord(rawValue);", "chat client avoids inline outgoing message input records");
assertIncludes(chatClient, "metadata: rawRecord.metadata,", "chat client reads normalized outgoing message metadata from the input boundary");
assertNotIncludes(chatClient, "metadata: toOutgoingMessageMetadata(rawRecord.metadata),", "chat client avoids re-normalizing outgoing message metadata after input projection");
assertIncludes(chatClient, "function sendMessageText(rawText: unknown, { clearComposer = false }: SendMessageOptions = {}): boolean", "chat client types send message input and result");
assertIncludes(chatClient, "const outgoingMetadata: OutgoingMessageMetadata = {", "chat client keeps outgoing metadata behind the named boundary");
assertIncludes(chatClient, "function submitMessage(event: ComposerSubmitEvent): void", "chat client types composer submit handler");
assertIncludes(chatClient, "function handleComposerKeydown(event: ComposerKeyboardEvent): void", "chat client types composer key handler");
assertIncludes(chatClient, "function applyPrompt(text: string): void", "chat client types prompt application text");
assertIncludes(chatClient, "function applyCommandHint(command: CommandCatalogItem): void", "chat client applies typed command hints");
assertIncludes(chatClient, "function handleGlobalKeydown(event: KeyboardEvent): void", "chat client types global keyboard handler");
assertIncludes(chatClient, "function setSettingsSuccess(noticeKey: string, text: string): void", "chat client types generic settings success notices");
assertIncludes(chatClient, "session.runsError = settingsErrorMessage(error, copy.value.notices.runHistoryLoadFailed);", "chat client narrows run history load errors");
assertIncludes(chatClient, "function normalizeRunsPayload(payload: RunsPayload | null): RunViewState[]", "chat client normalizes nullable run history payloads at one typed boundary");
assertIncludes(chatClient, "function shouldBackfillSessionRuns(session: ChatSession | null | undefined): boolean", "chat client types run backfill predicate");
assertIncludes(chatClient, "function getActiveCronSessionId(): string", "chat client types active cron session id helper");
assertIncludes(chatClient, "function formatDateTimeLocal(timestampMs: unknown): string", "chat client narrows local datetime formatting input");
assertIncludes(chatClient, "function resetCronJobForm(): void", "chat client types cron form reset");
assertIncludes(chatClient, "import { DEFAULT_CRON_TIMEZONE, normalizeCronJobMode, type CronJobAction, type CronJobMode } from \"./scheduleDefaults\";", "chat client imports typed cron job action and mode boundary");
assertIncludes(chatClient, "kind: CronJobMode;", "chat client narrows cron job payload kind");
assertIncludes(chatClient, "async function loadCronJobs(): Promise<void>", "chat client types cron jobs loader");
assertIncludes(chatClient, "settingsState.cronJobsError = settingsErrorMessage(error, copy.value.notices.cronJobsLoadFailed);", "chat client narrows cron jobs load errors");
assertIncludes(chatClient, "function beginCronJobEdit(job: CronJobView): void", "chat client types cron job edit input");
assertIncludes(chatClient, "const schedule = job.schedule;", "chat client consumes normalized cron job schedule records");
assertIncludes(chatClient, "const payload = job.payload;", "chat client consumes normalized cron job payload records");
assertNotIncludes(chatClient, "toJsonRecord(job.schedule)", "chat client does not re-narrow normalized cron job schedules");
assertNotIncludes(chatClient, "toJsonRecord(job.payload)", "chat client does not re-narrow normalized cron job payloads");
assertIncludes(chatClient, "settingsState.cronJobForm.mode = normalizeCronJobMode(schedule.kind);", "chat client normalizes edited cron job mode");
assertIncludes(chatClient, "const everyMs = Number(schedule.every_ms);", "chat client narrows cron interval milliseconds");
assertIncludes(chatClient, "function cancelCronJobEdit(): void", "chat client types cron edit cancel handler");
assertIncludes(chatClient, "function beginCronJobCreate(): void", "chat client types cron create handler");
assertIncludes(chatClient, "async function saveCronJob(): Promise<void>", "chat client types cron job save handler");
assertIncludes(chatClient, "settingsState.cronJobsError = settingsErrorMessage(error, copy.value.notices.cronJobSaveFailed);", "chat client narrows cron job save errors");
assertIncludes(chatClient, "async function runCronJobAction(job: CronJobView, action: CronJobAction): Promise<void>", "chat client narrows cron job action handler");
assertIncludes(chatClient, "const jobId = String(job.id || \"\").trim();", "chat client narrows cron job ids before URL building");
assertIncludes(chatClient, "settingsState.cronJobsError = settingsErrorMessage(error, copy.value.notices.cronJobActionFailed);", "chat client narrows cron job action errors");
assertIncludes(chatClient, "async function loadCurrentSessionRuns({ force = false }: LoadRunsOptions = {}): Promise<void>", "chat client types current session run loader");
assertIncludes(chatClientHistoryPayloads, "export function toHistoryRunPayloadList(value: unknown): Array<HistoryRunPayload | null>", "history payload adapter owns reusable run collection projection");
assertIncludes(chatClient, "function normalizeRunList(runs: Array<HistoryRunPayload | null>): RunViewState[]", "chat client normalizes only projected run list items");
assertIncludes(chatClient, "function normalizeRunsPayload(payload: RunsPayload | null): RunViewState[] {\n    return normalizeRunList(toHistoryRunPayloadList(payload?.runs));\n  }", "chat client routes current run lists through the history adapter collection boundary");
assertIncludes(chatClient, "const payload = toRunsPayload(await requestSettingsJson(buildRunsPath(session.sessionId, RUN_HISTORY_LIMIT)));", "chat client keeps current run history API data unknown until projection");
assertNotIncludes(chatClient, "requestSettingsJson<RunsPayload>(buildRunsPath(session.sessionId, RUN_HISTORY_LIMIT))", "chat client avoids trusting an unchecked run history response generic");
assertNotIncludes(chatClient, "const payload = await requestSettingsJson<RunsPayload>(buildRunsPath(session.sessionId, RUN_HISTORY_LIMIT));", "chat client avoids direct current run list response field reads");
assertIncludes(chatClient, "const runs = normalizeRunsPayload(payload);", "chat client assigns only normalized current runs to session state");
assertNotIncludes(chatClient, "Array.isArray(payload?.runs)", "chat client avoids direct run history payload array checks in loader");
assertNotIncludes(chatClient, "const runs = Array.isArray(payload.runs) ? payload.runs : [];", "chat client avoids raw run list array checks in runs payload normalizer");
assertNotIncludes(chatClient, "type RunsPayload = { runs?: unknown[] };", "chat client avoids pre-trusting run history response arrays");
assertIncludes(chatClient, "function cancelProviderConnect(): void", "chat client types provider connect reset helper");
assertIncludes(chatClient, "function toggleSettingsConnection(shouldConnect: boolean): void", "chat client types settings connection toggle");
assertIncludes(chatClient, "async function initializeClient(): Promise<void>", "chat client types initialization flow");
assertIncludes(chatClientHistoryPayloads, "metadata?: HistoryMessageMetadata;", "history payload adapter exposes projected message metadata");
assertIncludes(chatClientHistoryPayloads, "export type HistoryMessagePayload = {", "history payload adapter owns the message boundary");
assertNotIncludes(chatClientHistoryPayloads, "type HistoryMessageApiRecord", "history payload adapter keeps one message boundary");
assertIncludes(chatClientHistoryPayloads, "export type HistoryMessageMetadata = {", "history payload adapter owns the message metadata boundary");
assertNotIncludes(chatClientHistoryPayloads, "type HistoryMessageMetadataApiRecord", "history payload adapter keeps one message metadata boundary");
assertIncludes(chatClientHistoryPayloads, "sender_name?: unknown;", "history payload adapter names sender aliases");
assertIncludes(chatClientHistoryPayloads, "sender_id?: unknown;", "history payload adapter names sender id aliases");
assertNotIncludes(chatClientHistoryPayloads, "type HistoryMessageMetadata = JsonRecord", "history payload adapter avoids generic message metadata records");
assertNotIncludes(chatClientHistoryPayloads, "type HistoryMessagePayload = JsonRecord", "history payload adapter avoids generic message payload records");
assertIncludes(chatClientHistoryPayloads, "function toHistoryMessagePayload(value: unknown): HistoryMessagePayload", "history payload adapter privately narrows history messages");
assertNotIncludes(chatClientHistoryPayloads, "export function toHistoryMessagePayload", "history payload adapter exposes message conversion only through collections");
assertIncludes(chatClientHistoryPayloads, "role: payload.role,\n    content: payload.content,\n    created_at: payload.created_at,\n    createdAt: payload.createdAt,\n    metadata: toHistoryMessageMetadata(payload.metadata),", "history payload adapter projects message fields and nested metadata");
assertIncludes(chatClientHistoryPayloads, "function toHistoryMessageMetadata(value: unknown): HistoryMessageMetadata", "history payload adapter privately narrows message metadata");
assertNotIncludes(chatClientHistoryPayloads, "export function toHistoryMessageMetadata", "history payload adapter keeps nested message metadata conversion private");
assertIncludes(chatClientHistoryPayloads, "sender_name: payload.sender_name,\n    sender_id: payload.sender_id,", "history payload adapter projects sender fields");
assertIncludes(chatClient, "function makeHistoryMessage(payload: HistoryMessagePayload, index: number): ChatMessage", "chat client receives projected history messages");
assertIncludes(chatClient, "const metadata = payload.metadata || {};", "chat client consumes projected message metadata directly");
assertNotIncludes(chatClient, "const payload = toJsonRecord(message) || {};", "chat client avoids generic history message payload reads");
assertNotIncludes(chatClient, "const metadata = toJsonRecord(payload.metadata) || {};", "chat client avoids inline history message metadata records");
assertIncludes(chatClientHistoryPayloads, "export type HistoryEntryContentPayload = {", "history payload adapter owns the entry content boundary");
assertNotIncludes(chatClientHistoryPayloads, "type HistoryEntryContentApiRecord", "history payload adapter keeps one entry content boundary");
assertIncludes(chatClientHistoryPayloads, "artifact?: unknown;", "history payload adapter treats entry artifacts as unknown input");
assertIncludes(chatClientHistoryPayloads, "export type HistoryEntryPayload = {", "history payload adapter owns the entry boundary");
assertNotIncludes(chatClientHistoryPayloads, "type HistoryEntryApiRecord", "history payload adapter keeps one entry boundary");
assertNotIncludes(chatClientHistoryPayloads, "JsonRecord", "history payload adapter avoids open-ended entry records");
assertIncludes(chatClientHistoryPayloads, "function toHistoryEntryContentPayload(value: unknown): HistoryEntryContentPayload | null", "history payload adapter privately narrows entry content");
assertNotIncludes(chatClientHistoryPayloads, "export function toHistoryEntryContentPayload", "history payload adapter exposes entry content only through projected collections");
assertIncludes(chatClientHistoryPayloads, "part_id: payload.part_id,\n    partId: payload.partId,\n    artifact_id: payload.artifact_id,\n    artifactId: payload.artifactId,\n    type: payload.type,\n    status: payload.status,\n    title: payload.title,\n    detail: payload.detail,\n    text: payload.text,\n    created_at: payload.created_at,\n    createdAt: payload.createdAt,\n    artifact: payload.artifact,", "history payload adapter projects entry content fields");
assertIncludes(chatClientHistoryPayloads, "function toHistoryEntryPayload(value: unknown): HistoryEntryPayload | null", "history payload adapter privately narrows history entries");
assertNotIncludes(chatClientHistoryPayloads, "export function toHistoryEntryPayload", "history payload adapter exposes entries only through projected collections");
assertIncludes(chatClientHistoryPayloads, "entry_id: payload.entry_id,\n    entryId: payload.entryId,\n    entry_type: payload.entry_type,\n    entryType: payload.entryType,\n    role: payload.role,\n    run_id: payload.run_id,\n    runId: payload.runId,\n    status: payload.status,\n    text: payload.text,\n    content: toHistoryEntryContentPayloadList(payload.content),\n    created_at: payload.created_at,\n    createdAt: payload.createdAt,\n    updated_at: payload.updated_at,\n    updatedAt: payload.updatedAt,\n    metadata: payload.metadata,", "history payload adapter projects entry fields and nested content");
assertIncludes(chatClient, "const metadata = toLiveEntryMetadata(payload.metadata);", "chat client routes history entry metadata through the shared live entry boundary");
assertIncludes(chatClient, "function normalizeSessionEntryContent(entry: HistoryEntryContentPayload | null, index: number): LiveEntryContentItem | null", "chat client normalizes projected entry content while retaining null positions");
assertIncludes(chatClient, "function normalizeHistoryEntryContent(content: Array<HistoryEntryContentPayload | null>): LiveEntryContentItem[]", "chat client receives projected history entry content collections");
assertNotIncludes(chatClient, "function normalizeHistoryEntryContent(value: unknown): RunJsonObject[]", "chat client avoids generic history entry content state");
assertNotIncludes(chatClient, "toHistoryEntryContentPayload", "chat client does not convert raw history entry content");
assertIncludes(chatClient, "function makeHistoryEntry(payload: HistoryEntryPayload | null, index: number): LiveEntry | null", "chat client receives projected history entries while retaining null positions");
assertNotIncludes(chatClient, "toHistoryEntryPayload", "chat client does not convert raw history entries");
assertNotIncludes(chatClient, "const payload = toJsonRecord(entry);", "chat client avoids generic history entry payload reads");
assertIncludes(chatClient, "const content = normalizeHistoryEntryContent(payload.content);", "chat client stores normalized history entry content");
assertNotIncludes(chatClient, "const content = Array.isArray(payload.content)", "chat client avoids raw history entry content array checks in entry normalizer");
assertIncludes(chatClientHistoryPayloads, "export type HistoryRunPayload = {", "history payload adapter owns the run response boundary");
assertNotIncludes(chatClientHistoryPayloads, "type HistoryRunApiRecord", "history payload adapter avoids redundant run aliases");
assertNotIncludes(chatClientHistoryPayloads, "type HistoryRunPayload = Record<string, unknown>", "history payload adapter avoids generic run records");
assertIncludes(chatClientHistoryPayloads, "finished_at?: unknown;", "history payload adapter lists run finish timestamp aliases");
assertIncludes(chatClientHistoryPayloads, "function toHistoryRunPayload(value: unknown): HistoryRunPayload | null", "history payload adapter privately narrows history runs");
assertNotIncludes(chatClientHistoryPayloads, "export function toHistoryRunPayload(value", "history payload adapter exports only run-list projection");
assertIncludes(chatClientHistoryPayloads, "run_id: payload.run_id,\n    runId: payload.runId,\n    session_id: payload.session_id,\n    sessionId: payload.sessionId,\n    status: payload.status,\n    created_at: payload.created_at,\n    createdAt: payload.createdAt,\n    updated_at: payload.updated_at,\n    updatedAt: payload.updatedAt,\n    finished_at: payload.finished_at,\n    finishedAt: payload.finishedAt,", "history payload adapter projects run fields");
assertNotIncludes(chatClient, "toHistoryRunPayload(value)", "chat client does not convert raw history runs");
assertNotIncludes(chatClient, "function normalizeHistoryRun(value: unknown): RunViewState | null {\n    const payload = toJsonRecord(value) || {};", "chat client avoids generic history run payload reads");
assertIncludes(chatClient, "function normalizeHistoryRun(payload: HistoryRunPayload | null): RunViewState | null", "chat client normalizes projected history runs");
assertIncludes(chatClient, "function normalizeHistoryMessages(messages: HistoryMessagePayload[]): ChatMessage[]", "chat client normalizes projected history messages");
assertNotIncludes(chatClient, "function normalizeHistoryMessages(value: unknown): ChatMessage[]", "chat client avoids unscoped history message normalization inputs");
assertIncludes(chatClient, "function normalizeHistoryEntries(entries: Array<HistoryEntryPayload | null>): LiveEntry[]", "chat client normalizes projected history entries");
assertNotIncludes(chatClient, "function normalizeHistoryEntries(value: unknown): LiveEntry[]", "chat client avoids unscoped history entry normalization inputs");
assertIncludes(chatClient, "function normalizeHistoryRuns(runs: Array<HistoryRunPayload | null>): RunViewState[]", "chat client normalizes projected history runs");
assertIncludes(chatClient, "function normalizeHistoryRuns(runs: Array<HistoryRunPayload | null>): RunViewState[] {\n    return normalizeRunList(runs);\n  }", "chat client reuses the typed run list helper for history runs");
assertNotIncludes(chatClient, "function normalizeHistoryRuns(value: unknown): RunViewState[]", "chat client avoids unscoped history run normalization inputs");
assertIncludes(chatClient, "function normalizeHistorySession(payload: HistorySessionPayload | null): ChatSession | null", "chat client normalizes projected history sessions while retaining null positions");
assertNotIncludes(chatClient, "toHistorySessionPayload(value)", "chat client does not convert raw history sessions");
assertIncludes(chatClient, "if (!payload) {\n      return null;\n    }\n    const sessionId = String(payload.session_id || \"\").trim();", "chat client rejects non-record history sessions");
assertIncludes(chatClient, "session.messages = normalizeHistoryMessages(payload.messages || []);", "chat client consumes adapter-projected history messages");
assertIncludes(chatClient, "session.entries = normalizeHistoryEntries(payload.entries || []);", "chat client consumes adapter-projected history entries");
assertIncludes(chatClient, "session.runs = normalizeHistoryRuns(payload.runs || []);", "chat client consumes adapter-projected history runs");
assertNotIncludes(chatClient, "session.messages = Array.isArray(payload.messages)", "chat client avoids raw history message array checks in session normalizer");
assertNotIncludes(chatClient, "session.entries = Array.isArray(payload.entries)", "chat client avoids raw history entry array checks in session normalizer");
assertNotIncludes(chatClient, "session.runs = Array.isArray(payload.runs)", "chat client avoids raw history run array checks in session normalizer");
assertIncludes(chatClient, "function mergeHistorySession(\n    existing: ChatSession,\n    incoming: ChatSession,\n    { preserveDetails = false, changedSinceRequest = false }: MergeHistorySessionOptions = {},\n  ): ChatSession", "chat client types merged history session return");
assertIncludes(chatClient, "function mergeHistorySessions(historySessions: ChatSession[], options: MergeHistorySessionsOptions = {}): void", "chat client types history session merge side effect");
assertIncludes(chatClient, "const historySessionIds = new Set(visibleHistorySessions.map((session) => session.sessionId).filter(isNonEmptyString));", "chat client narrows history session id sets");
assertIncludes(chatClient, "const sessionsByExternalChatId = new Map<string, ChatSession>();", "chat client types history session merge map");
assertIncludes(chatClient, "async function loadSessionHistory(options: LoadSessionHistoryOptions = {}): Promise<void>", "chat client types session history loader");
assertNotIncludes(chatClient, "state.sessionHistory.channelTotals = toJsonRecord(payload.channel_totals)", "chat client avoids storing raw history channel totals");
assertNotIncludes(chatClient, "Number(state.sessionHistory.channelTotals", "chat client avoids late coercion of session history channel totals");
assertIncludes(chatClient, "function mergeSessionRuns(session: ChatSession, runs: RunViewState[]): void", "chat client merges typed run state");
assertIncludes(chatClient, "filter(isChatSession)", "chat client filters session history with a type guard");
assertIncludes(chatClient, "STORAGE_KEYS.showRunHistory", "run history preference retained");
assertIncludes(chatClient, "deferSettingsWork", "settings loads are deferred after opening");
assertIncludes(chatClient, "window.requestAnimationFrame", "settings deferred work yields after user interaction");
assertNotIncludes(chatClient, "/api/background-processes", "background process polling remains removed");
assertNotIncludes(chatClient, "/api/curator/", "curator action fetch remains removed");
assertIncludes(browserDefaults, "export interface BrowserState", "browser defaults expose typed browser state");
assertIncludes(browserDefaults, "export interface BrowserRuntimeState", "browser defaults expose typed browser runtime state");
assertIncludes(browserDefaults, "export interface BrowserOperationResult", "browser defaults expose typed browser operation result");
assertIncludes(browserDefaults, "export interface BrowserResultCheck", "browser defaults expose typed browser check result");
assertIncludes(browserDefaults, "export type BrowserCloudSettings = {\n  [key: string]: unknown;\n};", "browser defaults name dynamic cloud settings boundary");
assertNotIncludes(browserDefaults, "type JsonRecord = Record<string, unknown>;", "browser defaults avoid a shared generic JSON record alias");
assertNotIncludes(browserDefaults, "function toJsonRecord(value: unknown): JsonRecord", "browser defaults avoid a shared generic JSON record converter");
for (const payloadType of ["BrowserResultCheck", "BrowserOperationResult", "BrowserRuntimeState", "BrowserState", "BrowserCloudSettings"]) {
  assertIncludes(browserDefaults, `toPayloadSource<${payloadType}>`, `browser defaults limit ${payloadType} source reads to known fields`);
}
for (const payloadType of ["BrowserCloudSettings", "BrowserResultCheck", "BrowserOperationResult", "BrowserRuntimeState"]) {
  assertIncludes(browserDefaults, `toPayloadSource<${payloadType}>(value) || {}`, `browser defaults preserve the empty ${payloadType} fallback`);
}
assertIncludes(browserDefaults, "toPayloadSource<BrowserState>(browser) || {}", "browser defaults preserve the empty browser state fallback");
assertIncludes(browserDefaults, "cloud: BrowserCloudSettings;", "browser defaults type dynamic browser cloud settings");
assertIncludes(browserDefaults, "function toBrowserCloudSettings(value: unknown): BrowserCloudSettings", "browser defaults isolate dynamic cloud settings conversion");
assertIncludes(browserDefaults, "cloud: toBrowserCloudSettings(payload.cloud),", "browser defaults preserve dynamic browser cloud settings");
assertIncludes(browserDefaults, "runtime: BrowserRuntimeState;", "browser defaults keeps runtime state typed");
assertIncludes(browserDefaults, "browser?: BrowserState;", "browser defaults keeps browser operation settings typed");
assertIncludes(browserDefaults, "runtime?: BrowserRuntimeState;", "browser defaults keeps browser operation runtime typed");
assertNotIncludes(browserDefaults, "runtime: JsonRecord;", "browser defaults avoids generic runtime state");
assertNotIncludes(browserDefaults, "browser?: unknown;", "browser defaults avoids raw operation browser settings payloads");
assertNotIncludes(browserDefaults, "runtime?: unknown;", "browser defaults avoids raw operation runtime payloads");
assertIncludes(browserDefaults, "export function normalizeBrowserSettings(browser: unknown = {}): BrowserState", "browser defaults normalize unknown settings payloads");
assertIncludes(browserDefaults, "export function normalizeBrowserOperationResult(value: unknown): BrowserOperationResult", "browser defaults normalize unknown browser operation payloads");
assertIncludes(browserDefaults, "export function normalizeBrowserResultCheck(value: unknown): BrowserResultCheck", "browser defaults normalize unknown browser check payloads");
assertIncludes(browserDefaults, "function normalizeBrowserRuntime(value: unknown, fallback: BrowserRuntimeState): BrowserRuntimeState", "browser defaults narrows browser runtime payloads");
assertIncludes(browserDefaults, "function normalizeOptionalBrowserRuntime(value: unknown): BrowserRuntimeState | undefined", "browser defaults narrows optional browser operation runtime payloads");
assertIncludes(browserDefaults, "available: payload.available === true,\n    command: String(payload.command || \"\"),\n    install_hint: String(payload.install_hint ?? \"\"),", "browser defaults projects browser runtime payload fields");
assertIncludes(browserDefaults, "if (payload.browser !== undefined) result.browser = normalizeBrowserSettings(payload.browser);", "browser defaults normalizes operation browser settings before state writes");
assertNotIncludes(browserDefaults, "if (payload.browser !== undefined) result.browser = payload.browser;", "browser defaults avoids raw operation browser settings passthrough");
assertIncludes(browserDefaults, "const runtime = normalizeOptionalBrowserRuntime(payload.runtime);\n  if (runtime !== undefined) result.runtime = runtime;", "browser defaults normalizes operation runtime before state writes");
assertNotIncludes(browserDefaults, "if (payload.runtime !== undefined) result.runtime = payload.runtime;", "browser defaults avoids raw operation runtime passthrough");
assertIncludes(browserDefaults, "runtime: normalizeBrowserRuntime(payload.runtime, defaultState.runtime),", "browser defaults preserve default runtime fallback");
assertNotIncludes(browserDefaults, "Record<string, any>", "browser defaults avoid broad any records");
assertIncludes(browserDefaults, "DEFAULT_BROWSER_TEST_URL = \"https://quotes.toscrape.com/js/\"", "browser defaults keep manual test URL");
assertIncludes(browserSettingsActions, "export function useBrowserSettingsActions", "browser settings actions remain exported");
assertIncludes(browserSettingsActions, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", "browser settings actions keep unchecked API responses unknown");
assertIncludes(browserSettingsActions, "interface BrowserSettingsState", "browser settings actions type browser state boundary");
assertIncludes(browserSettingsActions, "type BrowserLoadingKey =", "browser settings actions type operation loading keys");
assertIncludes(browserSettingsActions, "type BrowserResultKey =", "browser settings actions type operation result keys");
assertIncludes(browserSettingsActions, "type BrowserSettingsPayload = {", "browser settings actions name browser settings payload boundary");
assertIncludes(browserSettingsActions, "restart_required?: unknown;", "browser settings actions treat browser restart flags as unknown payload fields");
assertIncludes(browserSettingsActions, "type BrowserOperationPayload = {", "browser settings actions names raw browser operation payload boundary");
assertIncludes(browserSettingsActions, "type BrowserOperationRequestPayload = {", "browser settings actions names browser operation request body fields");
assertIncludes(browserSettingsActions, "url?: string;", "browser settings actions limits operation request bodies to the test URL field");
assertIncludes(browserSettingsActions, "body: BrowserOperationRequestPayload | null = null,", "browser settings actions keep operation request bodies on a finite boundary");
assertNotIncludes(browserSettingsActions, "type JsonRecord", "browser settings actions avoid generic JSON aliases");
assertNotIncludes(browserSettingsActions, "body: JsonRecord", "browser settings actions avoid open-ended operation request bodies");
assertNotIncludes(browserSettingsActions, "function toJsonRecord(value: unknown): JsonRecord", "browser settings actions avoid a generic record converter for finite API envelopes");
assertIncludes(browserSettingsActions, "function toBrowserSettingsPayload(value: unknown): BrowserSettingsPayload", "browser settings actions narrows browser settings responses");
assertIncludes(browserSettingsActions, "function toBrowserSettingsPayload(value: unknown): BrowserSettingsPayload {\n  const payload = toPayloadSource<BrowserSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "browser settings actions handles non-object browser settings responses before field projection");
assertIncludes(browserSettingsActions, "browser: payload.browser,\n    restart_required: payload.restart_required,", "browser settings actions projects browser settings payloads onto named fields");
assertNotIncludes(browserSettingsActions, "const payload = await requestSettingsJson(\"/api/settings/browser\");", "browser settings actions avoids direct raw browser settings load payloads");
assertIncludes(browserSettingsActions, "function toBrowserOperationPayload(value: unknown): BrowserOperationPayload", "browser settings actions narrows browser operation responses");
assertIncludes(browserSettingsActions, "function toBrowserOperationPayload(value: unknown): BrowserOperationPayload {\n  const payload = toPayloadSource<BrowserOperationPayload>(value);\n  if (!payload) {\n    return {};\n  }", "browser settings actions handles non-object browser operation responses before field projection");
assertIncludes(browserSettingsActions, "browser: payload.browser,\n    ok: payload.ok,\n    url: payload.url,\n    suggestion: payload.suggestion,\n    error: payload.error,\n    already_installed: payload.already_installed,\n    checks: payload.checks,\n    after: payload.after,\n    install: payload.install,\n    open: payload.open,\n    snapshot: payload.snapshot,\n    runtime: payload.runtime,", "browser settings actions projects browser operation payloads onto named fields");
assertIncludes(browserSettingsActions, "const rawPayload = toBrowserOperationPayload(await requestSettingsJson(endpoint, requestOptions));", "browser settings actions converts unknown browser operation responses through typed payload boundary");
assertIncludes(browserSettingsActions, "type BrowserOperationSummary = (payload: BrowserOperationResult", "browser settings actions summarize normalized browser operation results");
assertIncludes(browserSettingsActions, "function resultReason(value: BrowserResultCheck | null | undefined): string", "browser settings actions reads typed browser result reasons");
assertIncludes(browserSettingsActions, "return optionalText(value?.suggestion || value?.error);", "browser settings actions reads result reasons without raw records");
assertNotIncludes(browserSettingsActions, "function resultReason(value: unknown): string", "browser settings actions avoids raw result reason payloads");
assertNotIncludes(browserSettingsActions, "const payload = toJsonRecord(value);\n  return optionalText(payload.suggestion || payload.error);", "browser settings actions avoids reopening browser result checks as raw records");
assertIncludes(browserSettingsActions, "function browserChecks(value: unknown): BrowserResultCheck[]", "browser settings actions normalize browser check arrays through shared result checks");
assertIncludes(browserSettingsActions, "return value.map(normalizeBrowserResultCheck).filter((check) => Object.keys(check).length > 0);", "browser settings actions route browser checks through shared payload normalizer");
assertIncludes(browserSettingsActions, "const payload = normalizeBrowserOperationResult(rawPayload);", "browser settings actions normalize browser operation payload before state write");
assertIncludes(browserSettingsActions, "settingsState.browser = payload.browser || settingsState.browser;", "browser settings actions writes typed browser operation state");
assertIncludes(browserSettingsActions, "const after = normalizeBrowserResultCheck(payload.after);", "browser settings actions route install after-check through shared payload normalizer");
assertNotIncludes(browserSettingsActions, "type BrowserCheckPayload = JsonRecord & {", "browser settings actions no longer own generic browser check payload records");
assertNotIncludes(browserSettingsActions, "function toBrowserCheckPayload", "browser settings actions no longer owns browser check converter");
assertNotIncludes(browserSettingsActions, "function browserChecks(value: unknown): JsonRecord[]", "browser settings actions avoid raw browser check records");
assertNotIncludes(browserSettingsActions, "settingsState.browser = normalizeBrowserSettings(payload.browser || settingsState.browser || {});", "browser settings actions avoids renormalizing typed browser operation state");
assertNotIncludes(browserSettingsActions, "const after = toJsonRecord(payload.after);", "browser settings actions avoid inline install after-check records");
assertIncludes(browserSettingsActions, "function errorMessage(error: unknown): string", "browser settings actions narrow unknown errors");
assertIncludes(browserSettingsActions, "\"/api/settings/browser\"", "browser settings actions keep browser settings endpoint");
assertIncludes(browserSettingsActions, "toBrowserSettingsPayload(await requestSettingsJson(\"/api/settings/browser\"))", "browser settings actions convert unknown browser load responses through the payload boundary");
assertIncludes(browserSettingsActions, "toBrowserSettingsPayload(await requestSettingsJson(\"/api/settings/browser\",", "browser settings actions convert unknown browser save responses through the payload boundary");
assertNotIncludes(browserSettingsActions, "requestSettingsJson<", "browser settings actions avoid trusting unchecked API response generics");
assertIncludes(browserSettingsActions, "\"/api/settings/browser/test\"", "browser settings actions keep browser test endpoint");
assertIncludes(browserSettingsActions, "\"/api/settings/browser/doctor\"", "browser settings actions keep browser doctor endpoint");
assertIncludes(browserSettingsActions, "\"/api/settings/browser/install\"", "browser settings actions keep browser install endpoint");
assertIncludes(browserSettingsActions, "allow_private_urls: settingsState.browserForm.allowPrivateUrls", "browser settings actions keep private URL payload");
assertNotIncludes(browserSettingsActions, "Promise<any>", "browser settings actions avoid any request promises");
assertNotIncludes(browserSettingsActions, "catch (error: any)", "browser settings actions avoid any catch boundaries");
assertNotIncludes(browserSettingsActions, "Record<string, any>", "browser settings actions avoid broad dynamic state records");
assertIncludes(useSettingsState, "browser: BrowserState", "settings state types browser settings");
assertIncludes(useSettingsState, "browserForm: BrowserForm", "settings state types browser form");
assertIncludes(useSettingsState, "browserTestResult: BrowserOperationResult | null;", "settings state types browser test result boundary");
assertIncludes(useSettingsState, "browserDoctorResult: BrowserOperationResult | null;", "settings state types browser doctor result boundary");
assertIncludes(useSettingsState, "browserInstallResult: BrowserOperationResult | null;", "settings state types browser install result boundary");
assertNotIncludes(useSettingsState, "browserTestResult: JsonRecord | null;", "settings state keeps browser test result off generic JSON records");
assertNotIncludes(useSettingsState, "browserDoctorResult: JsonRecord | null;", "settings state keeps browser doctor result off generic JSON records");
assertNotIncludes(useSettingsState, "browserInstallResult: JsonRecord | null;", "settings state keeps browser install result off generic JSON records");
assertIncludes(chatClientCoercion, "export function coerceNonNegativeInteger(value: unknown): number", "chat client coercion helpers are typed");
assertIncludes(chatClientCoercion, "export function coerceText(value: unknown): string", "chat client coercion owns shared scalar text normalization");
assertIncludes(chatClientCoercion, "export function coerceFiniteNumber(value: unknown): number | null", "chat client coercion owns shared finite-number normalization");
assertIncludes(chatClient, "coerceText as textField,", "chat client aliases shared text coercion for field semantics");
assertIncludes(chatClientCronPayloads, "coerceText as textField", "cron adapter reuses shared text coercion");
assertIncludes(chatClientRunPayloads, "coerceText as textField", "run adapter reuses shared text coercion");
assertNotIncludes(chatClientCronPayloads, "function textField", "cron adapter avoids a duplicate text coercion helper");
assertNotIncludes(chatClientRunPayloads, "function textField", "run adapter avoids a duplicate text coercion helper");
assertIncludes(chatClientCoercion, "return numericValue > 1_000_000_000_000 ? numericValue : numericValue * 1000;", "chat client timestamp normalization preserves seconds conversion");
assertIncludes(chatClientSessionIds, "export function channelFromSessionId(sessionId: unknown): string", "chat client session id helpers are typed");
assertIncludes(chatClientSessionIds, "return separatorIndex > 0 ? normalized.slice(0, separatorIndex).trim() : \"web\";", "chat client session channel fallback remains web");
assertIncludes(chatClientRunHelpers, "export interface RunViewState", "chat client run helpers expose typed run view state");
assertNotIncludes(chatClientRunHelpers, "type JsonRecord = Record<string, unknown>;", "chat client run helpers avoid private generic JSON aliases");
assertNotIncludes(chatClientRunHelpers, "Record<string, unknown>", "chat client run helpers avoid generic JSON payload records");
assertIncludes(chatClientRunHelpers, "export type RunTimelinePayload = RunLifecycleEventPayload & RunTimelineDetailPayload;", "chat client run helpers own the fixed timeline payload boundary");
assertIncludes(chatClientRunHelpers, "import { toPayloadSource } from \"./payloadBoundary\";", "chat client run helpers reuse the shared finite payload guard");
assertNotIncludes(chatClientRunHelpers, "type RunTimelineSourcePayload", "chat client run helpers avoid a duplicate timeline source type");
assertNotIncludes(chatClientRunHelpers, "function toRunTimelinePayloadRecord", "chat client run helpers avoid a duplicate timeline object guard");
assertIncludes(chatClientRunHelpers, "export function normalizeRunTimelinePayload(value: unknown): RunTimelinePayload", "chat client run helpers normalize timeline payloads at the named boundary");
assertIncludes(chatClientRunHelpers, "const payload = toPayloadSource<RunTimelinePayload>(value) || {};\n  return {\n    ...normalizeRunLifecycleEventPayload(payload),", "chat client run helpers guard timeline inputs before projecting lifecycle fields");
assertNotIncludes(chatClientRunHelpers, "type RunLifecycleEventSourcePayload", "chat client run helpers avoid a duplicate lifecycle source type");
assertIncludes(chatClientRunHelpers, "const payload = toPayloadSource<RunLifecycleEventPayload>(value) || {};", "chat client run helpers guard lifecycle inputs with the shared finite payload boundary");
assertNotIncludes(chatClientRunHelpers, "export type RunTimelinePayload = {\n  [key: string]: unknown;\n};", "chat client run helpers avoid open-ended timeline payload indexes");
assertNotIncludes(chatClientRunHelpers, "value as RunTimelinePayload", "chat client run helpers avoid casting raw timeline payloads wholesale");
assertNotIncludes(chatClientRunHelpers, "export type RunTimelinePayload = TraceEventPayload;", "chat client run helpers avoid carrying timeline payloads through trace event payloads");
assertNotIncludes(chatClientRunHelpers, "export type RunTimelinePayload = JsonRecord;", "chat client run helpers avoid duplicate timeline JSON payload aliases");
assertNotIncludes(chatClientRunHelpers, "export type RunTimelinePayload = Record<string, unknown>;", "chat client run helpers avoid inline timeline payload records");
assertNotIncludes(chatClientRunHelpers, "export type RunJsonObject = Record<string, unknown>;", "chat client run helpers avoid generic run JSON aliases");
assertIncludes(chatClientRunHelpers, "type RunArtifactView,", "chat client run helpers import typed run artifact view");
assertIncludes(chatClientRunHelpers, "type TraceEventView,", "chat client run helpers import typed trace event view");
assertIncludes(chatClientRunHelpers, "rawEvents: TraceEventView[];", "chat client run view state stores typed raw trace events");
assertNotIncludes(chatClientRunHelpers, "rawEvents: RunJsonObject[];", "chat client run view state avoids generic raw run events");
assertIncludes(chatClientRunHelpers, "import type { DiffSummaryView, RunSummaryView } from \"./runSummaryNormalizers\";", "chat client run helpers import typed run summary views");
assertIncludes(chatClientRunHelpers, "diffSummary: DiffSummaryView | null;", "chat client run view state stores typed diff summaries");
assertNotIncludes(chatClientRunHelpers, "diffSummary: RunJsonObject | null;", "chat client run view state avoids generic diff summaries");
assertIncludes(chatClientRunHelpers, "summary: RunSummaryView | null;", "chat client run view state stores typed run summaries");
assertNotIncludes(chatClientRunHelpers, "summary: RunJsonObject | null;", "chat client run view state avoids generic run summaries");
assertIncludes(chatClientRunHelpers, "type TraceFileChangeView,", "chat client run helpers import typed file change view");
assertIncludes(chatClientRunHelpers, "type TracePartView,", "chat client run helpers import typed trace part view");
assertIncludes(chatClientRunHelpers, "parts: TracePartView[];", "chat client run view state stores typed trace parts");
assertNotIncludes(chatClientRunHelpers, "parts: RunJsonObject[];", "chat client run view state avoids generic run trace parts");
assertIncludes(chatClientRunHelpers, "artifacts: RunArtifactView[];", "chat client run view state stores typed run artifacts");
assertNotIncludes(chatClientRunHelpers, "artifacts: RunJsonObject[];", "chat client run view state avoids generic run artifacts");
assertIncludes(chatClientRunHelpers, "fileChanges: TraceFileChangeView[];", "chat client run view state stores typed file changes");
assertNotIncludes(chatClientRunHelpers, "fileChanges: RunJsonObject[];", "chat client run view state avoids generic run file changes");
assertIncludes(chatClientRunHelpers, "type RunEventKind,", "chat client run helpers import typed run event kind");
assertNotIncludes(chatClientRunHelpers, "type TraceEventPayload,", "chat client run helpers no longer imports trace event payload for helper-local payloads");
assertIncludes(chatClientRunHelpers, "type TraceEventCountsView,", "chat client run helpers import typed trace event counts");
assertIncludes(chatClientRunHelpers, "export type RunLifecycleEventPayload = {", "chat client run helper exports typed lifecycle payload boundary");
assertNotIncludes(chatClientRunHelpers, "export type RunLifecycleEventPayload = {\n  [key: string]: unknown;", "chat client run helper avoids open-ended lifecycle payload indexes");
assertNotIncludes(chatClientRunHelpers, "export type RunLifecycleEventPayload = TraceEventPayload & {", "chat client run helpers avoid carrying lifecycle events through trace event payloads");
assertNotIncludes(chatClientRunHelpers, "export type RunLifecycleEventPayload = JsonRecord & {", "chat client run helpers avoid carrying lifecycle events through generic JSON records");
assertIncludes(chatClientRunHelpers, "export function normalizeRunLifecycleEventPayload(value: unknown): RunLifecycleEventPayload", "chat client run helpers narrow lifecycle payloads through a typed converter");
assertNotIncludes(chatClientRunHelpers, "type RunEventPayload = {", "chat client run helpers avoid private duplicate lifecycle payload shapes");
assertNotIncludes(chatClientRunHelpers, "type RunEventPayload = Record<string, unknown>;", "chat client run event helper avoids bare unknown record payloads");
assertIncludes(chatClientRunHelpers, "executed_tool_calls?: unknown;", "chat client run event helper lists run finish payload aliases");
assertIncludes(chatClientRunHelpers, "export type RunEventCounts = TraceEventCountsView;", "chat client run event counts use explicit trace count view");
assertIncludes(chatClientRunHelpers, "export type RunTimelineTone = \"running\" | \"neutral\" | \"warning\" | \"success\" | \"error\";", "chat client run helpers expose typed timeline tones");
assertIncludes(chatClientRunHelpers, "const TERMINAL_RUN_STATUSES = [\"completed\", \"failed\", \"cancelled\", \"stopped\"] as const;", "chat client run helpers keep all terminal run statuses as a typed array");
assertIncludes(chatClientRunHelpers, "type TerminalRunStatus = (typeof TERMINAL_RUN_STATUSES)[number];", "chat client run helpers derive terminal run status union");
assertIncludes(chatClientRunHelpers, "const TERMINAL_RUN_STATUS_SET: ReadonlySet<string> = new Set<string>(TERMINAL_RUN_STATUSES);", "chat client run helpers validate terminal run statuses through a readonly set");
assertIncludes(chatClientRunHelpers, "const RUN_STATUS_EVENT_TYPES = [\"run_started\", \"run_finished\", \"run_failed\", \"run_cancelled\", \"run_cancel_requested\"] as const;", "chat client run helpers keep status event types as a typed array");
assertIncludes(chatClientRunHelpers, "type RunStatusEventType = (typeof RUN_STATUS_EVENT_TYPES)[number];", "chat client run helpers derive run status event union");
assertIncludes(chatClientRunHelpers, "const RUN_STATUS_EVENT_TYPE_SET: ReadonlySet<string> = new Set<string>(RUN_STATUS_EVENT_TYPES);", "chat client run helpers validate run status events through a readonly set");
assertIncludes(chatClientRunHelpers, "function isRunStatusEventType(eventType: string): eventType is RunStatusEventType", "chat client run helpers narrow status event types with a named guard");
assertIncludes(chatClientRunHelpers, "function normalizeRunStatusEventType(eventType: string): RunStatusEventType | null", "chat client run helpers normalize status event types");
assertIncludes(chatClientRunHelpers, "return isRunStatusEventType(eventType) ? eventType : null;", "chat client run helpers normalize status event types without assertion");
assertNotIncludes(chatClientRunHelpers, "eventType as RunStatusEventType", "chat client run helpers avoid asserting validated status event types");
assertIncludes(chatClientRunHelpers, "export type RunStatusEventPayloadView = {", "chat client run helpers expose typed run status event payload view");
assertIncludes(chatClientRunHelpers, "export function normalizeRunStatusEventPayload(\n  payload: RunLifecycleEventPayload,\n  eventStatus = \"\",\n): RunStatusEventPayloadView", "chat client run helpers normalize run status event payloads before status mapping");
assertIncludes(chatClientRunHelpers, "const RUN_SUMMARY_TRIGGER_EVENT_TYPES = [\"run_finished\", \"run_failed\"] as const;", "chat client run helpers keep summary trigger event types as a typed array");
assertIncludes(chatClientRunHelpers, "type RunSummaryTriggerEventType = (typeof RUN_SUMMARY_TRIGGER_EVENT_TYPES)[number];", "chat client run helpers derive summary trigger event union");
assertIncludes(chatClientRunHelpers, "const RUN_SUMMARY_TRIGGER_EVENT_TYPE_SET: ReadonlySet<string> = new Set<string>(RUN_SUMMARY_TRIGGER_EVENT_TYPES);", "chat client run helpers validate summary trigger events through a readonly set");
assertIncludes(chatClientRunHelpers, "export function isRunSummaryTriggerEventType(eventType: string): eventType is RunSummaryTriggerEventType", "chat client run helpers expose typed summary trigger event guard");
assertIncludes(chatClientRunHelpers, "export function isTerminalRunStatus(status: string): status is TerminalRunStatus", "chat client run helpers expose typed terminal run status guard");
assertIncludes(chatClientRunHelpers, "const terminalStatus = isTerminalRunStatus(status) ? status : null;", "chat client run tone uses typed terminal run status guard");
assertIncludes(chatClientRunHelpers, "if (terminalStatus === \"stopped\")", "chat client run tone treats stopped runs as warnings");
assertIncludes(chatClientRunHelpers, "const normalizedEventType = normalizeRunStatusEventType(eventType);", "chat client run status updates use typed event normalization");
assertIncludes(chatClientRunHelpers, "const statusPayload = normalizeRunStatusEventPayload(payload, eventStatus);", "chat client run status updates read normalized payload status");
assertIncludes(chatClientRunHelpers, "return statusPayload.status || \"completed\";", "chat client run status finished fallback reads normalized status");
assertNotIncludes(chatClientRunHelpers, "return String(payload.status || eventStatus || \"completed\");", "chat client run status mapping avoids raw completed payload status reads");
assertNotIncludes(chatClientRunHelpers, "return String(payload.status || eventStatus || \"failed\");", "chat client run status mapping avoids raw failed payload status reads");
assertNotIncludes(chatClientRunHelpers, "return String(payload.status || eventStatus || \"cancelled\");", "chat client run status mapping avoids raw cancelled payload status reads");
assertNotIncludes(chatClientRunHelpers, "return String(payload.status || eventStatus || \"cancelling\");", "chat client run status mapping avoids raw cancelling payload status reads");
assertNotIncludes(chatClientRunHelpers, "const TERMINAL_RUN_STATUSES = new Set([", "chat client run helpers avoid untyped terminal run status sets");
assertNotIncludes(chatClientRunHelpers, "if (status === \"completed\")", "chat client run tone avoids direct status string checks");
assertIncludes(chatClientRunHelpers, "export type RunTimelineEventView = {", "chat client run helpers expose typed timeline events");
assertNotIncludes(chatClientRunHelpers, "export type RunTimelineEventView = RunJsonObject & {", "chat client run helpers avoid extending timeline events from generic JSON records");
assertIncludes(chatClientRunHelpers, "kind: RunEventKind;", "chat client run timeline event kinds are typed");
assertIncludes(chatClientRunHelpers, "payload: RunTimelinePayload;", "chat client run timeline event keeps payload as the explicit dynamic boundary");
assertNotIncludes(chatClientRunHelpers, "payload: RunJsonObject;", "chat client run timeline payload avoids generic run JSON naming");
assertIncludes(chatClientRunHelpers, "detail: string;", "chat client run timeline event details are normalized strings");
assertIncludes(chatClientRunHelpers, "tone: RunTimelineTone;", "chat client run timeline event tones are typed");
assertIncludes(chatClientRunHelpers, "eventCounts: RunEventCounts;", "chat client run view state keeps typed event counts");
assertIncludes(chatClientRunHelpers, "events: RunTimelineEventView[];", "chat client run view state keeps typed timeline events");
assertIncludes(chatClientRunHelpers, "cancelPending: boolean;", "chat client run view state tracks typed cancel pending flag");
assertIncludes(chatClientRunHelpers, "export function createRunViewState({", "chat client run view state factory remains exported");
assertIncludes(chatClientRunHelpers, "eventCounts: normalizeTraceEventCounts(null, [])", "chat client run view state preserves initial trace event counts");
assertIncludes(chatClientRunHelpers, "cancelPending: false,", "chat client run view state initializes cancel pending flag");
assertIncludes(chatClientRunHelpers, "export type RunFinishDetailView = {", "chat client run helpers expose typed run finish detail view");
assertIncludes(chatClientRunHelpers, "executedToolCalls: number | null;", "chat client run helpers type run finish tool call counts");
assertIncludes(chatClientRunHelpers, "contextCompactions: number;", "chat client run helpers type run finish compaction counts");
assertNotIncludes(chatClientRunHelpers, "executedToolCalls: unknown;", "chat client run helpers avoids generic run finish tool call counts");
assertNotIncludes(chatClientRunHelpers, "contextCompactions: unknown;", "chat client run helpers avoids generic run finish compaction counts");
assertIncludes(chatClientRunHelpers, "export type SubagentDetailView = {", "chat client run helpers expose typed subagent detail view");
assertIncludes(chatClientRunHelpers, "export type WorkflowDetailView = {", "chat client run helpers expose typed workflow detail view");
assertIncludes(chatClientRunHelpers, "function fieldText(value: unknown): string", "chat client run helpers normalize unknown text fields in one helper");
assertIncludes(chatClientRunHelpers, "function optionalNonNegativeInteger(value: unknown): number | null", "chat client run helpers normalize optional numeric counters");
assertIncludes(chatClientRunHelpers, "toolCalls: (value: number) => string;", "chat client run helpers types tool-call copy formatter");
assertIncludes(chatClientRunHelpers, "compactions: (value: number) => string;", "chat client run helpers types compaction copy formatter");
assertNotIncludes(chatClientRunHelpers, "toolCalls: (value: unknown) => string;", "chat client run helpers avoids generic tool-call copy formatter");
assertNotIncludes(chatClientRunHelpers, "compactions: (value: unknown) => string;", "chat client run helpers avoids generic compaction copy formatter");
assertIncludes(chatClientRunHelpers, "export function normalizeRunFinishDetail(payload: RunLifecycleEventPayload): RunFinishDetailView", "chat client run helpers normalize run finish payloads before formatting");
assertIncludes(chatClientRunHelpers, "executedToolCalls: optionalNonNegativeInteger(payload.executed_tool_calls ?? payload.executedToolCalls)", "chat client run helpers narrows run finish tool call count");
assertIncludes(chatClientRunHelpers, "contextCompactions: coerceNonNegativeInteger(payload.context_compactions ?? payload.contextCompactions)", "chat client run helpers narrows run finish compaction count");
assertIncludes(chatClientRunHelpers, "export function normalizeSubagentDetail(payload: RunLifecycleEventPayload): SubagentDetailView", "chat client run helpers normalize subagent payloads before formatting");
assertIncludes(chatClientRunHelpers, "export function normalizeWorkflowDetail(payload: RunLifecycleEventPayload): WorkflowDetailView", "chat client run helpers normalize workflow payloads before formatting");
assertIncludes(chatClientRunHelpers, "const parts: string[] = [];", "chat client run finish detail uses typed string parts");
assertIncludes(chatClientRunHelpers, "if (detail.executedToolCalls !== null)", "chat client run helpers preserves missing run finish tool call display");
assertIncludes(chatClientRunHelpers, "if (detail.contextCompactions > 0)", "chat client run helpers formats typed compaction count");
assertNotIncludes(chatClientRunHelpers, "Number.isFinite(Number(detail.executedToolCalls))", "chat client run helpers avoids dynamic run finish tool call checks");
assertNotIncludes(chatClientRunHelpers, "Number.isFinite(Number(detail.contextCompactions))", "chat client run helpers avoids dynamic run finish compaction checks");
assertIncludes(chatClientRunHelpers, "promptType: fieldText(payload.prompt_type || payload.promptType)", "chat client subagent detail normalizes prompt type");
assertIncludes(chatClientRunHelpers, "taskId: fieldText(payload.task_id || payload.taskId)", "chat client subagent detail normalizes task id");
assertIncludes(chatClientRunHelpers, "export function formatSubagentDetail(detail: SubagentDetailView): string", "chat client subagent formatter consumes normalized detail view");
assertIncludes(chatClientRunHelpers, "export function formatWorkflowDetail(detail: WorkflowDetailView): string", "chat client workflow formatter consumes normalized detail view");
assertNotIncludes(chatClientRunHelpers, "export function formatSubagentDetail(payload: RunLifecycleEventPayload): string", "chat client subagent formatter avoids raw payload input");
assertNotIncludes(chatClientRunHelpers, "export function formatWorkflowDetail(payload: RunLifecycleEventPayload): string", "chat client workflow formatter avoids raw payload input");
assertIncludes(chatClientRunHelpers, "return fallbackTone === \"warning\" ? \"warning\" : \"success\";", "chat client run tone preserves completed warning fallback");
assertIncludes(runSummaryNormalizers, "export type DiffSummaryView = {", "run summary normalizers expose typed diff summary view");
assertIncludes(runSummaryNormalizers, "import { toPayloadList, toPayloadSource } from \"./payloadBoundary\";", "run summary normalizers reuse shared object and list payload guards");
assertIncludes(runSummaryNormalizers, "toPayloadList(summary.paths)", "run summary normalizers narrow diff paths through the shared list boundary");
assertIncludes(runSummaryNormalizers, "toPayloadList(value)", "run summary normalizers count summary collections through the shared list boundary");
assertNotIncludes(runSummaryNormalizers, "Array.isArray(", "run summary normalizers delegate array validation to the shared payload boundary");
assertNotIncludes(runSummaryNormalizers, "as unknown[]", "run summary normalizers avoid asserting raw payload arrays");
assertIncludes(runSummaryNormalizers, "type DiffSummaryActionsPayload = {\n  [action: string]: unknown;\n};", "run summary normalizers name dynamic diff action map boundary");
assertIncludes(runSummaryNormalizers, "type DiffSummaryActionEntry = [string, unknown];", "run summary normalizers names diff action entry boundary");
assertIncludes(runSummaryNormalizers, "function toDiffSummaryPayload(value: unknown): DiffSummaryPayload | null", "run summary normalizers narrow raw diff summary payloads");
assertIncludes(runSummaryNormalizers, "function normalizeDiffSummaryActions(payload: unknown): Record<string, number>", "run summary normalizers normalize diff action counts");
assertIncludes(runSummaryNormalizers, "export function normalizeDiffSummary(payload: unknown): DiffSummaryView | null", "run summary normalizers keep the shared trace diff boundary");
assertIncludes(runSummaryNormalizers, "actions: normalizeDiffSummaryActions(summary.actions),", "run summary normalizers use the named diff action normalizer");
assertIncludes(runSummaryNormalizers, "export type RunSummaryView = {", "run summary normalizers expose the minimal run summary view");
assertIncludes(runSummaryNormalizers, "toolCount: number;", "run summary view stores only the consumed tool count");
assertIncludes(runSummaryNormalizers, "fileChangeCount: number;", "run summary view stores only the consumed file-change count");
assertIncludes(runSummaryNormalizers, "type RunSummaryPayload = {", "run summary normalizers keep the API payload boundary private");
assertNotIncludes(runSummaryNormalizers, "export type RunSummaryPayload", "run summary normalizers do not expose the raw API payload");
assertIncludes(runSummaryNormalizers, "toPayloadSource<RunSummaryToolPayload>(item)", "run summary normalizers narrow tool items before counting");
assertIncludes(runSummaryNormalizers, "toPayloadSource<RunSummaryFileChangePayload>(item)", "run summary normalizers narrow file-change items before counting");
assertIncludes(runSummaryNormalizers, "function countRunSummaryTools(value: unknown): number", "run summary normalizers count valid tool names without retaining item detail");
assertIncludes(runSummaryNormalizers, "function countRunSummaryFileChanges(value: unknown): number", "run summary normalizers count valid file paths without retaining item detail");
assertIncludes(runSummaryNormalizers, "function toRunSummaryPayload(value: unknown): RunSummaryPayload | null", "run summary normalizers narrow raw run summary payloads");
assertIncludes(runSummaryNormalizers, "status: payload.status,\n        duration_seconds: payload.duration_seconds,\n        durationSeconds: payload.durationSeconds,", "run summary normalizers project only displayed scalar fields");
assertIncludes(runSummaryNormalizers, "file_changes: payload.file_changes,\n        fileChanges: payload.fileChanges,", "run summary normalizers preserve file-change aliases needed for the trace decision");
assertIncludes(runSummaryNormalizers, "export function normalizeRunSummary(payload: unknown): RunSummaryView | null", "run summary normalizers type the minimal summary boundary");
assertIncludes(runSummaryNormalizers, "toolCount: countRunSummaryTools(summary.tools),", "run summary normalizers expose the tool count");
assertIncludes(runSummaryNormalizers, "fileChangeCount: countRunSummaryFileChanges(summary.file_changes || summary.fileChanges),", "run summary normalizers expose the file-change count");
assertNotIncludes(runSummaryNormalizers, "type JsonRecord = Record<string, unknown>;", "run summary normalizers avoid a shared generic JSON record alias");
assertNotIncludes(runSummaryNormalizers, "function toJsonRecord(value: unknown): JsonRecord | null", "run summary normalizers avoid a shared generic JSON record converter");
assertNotIncludes(runTraceNormalizers, "type JsonRecord = Record<string, unknown>;", "run trace normalizers avoid a shared unknown record boundary");
assertIncludes(runTraceNormalizers, "export type TraceEventPayload = {", "run trace normalizers own finite trace event payload boundary");
assertIncludes(runTraceNormalizers, "created_at?: unknown;", "run trace normalizers trace event payload names created timestamp alias");
assertIncludes(runTraceNormalizers, "exit_code?: unknown;", "run trace normalizers trace event payload names process exit code alias");
assertIncludes(runTraceNormalizers, "tool_name?: unknown;", "run trace normalizers trace event payload names tool name alias");
assertIncludes(runTraceNormalizers, "type TraceEventEnvelopePayload = {", "run trace normalizers names trace event envelope payload boundary");
assertIncludes(runTraceNormalizers, "event_id?: unknown;", "run trace normalizers trace event envelope names event id alias");
assertIncludes(runTraceNormalizers, "event_type?: unknown;", "run trace normalizers trace event envelope names event type alias");
assertNotIncludes(runTraceNormalizers, "type TraceEventEnvelopePayload = JsonRecord & {", "run trace normalizers avoid carrying trace event envelopes through generic JSON records");
assertNotIncludes(runTraceNormalizers, "type TraceEventPayloadFields = {", "run trace normalizers avoid a separate trace event payload field alias");
assertNotIncludes(runTraceNormalizers, "export type TraceEventPayload = JsonRecord & TraceEventPayloadFields;", "run trace normalizers avoid carrying trace event payloads through generic JSON records");
assertNotIncludes(runTraceNormalizers, "export type TraceEventPayload = JsonRecord;", "run trace normalizers avoids a pure trace event JSON payload");
assertNotIncludes(runTraceNormalizers, "type RunArtifactFallbackRecord = TraceEventPayload;", "run trace normalizers avoid routing artifact fallback records through trace event payloads");
assertNotIncludes(runTraceNormalizers, "type RunArtifactFallbackRecord = JsonRecord;", "run trace normalizers avoid duplicate artifact fallback JSON aliases");
assertIncludes(runTraceNormalizers, "type RunArtifactFallbackPayload = {", "run trace normalizers name artifact fallback payload boundary");
assertNotIncludes(runTraceNormalizers, "type RunArtifactFallbackPayload = {\n  [key: string]: unknown;", "run trace normalizers avoid open-ended artifact fallback payload indexes");
assertNotIncludes(runTraceNormalizers, "type RunArtifactFallbackPayload = RunArtifactFallbackRecord & {", "run trace normalizers avoid carrying artifact fallback through a generic record alias");
assertNotIncludes(runTraceNormalizers, "type RunArtifactFallbackPayload = TraceEventPayload & {", "run trace normalizers avoid carrying artifact fallback through trace event payloads");
assertNotIncludes(runTraceNormalizers, "type RunArtifactFallbackPayload = JsonRecord & {", "run trace normalizers avoid carrying artifact fallback through generic JSON records");
assertNotIncludes(runTraceNormalizers, "JsonObject", "run trace normalizers avoid duplicate generic JSON object aliases");
assertIncludes(runTraceNormalizers, "export const RUN_EVENT_KINDS = [\"run\", \"llm\", \"tool\", \"verification\", \"work\", \"file\", \"process\", \"text\", \"system\", \"other\"] as const;", "run trace normalizers expose typed run event kinds");
assertIncludes(runTraceNormalizers, "export type RunEventKind = (typeof RUN_EVENT_KINDS)[number];", "run trace normalizers derive run event kind union");
assertIncludes(runTraceNormalizers, "const RUN_EVENT_KIND_SET: ReadonlySet<string> = new Set(RUN_EVENT_KINDS);", "run trace normalizers validate kinds through readonly set");
assertIncludes(runTraceNormalizers, "function isRunEventKind(value: string): value is RunEventKind", "run trace normalizers narrow run event kind strings");
assertIncludes(runTraceNormalizers, "export function normalizeRunKind(value: unknown, fallback: RunEventKind = \"other\"): RunEventKind", "run trace normalizers type run kind normalization");
assertIncludes(runTraceNormalizers, "export function inferRunEventKind(eventType: unknown): RunEventKind", "run trace normalizers type run kind inference");
assertIncludes(runTraceNormalizers, "export function coerceEventPayload(value: unknown): TraceEventPayload", "run trace normalizers type event payload coercion boundary");
assertIncludes(runTraceNormalizers, "return toPayloadSource<TraceEventPayload>(value) || {};", "run trace normalizers guard trace event payloads through the shared finite boundary");
assertNotIncludes(runTraceNormalizers, "value as TraceEventPayload", "run trace normalizers avoid casting raw trace event objects");
assertIncludes(runTraceNormalizers, "export function inferRunEventStatus(eventType: unknown, payload: TraceEventPayload = {}): string", "run trace normalizers type event status inference boundary");
assertNotIncludes(runTraceNormalizers, "type DecisionEventPayload = {\n  [key: string]: unknown;", "run trace normalizers avoid open-ended decision event payloads");
assertNotIncludes(runTraceNormalizers, "export type TraceEventPayload = {\n  [key: string]: unknown;", "run trace normalizers avoid open-ended trace event payloads");
assertNotIncludes(runTraceNormalizers, "Record<string, any>", "run trace normalizers avoid broad any records");
assertIncludes(runTraceNormalizers, "export type TraceEventCountsView = {", "run trace normalizers type event counts");
assertIncludes(runTraceNormalizers, "kind: RunEventKind;", "run trace normalizers type run event kind fields");
assertIncludes(runTraceNormalizers, "export type TraceEventView = {", "run trace normalizers type trace events");
assertIncludes(runTraceNormalizers, "payload: TraceEventPayload;", "run trace normalizers store named event payloads");
assertNotIncludes(runTraceNormalizers, "export type TraceEventView = JsonObject & {", "run trace normalizers avoids generic trace event object surface");
assertIncludes(runTraceNormalizers, "export type RunArtifactView = {", "run trace normalizers type run artifacts");
assertNotIncludes(runTraceNormalizers, "export type RunArtifactView = JsonObject & {", "run trace normalizers avoids generic artifact object surface");
assertIncludes(runTraceNormalizers, "type MetadataTimestamp = string | number;", "run trace normalizers types metadata timestamp values");
assertIncludes(runTraceNormalizers, "export type RunArtifactMetadataPayload = {", "run trace normalizers name raw run artifact metadata payload boundary");
assertIncludes(runTraceNormalizers, "export type RunArtifactMetadata = {", "run trace normalizers own normalized run artifact metadata boundary");
assertNotIncludes(runTraceNormalizers, "export type RunArtifactMetadataPayload = {\n  [key: string]: unknown;", "run trace normalizers avoid open-ended raw run artifact metadata indexes");
assertIncludes(runTraceNormalizers, "export type RunArtifactMetadata = {\n  [key: string]: unknown;", "run trace normalizers preserve extra artifact metadata keys explicitly");
assertNotIncludes(runTraceNormalizers, "export type RunArtifactMetadataPayload = JsonRecord & {", "run trace normalizers avoid carrying generic raw artifact metadata record");
assertNotIncludes(runTraceNormalizers, "export type RunArtifactMetadata = JsonRecord & {", "run trace normalizers avoid carrying generic normalized artifact metadata record");
assertIncludes(runTraceNormalizers, "finished_at?: unknown;", "run trace normalizers raw run artifact metadata names finished timestamp alias");
assertIncludes(runTraceNormalizers, "finished_at?: MetadataTimestamp;", "run trace normalizers normalizes artifact finished timestamp alias");
assertNotIncludes(runTraceNormalizers, "export type RunArtifactMetadata = JsonRecord;", "run trace normalizers avoid a pure run artifact metadata record");
assertNotIncludes(runTraceNormalizers, "export type RunArtifactMetadata = RunArtifactMetadataPayload & {", "run trace normalizers avoids carrying raw artifact metadata into normalized state");
assertIncludes(runTraceNormalizers, "metadata: RunArtifactMetadata;", "run trace normalizers routes artifact metadata through the named boundary");
assertIncludes(runTraceNormalizers, "iteration: string;", "run trace normalizers type artifact iteration");
assertNotIncludes(runTraceNormalizers, "iteration: unknown;", "run trace normalizers avoids generic artifact iteration");
assertIncludes(runTraceNormalizers, "export type TracePartView = {", "run trace normalizers type trace parts");
assertNotIncludes(runTraceNormalizers, "export type TracePartView = JsonObject & {", "run trace normalizers avoids generic trace part object surface");
assertIncludes(runTraceNormalizers, "export type TracePartMetadataPayload = {", "run trace normalizers name raw trace part metadata payload boundary");
assertIncludes(runTraceNormalizers, "export type TracePartMetadata = {\n  [key: string]: unknown;", "run trace normalizers own normalized trace part metadata boundary");
assertNotIncludes(runTraceNormalizers, "export type TracePartMetadataPayload = {\n  [key: string]: unknown;", "run trace normalizers avoid open-ended raw trace part metadata indexes");
assertNotIncludes(runTraceNormalizers, "export type TracePartMetadataPayload = JsonRecord & {", "run trace normalizers avoid carrying generic raw trace part metadata record");
assertNotIncludes(runTraceNormalizers, "export type TracePartMetadata = JsonRecord & {", "run trace normalizers avoid carrying generic normalized trace part metadata record");
assertIncludes(runTraceNormalizers, "tool_call_id?: unknown;", "run trace normalizers raw trace part metadata names tool call id alias");
assertIncludes(runTraceNormalizers, "streaming?: unknown;", "run trace normalizers raw trace part metadata names streaming state");
assertIncludes(runTraceNormalizers, "tool_call_id?: string;", "run trace normalizers normalizes trace part tool call id alias");
assertIncludes(runTraceNormalizers, "state?: string;", "run trace normalizers normalizes trace part metadata state");
assertIncludes(runTraceNormalizers, "streaming?: boolean;", "run trace normalizers normalizes trace part streaming state");
assertNotIncludes(runTraceNormalizers, "export type TracePartMetadata = JsonRecord;", "run trace normalizers avoid a pure trace part metadata record");
assertNotIncludes(runTraceNormalizers, "export type TracePartMetadata = TracePartMetadataPayload & {", "run trace normalizers avoids carrying raw trace part fields into normalized metadata");
assertIncludes(runTraceNormalizers, "metadata: TracePartMetadata;", "run trace normalizers routes trace part metadata through the named boundary");
assertIncludes(runTraceNormalizers, "type TracePartPayload = {", "run trace normalizers names raw trace part payload boundary");
assertIncludes(runTraceNormalizers, "part_id?: unknown;", "run trace normalizers raw trace part payload names part id alias");
assertIncludes(runTraceNormalizers, "part_type?: unknown;", "run trace normalizers raw trace part payload names part type alias");
assertNotIncludes(runTraceNormalizers, "type TracePartPayload = JsonRecord & {", "run trace normalizers avoid carrying raw trace parts through generic JSON records");
assertIncludes(runTraceNormalizers, "export type TraceFileChangeView = {", "run trace normalizers type trace file changes");
assertNotIncludes(runTraceNormalizers, "export type TraceFileChangeView = JsonObject & {", "run trace normalizers avoids generic file change object surface");
assertIncludes(runTraceNormalizers, "sourceId: string;", "run trace normalizers type file change source ids");
assertIncludes(runTraceNormalizers, "status: string;", "run trace normalizers type file change status aliases");
assertIncludes(runTraceNormalizers, "label: string;", "run trace normalizers type file change labels");
assertIncludes(runTraceNormalizers, "diffPreview: string;", "run trace normalizers type file change diff previews");
assertIncludes(runTraceNormalizers, "revertSupported: boolean;", "run trace normalizers type file revert support");
assertIncludes(runTraceNormalizers, "beforeContent: string | null;", "run trace normalizers type file change before content");
assertIncludes(runTraceNormalizers, "afterContent: string | null;", "run trace normalizers type file change after content");
assertNotIncludes(runTraceNormalizers, "beforeContent: unknown;", "run trace normalizers avoids generic file change before content");
assertNotIncludes(runTraceNormalizers, "afterContent: unknown;", "run trace normalizers avoids generic file change after content");
assertIncludes(runTraceNormalizers, "type TraceEventCountTarget = {", "run trace normalizers type live trace count targets");
assertIncludes(runTraceNormalizers, "rawEvents: TraceEventView[];", "run trace normalizers type live trace count raw events");
assertNotIncludes(runTraceNormalizers, "rawEvents: JsonObject[];", "run trace normalizers avoid generic raw event count targets");
assertNotIncludes(runTraceNormalizers, "type DecisionEventContext = JsonObject & {", "run trace normalizers avoid extending decision event context from generic JSON records");
assertIncludes(runTraceNormalizers, "function isTextRunEvent(event: Pick<TraceEventView, \"kind\" | \"eventType\">): boolean", "run trace normalizers check typed trace event text boundaries");
assertIncludes(runTraceNormalizers, "export function compactRunEvents(events: TraceEventView[]): TraceEventView[]", "run trace normalizers compact typed trace events");
assertIncludes(runTraceNormalizers, "export function normalizeTraceEventCounts(counts: unknown, events: TraceEventView[] = []): TraceEventCountsView", "run trace normalizers count typed trace events");
assertIncludes(runTraceNormalizers, "const kept: TraceEventView[] = [];", "run trace normalizers preserve typed event compaction item type");
assertNotIncludes(runTraceNormalizers, "export function normalizeTraceEventCounts(counts: unknown, events: unknown[] = []): TraceEventCountsView", "run trace normalizers avoid unknown event count lists");
for (const payloadType of [
  "TraceEventCountsPayload",
]) {
  assertIncludes(runTraceNormalizers, `type ${payloadType} =`, `run trace normalizers name ${payloadType} boundary`);
}
assertIncludes(runTraceNormalizers, "const countsRecord = toPayloadSource<TraceEventCountsPayload>(counts) || {};", "run trace normalizers narrow event count payloads to known fields");
assertIncludes(runTraceNormalizers, "toPayloadSource<SnapshotAvailability>(artifactRecord.snapshots_available || artifactRecord.snapshotsAvailable)", "run trace normalizers narrow artifact snapshot availability");
assertIncludes(runTraceNormalizers, "export function updateLiveTraceEventCounts(run: TraceEventCountTarget, event: TraceEventView): void", "run trace normalizers type live event count updates");
assertIncludes(runTraceNormalizers, "export function normalizeTraceEvent(event: unknown): TraceEventView", "run trace normalizers type trace event normalization");
assertIncludes(runTraceNormalizers, "const eventRecord = toTraceEventEnvelopePayload(event);", "run trace normalizers narrow trace events through envelope payload boundary");
assertIncludes(runTraceNormalizers, "export function normalizeRunArtifact(artifact: unknown, fallback: RunArtifactFallbackPayload = {}): RunArtifactView | null", "run trace normalizers type run artifact boundary");
assertIncludes(runTraceNormalizers, "type RunArtifactPayload = {", "run trace normalizers name fixed run artifact payload boundary");
assertIncludes(runTraceNormalizers, "const artifactRecord = toPayloadSource<RunArtifactPayload>(artifact);", "run trace normalizers narrow run artifacts before field reads");
assertIncludes(runTraceNormalizers, "const fallbackKind = normalizeRunKind(fallback.kind);", "run trace normalizers normalize artifact fallback kind");
assertIncludes(runTraceNormalizers, "function normalizeArtifactIteration(value: unknown): string", "run trace normalizers narrows artifact iteration");
assertIncludes(runTraceNormalizers, "const iteration = normalizeArtifactIteration(artifactRecord.iteration ?? fallback.iteration);", "run trace normalizers normalizes artifact iteration");
assertIncludes(runTraceNormalizers, "toolName && iteration !== \"\"", "run trace normalizers builds tool artifact ids from typed iteration");
assertNotIncludes(runTraceNormalizers, "const iteration = artifactRecord.iteration ?? fallback.iteration ?? \"\";", "run trace normalizers avoids raw artifact iteration passthrough");
assertNotIncludes(runTraceNormalizers, "iteration !== \"\" && iteration !== null && iteration !== undefined", "run trace normalizers avoids nullable artifact iteration checks");
assertIncludes(runTraceNormalizers, "export function normalizeRunArtifactMetadata(value: unknown): RunArtifactMetadata", "run trace normalizers exports run artifact metadata normalization");
assertIncludes(runTraceNormalizers, "function toRunArtifactMetadataPayload(value: unknown): RunArtifactMetadataPayload | null", "run trace normalizers narrows raw run artifact metadata payloads");
assertIncludes(runTraceNormalizers, "return toPayloadSource<RunArtifactMetadataPayload>(value);", "run trace normalizers preserve artifact metadata extensions behind a named payload source");
assertIncludes(runTraceNormalizers, "function normalizeMetadataTimestamp(value: unknown): MetadataTimestamp | null", "run trace normalizers normalizes artifact metadata timestamps");
assertIncludes(runTraceNormalizers, "const metadata: RunArtifactMetadata = {};", "run trace normalizers builds normalized run artifact metadata explicitly");
assertIncludes(runTraceNormalizers, "metadata.finished_at = finishedAt;", "run trace normalizers writes normalized artifact finished timestamp");
assertNotIncludes(runTraceNormalizers, "export function normalizeRunArtifactMetadata(value: unknown): RunArtifactMetadata {\n  return toJsonRecord(value) || {};\n}", "run trace normalizers avoids raw run artifact metadata passthrough");
assertIncludes(runTraceNormalizers, "metadata: normalizeRunArtifactMetadata(artifactRecord.metadata),", "run trace normalizers narrow run artifact metadata through the named boundary");
assertIncludes(runTraceNormalizers, "type BackgroundProcessEventPayload = {", "run trace normalizers keep a typed background process event payload boundary");
assertNotIncludes(runTraceNormalizers, "type BackgroundProcessEventPayload = {\n  [key: string]: unknown;", "run trace normalizers avoid open-ended background process payload indexes");
assertNotIncludes(runTraceNormalizers, "type BackgroundProcessEventPayload = TraceEventPayload & {", "run trace normalizers avoid carrying background process payloads through trace event payloads");
assertNotIncludes(runTraceNormalizers, "type BackgroundProcessEventPayload = JsonRecord & {", "run trace normalizers avoid carrying background process payloads through generic JSON records");
assertIncludes(runTraceNormalizers, "process_session_id?: unknown;", "run trace normalizers background process payload lists process session ids");
assertIncludes(runTraceNormalizers, "termination_reason?: unknown;", "run trace normalizers background process payload lists termination reasons");
assertIncludes(runTraceNormalizers, "function normalizeBackgroundProcessArtifact(\n  eventType: unknown,\n  payload: BackgroundProcessEventPayload,\n  fallback: RunArtifactFallbackPayload = {},\n): RunArtifactView | null", "run trace normalizers type background process artifact boundary");
assertIncludes(runTraceNormalizers, "const detailParts: string[] = [];", "run trace normalizers type background process detail parts");
assertIncludes(runTraceNormalizers, "export function normalizeTraceEventArtifact(\n  eventType: unknown,\n  payload: TraceEventPayload,\n  artifact: unknown,\n  fallback: RunArtifactFallbackPayload = {},\n): RunArtifactView | null", "run trace normalizers type event artifact boundary");
assertIncludes(runTraceNormalizers, "export function normalizeTracePart(part: unknown): TracePartView | null", "run trace normalizers type part export");
assertIncludes(runTraceNormalizers, "function toTracePartPayload(value: unknown): TracePartPayload | null", "run trace normalizers narrows raw trace part payloads");
assertIncludes(runTraceNormalizers, "const payload = toPayloadSource<TracePartPayload>(value);", "run trace normalizers limit trace part source reads to named fields");
assertIncludes(runTraceNormalizers, "part_id: payload.part_id,\n        partId: payload.partId,\n        part_type: payload.part_type,", "run trace normalizers projects trace part identity payload aliases");
assertIncludes(runTraceNormalizers, "metadata: payload.metadata,\n        artifact: payload.artifact,\n        created_at: payload.created_at,", "run trace normalizers preserves trace part metadata and artifact payloads");
assertIncludes(runTraceNormalizers, "const partRecord = toTracePartPayload(part);", "run trace normalizers narrow parts through typed payload boundary");
assertNotIncludes(runTraceNormalizers, "const partRecord = toJsonRecord(part);", "run trace normalizers avoids raw trace part records");
assertNotIncludes(runTraceNormalizers, "function toTracePartPayload(value: unknown): TracePartPayload | null {\n  return toJsonRecord(value);\n}", "run trace normalizers avoids passing raw trace parts through converter");
assertIncludes(runTraceNormalizers, "export function normalizeTracePartMetadata(value: unknown): TracePartMetadata", "run trace normalizers exports trace part metadata normalization");
assertIncludes(runTraceNormalizers, "function toTracePartMetadataPayload(value: unknown): TracePartMetadataPayload | null", "run trace normalizers narrows raw trace part metadata payloads");
assertIncludes(runTraceNormalizers, "return toPayloadSource<TracePartMetadataPayload>(value);", "run trace normalizers preserve trace part metadata extensions behind a named payload source");
assertIncludes(runTraceNormalizers, "const metadata: TracePartMetadata = {};", "run trace normalizers builds normalized trace part metadata explicitly");
assertIncludes(runTraceNormalizers, "metadata.tool_call_id = toolCallId;", "run trace normalizers writes normalized trace part tool call id");
assertIncludes(runTraceNormalizers, "metadata.streaming = coerceBoolean(payload.streaming);", "run trace normalizers writes normalized trace part streaming state");
assertNotIncludes(runTraceNormalizers, "export function normalizeTracePartMetadata(value: unknown): TracePartMetadata {\n  return toJsonRecord(value) || {};\n}", "run trace normalizers avoids passing raw trace part metadata directly into state");
assertIncludes(runTraceNormalizers, "metadata: normalizeTracePartMetadata(partRecord.metadata),", "run trace normalizers narrow part metadata through the named boundary");
assertIncludes(runTraceNormalizers, "export function normalizeTraceFileChange(change: unknown): TraceFileChangeView | null", "run trace normalizers type file change export");
assertIncludes(runTraceNormalizers, "type TraceFileChangePayload = {", "run trace normalizers name fixed file change payload boundary");
assertIncludes(runTraceNormalizers, "const changeRecord = toPayloadSource<TraceFileChangePayload>(change);", "run trace normalizers narrow file changes before field reads");
assertIncludes(runTraceNormalizers, "function normalizeOptionalContent(value: unknown): string | null", "run trace normalizers narrows optional file content");
assertIncludes(runTraceNormalizers, "const beforeContent = normalizeOptionalContent(changeRecord.before_content ?? changeRecord.beforeContent);", "run trace normalizers normalizes before file content");
assertIncludes(runTraceNormalizers, "const afterContent = normalizeOptionalContent(changeRecord.after_content ?? changeRecord.afterContent);", "run trace normalizers normalizes after file content");
assertIncludes(runTraceNormalizers, "const sourceId = String(changeRecord.source_id || changeRecord.sourceId || changeId).trim();", "run trace normalizers normalizes file change source ids");
assertIncludes(runTraceNormalizers, "const state = String(changeRecord.state || changeRecord.status || \"completed\").trim() || \"completed\";", "run trace normalizers normalizes file change status");
assertIncludes(runTraceNormalizers, "const label = String(changeRecord.label || path).trim() || path;", "run trace normalizers normalizes file change labels");
assertIncludes(runTraceNormalizers, "diffPreview: String(changeRecord.diff_preview || changeRecord.diffPreview || \"\"),", "run trace normalizers normalizes file change diff previews");
assertIncludes(runTraceNormalizers, "revertSupported: coerceBoolean(changeRecord.revert_supported ?? changeRecord.revertSupported),", "run trace normalizers normalizes file revert support");
assertNotIncludes(runTraceNormalizers, "const beforeContent = changeRecord.before_content ?? changeRecord.beforeContent ?? null;", "run trace normalizers avoids raw before file content passthrough");
assertNotIncludes(runTraceNormalizers, "const afterContent = changeRecord.after_content ?? changeRecord.afterContent ?? null;", "run trace normalizers avoids raw after file content passthrough");
assertIncludes(runTraceNormalizers, "const snapshots = toPayloadSource<SnapshotAvailability>(changeRecord.snapshots_available || changeRecord.snapshotsAvailable) || {};", "run trace normalizers narrow file change snapshots");
assertNotIncludes(runTraceNormalizers, "export type DelegatedTaskMetadata = JsonRecord;", "run trace normalizers avoid pure delegated task metadata JSON aliases");
assertNotIncludes(runTraceNormalizers, "type JsonRecord = Record<string, unknown>;", "run trace normalizers avoid a shared generic JSON record alias");
assertNotIncludes(runTraceNormalizers, "function toJsonRecord(value: unknown): JsonRecord | null", "run trace normalizers avoid a shared generic JSON record converter");
assertIncludes(runTraceNormalizers, "function toTraceEventEnvelopePayload(value: unknown): TraceEventEnvelopePayload", "run trace normalizers narrows raw trace event envelopes");
assertIncludes(runTraceNormalizers, "const payload = toPayloadSource<TraceEventEnvelopePayload>(value);", "run trace normalizers limit event envelope source reads to known fields");
assertIncludes(runTraceNormalizers, "schema_version: payload.schema_version,\n        schemaVersion: payload.schemaVersion,\n        event_id: payload.event_id,", "run trace normalizers projects trace event envelope identity fields");
assertIncludes(runTraceNormalizers, "payload: payload.payload,\n        artifact: payload.artifact,\n        kind: payload.kind,", "run trace normalizers preserves trace event envelope payload and artifact fields");
assertIncludes(runTraceNormalizers, "const eventRecord = toTraceEventEnvelopePayload(event);", "run trace normalizers normalizes trace events through envelope boundary");
assertNotIncludes(runTraceNormalizers, "const eventRecord = toJsonRecord(event) || {};", "run trace normalizers avoids raw trace event envelope records");
assertNotIncludes(runTraceNormalizers, "function toTraceEventEnvelopePayload(value: unknown): TraceEventEnvelopePayload {\n  return toJsonRecord(value) || {};\n}", "run trace normalizers avoids passing raw trace event envelopes through converter");
assertIncludes(chatClientSessions, "export interface ChatSession", "chat client sessions expose typed session model");
assertIncludes(chatClientSessions, "export type ChatMessageRole = \"user\" | \"assistant\";", "chat client sessions expose typed chat message roles");
assertIncludes(chatClientSessions, "export function normalizeChatMessageRole(value: unknown): ChatMessageRole", "chat client sessions normalize unknown message roles");
assertIncludes(chatClientSessions, "role: ChatMessageRole;", "chat client sessions type chat message roles");
assertIncludes(chatClientSessions, "export function makeMessage(role: ChatMessageRole, text: string, meta: string): ChatMessage", "chat client session message factory accepts typed roles");
assertIncludes(chatClientSessions, "export const SESSION_CHANNEL_FILTERS = [\"all\", \"web\"] as const;", "chat client sessions expose typed session channel filters");
assertIncludes(chatClientSessions, "export type SessionChannelFilter = (typeof SESSION_CHANNEL_FILTERS)[number];", "chat client sessions derive session channel filter union");
assertIncludes(chatClientSessions, "export function normalizeSessionChannelFilter(value: unknown): SessionChannelFilter", "chat client sessions normalize unknown channel filters");
assertNotIncludes(chatClientSessions, "type JsonRecord = Record<string, unknown>;", "chat client sessions avoid generic JSON aliases");
assertNotIncludes(chatClientSessions, "function toJsonRecord(value: unknown): JsonRecord | null", "chat client sessions avoid shared raw record converters");
assertIncludes(chatClientSessions, "export interface LiveEntryContentItem", "chat client sessions expose typed live entry content items");
assertIncludes(chatClientSessions, "artifact: RunArtifactView | null;", "chat client sessions type live entry content artifacts");
assertIncludes(chatClientSessions, "content: LiveEntryContentItem[];", "chat client sessions type live entry content state");
assertNotIncludes(chatClientSessions, "content: unknown[];", "chat client sessions avoid generic live entry content arrays");
assertIncludes(chatClientSessions, "export type LiveEntryMetadataPayload = {", "chat client sessions name raw live entry metadata payload boundary");
assertNotIncludes(chatClientSessions, "export type LiveEntryMetadataPayload = {\n  [key: string]: unknown;", "chat client sessions avoid open-ended raw live entry metadata indexes");
assertNotIncludes(chatClientSessions, "export type LiveEntryMetadataPayload = JsonRecord & {", "chat client sessions avoids open-ended raw live entry metadata records");
assertIncludes(chatClientSessions, "export type LiveEntryMetadata = {", "chat client sessions own normalized live entry metadata");
assertNotIncludes(chatClientSessions, "export type LiveEntryMetadata = JsonRecord & {", "chat client sessions avoids aliasing normalized live entry metadata to raw JSON records");
assertNotIncludes(chatClientSessions, "export type LiveEntryMetadata = {\n  [key: string]: unknown;", "chat client sessions removes open-ended live entry metadata keys");
assertIncludes(chatClientSessions, "sender_name?: unknown;", "chat client sessions raw live entry metadata names sender alias");
assertIncludes(chatClientSessions, "sender_id?: unknown;", "chat client sessions raw live entry metadata names sender id alias");
assertIncludes(chatClientSessions, "run_id?: unknown;", "chat client sessions raw live entry metadata names legacy run references");
assertIncludes(chatClientSessions, "runId?: unknown;", "chat client sessions raw live entry metadata names camel-case run references");
assertIncludes(chatClientSessions, "sender_name?: string;", "chat client sessions normalizes live entry sender alias to string");
assertIncludes(chatClientSessions, "sender_id?: string;", "chat client sessions normalizes live entry sender id to string");
assertIncludes(chatClientSessions, "run_id?: string;", "chat client sessions normalizes legacy run references to strings");
assertIncludes(chatClientSessions, "runId?: string;", "chat client sessions normalizes camel-case run references to strings");
assertNotIncludes(chatClientSessions, "export type LiveEntryMetadata = Record<string, unknown>;", "chat client sessions avoid a pure live entry metadata record");
assertNotIncludes(chatClientSessions, "export type LiveEntryMetadata = Record<string, unknown> & {", "chat client sessions avoid inline live entry metadata records");
assertNotIncludes(chatClientSessions, "export type LiveEntryMetadata = LiveEntryMetadataPayload & {", "chat client sessions avoids carrying raw sender fields into normalized metadata");
assertIncludes(chatClientSessions, "metadata: LiveEntryMetadata;", "chat client sessions route live entry metadata through the shared metadata boundary");
assertIncludes(chatClientSessions, "export type ChatSessionStatusMetadata = Record<string, never>;", "chat client sessions keep session status metadata fixed");
assertNotIncludes(chatClientSessions, "export type ChatSessionStatusMetadata = {\n  [key: string]: unknown;\n};", "chat client sessions avoid open-ended session status metadata");
assertNotIncludes(chatClientSessions, "export type ChatSessionStatusMetadataPayload", "chat client sessions keep a single session status metadata boundary");
assertNotIncludes(chatClientSessions, "export type ChatSessionStatusMetadata = ChatSessionStatusMetadataPayload;", "chat client sessions avoid status metadata alias wrappers");
assertNotIncludes(chatClientSessions, "export type ChatSessionStatusMetadata = JsonRecord;", "chat client sessions avoid aliasing status metadata to raw JSON records");
assertNotIncludes(chatClientSessions, "export type ChatSessionStatusMetadata = Record<string, unknown>;", "chat client sessions avoid inline status metadata records");
assertIncludes(chatClientSessions, "metadata: ChatSessionStatusMetadata;", "chat client sessions route status metadata through the shared metadata boundary");
assertIncludes(chatClientSessions, "runs: RunViewState[];", "chat client sessions type run list boundary");
assertIncludes(chatClientSessions, "export function createSession(externalChatId?: string): ChatSession", "chat client session factory is typed");
assertIncludes(chatClientSessions, "type StoredDraftSessionPayload = {", "chat client sessions types stored draft payloads");
assertNotIncludes(chatClientSessions, "type StoredDraftSessionRecord", "chat client sessions keep a single stored draft payload boundary");
assertNotIncludes(chatClientSessions, "type StoredDraftSessionPayload = StoredDraftSessionRecord & {", "chat client sessions avoids stored draft alias wrappers");
assertNotIncludes(chatClientSessions, "type StoredDraftSessionPayload = JsonRecord & {", "chat client sessions avoids open-ended stored draft payload records");
assertIncludes(chatClientSessions, "function toStoredDraftSessionPayload(value: unknown): StoredDraftSessionPayload | null", "chat client sessions narrows stored draft payloads before session normalization");
assertIncludes(chatClientSessions, "const payload = toPayloadSource<StoredDraftSessionPayload>(value);", "chat client sessions limits stored draft reads to known payload fields");
assertIncludes(chatClientSessions, "externalChatId: payload.externalChatId,\n        title: payload.title,\n        updatedAt: payload.updatedAt,", "chat client sessions project stored draft payloads onto named fields");
assertNotIncludes(chatClientSessions, "value as Record<string, unknown>", "chat client sessions avoid casting finite stored drafts to open records");
assertNotIncludes(chatClientSessions, "function toStoredDraftSessionPayload(value: unknown): StoredDraftSessionPayload | null {\n  return toJsonRecord(value);\n}", "chat client sessions avoid passing raw stored draft records through converter");
assertIncludes(chatClientSessions, "export function normalizeStoredDraftSession(\n  value: unknown,\n  normalizeEventTimestamp: TimestampNormalizer,\n): ChatSession | null {\n  const payload = toStoredDraftSessionPayload(value);", "chat client sessions routes stored draft reads through typed payload boundary");
assertIncludes(chatClientSessions, "const drafts: unknown = raw ? JSON.parse(raw) : [];", "chat client sessions keeps localStorage draft JSON at the unknown boundary");
assertNotIncludes(chatClientSessions, "interface StoredDraftSession {", "chat client sessions avoids trusting stored draft records before narrowing");
assertIncludes(chatClientSessions, "session.status = {", "stored draft session normalization preserves idle status reset");
assertIncludes(chatClientSessions, "localStorage.setItem(storageKey, JSON.stringify(drafts));", "chat client draft sessions preserve localStorage persistence");
assertIncludes(chatClientTokens, "export function randomToken(): string", "chat client token helper is typed");
assertIncludes(logDefaults, "export interface LogState", "log defaults expose typed log state");
assertIncludes(logDefaults, "type LogSettingsDataPayload = {", "log defaults type fixed log settings data payload boundary");
assertNotIncludes(logDefaults, "type LogSettingsDataPayload = JsonRecord & {", "log defaults avoid open-ended log settings data payload records");
assertIncludes(logDefaults, "retention_days?: unknown;", "log defaults name retention payload field");
assertIncludes(logDefaults, "log_system_prompt?: unknown;", "log defaults name system prompt payload field");
assertIncludes(logDefaults, "log_system_prompt_lines?: unknown;", "log defaults name system prompt line payload field");
assertIncludes(logDefaults, "log_reasoning_details?: unknown;", "log defaults name reasoning detail payload field");
assertIncludes(logDefaults, "levels?: unknown;", "log defaults name levels payload field");
assertIncludes(logDefaults, "function toLogSettingsDataPayload(value: unknown): LogSettingsDataPayload", "log defaults narrow payload objects before field reads");
assertIncludes(logDefaults, "import { toPayloadSource } from \"./payloadBoundary\";", "log defaults reuse the shared finite payload guard");
assertIncludes(logDefaults, "return toPayloadSource<LogSettingsDataPayload>(value) || {};", "log defaults guard log payloads through the shared boundary");
assertNotIncludes(logDefaults, "value as LogSettingsDataPayload", "log defaults avoid casting raw log payload objects");
assertIncludes(logDefaults, "log_system_prompt: payload.log_system_prompt !== false", "log defaults preserve system prompt fallback");
assertIncludes(logDefaults, "const payload = toLogSettingsDataPayload(log);", "log defaults use typed log payload in normalizer");
assertIncludes(networkDefaults, "type NetworkSettingsDataPayload = {", "network defaults type fixed network settings data payload boundary");
assertNotIncludes(networkDefaults, "type NetworkSettingsDataPayload = JsonRecord & {", "network defaults avoid open-ended network settings data payload records");
assertIncludes(networkDefaults, "http_proxy?: unknown;", "network defaults name HTTP proxy payload field");
assertIncludes(networkDefaults, "https_proxy?: unknown;", "network defaults name HTTPS proxy payload field");
assertIncludes(networkDefaults, "no_proxy?: unknown;", "network defaults name no proxy payload field");
assertIncludes(networkDefaults, "function toNetworkSettingsDataPayload(value: unknown): NetworkSettingsDataPayload", "network defaults narrow payload objects before field reads");
assertIncludes(networkDefaults, "import { toPayloadSource } from \"./payloadBoundary\";", "network defaults reuse the shared finite payload guard");
assertIncludes(networkDefaults, "return toPayloadSource<NetworkSettingsDataPayload>(value) || {};", "network defaults guard network payloads through the shared boundary");
assertNotIncludes(networkDefaults, "value as NetworkSettingsDataPayload", "network defaults avoid casting raw network payload objects");
assertIncludes(networkDefaults, "function stringOrDefault(value: unknown, fallback: string): string", "network defaults normalize proxy values to strings");
assertIncludes(networkDefaults, "const payload = toNetworkSettingsDataPayload(network);", "network defaults use typed network payload in normalizer");
assertIncludes(channelSettingsActions, "export function useChannelSettingsActions", "channel settings actions remain exported");
assertIncludes(channelSettingsActions, "\"/api/settings/channels\"", "channel settings actions keep channel settings endpoint");
assertIncludes(channelSettingsActions, "import { normalizeChannelSettings } from \"./settingsNormalizers\";", "channel settings actions only imports payload normalizer");
assertIncludes(channelSettingsActions, "import type { ChannelConnectForm, ChannelSettings, ChannelView } from \"./useSettingsState\";", "channel settings actions reuse settings state channel view types");
assertIncludes(channelSettingsActions, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", "channel settings actions keep unchecked API responses unknown");
assertIncludes(channelSettingsActions, "interface ChannelSettingsState", "channel settings actions type channel state boundary");
assertIncludes(channelSettingsActions, "type ChannelSettingsPayload = {", "channel settings actions name fixed channel settings payload boundary");
assertNotIncludes(channelSettingsActions, "type ChannelSettingsPayload = JsonRecord & {", "channel settings actions avoids open-ended channel settings payload records");
assertIncludes(channelSettingsActions, "type ChannelMutationPayload = {", "channel settings actions name fixed channel mutation payload boundary");
assertIncludes(channelSettingsActions, "type ChannelPayloadRecord = {", "channel settings actions name fixed channel item payload boundary");
assertIncludes(channelSettingsActions, "function toChannelPayloadRecord(value: unknown): ChannelPayloadRecord | null", "channel settings actions route channel records through named converter");
assertIncludes(channelSettingsActions, "id: payload.id,\n        name: payload.name,\n        type: payload.type,\n        enabled: payload.enabled,\n        description: payload.description,\n        status: payload.status,", "channel settings actions projects channel payloads onto named fields");
assertIncludes(channelSettingsActions, "function toChannelSettingsPayload(value: unknown): ChannelSettingsPayload | null", "channel settings actions route settings payload through named converter");
assertIncludes(channelSettingsActions, "connected: payload.connected,\n        available: payload.available,\n        channels: payload.channels,", "channel settings actions projects channel settings payloads onto named fields");
assertIncludes(channelSettingsActions, "function toChannelMutationPayload(value: unknown): ChannelMutationPayload", "channel settings actions narrows channel mutation responses");
assertIncludes(channelSettingsActions, "function toChannelMutationPayload(value: unknown): ChannelMutationPayload {\n  const payload = toPayloadSource<ChannelMutationPayload>(value);\n  if (!payload) {\n    return {};\n  }", "channel settings actions handles non-object mutation responses before field projection");
assertNotIncludes(channelSettingsActions, "channel: payload?.channel,\n    restart_required: payload?.restart_required,", "channel settings actions avoid optional chaining after nullable mutation payload boundary");
assertIncludes(channelSettingsActions, "channel: payload.channel,\n    restart_required: payload.restart_required,", "channel settings actions projects mutation payloads onto named fields");
assertIncludes(channelSettingsActions, "function toChannelView(value: unknown): ChannelView | null", "channel settings actions narrow channel payloads");
assertIncludes(channelSettingsActions, "const record = toChannelPayloadRecord(value);", "channel settings actions avoids inline channel item records");
assertIncludes(channelSettingsActions, "enabled: record.enabled === undefined ? undefined : Boolean(record.enabled),", "channel settings actions normalizes channel enabled flag");
assertIncludes(channelSettingsActions, "description: typeof record.description === \"string\" || typeof record.description === \"number\" ? String(record.description) : undefined,", "channel settings actions normalizes channel description");
assertIncludes(channelSettingsActions, "status: typeof record.status === \"string\" || typeof record.status === \"number\" ? String(record.status) : undefined,", "channel settings actions normalizes channel status");
assertIncludes(channelSettingsActions, "function normalizeChannels(payload: unknown): ChannelSettings", "channel settings actions normalize channel settings payload");
assertIncludes(channelSettingsActions, "function channelViewList(value: unknown): ChannelView[]", "channel settings actions normalize channel payload arrays into channel views");
assertIncludes(channelSettingsActions, "const settings = normalizeChannelSettings(toChannelSettingsPayload(payload) || {});", "channel settings actions normalize channel settings payload before state writes");
assertIncludes(channelSettingsActions, "return {\n    connected: channelViewList(settings.connected),\n    available: channelViewList(settings.available),\n    channels: channelViewList(settings.channels),\n  };", "channel settings actions project normalized channel settings into typed state");
assertNotIncludes(channelSettingsActions, "return normalizeChannelSettings(toChannelSettingsPayload(payload) || {}) as ChannelSettings;", "channel settings actions avoids casting normalized payloads into state");
assertIncludes(channelSettingsActions, "function isVisibleChannel(channel: ChannelView): boolean", "channel settings actions filters typed channel views locally");
assertIncludes(channelSettingsActions, "function sortChannelViews(channels: ChannelView[]): ChannelView[]", "channel settings actions sorts typed channel views locally");
assertIncludes(channelSettingsActions, "settingsState.channels = {\n      connected: nextConnected,\n      available: currentChannels.available,\n      channels: nextConnected,\n    };", "channel settings actions patch channel state with fixed fields");
assertNotIncludes(channelSettingsActions, "settingsState.channels = {\n      ...settingsState.channels,", "channel settings actions avoids preserving arbitrary channel settings keys");
assertNotIncludes(channelSettingsActions, "type ChannelSettingsPayload = JsonRecord;", "channel settings actions avoids a pure channel settings payload record");
assertNotIncludes(channelSettingsActions, "interface ChannelView extends ChannelPayloadRecord", "channel settings actions avoids local generic channel view inheritance");
assertNotIncludes(channelSettingsActions, "interface ChannelView extends JsonRecord", "channel settings actions avoids generic channel view inheritance");
assertNotIncludes(channelSettingsActions, "visibleChannels([channel])", "channel settings actions avoids passing typed channel views through payload visibility helper");
assertNotIncludes(channelSettingsActions, "sortChannelList([...connected", "channel settings actions avoids passing typed channel views through payload sorter");
assertNotIncludes(channelSettingsActions, "const record = toJsonRecord(value);\n  const id = String(record?.id || \"\").trim();", "channel settings actions avoids inline channel item records");
assertNotIncludes(channelSettingsActions, "return normalizeChannelSettings(toJsonRecord(payload) || {}) as ChannelSettings;", "channel settings actions avoids inline channel settings records");
assertIncludes(channelSettingsActions, "requestSettingsJson(\"/api/settings/channels\")", "channel settings actions load channel settings as an unchecked response");
assertIncludes(channelSettingsActions, "const payload = toChannelMutationPayload(await requestSettingsJson(\"/api/settings/channels\",", "channel settings actions converts channel connect responses through typed payload boundary");
assertIncludes(channelSettingsActions, "const payload = toChannelMutationPayload(await requestSettingsJson(`/api/settings/channels/${encodeURIComponent(channel.id)}/disconnect`", "channel settings actions converts channel disconnect responses through typed payload boundary");
assertNotIncludes(channelSettingsActions, "requestSettingsJson<", "channel settings actions avoid trusting unchecked API response generics");
assertIncludes(channelSettingsActions, "upsertConnectedChannel(channel)", "channel settings actions keep local connected channel update");
assertIncludes(channelSettingsActions, "function errorMessage(error: unknown): string", "channel settings actions narrow unknown errors");
assertNotIncludes(channelSettingsActions, "Promise<any>", "channel settings actions avoid any request promises");
assertNotIncludes(channelSettingsActions, "catch (error: any)", "channel settings actions avoid any catch boundaries");
assertIncludes(logSettingsActions, "export function useLogSettingsActions", "log settings actions remain exported");
assertIncludes(payloadBoundary, "type PayloadSource<Payload extends object> = {\n  [Key in keyof Payload]?: unknown;\n};", "payload boundary limits finite source reads to declared fields");
assertIncludes(payloadBoundary, "export function toPayloadSource<Payload extends object>(value: unknown): PayloadSource<Payload> | null", "payload boundary exposes the shared non-array object guard");
assertIncludes(payloadBoundary, "export function toPayloadSource(value: unknown): object | null", "payload boundary implements object validation without a generic assertion");
assertIncludes(payloadBoundary, "!Array.isArray(value)", "payload boundary rejects arrays before field projection");
assertNotIncludes(payloadBoundary, "as PayloadSource", "payload boundary avoids asserting guarded objects as generic payloads");
assertIncludes(payloadBoundary, "export function toPayloadList(value: unknown): unknown[]", "payload boundary exposes the shared array guard");
assertIncludes(payloadBoundary, "return Array.isArray(value) ? value : [];", "payload boundary rejects non-arrays before item normalization");
for (const [payloadAdapter, moduleName] of [
  [chatClientHistoryPayloads, "history payload adapter"],
  [chatClientLiveSocket, "live socket adapter"],
  [chatClientRunPayloads, "run payload adapter"],
  [chatClientSessions, "chat session adapter"],
  [runTraceNormalizers, "run trace normalizers"],
  [settingsNormalizers, "settings normalizers"],
  [browserDefaults, "browser defaults"],
]) {
  assertIncludes(payloadAdapter, "import { toPayloadSource } from \"./payloadBoundary\";", `${moduleName} reuses the shared finite payload guard`);
  assertNotIncludes(payloadAdapter, "type PayloadSource<Payload extends object>", `${moduleName} avoids a duplicate payload source type`);
  assertNotIncludes(payloadAdapter, "function toPayloadSource<Payload extends object>", `${moduleName} avoids a duplicate payload source guard`);
}
for (const [settingsActions, moduleName, payloadTypes] of [
  [browserSettingsActions, "browser settings actions", ["BrowserSettingsPayload", "BrowserOperationPayload"]],
  [channelSettingsActions, "channel settings actions", ["ChannelPayloadRecord", "ChannelSettingsPayload", "ChannelMutationPayload"]],
  [logSettingsActions, "log settings actions", ["LogSettingsPayload"]],
  [mcpSettingsActions, "MCP settings actions", ["McpSettingsPayload", "McpImportedServerPayload", "McpRuntimeView", "McpServerView"]],
  [modelSettingsActions, "model settings actions", ["ModelSelectPayload", "ModelSettingsPayload", "ModelProviderPayload", "MediaSettingsPayload", "MediaSectionPayload", "MediaSavePayload", "ModelMetadataEntryView"]],
  [networkSettingsActions, "network settings actions", ["NetworkSettingsPayload"]],
  [scheduleSettingsActions, "schedule settings actions", ["ScheduleSettingsPayload"]],
  [searchSettingsActions, "search settings actions", ["SearchSettingsPayload", "SearchDataPayload", "SearxngOptionsPayload", "SearxngOptionsDataPayload", "SearxngOptionPayload"]],
  [updateSettingsActions, "update settings actions", ["UpdateStatusPayload", "RunUpdatePayload"]],
]) {
  assertIncludes(settingsActions, "import { toPayloadSource } from \"./payloadBoundary\";", `${moduleName} reuse the shared finite payload guard`);
  assertNotIncludes(settingsActions, "type PayloadSource<Payload extends object>", `${moduleName} avoid duplicate payload source types`);
  assertNotIncludes(settingsActions, "function toPayloadSource<Payload extends object>", `${moduleName} avoid duplicate payload source guards`);
  assertIncludes(settingsActions, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", `${moduleName} keep unchecked API responses unknown`);
  assertNotIncludes(settingsActions, "type RequestSettingsJson = <T = unknown>", `${moduleName} avoid caller-selected response types`);
  assertNotIncludes(settingsActions, "function toJsonRecord(value: unknown): JsonRecord", `${moduleName} avoid redundant generic record converters`);
  for (const payloadType of payloadTypes) {
    assertIncludes(settingsActions, `toPayloadSource<${payloadType}>(value)`, `${moduleName} limit ${payloadType} source reads to known fields`);
  }
}
assertIncludes(logSettingsActions, "\"/api/settings/log\"", "log settings actions keep log settings endpoint");
assertIncludes(logSettingsActions, "type LogSettingsPayload = {", "log settings actions type log API payload boundary");
assertNotIncludes(logSettingsActions, "type LogSettingsPayload = JsonRecord & {", "log settings actions avoids open-ended log API payload records");
assertIncludes(logSettingsActions, "interface LogSettingsState", "log settings actions type log state boundary");
assertIncludes(logSettingsActions, "function toLogSettingsPayload(value: unknown): LogSettingsPayload", "log settings actions narrows log settings responses");
assertIncludes(logSettingsActions, "if (!payload) {\n    return {};\n  }", "log settings actions handles non-object log settings responses before field projection");
assertIncludes(logSettingsActions, "log: payload.log,", "log settings actions projects log settings payloads onto named fields");
assertIncludes(logSettingsActions, "toLogSettingsPayload(await requestSettingsJson(\"/api/settings/log\"))", "log settings actions convert unknown log load responses through the payload boundary");
assertIncludes(logSettingsActions, "toLogSettingsPayload(await requestSettingsJson(\"/api/settings/log\",", "log settings actions convert unknown log save responses through the payload boundary");
assertNotIncludes(logSettingsActions, "requestSettingsJson<LogSettingsPayload>", "log settings actions avoid trusting unchecked API response generics");
assertNotIncludes(logSettingsActions, "const payload = await requestSettingsJson<LogSettingsPayload>(\"/api/settings/log\");", "log settings actions avoids direct raw log load payloads");
assertNotIncludes(logSettingsActions, "const payload = await requestSettingsJson<LogSettingsPayload>(\"/api/settings/log\",", "log settings actions avoids direct raw log save payloads");
assertIncludes(logSettingsActions, "function errorMessage(error: unknown): string", "log settings actions narrow unknown errors");
assertNotIncludes(logSettingsActions, "Promise<any>", "log settings actions avoid any request promises");
assertNotIncludes(logSettingsActions, "catch (error: any)", "log settings actions avoid any catch boundaries");
assertIncludes(logSettingsActions, "log_reasoning_details: Boolean(settingsState.logForm.logReasoningDetails)", "log settings actions keep reasoning detail payload");
assertIncludes(networkSettingsActions, "export function useNetworkSettingsActions", "network settings actions remain exported");
assertIncludes(networkSettingsActions, "\"/api/settings/network\"", "network settings actions keep network settings endpoint");
assertIncludes(networkSettingsActions, "type NetworkSettingsPayload = {", "network settings actions type network API payload boundary");
assertNotIncludes(networkSettingsActions, "type NetworkSettingsPayload = JsonRecord & {", "network settings actions avoids open-ended network API payload records");
assertIncludes(networkSettingsActions, "function toNetworkSettingsPayload(value: unknown): NetworkSettingsPayload", "network settings actions narrows network settings responses");
assertIncludes(networkSettingsActions, "if (!payload) {\n    return {};\n  }", "network settings actions handles non-object network settings responses before field projection");
assertIncludes(networkSettingsActions, "network: payload.network,", "network settings actions projects network settings payloads onto named fields");
assertIncludes(networkSettingsActions, "toNetworkSettingsPayload(await requestSettingsJson(\"/api/settings/network\"))", "network settings actions convert unknown network load responses through the payload boundary");
assertIncludes(networkSettingsActions, "toNetworkSettingsPayload(await requestSettingsJson(\"/api/settings/network\",", "network settings actions convert unknown network save responses through the payload boundary");
assertNotIncludes(networkSettingsActions, "requestSettingsJson<NetworkSettingsPayload>", "network settings actions avoid trusting unchecked API response generics");
assertNotIncludes(networkSettingsActions, "const payload = await requestSettingsJson<NetworkSettingsPayload>(\"/api/settings/network\");", "network settings actions avoids direct raw network load payloads");
assertNotIncludes(networkSettingsActions, "const payload = await requestSettingsJson<NetworkSettingsPayload>(\"/api/settings/network\",", "network settings actions avoids direct raw network save payloads");
assertIncludes(networkSettingsActions, "function errorMessage(error: unknown): string", "network settings actions narrow unknown errors");
assertNotIncludes(networkSettingsActions, "Promise<any>", "network settings actions avoid any request promises");
assertNotIncludes(networkSettingsActions, "catch (error: any)", "network settings actions avoid any catch boundaries");
assertIncludes(networkSettingsActions, "http_proxy: settingsState.networkForm.httpProxy", "network settings actions keep proxy payload");
assertIncludes(modelSettingsActions, "export function useModelSettingsActions", "model settings actions remain exported");
assertIncludes(modelSettingsActions, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", "model settings actions keep unchecked API responses unknown");
assertIncludes(modelSettingsActions, "interface ModelSettingsState", "model settings actions type model/media state boundary");
assertIncludes(modelSettingsActions, "interface ModelSettingsCopy", "model settings actions type model/media copy boundary");
assertIncludes(modelSettingsActions, "import { normalizeModelReasoningEffort, type ModelReasoningEffort } from \"./modelReasoning\";", "model settings actions import typed reasoning effort boundary");
assertIncludes(modelSettingsActions, "type ModelSelectPayload = {", "model settings actions name fixed model select payload boundary");
assertIncludes(modelSettingsActions, "restart_required?: unknown;", "model settings actions treat restart flags as unknown payload fields");
assertIncludes(modelSettingsActions, "reasoning_effort?: unknown;", "model settings actions treat select payload reasoning effort as unknown");
assertIncludes(modelSettingsActions, "type ModelSettingsPayload = {", "model settings actions name fixed model settings payload boundary");
assertNotIncludes(modelSettingsActions, "type ModelSettingsPayload = JsonRecord & {", "model settings actions avoid open-ended model settings payload records");
assertIncludes(modelSettingsActions, "default_provider?: unknown;", "model settings actions name default provider payload field");
assertIncludes(modelSettingsActions, "type ModelProviderPayload = {", "model settings actions name fixed model provider payload boundary");
assertNotIncludes(modelSettingsActions, "type ModelProviderPayload = JsonRecord & {", "model settings actions avoid open-ended model provider payload records");
assertIncludes(modelSettingsActions, "selected_model?: unknown;", "model settings actions name selected model payload field");
assertIncludes(modelSettingsActions, "model_metadata?: unknown;", "model settings actions preserve model metadata payload field");
assertIncludes(modelSettingsActions, "media_models?: unknown;", "model settings actions preserve media models payload field");
assertIncludes(modelSettingsActions, "type MediaSavePayload = {", "model settings actions name fixed media save payload boundary");
assertIncludes(modelSettingsActions, "type MediaSettingsPayload = {", "model settings actions name fixed media settings payload boundary");
assertNotIncludes(modelSettingsActions, "type MediaSettingsPayload = JsonRecord & {", "model settings actions avoid open-ended media settings payload records");
assertIncludes(modelSettingsActions, "type MediaSectionPayload = {", "model settings actions name fixed media section payload boundary");
assertNotIncludes(modelSettingsActions, "type MediaSectionPayload = JsonRecord & {", "model settings actions avoid open-ended media section payload records");
assertIncludes(modelSettingsActions, "type ModelMetadataMapPayload = {\n  [modelId: string]: unknown;\n};", "model settings actions name dynamic model metadata map boundary");
assertIncludes(modelSettingsActions, "type MediaModelMapPayload = {\n  [Category in MediaCategory]?: unknown;\n};", "model settings actions restrict media model payload keys to canonical categories");
assertIncludes(modelSettingsActions, "type MediaSectionsMapPayload = {\n  [Category in MediaCategory]?: unknown;\n};", "model settings actions restrict media section payload keys to canonical categories");
assertNotIncludes(modelSettingsActions, "[category: string]: unknown;", "model settings actions avoid open media category payload keys");
assertIncludes(modelSettingsActions, "reasoningSelections: Record<string, ModelReasoningEffort>;", "model settings actions narrow reasoning selection state");
assertNotIncludes(modelSettingsActions, "type JsonRecord = Record<string, unknown>;", "model settings actions avoid a shared generic JSON record alias");
assertNotIncludes(modelSettingsActions, "function toJsonRecord(value: unknown): JsonRecord", "model settings actions avoid a shared generic JSON record converter");
for (const payloadType of [
  "ModelSelectPayload",
  "ModelSettingsPayload",
  "ModelProviderPayload",
  "MediaSettingsPayload",
  "MediaSectionPayload",
  "MediaSavePayload",
  "ModelMetadataEntryView",
]) {
  assertIncludes(modelSettingsActions, `toPayloadSource<${payloadType}>(value)`, `model settings actions limit ${payloadType} source reads to known fields`);
}
assertIncludes(modelSettingsActions, "function toModelSelectPayload(value: unknown): ModelSelectPayload", "model settings actions narrows model select responses");
assertIncludes(modelSettingsActions, "function toModelSelectPayload(value: unknown): ModelSelectPayload {\n  const payload = toPayloadSource<ModelSelectPayload>(value);\n  if (!payload) {\n    return {};\n  }", "model settings actions handles non-object model select responses before field projection");
assertIncludes(modelSettingsActions, "restart_required: payload.restart_required,\n    reasoning_effort: payload.reasoning_effort,", "model settings actions projects model select payloads onto named fields");
assertIncludes(modelSettingsActions, "function toModelSettingsPayload(value: unknown): ModelSettingsPayload", "model settings actions narrow model settings before field reads");
assertIncludes(modelSettingsActions, "function toModelSettingsPayload(value: unknown): ModelSettingsPayload {\n  const payload = toPayloadSource<ModelSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "model settings actions handles non-object model settings responses before field projection");
assertIncludes(modelSettingsActions, "default_provider: payload.default_provider,\n    active_model: payload.active_model,\n    providers: payload.providers,", "model settings actions projects model settings payloads onto named fields");
assertIncludes(modelSettingsActions, "default_provider: String(settings.default_provider || \"\"),", "model settings actions normalizes default provider before state writes");
assertNotIncludes(modelSettingsActions, "default_provider: settings.default_provider ?? null,", "model settings actions avoids nullable default provider state writes");
assertIncludes(modelSettingsActions, "function toModelProviderPayload(value: unknown): ModelProviderPayload", "model settings actions narrow model providers before field reads");
assertIncludes(modelSettingsActions, "function toModelProviderPayload(value: unknown): ModelProviderPayload {\n  const payload = toPayloadSource<ModelProviderPayload>(value);\n  if (!payload) {\n    return {};\n  }", "model settings actions handles non-object model provider records before field projection");
assertIncludes(modelSettingsActions, "id: payload.id,\n    name: payload.name,\n    type: payload.type,\n    is_default: payload.is_default,\n    selected_model: payload.selected_model,\n    models: payload.models,\n    model_metadata: payload.model_metadata,\n    media_models: payload.media_models,\n    reasoning_effort: payload.reasoning_effort,", "model settings actions projects model provider payloads onto named fields");
assertIncludes(modelSettingsActions, "function toMediaSettingsPayload(value: unknown): MediaSettingsPayload", "model settings actions narrow media settings before field reads");
assertIncludes(modelSettingsActions, "function toMediaSettingsPayload(value: unknown): MediaSettingsPayload {\n  const payload = toPayloadSource<MediaSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "model settings actions handles non-object media settings responses before field projection");
assertIncludes(modelSettingsActions, "sections: payload.sections,\n    providers: payload.providers,", "model settings actions projects media settings payloads onto named fields");
assertIncludes(modelSettingsActions, "function toMediaSectionPayload(value: unknown): MediaSectionPayload", "model settings actions narrow media sections before field reads");
assertIncludes(modelSettingsActions, "function toMediaSectionPayload(value: unknown): MediaSectionPayload {\n  const payload = toPayloadSource<MediaSectionPayload>(value);\n  if (!payload) {\n    return {};\n  }", "model settings actions handles non-object media section records before field projection");
assertIncludes(modelSettingsActions, "category: payload.category,\n    enabled: payload.enabled,\n    provider_id: payload.provider_id,\n    model: payload.model,", "model settings actions projects media section payloads onto named fields");
assertIncludes(modelSettingsActions, "function toMediaSavePayload(value: unknown): MediaSavePayload", "model settings actions narrows media save responses");
assertIncludes(modelSettingsActions, "function toMediaSavePayload(value: unknown): MediaSavePayload {\n  const payload = toPayloadSource<MediaSavePayload>(value);\n  if (!payload) {\n    return {};\n  }", "model settings actions handles non-object media save responses before field projection");
assertIncludes(modelSettingsActions, "media: payload.media,\n    restart_required: payload.restart_required,", "model settings actions projects media save payloads onto named fields");
assertIncludes(modelSettingsActions, "function normalizeModelSettings(payload: unknown): ModelSettings", "model settings actions normalize model settings payload");
assertIncludes(modelSettingsActions, "function normalizeMediaSettingsView(payload: unknown): MediaSettings", "model settings actions normalize media settings payload");
assertIncludes(modelSettingsActions, "const provider = toModelProviderPayload(value);", "model settings actions use typed provider payload in normalizer");
assertIncludes(modelSettingsActions, "function optionalText(value: unknown): string | undefined", "model settings actions narrow optional provider text fields");
assertIncludes(modelSettingsActions, "name: optionalText(provider.name),\n    type: optionalText(provider.type),", "model settings actions normalize provider text fields before state writes");
assertNotIncludes(modelSettingsActions, "type: provider.type,", "model settings actions avoids raw provider type state writes");
assertIncludes(modelSettingsActions, "function normalizeModelMetadata(value: unknown): ModelMetadataByModel | undefined", "model settings actions normalize provider model metadata maps");
assertIncludes(modelSettingsActions, "const payload = toPayloadSource<ModelMetadataMapPayload>(value);\n  if (!payload) {\n    return undefined;\n  }\n  const entries = Object.entries(payload)", "model settings actions handles non-object metadata maps through a named payload source");
assertIncludes(modelSettingsActions, "function normalizeMediaModelMap(value: unknown): ModelMediaModelsByCategory | undefined {\n  const payload = toPayloadSource<MediaModelMapPayload>(value);", "model settings actions normalize finite media category payloads");
assertIncludes(modelSettingsActions, "for (const category of MEDIA_CATEGORIES)", "model settings actions iterate only canonical media categories");
assertIncludes(modelSettingsActions, "mediaModels[category] = normalizeTextList(models);", "model settings actions project provider media models into finite category state");
assertNotIncludes(modelSettingsActions, "Object.entries(payload).flatMap(([category, models])", "model settings actions avoid preserving arbitrary media model category keys");
assertIncludes(modelSettingsActions, "model_metadata: normalizeModelMetadata(provider.model_metadata),", "model settings actions normalize model metadata before state writes");
assertNotIncludes(modelSettingsActions, "model_metadata: provider.model_metadata,", "model settings actions avoid raw model metadata state writes");
assertIncludes(modelSettingsActions, "return contextLength !== undefined ? { context_length: contextLength } : null;", "model settings actions only store normalized model metadata fields");
assertNotIncludes(modelSettingsActions, "entry[key] = metadataValue;", "model settings actions avoids preserving arbitrary model metadata keys");
assertIncludes(modelSettingsActions, "function normalizeMediaModelMap(value: unknown): ModelMediaModelsByCategory | undefined", "model settings actions normalize provider media model maps");
assertIncludes(modelSettingsActions, "media_models: normalizeMediaModelMap(provider.media_models),", "model settings actions normalize media model maps before state writes");
assertNotIncludes(modelSettingsActions, "media_models: provider.media_models,", "model settings actions avoid raw media model map state writes");
assertNotIncludes(modelSettingsActions, "...provider,\n    id,", "model settings actions avoids spreading raw model provider payloads into state");
assertIncludes(modelSettingsActions, "const settings = toModelSettingsPayload(payload);", "model settings actions use typed model settings payload in normalizer");
assertIncludes(modelSettingsActions, "return {\n    default_provider: String(settings.default_provider || \"\"),\n    active_model: String(settings.active_model || \"\"),\n    providers: normalizeModelProviders(settings.providers),\n  };", "model settings actions project model settings state without raw spread");
assertNotIncludes(modelSettingsActions, "    ...settings,\n    default_provider: String(settings.default_provider || \"\"),", "model settings actions avoid spreading raw model settings payloads into state");
assertIncludes(modelSettingsActions, "const section = toMediaSectionPayload(value);", "model settings actions use typed media section payload in normalizer");
assertIncludes(modelSettingsActions, "function normalizeMediaCategory(value: unknown, fallback: MediaCategory): MediaCategory", "model settings actions validate API media categories");
assertIncludes(modelSettingsActions, "category: normalizeMediaCategory(section.category, category),", "model settings actions store only canonical media section categories");
assertNotIncludes(modelSettingsActions, "category: String(section.category || category)", "model settings actions avoid arbitrary media category state values");
assertIncludes(modelSettingsActions, "const settings = toMediaSettingsPayload(normalizeMediaSettings(toMediaSettingsPayload(payload)));", "model settings actions route the fixed media settings envelope through typed converters");
assertIncludes(modelSettingsActions, "const sectionsSource = toPayloadSource<MediaSectionsMapPayload>(settings.sections) || {};", "model settings actions narrow finite media sections before projection");
assertIncludes(modelSettingsActions, "vision: normalizeMediaSection(sectionsSource.vision, \"vision\"),\n      ocr: normalizeMediaSection(sectionsSource.ocr, \"ocr\"),\n      speech: normalizeMediaSection(sectionsSource.speech, \"speech\"),\n      video: normalizeMediaSection(sectionsSource.video, \"video\"),", "model settings actions project every canonical media section explicitly");
assertNotIncludes(modelSettingsActions, "const sections = Object.fromEntries", "model settings actions avoid widening media section keys through Object.fromEntries");
assertNotIncludes(modelSettingsActions, "    ...settings,\n    sections,", "model settings actions avoid spreading raw media settings payloads into state");
assertIncludes(modelSettingsActions, "function createEmptyMediaSelection(): MediaSelection", "model settings actions avoid dynamic empty media selections");
assertIncludes(modelSettingsActions, "requestSettingsJson(\"/api/settings/models\")", "model settings actions keep models endpoint");
assertIncludes(modelSettingsActions, "const payload = toModelSelectPayload(await requestSettingsJson(\"/api/settings/models/select\"", "model settings actions converts unknown model select responses through typed payload boundary");
assertNotIncludes(modelSettingsActions, "const payload = await requestSettingsJson(\"/api/settings/models/select\"", "model settings actions avoids direct raw model select payloads");
assertIncludes(modelSettingsActions, "reasoning_effort: normalizedReasoningEffort", "model settings actions keep reasoning effort payload");
assertIncludes(modelSettingsActions, "settingsState.reasoningSelections[providerId] = normalizeModelReasoningEffort(payload.reasoning_effort ?? normalizedReasoningEffort);", "model settings actions normalize response reasoning effort");
assertIncludes(modelSettingsActions, "requestSettingsJson(\"/api/settings/media\"", "model settings actions keep media settings endpoint");
assertIncludes(modelSettingsActions, "async function saveMediaModel(category: MediaCategory", "model settings actions restrict media saves to canonical categories");
assertIncludes(modelSettingsActions, "const payload = toMediaSavePayload(await requestSettingsJson(\"/api/settings/media\",", "model settings actions converts unknown media save responses through typed payload boundary");
assertNotIncludes(modelSettingsActions, "const payload = await requestSettingsJson(\"/api/settings/media\",", "model settings actions avoids direct raw media save payloads");
assertNotIncludes(modelSettingsActions, "requestSettingsJson<", "model settings actions avoid trusting unchecked API response generics");
assertIncludes(modelSettingsActions, "function errorMessage(error: unknown): string", "model settings actions narrow unknown errors");
assertNotIncludes(modelSettingsActions, "Promise<any>", "model settings actions avoid any request promises");
assertNotIncludes(modelSettingsActions, "catch (error: any)", "model settings actions avoid any catch boundaries");
assertNotIncludes(modelSettingsActions, "Record<string, any>", "model settings actions avoid broad dynamic state records");
assertIncludes(useSettingsState, "export interface UpdateStatusView {\n  supported: boolean;\n  dirty: boolean;\n  update_available: boolean;\n  commits_behind: number;\n  current_rev_short: string;\n  branch?: string;\n  project_root?: string;\n}", "settings state keeps update status state fixed");
assertNotIncludes(useSettingsState, "export interface UpdateStatusView {\n  supported: boolean;\n  dirty: boolean;\n  update_available: boolean;\n  commits_behind: number;\n  current_rev_short: string;\n  branch?: string;\n  project_root?: string;\n  [key: string]: unknown;\n}", "settings state avoids open-ended update status state");
assertIncludes(useSettingsState, "export interface ModelSettings", "settings state types model settings");
assertIncludes(useSettingsState, "export interface ModelSettings {\n  default_provider: string;", "settings state narrows model default provider id");
assertIncludes(useSettingsState, "export interface ModelSettings {\n  default_provider: string;\n  active_model: string;\n  providers: ModelProviderView[];\n}", "settings state keeps model settings state fixed");
assertNotIncludes(useSettingsState, "export interface ModelSettings {\n  default_provider: unknown;", "settings state avoids unknown model default provider ids");
assertNotIncludes(useSettingsState, "export interface ModelSettings {\n  default_provider: string;\n  active_model: string;\n  providers: ModelProviderView[];\n  [key: string]: unknown;\n}", "settings state avoids open-ended model settings state");
assertIncludes(useSettingsState, "import type { ModelReasoningEffort } from \"./modelReasoning\";", "settings state imports typed reasoning effort");
assertIncludes(useSettingsState, "export interface ModelProviderView {\n  id: string;\n  name?: string;\n  type?: string;\n  is_default?: boolean;\n  selected_model?: string;\n  models?: string[];\n  model_metadata?: ModelMetadataByModel;\n  media_models?: ModelMediaModelsByCategory;\n  reasoning_effort?: ModelReasoningEffort;\n}", "settings state keeps model provider state fixed");
assertNotIncludes(useSettingsState, "export interface ModelProviderView {\n  id: string;\n  name?: string;\n  type?: string;\n  is_default?: boolean;\n  selected_model?: string;\n  models?: string[];\n  model_metadata?: ModelMetadataByModel;\n  media_models?: ModelMediaModelsByCategory;\n  reasoning_effort?: ModelReasoningEffort;\n  [key: string]: unknown;\n}", "settings state avoids open-ended model provider state");
assertIncludes(useSettingsState, "reasoning_effort?: ModelReasoningEffort;", "settings state narrows provider reasoning effort");
assertIncludes(useSettingsState, "type?: string;", "settings state narrows model provider type");
assertNotIncludes(useSettingsState, "type?: unknown;", "settings state avoids unknown model provider type");
assertIncludes(useSettingsState, "export type ModelMetadataEntryView = {", "settings state types provider model metadata entries");
assertIncludes(useSettingsState, "export type ModelMetadataEntryView = {\n  context_length?: number;\n};", "settings state keeps model metadata entries fixed");
assertNotIncludes(useSettingsState, "export type ModelMetadataEntryView = {\n  context_length?: number;\n  [key: string]: unknown;\n};", "settings state avoids open-ended model metadata entries");
assertIncludes(useSettingsState, "export type ModelMetadataByModel = Record<string, ModelMetadataEntryView>;", "settings state types provider model metadata maps");
assertIncludes(useSettingsState, "model_metadata?: ModelMetadataByModel;", "settings state narrows provider model metadata");
assertNotIncludes(useSettingsState, "model_metadata?: unknown;", "settings state avoids unknown provider model metadata");
assertIncludes(useSettingsState, "export const MEDIA_CATEGORIES = [\"vision\", \"ocr\", \"speech\", \"video\"] as const;", "settings state owns canonical media categories");
assertIncludes(useSettingsState, "export type MediaCategory = (typeof MEDIA_CATEGORIES)[number];", "settings state derives the media category union");
assertIncludes(useSettingsState, "export type MediaCategoryMap<Value> = {\n  [Category in MediaCategory]: Value;\n};", "settings state exposes finite media category maps");
assertIncludes(useSettingsState, "export type PartialMediaCategoryMap<Value> = {\n  [Category in MediaCategory]?: Value;\n};", "settings state supports sparse provider media category maps");
assertIncludes(useSettingsState, "export type ModelMediaModelsByCategory = PartialMediaCategoryMap<string[]>;", "settings state types provider media models with finite category keys");
assertIncludes(useSettingsState, "media_models?: ModelMediaModelsByCategory;", "settings state narrows provider media models");
assertNotIncludes(useSettingsState, "media_models?: unknown;", "settings state avoids unknown provider media models");
assertIncludes(useSettingsState, "reasoningSelections: Record<string, ModelReasoningEffort>;", "settings state narrows reasoning selection map");
assertIncludes(useSettingsState, "export interface MediaSectionView {\n  category: MediaCategory;\n  enabled: boolean;\n  provider_id: string;\n  model: string;\n}", "settings state keeps media section categories finite");
assertIncludes(useSettingsState, "export interface MediaSettings", "settings state types media settings");
assertIncludes(useSettingsState, "export interface MediaSettings {\n  sections: MediaCategoryMap<MediaSectionView>;\n  providers: ModelProviderView[];\n}", "settings state keeps media settings category keys finite");
assertIncludes(useSettingsState, "export type MediaSelections = MediaCategoryMap<MediaSelection>;", "settings state types finite media selections");
assertIncludes(useSettingsState, "export type MediaCustomModels = MediaCategoryMap<string>;", "settings state types finite custom media models");
assertIncludes(useSettingsState, "mediaSelections: MediaSelections;\n  mediaCustomModels: MediaCustomModels;", "settings state uses finite media category maps");
assertNotIncludes(useSettingsState, "sections: Record<string, MediaSectionView>", "settings state avoids open media section category maps");
assertIncludes(modelReasoning, "export const MODEL_REASONING_EFFORTS = [\"\", \"none\", \"minimal\", \"low\", \"medium\", \"high\", \"xhigh\"] as const;", "model reasoning owns ordered reasoning effort values");
assertIncludes(modelReasoning, "export type ModelReasoningEffort = (typeof MODEL_REASONING_EFFORTS)[number];", "model reasoning exports typed reasoning union");
assertIncludes(modelReasoning, "function isModelReasoningEffort(value: string): value is ModelReasoningEffort", "model reasoning narrows finite effort values with a type guard");
assertIncludes(modelReasoning, "return isModelReasoningEffort(normalized) ? normalized : \"\";", "model reasoning keeps its empty fallback without assertion");
assertNotIncludes(modelReasoning, "normalized as ModelReasoningEffort", "model reasoning avoids asserting normalized effort values");
assertIncludes(modelReasoning, "export function normalizeModelReasoningEffort(value: unknown): ModelReasoningEffort", "model reasoning normalizes unknown values");
assertIncludes(mcpSettingsActions, "export function useMcpSettingsActions", "MCP settings actions remain exported");
assertIncludes(mcpSettingsActions, "import { normalizeMcpSettings, normalizeMcpTransport, type McpTransportType } from \"./settingsNormalizers\";", "MCP settings actions import typed transport boundary");
assertIncludes(mcpSettingsActions, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", "MCP settings actions keep unchecked API responses unknown");
assertIncludes(mcpSettingsActions, "interface McpSettingsState", "MCP settings actions type MCP state boundary");
assertIncludes(mcpSettingsActions, "interface McpSettingsCopy", "MCP settings actions type MCP copy boundary");
assertNotIncludes(mcpSettingsActions, "type JsonRecord = Record<string, unknown>;", "MCP settings actions avoid a shared generic JSON record alias");
assertNotIncludes(mcpSettingsActions, "type JsonObject = Record<string, unknown>;", "MCP settings actions avoid a duplicate generic JSON object alias");
assertIncludes(mcpSettingsActions, "type McpServerPayload = {", "MCP settings actions name fixed server payload boundary");
assertNotIncludes(mcpSettingsActions, "type McpServerPayload = JsonRecord & {", "MCP settings actions avoid open-ended server payload records");
assertIncludes(mcpSettingsActions, "type McpSettingsPayload = {", "MCP settings actions name fixed settings API payload boundary");
assertNotIncludes(mcpSettingsActions, "type McpSettingsPayload = JsonRecord & {", "MCP settings actions avoid open-ended settings API payload records");
assertIncludes(mcpSettingsActions, "servers?: unknown;", "MCP settings actions name server list payload field");
assertIncludes(mcpSettingsActions, "runtime?: unknown;", "MCP settings actions name runtime payload field");
assertIncludes(mcpSettingsActions, "reload_message?: unknown;", "MCP settings actions name reload message payload field");
assertIncludes(mcpSettingsActions, "type McpImportedServerPayload = {", "MCP settings actions name fixed imported server payload boundary");
assertNotIncludes(mcpSettingsActions, "type McpImportedServerPayload = JsonRecord & {", "MCP settings actions avoid open-ended imported server payload records");
assertIncludes(mcpSettingsActions, "serverId?: unknown;", "MCP settings actions name camel server id import field");
assertIncludes(mcpSettingsActions, "transport_type?: unknown;", "MCP settings actions name imported transport type field");
assertIncludes(mcpSettingsActions, "toolTimeout?: unknown;", "MCP settings actions name camel tool timeout import field");
assertIncludes(mcpSettingsActions, "enabledTools?: unknown;", "MCP settings actions name camel enabled tools import field");
assertIncludes(mcpSettingsActions, "type McpImportedServerMapPayload = {\n  [serverId: string]: unknown;\n};", "MCP settings actions name dynamic imported server map boundary");
assertIncludes(mcpSettingsActions, "type McpImportedJsonPayload = {\n  [key: string]: unknown;\n};", "MCP settings actions name pasted top-level JSON boundary");
assertIncludes(mcpSettingsActions, "type McpKeyValuePayload = {\n  [key: string]: unknown;\n};", "MCP settings actions name env and header map boundary");
assertIncludes(mcpSettingsActions, "type: McpTransportType;", "MCP settings actions narrow server transport payload");
assertIncludes(mcpSettingsActions, "env?: McpKeyValuePayload;\n  headers?: McpKeyValuePayload;", "MCP settings actions type server env and headers with the named key-value boundary");
assertNotIncludes(mcpSettingsActions, "function toJsonRecord(value: unknown): JsonRecord", "MCP settings actions avoid a shared generic JSON record converter");
for (const payloadType of ["McpSettingsPayload", "McpImportedServerPayload", "McpRuntimeView", "McpServerView"]) {
  assertIncludes(mcpSettingsActions, `toPayloadSource<${payloadType}>(value)`, `MCP settings actions limit ${payloadType} source reads to known fields`);
}
assertIncludes(mcpSettingsActions, "function toMcpImportedServerMapPayload(value: unknown): McpImportedServerMapPayload | null {\n  return toPayloadSource<McpImportedServerMapPayload>(value);\n}", "MCP settings actions preserve dynamic imported server IDs behind a named payload source");
assertIncludes(mcpSettingsActions, "const parsedObject = toPayloadSource<McpKeyValuePayload>(parsed);", "MCP settings actions preserve arbitrary env and header keys during parsing");
assertIncludes(mcpSettingsActions, "const parsedObject = toPayloadSource<McpImportedJsonPayload>(parsed);", "MCP settings actions preserve arbitrary pasted top-level JSON keys during import");
assertIncludes(mcpSettingsActions, "function toMcpSettingsPayload(value: unknown): McpSettingsPayload | null", "MCP settings actions narrow settings response before normalization");
assertIncludes(mcpSettingsActions, "servers: payload.servers,\n        runtime: payload.runtime,\n        reload_message: payload.reload_message,", "MCP settings actions projects settings payloads onto named fields");
assertIncludes(mcpSettingsActions, "function toMcpImportedServerPayload(value: unknown): McpImportedServerPayload | null", "MCP settings actions narrow imported server payloads");
assertIncludes(mcpSettingsActions, "serverName: payload.serverName,", "MCP settings actions projects imported server payloads onto named fields");
assertNotIncludes(mcpSettingsActions, "return toJsonRecord(value) as McpImportedServerPayload | null;", "MCP settings actions avoid direct imported server payload casts");
assertIncludes(mcpSettingsActions, "function toMcpImportedServerMapPayload(value: unknown): McpImportedServerMapPayload | null", "MCP settings actions narrow imported server maps");
assertIncludes(mcpSettingsActions, "function normalizeMcpRuntime(value: unknown, fallbackRuntime: McpRuntimeView): McpRuntimeView", "MCP settings actions normalize MCP runtime views");
assertIncludes(mcpSettingsActions, "function normalizeMcpServerView(value: unknown): McpServerView | null", "MCP settings actions normalize MCP server views");
assertIncludes(mcpSettingsActions, "function normalizeMcpSettingsView(payload: McpSettingsPayload, fallbackRuntime: McpRuntimeView): McpSettings", "MCP settings actions normalize finite MCP payloads to typed state views");
assertIncludes(mcpSettingsActions, "const normalized = normalizeMcpSettings(payload, fallbackRuntime);", "MCP settings actions reuse the normalizer return type directly");
assertNotIncludes(mcpSettingsActions, "normalizeMcpSettings(payload, fallbackRuntime) as McpSettingsPayload", "MCP settings actions avoid a redundant normalized payload cast");
assertIncludes(mcpSettingsActions, "servers: normalizeMcpServerList(normalized.servers)", "MCP settings actions stores typed MCP server views");
assertIncludes(mcpSettingsActions, "runtime: normalizeMcpRuntime(normalized.runtime, fallbackRuntime)", "MCP settings actions stores typed MCP runtime views");
assertIncludes(mcpSettingsActions, "function errorMessage(error: unknown): string", "MCP settings actions narrow unknown errors");
assertIncludes(mcpSettingsActions, "parseOptionalJsonObject(value: unknown, fieldLabel: string)", "MCP settings actions keep typed optional JSON parsing");
assertIncludes(mcpSettingsActions, "extractMcpServerFromJson(parsed: unknown)", "MCP settings actions keep JSON import extraction");
assertIncludes(mcpSettingsActions, "function getMcpServerMap(parsed: McpImportedJsonPayload): McpImportedServerMapPayload | null", "MCP settings actions type imported server maps");
assertIncludes(mcpSettingsActions, "function serverIdFromJson(server: McpImportedServerPayload): string", "MCP settings actions type imported server id reads");
assertIncludes(mcpSettingsActions, "const entries = Object.entries(serverMap).filter(([, value]) => toMcpImportedServerPayload(value) !== null);", "MCP settings actions filter imported server map entries through typed payloads");
assertIncludes(mcpSettingsActions, "const server = servers.length === 1 ? toMcpImportedServerPayload(servers[0]) : null;", "MCP settings actions narrow imported server arrays");
assertIncludes(mcpSettingsActions, "normalizeMcpTransport(rawType, server.url ? \"streamableHttp\" : \"stdio\")", "MCP settings actions keep transport fallback");
assertIncludes(mcpSettingsActions, "settingsState.mcpForm.type = normalizeMcpTransport(server.type);", "MCP settings actions normalize edited server transport");
assertIncludes(mcpSettingsActions, "const transportType = payload.type;", "MCP settings actions use typed transport payload");
assertIncludes(mcpSettingsActions, "toMcpSettingsPayload(await requestSettingsJson(\"/api/settings/mcp\")) || {}", "MCP settings actions convert unknown load responses through the finite payload boundary");
assertIncludes(mcpSettingsActions, "toMcpSettingsPayload(await requestSettingsJson(editingId ? `/api/settings/mcp/${encodeURIComponent(editingId)}` : \"/api/settings/mcp\"", "MCP settings actions convert unknown create/update responses through the finite payload boundary");
assertIncludes(mcpSettingsActions, "toMcpSettingsPayload(await requestSettingsJson(`/api/settings/mcp/${encodeURIComponent(serverId)}`", "MCP settings actions convert unknown delete responses through the finite payload boundary");
assertIncludes(mcpSettingsActions, "toMcpSettingsPayload(await requestSettingsJson(\"/api/settings/mcp/reload\", { method: \"POST\" })) || {}", "MCP settings actions convert unknown reload responses through the finite payload boundary");
assertNotIncludes(mcpSettingsActions, "requestSettingsJson<", "MCP settings actions avoid trusting unchecked API response generics");
assertIncludes(mcpSettingsActions, "payload.env = env;", "MCP settings actions keep env payload");
assertIncludes(mcpSettingsActions, "payload.headers = headers;", "MCP settings actions keep headers payload");
assertNotIncludes(mcpSettingsActions, "Promise<any>", "MCP settings actions avoid any request promises");
assertNotIncludes(mcpSettingsActions, "catch (error: any)", "MCP settings actions avoid any catch boundaries");
assertNotIncludes(mcpSettingsActions, "Record<string, any>", "MCP settings actions avoid broad dynamic state records");
assertNotIncludes(mcpSettingsActions, "function normalizeMcpSettingsView(payload: unknown, fallbackRuntime: JsonRecord): McpSettings", "MCP settings actions keeps MCP runtime fallback off generic JSON state");
assertNotIncludes(mcpHelpers, "type JsonRecord = Record<string, unknown>;", "MCP helpers avoid a shared generic record alias");
assertNotIncludes(mcpHelpers, "function toRecord", "MCP helpers avoid a shared generic record converter");
assertIncludes(mcpHelpers, "type McpCopyRootPayload = {", "MCP helpers name root copy boundary");
assertIncludes(mcpHelpers, "type McpSettingsCopyPayload = {", "MCP helpers name settings copy boundary");
assertNotIncludes(mcpHelpers, "type McpCopyView = JsonRecord & {", "MCP helpers keep MCP copy view finite");
assertIncludes(mcpHelpers, "import { toPayloadSource } from \"../composables/payloadBoundary\";", "MCP helpers reuse the shared finite payload guard");
assertNotIncludes(mcpHelpers, "type PayloadSource<Payload extends object>", "MCP helpers avoid a duplicate payload source type");
assertNotIncludes(mcpHelpers, "function toPayloadSource<Payload extends object>", "MCP helpers avoid a duplicate payload source guard");
assertIncludes(mcpHelpers, "import type { McpRuntimeView, McpServerView, McpSettings } from \"../composables/useSettingsState\";", "MCP helpers reuse typed MCP state views");
assertIncludes(mcpHelpers, "export type McpToolGroup", "MCP helpers expose typed tool group output");
assertIncludes(mcpHelpers, "function mcpRuntimeFor(state: McpStateView): McpRuntimeView", "MCP helpers centralize runtime reads");
assertIncludes(mcpHelpers, "function mcpServers(value: unknown): McpServerView[]", "MCP helpers normalize server lists at boundary");
assertIncludes(mcpHelpers, "function mcpCopyFor(copy: unknown): McpCopyView", "MCP helpers narrow unknown copy input internally");
assertIncludes(mcpHelpers, "return toPayloadSource<McpCopyView>(settings?.mcp) || {};", "MCP helpers project MCP copy through the finite view");
assertIncludes(mcpHelpers, "export function mcpRuntimeStatus(copy: unknown, state: McpStateView): string", "MCP helpers type runtime status copy boundary");
assertIncludes(mcpHelpers, "export function mcpToolGroups(copy: unknown, state: McpStateView): McpToolGroup[]", "MCP helpers return typed tool groups");
assertNotIncludes(mcpHelpers, "type AnyRecord", "MCP helpers avoid dynamic AnyRecord alias");
assertNotIncludes(mcpHelpers, "Record<string, any>", "MCP helpers avoid broad dynamic records");
assertNotIncludes(mcpHelpers, "type McpRuntimeView = JsonRecord & {", "MCP helpers no longer owns generic runtime view records");
assertNotIncludes(mcpHelpers, "type McpServerView = JsonRecord & {", "MCP helpers no longer owns generic server view records");
assertIncludes(useSettingsState, "export interface McpSettings", "settings state types MCP settings");
assertIncludes(useSettingsState, "export interface McpRuntimeView", "settings state exposes typed MCP runtime view");
assertIncludes(useSettingsState, "export interface McpServerView", "settings state exposes typed MCP server view");
assertIncludes(useSettingsState, "servers: McpServerView[];", "settings state types MCP server list");
assertIncludes(useSettingsState, "runtime: McpRuntimeView;", "settings state types MCP runtime");
assertNotIncludes(useSettingsState, "servers: JsonRecord[];", "settings state keeps MCP servers off generic JSON records");
assertNotIncludes(useSettingsState, "runtime: JsonRecord;", "settings state keeps MCP runtime off generic JSON records");
assertIncludes(useSettingsState, "export interface McpForm", "settings state types MCP form");
assertIncludes(useSettingsState, "import type { McpTransportType } from \"./settingsNormalizers\";", "settings state imports typed MCP transport");
assertIncludes(useSettingsState, "type: McpTransportType;", "settings state narrows MCP form transport");
assertIncludes(useSettingsState, "mcpToolGroupsExpanded: Record<string, boolean>", "settings state types MCP tool group expansion");
assertIncludes(scheduleDefaults, "export interface ScheduleState", "schedule defaults expose typed schedule state");
assertIncludes(scheduleDefaults, "export interface ScheduleForm", "schedule defaults expose typed schedule form");
assertIncludes(scheduleDefaults, "export const CRON_JOB_MODES = [\"cron\", \"every\", \"at\"] as const;", "schedule defaults own cron job mode values");
assertIncludes(scheduleDefaults, "export const CRON_JOB_ACTIONS = [\"pause\", \"enable\", \"run\", \"remove\"] as const;", "schedule defaults own cron job action values");
assertIncludes(scheduleDefaults, "export type CronJobMode = (typeof CRON_JOB_MODES)[number];", "schedule defaults export typed cron job mode union");
assertIncludes(scheduleDefaults, "export type CronJobAction = (typeof CRON_JOB_ACTIONS)[number];", "schedule defaults export typed cron job action union");
assertIncludes(scheduleDefaults, "function isCronJobMode(value: string): value is CronJobMode", "schedule defaults narrow finite cron modes with a type guard");
assertIncludes(scheduleDefaults, "return isCronJobMode(normalized) ? normalized : \"cron\";", "schedule defaults keep the cron fallback without assertion");
assertNotIncludes(scheduleDefaults, "normalized as CronJobMode", "schedule defaults avoid asserting normalized cron modes");
assertIncludes(scheduleDefaults, "export function normalizeCronJobMode(value: unknown): CronJobMode", "schedule defaults normalize unknown cron job modes");
assertIncludes(scheduleSettingsActions, "export function useScheduleSettingsActions", "schedule settings actions remain exported");
assertIncludes(scheduleSettingsActions, "\"/api/settings/schedule\"", "schedule settings actions keep schedule settings endpoint");
assertIncludes(scheduleSettingsActions, "interface ScheduleSettingsState", "schedule settings actions type schedule state boundary");
assertIncludes(scheduleSettingsActions, "interface CronJobTimezoneForm", "schedule settings actions type cron timezone form boundary");
assertIncludes(scheduleSettingsActions, "type ScheduleSettingsPayload = {", "schedule settings actions name fixed schedule payload boundary");
assertIncludes(scheduleSettingsActions, "default_timezone?: unknown;\n  common_timezones?: unknown;\n  restart_required?: unknown;", "schedule settings actions project known schedule response fields");
assertNotIncludes(scheduleSettingsActions, "const payload = value && typeof value === \"object\" ? value as ScheduleSettingsPayload : {};", "schedule settings actions avoids direct object casts for schedule payloads");
assertIncludes(scheduleSettingsActions, "function toScheduleSettingsPayload(value: unknown): ScheduleSettingsPayload", "schedule settings actions narrows schedule responses");
assertIncludes(scheduleSettingsActions, "function toScheduleSettingsPayload(value: unknown): ScheduleSettingsPayload {\n  const payload = toPayloadSource<ScheduleSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "schedule settings actions handles non-object schedule responses before field projection");
assertIncludes(scheduleSettingsActions, "const payload = toScheduleSettingsPayload(await requestSettingsJson(\"/api/settings/schedule\"));", "schedule settings actions convert unknown schedule load responses through the payload boundary");
assertIncludes(scheduleSettingsActions, "const payload = toScheduleSettingsPayload(await requestSettingsJson(\"/api/settings/schedule\",", "schedule settings actions convert unknown schedule save responses through the payload boundary");
assertNotIncludes(scheduleSettingsActions, "requestSettingsJson<ScheduleSettingsPayload>", "schedule settings actions avoid trusting unchecked API response generics");
assertNotIncludes(scheduleSettingsActions, "const payload = await requestSettingsJson<ScheduleSettingsPayload>(\"/api/settings/schedule\")", "schedule settings actions avoids direct raw schedule load payloads");
assertIncludes(scheduleSettingsActions, "function normalizeScheduleSettings(payload: ScheduleSettingsPayload): ScheduleState", "schedule settings actions normalize schedule payloads");
assertIncludes(scheduleSettingsActions, "function errorMessage(error: unknown): string", "schedule settings actions narrow unknown errors");
assertNotIncludes(scheduleSettingsActions, "Promise<any>", "schedule settings actions avoid any request promises");
assertNotIncludes(scheduleSettingsActions, "catch (error: any)", "schedule settings actions avoid any catch boundaries");
assertIncludes(scheduleSettingsActions, "copy.value.notices.scheduleSaved(settingsState.scheduleForm.defaultTimezone)", "schedule settings actions keep saved notice");
assertIncludes(searchDefaults, "export interface SearchState", "search defaults expose typed search state");
assertIncludes(searchDefaults, "export interface SearxngOptionEntry", "search defaults expose typed SearXNG option entries");
assertIncludes(searchDefaults, "export interface SearxngOptions", "search defaults expose typed SearXNG options");
assertIncludes(searchDefaults, "DEFAULT_SEARCH_PROVIDERS = [\"duckduckgo\", \"searxng\", \"jina\"]", "search defaults keep provider order");
assertIncludes(searchSettingsActions, "export function useSearchSettingsActions", "search settings actions remain exported");
assertIncludes(searchSettingsActions, "\"/api/settings/search\"", "search settings actions keep search settings endpoint");
assertIncludes(searchSettingsActions, "type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;", "search settings actions keep unchecked API responses unknown");
assertIncludes(searchSettingsActions, "interface SearchSettingsState", "search settings actions type search state boundary");
assertIncludes(searchSettingsActions, "type SearchSettingsPayload = {", "search settings actions type search API payload boundary");
assertNotIncludes(searchSettingsActions, "type SearchSettingsPayload = JsonRecord & {", "search settings actions avoids open-ended search API payload records");
assertIncludes(searchSettingsActions, "type SearchDataPayload = {", "search settings actions type normalized search data payload");
assertNotIncludes(searchSettingsActions, "type SearchDataPayload = JsonRecord & {", "search settings actions avoids open-ended search data payload records");
assertIncludes(searchSettingsActions, "searxng_options?: unknown;", "search settings actions names nested SearXNG options payload");
assertIncludes(searchSettingsActions, "type SearxngOptionsPayload = {", "search settings actions type SearXNG options API payload boundary");
assertNotIncludes(searchSettingsActions, "type SearxngOptionsPayload = JsonRecord & {", "search settings actions avoids open-ended SearXNG options API payload records");
assertIncludes(searchSettingsActions, "type SearxngOptionsDataPayload = {", "search settings actions type SearXNG options data payload");
assertNotIncludes(searchSettingsActions, "type SearxngOptionsDataPayload = JsonRecord & {", "search settings actions avoids open-ended SearXNG options data payload records");
assertIncludes(searchSettingsActions, "type SearxngOptionPayload = {", "search settings actions type individual SearXNG option payload");
assertNotIncludes(searchSettingsActions, "type SearxngOptionPayload = JsonRecord & {", "search settings actions avoids open-ended SearXNG option payload records");
assertIncludes(searchSettingsActions, "function toSearchSettingsPayload(value: unknown): SearchSettingsPayload", "search settings actions narrows search settings responses");
assertIncludes(searchSettingsActions, "function toSearchSettingsPayload(value: unknown): SearchSettingsPayload {\n  const payload = toPayloadSource<SearchSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "search settings actions handles non-object search responses before field projection");
assertNotIncludes(searchSettingsActions, "search: payload?.search,", "search settings actions avoid optional chaining after nullable payload boundary");
assertIncludes(searchSettingsActions, "search: payload.search,", "search settings actions projects search settings payloads onto named fields");
assertIncludes(searchSettingsActions, "function toSearchDataPayload(value: unknown): SearchDataPayload | null", "search settings actions narrow search data before field reads");
assertIncludes(searchSettingsActions, "provider: payload.provider,\n    providers: payload.providers,\n    freshness: payload.freshness,\n    freshness_options: payload.freshness_options,\n    max_results: payload.max_results,\n    duckduckgo_max_pages: payload.duckduckgo_max_pages,\n    searxng_max_pages: payload.searxng_max_pages,\n    searxng_url: payload.searxng_url,\n    searxng_engines: payload.searxng_engines,\n    searxng_categories: payload.searxng_categories,\n    searxng_options: payload.searxng_options,\n    proxy: payload.proxy,\n    jina_api_key_configured: payload.jina_api_key_configured,", "search settings actions projects search data payloads onto named fields");
assertIncludes(searchSettingsActions, "function toSearxngOptionsPayload(value: unknown): SearxngOptionsPayload", "search settings actions narrows SearXNG option responses");
assertIncludes(searchSettingsActions, "function toSearxngOptionsPayload(value: unknown): SearxngOptionsPayload {\n  const payload = toPayloadSource<SearxngOptionsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "search settings actions handles non-object SearXNG option responses before field projection");
assertNotIncludes(searchSettingsActions, "searxng: payload?.searxng,", "search settings actions avoid optional chaining after nullable SearXNG payload boundary");
assertIncludes(searchSettingsActions, "searxng: payload.searxng,", "search settings actions projects SearXNG options payloads onto named fields");
assertIncludes(searchSettingsActions, "function toSearxngOptionsDataPayload(value: unknown): SearxngOptionsDataPayload | null", "search settings actions narrow SearXNG options data before field reads");
assertIncludes(searchSettingsActions, "engines: payload.engines,\n    categories: payload.categories,\n    url: payload.url,\n    fallback: payload.fallback,\n    warning: payload.warning,", "search settings actions projects SearXNG options data payloads onto named fields");
assertIncludes(searchSettingsActions, "function toSearxngOptionPayload(value: unknown): SearxngOptionPayload | null", "search settings actions narrow individual SearXNG options before field reads");
assertIncludes(searchSettingsActions, "id: payload.id,\n    name: payload.name,\n    label: payload.label,\n    display_name: payload.display_name,\n    displayName: payload.displayName,\n    categories: payload.categories,\n    shortcut: payload.shortcut,\n    enabled: payload.enabled,", "search settings actions projects individual SearXNG options onto named fields");
assertIncludes(searchSettingsActions, "function normalizeSearxngOptions(value: unknown = {}): SearxngOptions", "search settings actions normalize typed SearXNG options");
assertIncludes(searchSettingsActions, "function normalizeSearchSettings(search: unknown = {}): SearchState", "search settings actions normalize typed search settings");
assertIncludes(searchSettingsActions, "const payload = toSearxngOptionsDataPayload(value) || {};", "search settings actions use typed SearXNG options payload in normalizer");
assertIncludes(searchSettingsActions, "const payload = toSearchDataPayload(search) || {};", "search settings actions use typed search payload in normalizer");
assertIncludes(searchSettingsActions, "toSearchSettingsPayload(await requestSettingsJson(\"/api/settings/search\"))", "search settings actions converts unknown search load responses through typed payload boundary");
assertIncludes(searchSettingsActions, "toSearxngOptionsPayload(await requestSettingsJson(`/api/settings/search/searxng-options${suffix}`))", "search settings actions converts unknown SearXNG options responses through typed payload boundary");
assertIncludes(searchSettingsActions, "toSearchSettingsPayload(await requestSettingsJson(\"/api/settings/search\",", "search settings actions converts unknown search save responses through typed payload boundary");
assertNotIncludes(searchSettingsActions, "requestSettingsJson<", "search settings actions avoid trusting unchecked API response generics");
assertIncludes(searchSettingsActions, "function errorMessage(error: unknown): string", "search settings actions narrow unknown errors");
assertNotIncludes(searchSettingsActions, "Promise<any>", "search settings actions avoid any request promises");
assertNotIncludes(searchSettingsActions, "catch (error: any)", "search settings actions avoid any catch boundaries");
assertIncludes(searchSettingsActions, "searxng-options${suffix}", "search settings actions keep SearXNG options endpoint suffix");
assertIncludes(searchSettingsActions, "...secretPayload(form)", "search settings actions keep optional secret payload merge");
assertIncludes(updateSettingsActions, "export function useUpdateSettingsActions", "update settings actions remain exported");
assertIncludes(updateSettingsActions, "\"/api/settings/update\"", "update settings actions keep update endpoint");
assertIncludes(updateSettingsActions, "import type { UpdateStatusView } from \"./useSettingsState\";", "update settings actions reuse normalized update status view");
assertIncludes(updateSettingsActions, "interface UpdateSettingsState", "update settings actions type update state boundary");
assertIncludes(updateSettingsActions, "type UpdateStatusPayload = {", "update settings actions type update status payload boundary");
assertIncludes(updateSettingsActions, "update_available?: unknown;", "update settings actions names update availability field");
assertIncludes(updateSettingsActions, "current_rev_short?: unknown;", "update settings actions names current revision field");
assertIncludes(updateSettingsActions, "branch?: unknown;\n  project_root?: unknown;", "update settings actions names optional update context fields");
assertIncludes(updateSettingsActions, "updateStatus: UpdateStatusView;", "update settings actions stores normalized update status state");
assertNotIncludes(updateSettingsActions, "type UpdateStatusPayload = JsonRecord;", "update settings actions avoids a pure update status payload record");
assertNotIncludes(updateSettingsActions, "type UpdateStatusPayload = JsonRecord & {", "update settings actions avoids open-ended update status payload records");
assertNotIncludes(updateSettingsActions, "updateStatus: JsonRecord;", "update settings actions avoids generic update status state");
assertIncludes(updateSettingsActions, "type RunUpdatePayload = {", "update settings actions type run update response");
assertNotIncludes(updateSettingsActions, "type RunUpdatePayload = JsonRecord & {", "update settings actions avoids open-ended run update payload records");
assertIncludes(updateSettingsActions, "type RunUpdateResultView = {", "update settings actions type normalized run update result");
assertIncludes(updateSettingsActions, "restart_scheduled: boolean;", "update settings actions narrows run update restart flag");
assertIncludes(updateSettingsActions, "function toUpdateStatusPayload(value: unknown): UpdateStatusPayload", "update settings actions narrows raw update status payloads");
assertIncludes(updateSettingsActions, "function toUpdateStatusPayload(value: unknown): UpdateStatusPayload {\n  const payload = toPayloadSource<UpdateStatusPayload>(value);\n  if (!payload) {\n    return {};\n  }", "update settings actions handles non-object update status responses before field projection");
assertIncludes(updateSettingsActions, "supported: payload.supported,\n    dirty: payload.dirty,\n    update_available: payload.update_available,\n    commits_behind: payload.commits_behind,\n    current_rev_short: payload.current_rev_short,\n    branch: payload.branch,\n    project_root: payload.project_root,", "update settings actions projects update status payloads onto named fields");
assertNotIncludes(updateSettingsActions, "function toUpdateStatusPayload(value: unknown): UpdateStatusPayload {\n  return toJsonRecord(value);\n}", "update settings actions avoids passing raw update status records through converter");
assertIncludes(updateSettingsActions, "function normalizeUpdateStatus(value: unknown): UpdateStatusView", "update settings actions normalizes update status state");
assertIncludes(updateSettingsActions, "function toRunUpdatePayload(value: unknown): RunUpdatePayload", "update settings actions narrows raw run update payloads");
assertIncludes(updateSettingsActions, "function toRunUpdatePayload(value: unknown): RunUpdatePayload {\n  const payload = toPayloadSource<RunUpdatePayload>(value);\n  if (!payload) {\n    return {};\n  }", "update settings actions handles non-object run update responses before field projection");
assertIncludes(updateSettingsActions, "after_rev_short: payload.after_rev_short,\n    restart_scheduled: payload.restart_scheduled,", "update settings actions projects run update payloads onto named fields");
assertNotIncludes(updateSettingsActions, "function toRunUpdatePayload(value: unknown): RunUpdatePayload {\n  return toJsonRecord(value);\n}", "update settings actions avoids passing raw run update records through converter");
assertIncludes(updateSettingsActions, "function normalizeRunUpdateResult(value: unknown): RunUpdateResultView", "update settings actions normalizes run update response");
assertIncludes(updateSettingsActions, "branch: textValue(payload.branch),\n    project_root: textValue(payload.project_root),", "update settings actions normalizes optional update context fields");
assertNotIncludes(updateSettingsActions, "...payload,\n    supported: Boolean(payload.supported),", "update settings actions avoids spreading raw update status payloads into state");
assertIncludes(updateSettingsActions, "settingsState.updateStatus = normalizeUpdateStatus(await requestSettingsJson(\"/api/settings/update\"));", "update settings actions normalize unknown update status responses");
assertNotIncludes(updateSettingsActions, "requestSettingsJson<UpdateStatusPayload>", "update settings actions avoid trusting unchecked status response generics");
assertNotIncludes(updateSettingsActions, "settingsState.updateStatus = await requestSettingsJson<UpdateStatusPayload>(\"/api/settings/update\");", "update settings actions avoids raw update status assignment");
assertIncludes(updateSettingsActions, "normalizeRunUpdateResult(await requestSettingsJson(\"/api/settings/update\"", "update settings actions normalize unknown run update responses");
assertNotIncludes(updateSettingsActions, "requestSettingsJson<RunUpdatePayload>", "update settings actions avoid trusting unchecked run update response generics");
assertIncludes(updateSettingsActions, "const restartScheduled = payload.restart_scheduled;", "update settings actions reads normalized restart flag");
assertNotIncludes(updateSettingsActions, "const restartScheduled = Boolean(payload.restart_scheduled);", "update settings actions avoids raw restart flag coercion in update flow");
assertIncludes(updateSettingsActions, "const currentStatus = settingsState.updateStatus;", "update settings actions snapshots normalized update status before result patching");
assertIncludes(updateSettingsActions, "settingsState.updateStatus = {\n        supported: currentStatus.supported,\n        dirty: currentStatus.dirty,\n        update_available: false,\n        commits_behind: 0,\n        current_rev_short: payload.after_rev_short || currentStatus.current_rev_short,\n        branch: currentStatus.branch,\n        project_root: currentStatus.project_root,\n      };", "update settings actions patches update status with fixed fields");
assertNotIncludes(updateSettingsActions, "settingsState.updateStatus = {\n        ...settingsState.updateStatus,", "update settings actions avoids preserving arbitrary update status keys");
assertIncludes(updateSettingsActions, "function errorMessage(error: unknown): string", "update settings actions narrow unknown errors");
assertNotIncludes(updateSettingsActions, "Promise<any>", "update settings actions avoid any request promises");
assertNotIncludes(updateSettingsActions, "catch (error: any)", "update settings actions avoid any catch boundaries");
assertIncludes(updateSettingsActions, "window.setTimeout(() => window.location.reload(), 5000)", "update settings actions keep restart reload delay");
assertIncludes(settingsApi, "const error = Object.assign(new Error(text || `HTTP ${response.status}`), {", "settings API creates an error with inferred transport metadata");
assertIncludes(settingsApi, "status: response.status,\n      statusText: response.statusText,", "settings API preserves HTTP status metadata for callers");
assertNotIncludes(settingsApi, "SettingsApiError", "settings API avoids casting Error instances to a declared shape");
assertIncludes(settingsApi, "options: RequestInit = {}", "settings API accepts typed fetch options");
assertIncludes(settingsApi, "): Promise<unknown> {", "settings API exposes unverified JSON as unknown");
assertIncludes(settingsApi, "const payload: unknown = await response.json();\n  return payload;", "settings API keeps parsed JSON unknown at the transport boundary");
assertIncludes(settingsApi, "const headers = new Headers(options.headers);", "settings API normalizes every standard fetch header input");
assertIncludes(settingsApi, "if (options.body && !headers.has(\"Content-Type\"))", "settings API only supplies JSON content type when callers did not provide one");
assertIncludes(settingsApi, "headers.set(\"Content-Type\", \"application/json\");", "settings API preserves the JSON body default");
assertIncludes(settingsApi, "...options,\n    headers,", "settings API forwards normalized headers to fetch");
assertNotIncludes(settingsApi, "...(options.headers || {})", "settings API avoids object-spreading non-record header inputs");
assertNotIncludes(settingsApi, "requestSettingsJson<T", "settings API does not let callers select an unchecked response type");
assertNotIncludes(settingsApi, "as Promise<T>", "settings API avoids casting parsed JSON to caller-selected types");
assertIncludes(chatClientPaths, "export function buildRunSummaryPath(runId: string, sessionId: string): string", "chat client path helpers are typed");
assertIncludes(chatClientPaths, "encodeURIComponent(changeId)", "chat client path helpers keep file change encoding");
assertIncludes(chatClientPreferences, "export type LanguagePreference = (typeof LANGUAGE_OPTIONS)[number];", "chat client preferences expose typed language values");
assertIncludes(chatClientPreferences, "export type ColorSchemePreference = (typeof COLOR_SCHEME_OPTIONS)[number];", "chat client preferences expose typed color scheme values");
assertIncludes(chatClientPreferences, "export const SUPPORTED_LANGUAGES: ReadonlySet<LanguagePreference>", "chat client preferences expose typed language set");
assertIncludes(chatClientPreferences, "export const SUPPORTED_COLOR_SCHEMES: ReadonlySet<ColorSchemePreference>", "chat client preferences expose typed color scheme set");
assertIncludes(chatClientPreferences, "function isAllowedChoice<T extends string>(value: string, allowedValues: ReadonlySet<T>): value is T", "chat client preferences narrow generic finite choices with a type guard");
assertIncludes(chatClientPreferences, "export function normalizeChoice<T extends string>", "chat client preferences keep typed choice normalization");
assertIncludes(chatClientPreferences, "return isAllowedChoice(normalized, allowedValues) ? normalized : fallback;", "chat client preferences preserve fallback behavior without assertion");
assertNotIncludes(chatClientPreferences, "normalized as T", "chat client preferences avoid asserting normalized stored choices");
assertIncludes(chatClientPreferences, "export function getResolvedColorScheme(colorScheme: ColorSchemePreference): ResolvedColorScheme", "chat client preferences resolve typed color schemes");
assertIncludes(chatClientPreferences, "localStorage.getItem(key) || fallback", "chat client preferences preserve fallback behavior");
assertNotIncludes(settingsNormalizers, "type JsonRecord = Record<string, unknown>;", "settings normalizers avoid a shared generic JSON record alias");
assertNotIncludes(settingsNormalizers, "type SettingsPayload", "settings normalizers avoid a shared generic settings payload alias");
assertIncludes(settingsNormalizers, "type ChannelPayload = {", "settings normalizers type channel payload boundary");
assertNotIncludes(settingsNormalizers, "type ChannelPayload = SettingsPayload & {", "settings normalizers avoids dynamic channel item payload boundary");
assertIncludes(settingsNormalizers, "type?: unknown;", "settings normalizers name channel type field");
assertIncludes(settingsNormalizers, "enabled?: unknown;", "settings normalizers name channel enabled field");
assertIncludes(settingsNormalizers, "description?: unknown;", "settings normalizers name channel description field");
assertIncludes(settingsNormalizers, "status?: unknown;", "settings normalizers name channel status field");
assertIncludes(settingsNormalizers, "token_configured?: unknown;", "settings normalizers name channel token status field");
assertIncludes(settingsNormalizers, "type ChannelSettingsPayload = {", "settings normalizers type fixed channel settings payload boundary");
assertNotIncludes(settingsNormalizers, "type ChannelSettingsPayload = SettingsPayload & {", "settings normalizers keep generic settings records out of channel settings payloads");
assertIncludes(settingsNormalizers, "connected?: unknown;", "settings normalizers name connected channels payload field");
assertIncludes(settingsNormalizers, "available?: unknown;", "settings normalizers name available channels payload field");
assertIncludes(settingsNormalizers, "channels?: unknown;", "settings normalizers name channels payload field");
assertIncludes(settingsNormalizers, "type NormalizedChannelSettingsPayload = {", "settings normalizers name normalized channel settings payload boundary");
assertIncludes(settingsNormalizers, "type MediaSectionsPayload = {", "settings normalizers type fixed media sections payload boundary");
assertNotIncludes(settingsNormalizers, "type MediaSectionsPayload = SettingsPayload & {", "settings normalizers keep generic settings records out of media sections payloads");
assertIncludes(settingsNormalizers, "vision?: unknown;", "settings normalizers name vision media section field");
assertIncludes(settingsNormalizers, "ocr?: unknown;", "settings normalizers name OCR media section field");
assertIncludes(settingsNormalizers, "speech?: unknown;", "settings normalizers name speech media section field");
assertIncludes(settingsNormalizers, "video?: unknown;", "settings normalizers name video media section field");
assertIncludes(settingsNormalizers, "type MediaSettingsPayload = {", "settings normalizers type fixed media settings payload boundary");
assertNotIncludes(settingsNormalizers, "type MediaSettingsPayload = SettingsPayload & {", "settings normalizers keep generic settings records out of media settings payloads");
assertIncludes(settingsNormalizers, "providers?: unknown;", "settings normalizers name media providers payload field");
assertIncludes(settingsNormalizers, "type McpSettingsPayload = {", "settings normalizers type fixed MCP settings payload boundary");
assertNotIncludes(settingsNormalizers, "type McpSettingsPayload = SettingsPayload & {", "settings normalizers keep generic settings records out of MCP settings payloads");
assertIncludes(settingsNormalizers, "servers?: unknown;", "settings normalizers name MCP servers payload field");
assertIncludes(settingsNormalizers, "runtime?: unknown;", "settings normalizers name MCP runtime payload field");
assertIncludes(settingsNormalizers, "type McpRuntimePayload = {", "settings normalizers type fixed MCP runtime payload boundary");
assertNotIncludes(settingsNormalizers, "type McpRuntimePayload = SettingsPayload & {", "settings normalizers keep generic settings records out of MCP runtime payloads");
assertIncludes(settingsNormalizers, "connect_failures?: unknown;", "settings normalizers name MCP runtime failures field");
assertIncludes(settingsNormalizers, "tool_names?: unknown;", "settings normalizers name MCP runtime tool names field");
assertIncludes(settingsNormalizers, "type McpServerPayload = {", "settings normalizers name fixed MCP server payload boundary");
assertIncludes(settingsNormalizers, "id?: unknown;\n  name?: unknown;\n  type?: unknown;", "settings normalizers name MCP server identity fields");
assertIncludes(settingsNormalizers, "tool_timeout?: unknown;\n  enabled_tools?: unknown;", "settings normalizers name MCP server runtime fields");
assertIncludes(settingsNormalizers, "env_configured?: unknown;\n  env_keys?: unknown;\n  headers_configured?: unknown;\n  headers_keys?: unknown;", "settings normalizers name MCP server secret metadata fields");
assertNotIncludes(settingsNormalizers, "type McpServerPayload = {\n  [key: string]: unknown;", "settings normalizers avoid an open MCP server payload boundary");
assertIncludes(settingsNormalizers, "type ProviderModelMetadataPayload = {\n  model_metadata_fields?: unknown;\n};", "settings normalizers name provider metadata field boundary");
assertNotIncludes(settingsNormalizers, "function toSettingsPayload", "settings normalizers avoid a shared generic settings converter");
assertIncludes(settingsNormalizers, "function toChannelSettingsPayload(value: unknown): ChannelSettingsPayload", "settings normalizers narrow channel settings before field reads");
assertIncludes(settingsNormalizers, "function toChannelSettingsPayload(value: unknown): ChannelSettingsPayload {\n  const payload = toPayloadSource<ChannelSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "settings normalizers handle non-object channel settings before field projection");
assertIncludes(settingsNormalizers, "connected: payload.connected,\n    available: payload.available,\n    channels: payload.channels,", "settings normalizers project channel settings payloads onto named fields");
assertIncludes(settingsNormalizers, "function toMediaSettingsPayload(value: unknown): MediaSettingsPayload", "settings normalizers narrow media settings before field reads");
assertIncludes(settingsNormalizers, "function toMediaSettingsPayload(value: unknown): MediaSettingsPayload {\n  const payload = toPayloadSource<MediaSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "settings normalizers handle non-object media settings before field projection");
assertIncludes(settingsNormalizers, "sections: payload.sections,\n    providers: payload.providers,", "settings normalizers project media settings payloads onto named fields");
assertIncludes(settingsNormalizers, "function toMediaSectionsPayload(value: unknown): MediaSectionsPayload", "settings normalizers narrow media sections before field reads");
assertIncludes(settingsNormalizers, "function toMediaSectionsPayload(value: unknown): MediaSectionsPayload {\n  const payload = toPayloadSource<MediaSectionsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "settings normalizers handle non-object media sections before field projection");
assertIncludes(settingsNormalizers, "vision: payload.vision,\n    ocr: payload.ocr,\n    speech: payload.speech,\n    video: payload.video,", "settings normalizers project media sections payloads onto named fields");
assertIncludes(settingsNormalizers, "function toMcpSettingsPayload(value: unknown): McpSettingsPayload", "settings normalizers narrow MCP settings before field reads");
assertIncludes(settingsNormalizers, "function toMcpSettingsPayload(value: unknown): McpSettingsPayload {\n  const payload = toPayloadSource<McpSettingsPayload>(value);\n  if (!payload) {\n    return {};\n  }", "settings normalizers handle non-object MCP settings before field projection");
assertIncludes(settingsNormalizers, "servers: payload.servers,\n    runtime: payload.runtime,", "settings normalizers project MCP settings payloads onto named fields");
assertIncludes(settingsNormalizers, "function toMcpRuntimePayload(value: unknown): McpRuntimePayload | null", "settings normalizers narrow MCP runtime before field reads");
assertIncludes(settingsNormalizers, "const payload = toPayloadSource<McpRuntimePayload>(value);", "settings normalizers inspect raw MCP runtime through its named payload");
assertIncludes(settingsNormalizers, "return payload && Object.keys(payload).length > 0", "settings normalizers handles non-object MCP runtime before field projection");
assertIncludes(settingsNormalizers, "connected: payload.connected,\n        connecting: payload.connecting,\n        connect_failures: payload.connect_failures,\n        retry_after: payload.retry_after,\n        tool_names: payload.tool_names,", "settings normalizers project MCP runtime payloads onto named fields");
assertIncludes(settingsNormalizers, "function mcpServerPayloadList(value: unknown): McpServerPayload[]", "settings normalizers normalize MCP server arrays at their named boundary");
assertIncludes(settingsNormalizers, "function toMcpServerPayload(value: unknown): McpServerPayload | null", "settings normalizers project each MCP server through fixed fields");
assertIncludes(settingsNormalizers, "headers_keys: payload.headers_keys,", "settings normalizers complete the fixed MCP server field projection");
assertIncludes(settingsNormalizers, ".map(toMcpServerPayload)", "settings normalizers use the fixed MCP server projector for server arrays");
assertNotIncludes(settingsNormalizers, ".map((item) => toPayloadSource<McpServerPayload>(item))", "settings normalizers avoid returning raw MCP server records");
assertNotIncludes(settingsNormalizers, "function settingsPayloadList", "settings normalizers avoid a shared generic payload-list helper");
assertIncludes(settingsNormalizers, "function channelPayloadList(value: unknown): ChannelPayload[]", "settings normalizers normalize channel arrays at boundary");
assertIncludes(settingsNormalizers, ".map((item) => toPayloadSource<ChannelPayload>(item))", "settings normalizers narrow each channel item through its named payload");
assertIncludes(settingsNormalizers, "export function providerModelMetadataFields(provider: unknown = {}): string[]", "settings normalizers accept unknown provider metadata at the boundary");
assertIncludes(settingsNormalizers, "const payload = toPayloadSource<ProviderModelMetadataPayload>(provider);", "settings normalizers project provider metadata fields through the named payload");
assertIncludes(settingsNormalizers, "export function providerSupportsModelMetadata(provider: unknown, field: string): boolean", "settings normalizers keep provider metadata checks on the unknown boundary");
assertIncludes(settingsNormalizers, "export const MCP_TRANSPORT_TYPES = [\"stdio\", \"sse\", \"streamableHttp\"] as const;", "settings normalizers own MCP transport values");
assertIncludes(settingsNormalizers, "export type McpTransportType = (typeof MCP_TRANSPORT_TYPES)[number];", "settings normalizers export typed MCP transport union");
assertIncludes(settingsNormalizers, "function isMcpTransportType(value: string): value is McpTransportType", "settings normalizers narrow finite MCP transports with a type guard");
assertIncludes(settingsNormalizers, "if (isMcpTransportType(transport)) {\n    return transport;", "settings normalizers return validated MCP transports without assertion");
assertNotIncludes(settingsNormalizers, "transport as McpTransportType", "settings normalizers avoid asserting validated MCP transports");
assertIncludes(settingsNormalizers, "export function normalizeMcpTransport(value: unknown, fallback: McpTransportType = \"stdio\"): McpTransportType", "settings normalizers type MCP transport normalization");
assertIncludes(settingsNormalizers, "export function visibleChannels(channels: unknown = []): ChannelPayload[]", "settings normalizers return typed visible channel payloads");
assertIncludes(settingsNormalizers, "return channelPayloadList(channels).filter((channel) => channel.id !== \"web\" && channel.id !== \"console\");", "settings normalizers filter visible channels through typed channel payloads");
assertIncludes(settingsNormalizers, "export function normalizeChannelSettings(payload: ChannelSettingsPayload = {}): NormalizedChannelSettingsPayload", "settings normalizers normalize typed channel settings payloads");
assertIncludes(settingsNormalizers, "const settings = toChannelSettingsPayload(payload);", "settings normalizers use typed channel settings payload in normalizer");
assertIncludes(settingsNormalizers, "const channels = visibleChannels(settings.channels);", "settings normalizers read channels from typed channel settings payload");
assertNotIncludes(settingsNormalizers, "      ...settings,\n      connected: visibleChannels(settings.connected),", "settings normalizers avoid spreading grouped channel settings payloads");
assertNotIncludes(settingsNormalizers, "    ...settings,\n    connected: channels.filter((channel) => channel.token_configured),", "settings normalizers avoid spreading ungrouped channel settings payloads");
assertIncludes(settingsNormalizers, "export function sortChannelList(channels: ChannelPayload[]): ChannelPayload[]", "settings normalizers sort typed channel payloads");
assertIncludes(settingsNormalizers, "export function normalizeMediaSettings(payload: MediaSettingsPayload = {}): MediaSettingsPayload", "settings normalizers normalize typed media settings payloads");
assertIncludes(settingsNormalizers, "const settings = toMediaSettingsPayload(payload);", "settings normalizers use typed media settings payload in normalizer");
assertIncludes(settingsNormalizers, "const sections = toMediaSectionsPayload(settings.sections);", "settings normalizers use typed media sections payload in normalizer");
assertNotIncludes(settingsNormalizers, "    ...settings,\n    sections: {", "settings normalizers avoid spreading open-ended media settings payloads");
assertIncludes(settingsNormalizers, "providers: Array.isArray(settings.providers) ? settings.providers : [],", "settings normalizers read providers from typed media settings payload");
assertIncludes(settingsNormalizers, "export function normalizeMcpSettings(payload: McpSettingsPayload = {}, fallbackRuntime: McpRuntimePayload = {}): McpSettingsPayload", "settings normalizers type the MCP runtime fallback at its actual boundary");
assertNotIncludes(mcpSettingsActions, "fallbackRuntime as unknown as JsonRecord", "MCP settings actions avoid casting typed runtime fallback through generic JSON records");
assertIncludes(settingsNormalizers, "const settings = toMcpSettingsPayload(payload);", "settings normalizers use typed MCP settings payload in normalizer");
assertIncludes(settingsNormalizers, "const runtime = toMcpRuntimePayload(settings.runtime);", "settings normalizers use typed MCP runtime payload in normalizer");
assertIncludes(settingsNormalizers, "servers: mcpServerPayloadList(settings.servers),", "settings normalizers narrow MCP server items through the named server boundary");
assertNotIncludes(settingsNormalizers, "    ...settings,\n    servers: mcpServerPayloadList(settings.servers),", "settings normalizers avoid spreading open-ended MCP settings payloads");
assertIncludes(settingsNormalizers, "runtime: runtime\n      ? {", "settings normalizers preserve MCP runtime fallback when no runtime payload is present");
assertIncludes(settingsNormalizers, "return \"streamableHttp\";", "settings normalizers preserve streamable HTTP alias");
assertIncludes(settingsNormalizers, "channel.id !== \"web\" && channel.id !== \"console\"", "settings normalizers keep hidden built-in channel filter");
assertNotIncludes(settingsNormalizers, "Record<string, any>", "settings normalizers avoid broad dynamic records");

console.log("web smoke checks passed");
