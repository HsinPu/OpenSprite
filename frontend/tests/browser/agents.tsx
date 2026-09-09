/*
 * Browser-only verification fixture.
 *
 * This file intentionally replaces window.fetch with an in-memory API. It
 * must never be used by the product runtime or connect to a user's backend.
 */
import { useMemo } from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";

import type { AgentBatchAction, AgentScope, CustomAgent } from "../../src/api/customAgents";
import type { SubagentStatus } from "../../src/api/subagents";
import { SubagentExecution } from "../../src/features/chat/SubagentExecution";
import { AgentsSettings } from "../../src/features/settings/AgentsSettings";
import type { ProviderCatalogController } from "../../src/features/ai-settings/useProviderCatalog";
import type { WorkspaceCatalog } from "../../src/api/workspaces";
import { I18nProvider } from "../../src/i18n/I18nProvider";
import "../../src/app/app.css";
import "../../src/features/settings/settings.css";

const defaultWorkspaceId = "00000000-0000-4000-8000-000000000000";
const demoWorkspaceId = "11111111-1111-4111-8111-111111111111";
const parentRunId = "22222222-2222-4222-8222-222222222222";
const completedChildId = "33333333-3333-4333-8333-333333333333";
const runningChildId = "44444444-4444-4444-8444-444444444444";
const now = "2026-09-09T08:00:00Z";
const hash = "a".repeat(64);

type ScopeKey = `${AgentScope}:${string}`;

const scopeKey = (scope: AgentScope, workspaceId: string | null): ScopeKey => `${scope}:${workspaceId ?? "global"}`;

function definition(
  id: string,
  scope: AgentScope,
  workspaceId: string | null,
  name: string,
  description: string,
  instructions: string,
): CustomAgent {
  return {
    id,
    scope,
    workspaceId,
    fileName: `${name}.toml`,
    name,
    description,
    revision: 1,
    enabled: true,
    reason: "effective",
    shadowedByAgentId: null,
    providerId: null,
    model: null,
    contentHash: hash,
  };
}

const agents = new Map<string, CustomAgent>([
  ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", definition("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "global", null, "code-review", "檢查程式碼的正確性與可維護性", "Review code for correctness, security, and maintainability.")],
  ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", definition("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "global", null, "writing", "協助撰寫清晰且一致的內容", "Write clear, concise, and consistent content.")],
  ["cccccccc-cccc-4ccc-8ccc-cccccccccccc", definition("cccccccc-cccc-4ccc-8ccc-cccccccccccc", "workspace", demoWorkspaceId, "code-review", "工作區專用的程式碼審查規則", "Prefer the workspace coding conventions while reviewing code.")],
]);

const contents = new Map<string, string>([
  ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "name = \"code-review\"\ndescription = \"檢查程式碼的正確性與可維護性\"\ndeveloper_instructions = \"Review code for correctness, security, and maintainability.\"\n"],
  ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "name = \"writing\"\ndescription = \"協助撰寫清晰且一致的內容\"\ndeveloper_instructions = \"Write clear, concise, and consistent content.\"\n"],
  ["cccccccc-cccc-4ccc-8ccc-cccccccccccc", "name = \"code-review\"\ndescription = \"工作區專用的程式碼審查規則\"\ndeveloper_instructions = \"Prefer the workspace coding conventions while reviewing code.\"\n"],
]);

const revisions = new Map<ScopeKey, number>([
  [scopeKey("global", null), 1],
  [scopeKey("workspace", demoWorkspaceId), 1],
]);
let settingsRevision = 1;
let agentsEnabled = true;

const workspaceCatalog: WorkspaceCatalog = {
  revision: 1,
  activeWorkspaceId: demoWorkspaceId,
  workspaces: [
    {
      id: defaultWorkspaceId,
      kind: "default",
      name: "預設工作區",
      directoryName: "default",
      rootPath: "C:/Users/fixture/.opensprite/workspace/default",
      availability: "available",
      unavailableReason: null,
      mounts: [],
      revision: 1,
      createdAt: now,
      updatedAt: now,
      usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 },
    },
    {
      id: demoWorkspaceId,
      kind: "managed",
      name: "Demo Workspace",
      directoryName: "demo",
      rootPath: "C:/Users/fixture/.opensprite/workspace/demo",
      availability: "available",
      unavailableReason: null,
      mounts: [],
      revision: 1,
      createdAt: now,
      updatedAt: now,
      usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 },
    },
  ],
};

