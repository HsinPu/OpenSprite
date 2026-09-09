import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import {
  batchAgents,
  createAgent,
  getAgentSettings,
  listAgents,
  setAgentEnabled,
  type CustomAgent,
} from "../src/api/customAgents";
import { AgentsSettings } from "../src/features/settings/AgentsSettings";

vi.mock("../src/api/customAgents", async (importOriginal) => ({
  ...await importOriginal<typeof import("../src/api/customAgents")>(),
  batchAgents: vi.fn(),
  createAgent: vi.fn(),
  getAgent: vi.fn(),
  getAgentSettings: vi.fn(),
  listAgents: vi.fn(),
  scanAgents: vi.fn(),
  setAgentEnabled: vi.fn(),
  setAgentSettings: vi.fn(),
  updateAgent: vi.fn(),
  deleteAgent: vi.fn(),
}));

const workspaceId = "22222222-2222-4222-8222-222222222222";
const agent = (overrides: Partial<CustomAgent> = {}): CustomAgent => ({
  id: "11111111-1111-4111-8111-111111111111",
  scope: "global",
  workspaceId: null,
  fileName: "review.toml",
  name: "review",
  description: "Review code",
  revision: 1,
  enabled: true,
  reason: "effective",
  shadowedByAgentId: null,
  providerId: null,
  model: null,
  contentHash: "a".repeat(64),
  ...overrides,
});
const workspaceCatalog = {
  revision: 1,
  activeWorkspaceId: workspaceId,
  workspaces: [{
    id: workspaceId,
    kind: "managed" as const,
    name: "Project",
    directoryName: "Project",
    rootPath: "C:\\workspace\\Project",
    mounts: [],
    availability: "available" as const,
    unavailableReason: null,
    revision: 1,
    createdAt: "1970-01-01T00:00:00Z",
    updatedAt: "1970-01-01T00:00:00Z",
    usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 },
  }],
};
const providerCatalog = { modelChoices: [] } as never;

beforeEach(() => {
  vi.mocked(getAgentSettings).mockReset().mockResolvedValue({ enabled: true, revision: 1 });
  vi.mocked(listAgents).mockReset().mockResolvedValue({ revision: 1, items: [agent()], nextCursor: null });
  vi.mocked(setAgentEnabled).mockReset().mockResolvedValue(agent({ enabled: false, revision: 2 }));
  vi.mocked(batchAgents).mockReset().mockResolvedValue({ revision: 2, affected: 1 });
  vi.mocked(createAgent).mockReset().mockResolvedValue(agent({ revision: 2 }));
});

it("loads settings and toggles an Agent through the strict adapter", async () => {
  render(<AgentsSettings workspaces={{ catalog: null }} providerCatalog={providerCatalog} container={null} />);
  expect(await screen.findByText("review")).toBeTruthy();
  fireEvent.click(screen.getByRole("switch", { name: "啟用 review" }));
  await waitFor(() => expect(setAgentEnabled).toHaveBeenCalledWith({ id: agent().id, enabled: false, expectedRevision: 1 }));
});

it("loads every cursor page before exposing a scope batch", async () => {
  vi.mocked(listAgents).mockResolvedValueOnce({ revision: 1, items: [agent()], nextCursor: "next" }).mockResolvedValueOnce({ revision: 1, items: [agent({ id: "33333333-3333-4333-8333-333333333333", name: "write" })], nextCursor: null });
  render(<AgentsSettings workspaces={{ catalog: null }} providerCatalog={providerCatalog} container={null} />);
  await screen.findByText("write");
  expect(listAgents).toHaveBeenNthCalledWith(1, "global", null, undefined, 100);
  expect(listAgents).toHaveBeenNthCalledWith(2, "global", null, "next", 100);
  fireEvent.click(screen.getByRole("button", { name: "批次操作" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "全部啟用" }));
  expect(await screen.findByText(/共 2 個 Agents/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "確認操作" }));
  await waitFor(() => expect(batchAgents).toHaveBeenCalledWith({ scope: "global", workspaceId: null, ids: [agent().id, "33333333-3333-4333-8333-333333333333"], action: "enable", expectedRevision: 1 }));
});

it("shows workspace Agents separately from read-only inherited globals", async () => {
  const local = agent({ id: "44444444-4444-4444-8444-444444444444", scope: "workspace", workspaceId, name: "review", enabled: false, reason: "disabled" });
  const global = agent({ name: "review" });
  vi.mocked(listAgents).mockImplementation(async (scope) => scope === "workspace" ? { revision: 1, items: [local], nextCursor: null } : { revision: 1, items: [global], nextCursor: null });
  render(<AgentsSettings workspaces={{ catalog: workspaceCatalog }} providerCatalog={providerCatalog} container={null} />);
  fireEvent.click(screen.getByRole("tab", { name: "工作區" }));
  expect(await screen.findByText("已由工作區版本取代")).toBeTruthy();
  expect(screen.getAllByText("review").length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText("唯讀")).toBeTruthy();
  expect(screen.getByText("此工作區版本無法使用，不會回退同名全域版本。")).toBeTruthy();
});

it("previews and saves a single TOML import without an edit step", async () => {
  render(<AgentsSettings workspaces={{ catalog: null }} providerCatalog={providerCatalog} container={null} />);
  await screen.findByText("review");
  const importedContent = `name = "writer"\ndescription = "Writes"\ndeveloper_instructions = "Write clearly."\n`;
  const file = new File([importedContent], "writer.toml", { type: "text/plain" });
  Object.defineProperty(file, "arrayBuffer", { value: async () => new TextEncoder().encode(await file.text()).buffer });
  fireEvent.change(document.querySelector('input[accept=".toml,text/plain"]')!, { target: { files: [file] } });
  expect(await screen.findByText("writer.toml")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /儲\s*存/ }));
  await waitFor(() => expect(createAgent).toHaveBeenCalledWith(expect.objectContaining({ scope: "global", workspaceId: null, expectedRevision: 1, content: expect.stringContaining('name = "writer"') })));
});

it("bounds the mobile Agent editor to its Drawer viewport", async () => {
  render(<AgentsSettings workspaces={{ catalog: null }} providerCatalog={providerCatalog} container={null} />);
  await screen.findByText("review");
  fireEvent.click(screen.getByRole("button", { name: "新增 Agent" }));

  const drawer = await screen.findByRole("dialog");
  expect(drawer.closest(".agents-drawer")).toBeTruthy();
  expect(drawer.querySelector(".agents-editor")).toBeTruthy();
  expect(drawer.querySelector(".agents-editor .ant-input")).toBeTruthy();
});