type Child = {
  id: string;
  parentRunId: string;
  agentId: string;
  name: string;
  revision: number;
  providerId: "openrouter";
  modelId: string;
  status: SubagentStatus;
  errorCode: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  result: string;
};

const children = new Map<string, Child>([
  [completedChildId, {
    id: completedChildId,
    parentRunId: parentRunId,
    agentId: "55555555-5555-4555-8555-555555555555",
    name: "completed-reviewer",
    revision: 1,
    providerId: "openrouter",
    modelId: "openrouter/auto",
    status: "completed",
    errorCode: null,
    createdAt: now,
    startedAt: now,
    finishedAt: "2026-09-09T08:00:05Z",
    result: "Fixture report: the completed subagent returned this plain-text result.\nNo Markdown rendering is used.",
  }],
  [runningChildId, {
    id: runningChildId,
    parentRunId: parentRunId,
    agentId: "66666666-6666-4666-8666-666666666666",
    name: "running-researcher",
    revision: 1,
    providerId: "openrouter",
    modelId: "openrouter/auto",
    status: "running",
    errorCode: null,
    createdAt: now,
    startedAt: now,
    finishedAt: null,
    result: "This running fixture can be cancelled from the card.",
  }],
]);

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
}

function errorResponse(code: string, status = 400): Response {
  return jsonResponse({ error: { code, message: "Isolated fixture error", retryable: status >= 500 } }, status);
}

function bodyOf(init?: RequestInit): Record<string, any> {
  if (!init?.body) return {};
  return JSON.parse(String(init.body)) as Record<string, any>;
}

function contentValue(content: string, key: string): string {
  const match = content.match(new RegExp(`^${key}\\s*=\\s*"((?:\\\\.|[^"\\\\])*)"\\s*$`, "m"));
  return match?.[1] ?? "";
}

function currentItems(scope: AgentScope, workspaceId: string | null): CustomAgent[] {
  return [...agents.values()].filter((item) => item.scope === scope && item.workspaceId === workspaceId);
}

function agentPayload(item: CustomAgent): CustomAgent {
  return { ...item };
}

function childSummary(item: Child) {
  const { result: _result, ...summary } = item;
  return summary;
}

function dispatchSampleImport(): void {
  const input = document.querySelector<HTMLInputElement>(".agents-toolbar input[type=file]");
  if (!input) return;
  const file = new File([
    "name = \"fixture-import\"\n",
    "description = \"Imported by the isolated browser fixture\"\n",
    "developer_instructions = \"Use this only for browser verification.\"\n",
  ], "fixture-import.toml", { type: "text/plain" });
  const transfer = new DataTransfer();
  transfer.items.add(file);
  Object.defineProperty(input, "files", { configurable: true, value: transfer.files });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function urlFrom(input: RequestInfo | URL): URL {
  if (typeof input === "string") return new URL(input, window.location.href);
  if (input instanceof URL) return input;
  return new URL(input.url, window.location.href);
}

async function fixtureFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = urlFrom(input);
  const method = (init?.method ?? "GET").toUpperCase();
  const path = url.pathname;
  const body = bodyOf(init);

  if (path === "/api/agents/settings" && method === "GET") {
    return jsonResponse({ enabled: agentsEnabled, revision: settingsRevision });
  }
  if (path === "/api/agents/settings" && method === "PUT") {
    if (body.expectedRevision !== settingsRevision || typeof body.enabled !== "boolean") return errorResponse("revision_conflict", 409);
    agentsEnabled = body.enabled;
    settingsRevision += 1;
    return jsonResponse({ enabled: agentsEnabled, revision: settingsRevision });
  }
  if (path === "/api/workspaces" && method === "GET") return jsonResponse(workspaceCatalog);

  const listMatch = path.match(/^\/api\/agents$/);
  if (listMatch && method === "GET") {
    const scope = url.searchParams.get("scope");
    const workspaceId = url.searchParams.get("workspaceId");
    if (scope !== "global" && scope !== "workspace") return errorResponse("invalid_request");
    const actualWorkspaceId = scope === "workspace" ? workspaceId : null;
    const items = currentItems(scope, actualWorkspaceId).map(agentPayload);
    return jsonResponse({ revision: revisions.get(scopeKey(scope, actualWorkspaceId)) ?? 1, items, nextCursor: null });
  }

  if (path === "/api/agents" && method === "POST") {
    const scope = body.scope as AgentScope;
    const workspaceId = (body.workspaceId ?? null) as string | null;
    const key = scopeKey(scope, workspaceId);
    const expected = revisions.get(key) ?? 1;
    if (body.expectedRevision !== expected || (scope !== "global" && scope !== "workspace")) return errorResponse("revision_conflict", 409);
    const content = typeof body.content === "string" ? body.content : "";
    const name = contentValue(content, "name");
    if (!name) return errorResponse("invalid_format");
    const id = crypto.randomUUID();
    const item = definition(id, scope, workspaceId, name, contentValue(content, "description"), contentValue(content, "developer_instructions"));
    agents.set(id, item);
    contents.set(id, content);
    revisions.set(key, expected + 1);
    return jsonResponse(agentPayload(item), 201);
  }

  const scanMatch = path.match(/^\/api\/agents\/scan$/);
  if (scanMatch && method === "POST") {
    const key = scopeKey(body.scope as AgentScope, (body.workspaceId ?? null) as string | null);
    const expected = revisions.get(key) ?? 1;
    if (body.expectedRevision !== expected) return errorResponse("revision_conflict", 409);
    return jsonResponse({ revision: expected, added: 0 });
  }

  const batchMatch = path.match(/^\/api\/agents\/batch$/);
  if (batchMatch && method === "POST") {
    const scope = body.scope as AgentScope;
    const workspaceId = (body.workspaceId ?? null) as string | null;
    const key = scopeKey(scope, workspaceId);
    const expected = revisions.get(key) ?? 1;
    if (body.expectedRevision !== expected || !Array.isArray(body.ids) || !["enable", "disable", "remove"].includes(body.action as string)) return errorResponse("revision_conflict", 409);
    let affected = 0;
    for (const id of body.ids as string[]) {
      const item = agents.get(id);
      if (!item || item.scope !== scope || item.workspaceId !== workspaceId) continue;
      affected += 1;
      if (body.action === "remove") { agents.delete(id); contents.delete(id); }
      else agents.set(id, { ...item, enabled: body.action === "enable", reason: body.action === "enable" ? "effective" : "disabled", revision: item.revision + 1 });
    }
    revisions.set(key, expected + 1);
    return jsonResponse({ revision: expected + 1, affected });
  }

  const idMatch = path.match(/^\/api\/agents\/([^/]+)(?:\/(enabled))?$/);
  if (idMatch) {
    const id = decodeURIComponent(idMatch[1]);
    const item = agents.get(id);
    if (!item) return errorResponse("not_found", 404);
    const key = scopeKey(item.scope, item.workspaceId);
    const expected = revisions.get(key) ?? 1;
    if (method === "GET") return jsonResponse({ ...agentPayload(item), content: contents.get(id) ?? null });
    if (method === "PUT" && idMatch[2] === "enabled") {
      if (body.expectedRevision !== expected || typeof body.enabled !== "boolean") return errorResponse("revision_conflict", 409);
      const updated = { ...item, enabled: body.enabled, reason: body.enabled ? "effective" as const : "disabled" as const, revision: item.revision + 1 };
      agents.set(id, updated); revisions.set(key, expected + 1);
      return jsonResponse(agentPayload(updated));
    }
    if (method === "PUT") {
      if (body.expectedRevision !== expected || typeof body.content !== "string") return errorResponse("revision_conflict", 409);
      const content = body.content as string;
      const updated = { ...item, name: contentValue(content, "name") || item.name, description: contentValue(content, "description"), revision: item.revision + 1 };
      agents.set(id, updated); contents.set(id, content); revisions.set(key, expected + 1);
      return jsonResponse(agentPayload(updated));
    }
    if (method === "DELETE") {
      if (Number(url.searchParams.get("expectedRevision")) !== expected) return errorResponse("revision_conflict", 409);
      agents.delete(id); contents.delete(id); revisions.set(key, expected + 1);
      return new Response(null, { status: 204 });
    }
  }

  const childrenMatch = path.match(/^\/api\/runs\/([^/]+)\/agents(?:\/([^/]+)(?:\/cancel)?)?$/);
  if (childrenMatch) {
    const requestedParent = childrenMatch[1];
    const requestedChild = childrenMatch[2];
    if (requestedParent !== parentRunId) return errorResponse("not_found", 404);
    if (!requestedChild && method === "GET") {
      return jsonResponse({ items: [...children.values()].map(childSummary) });
    }
    if (requestedChild && path.endsWith("/cancel") && method === "POST") {
      const item = children.get(requestedChild);
      if (!item) return errorResponse("not_found", 404);
      const updated = { ...item, status: "cancelled" as const, finishedAt: now };
      children.set(requestedChild, updated);
      return jsonResponse(childSummary(updated));
    }
    if (requestedChild && method === "GET") {
      const item = children.get(requestedChild);
      if (!item) return errorResponse("not_found", 404);
      const offset = Number(url.searchParams.get("offset") ?? 0);
      const text = item.result.slice(offset, offset + 4000);
      return jsonResponse({ childId: item.id, status: item.status, error: item.errorCode, text, nextOffset: offset + text.length < item.result.length ? offset + text.length : null });
    }
  }

  throw new Error(`Unknown isolated fixture route: ${method} ${path}`);
}

const providerCatalog: ProviderCatalogController = {
  providers: [{ id: "openrouter", name: "OpenRouter", connected: true, status: "connected", credentialPreview: "fixture", lastCheckedAt: now }],
  catalogError: null,
  openRouterModels: null,
  openRouterModelLoadStatus: "success",
  openRouterModelError: null,
  modelChoices: [{ label: "OpenRouter Auto", selection: { providerId: "openrouter", modelId: "openrouter/auto", contextBudget: "auto", outputBudget: "auto" } }],
  refreshProviders: async () => providerCatalog.providers,
  readProviderSummary: async () => providerCatalog.providers?.[0] ?? null,
  updateProviderSummary: () => undefined,
  loadOpenRouterModels: async () => undefined,
  invalidateOpenRouterModels: () => undefined,
};

function Fixture() {
  const workspaces = useMemo(() => ({ catalog: workspaceCatalog }), []);
  return <ConfigProvider theme={{ token: { colorPrimary: "#ff6545", borderRadius: 10 } }}>
    <div className="settings-page" style={{ minHeight: "100vh" }}>
      <header className="settings-header">
        <div><h1>OpenSprite isolated Agents</h1><p>Browser fixture · in-memory API only · no user runtime connection</p></div>
        <span className="settings-save-status">agents.html</span>
      </header>
      <main className="settings-content">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 18 }}>
          <button type="button" onClick={dispatchSampleImport}>匯入範例 TOML</button>
          <span>使用上方按鈕可開啟真實匯入預覽；資料只存在此頁面的記憶體 fixture。</span>
        </div>
        <AgentsSettings workspaces={workspaces} providerCatalog={providerCatalog} container={null} />
        <section style={{ marginTop: 32 }} aria-label="Subagent fixture">
          <h2>Subagent execution fixture</h2>
          <p>Expand the completed child to load its bounded plain-text result; cancel the running child.</p>
          <SubagentExecution parentRunId={parentRunId} parentActive historical={false} />
        </section>
      </main>
    </div>
  </ConfigProvider>;
}

window.fetch = fixtureFetch;
createRoot(document.getElementById("root")!).render(<I18nProvider><Fixture /></I18nProvider>);
