import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspacesSettings } from "../src/features/settings/WorkspacesSettings";
import type { Workspace, WorkspaceCatalog } from "../src/api/workspaces";
import type { WorkspaceController } from "../src/features/workspaces/useWorkspaces";

const defaultWorkspace: Workspace = { id: "00000000-0000-4000-8000-000000000000", kind: "default", name: "Default workspace", directoryName: "default", rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\default", mounts: [], availability: "available", unavailableReason: null, revision: 1, createdAt: "1970-01-01T00:00:00Z", updatedAt: "1970-01-01T00:00:00Z", usage: { conversationCount: 3, scheduleCount: 0, activeRunCount: 0 } };
const alpha: Workspace = { ...defaultWorkspace, id: "11111111-1111-4111-8111-111111111111", kind: "managed", name: "Alpha", directoryName: "Alpha", rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\Alpha", usage: { conversationCount: 1, scheduleCount: 0, activeRunCount: 0 } };
const empty: Workspace = { ...alpha, id: "22222222-2222-4222-8222-222222222222", name: "Empty", directoryName: "Empty", rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\Empty", usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 } };
const catalog: WorkspaceCatalog = { revision: 2, activeWorkspaceId: alpha.id, workspaces: [defaultWorkspace, alpha, empty] };
const create = vi.fn(async () => ({ ...catalog, revision: 3, activeWorkspaceId: empty.id }));
const update = vi.fn(async (item: Workspace) => item);
const remove = vi.fn(async () => undefined);
const importExisting = vi.fn(async () => ({ ...catalog, revision: 3, activeWorkspaceId: empty.id }));
const addMount = vi.fn(async (item: Workspace) => item);
const updateMount = vi.fn(async (item: Workspace) => item);
const removeMount = vi.fn(async (item: Workspace) => item);
const loadImportCandidates = vi.fn(async () => undefined);
const controller: WorkspaceController = {
  catalog,
  activeWorkspace: alpha,
  loaded: true,
  loading: false,
  saving: false,
  error: null,
  importCandidates: [{ directoryName: "Existing", rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\Existing" }],
  importCandidatesLoading: false,
  importCandidatesNextCursor: null,
  reload: async () => catalog,
  loadImportCandidates,
  create,
  importExisting,
  update,
  activate: async () => catalog,
  remove,
  addMount,
  updateMount,
  removeMount,
};

beforeEach(() => {
  for (const mock of [create, update, remove, importExisting, addMount, updateMount, removeMount, loadImportCandidates]) mock.mockClear();
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
});

describe("Workspace settings", () => {
  it("shows a selectable full path and closes it with Escape", async () => {
    render(<WorkspacesSettings controller={controller} container={null} onActivated={vi.fn()} />);
    const trigger = screen.getByRole("button", { name: "查看 Alpha 的完整路徑" });
    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(document.querySelector(".workspace-full-path")?.textContent).toBe(alpha.rootPath);
    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });

  it("requires confirmation before removing an empty Workspace", async () => {
    render(<WorkspacesSettings controller={controller} container={null} onActivated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Empty 的工作區操作" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "移除" }));
    expect(remove).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /移.*除/ }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(empty));
  });

  it("does not show an expansion control for empty mounts", () => {
    render(<WorkspacesSettings controller={controller} container={null} onActivated={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "外部掛載（0）" })).toBeNull();
    expect(screen.getAllByRole("heading", { name: "外部掛載（0）" })).toHaveLength(3);
  });

  it("automatically expands a newly added mount after the catalog updates", async () => {
    const { rerender } = render(<WorkspacesSettings controller={controller} container={null} onActivated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "新增掛載 Alpha" }));
    fireEvent.change(screen.getByLabelText("掛載名稱"), { target: { value: "Docs" } });
    fireEvent.change(screen.getByRole("textbox", { name: /外部目錄/ }), { target: { value: "D:\\Docs" } });
    fireEvent.click(screen.getByRole("button", { name: /儲.*存/ }));
    await waitFor(() => expect(addMount).toHaveBeenCalledWith(alpha, "Docs", "D:\\Docs", "read_only"));
    const mounted: Workspace = { ...alpha, mounts: [{ id: "33333333-3333-4333-8333-333333333333", alias: "Docs", rootPath: "D:\\Docs", rootHash: "a".repeat(64), accessMode: "read_only", enabled: true, availability: "available", unavailableReason: null }] };
    rerender(<WorkspacesSettings controller={{ ...controller, catalog: { ...catalog, workspaces: [mounted] } }} container={null} onActivated={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "外部掛載（1）" }).getAttribute("aria-expanded")).toBe("true"));
    expect(screen.getByRole("button", { name: "編輯 Docs" })).toBeTruthy();
  });

  it("shows managed roots and keeps the fixed default Workspace immutable", async () => {
    render(<WorkspacesSettings controller={controller} container={null} onActivated={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "預設工作區" })).toBeTruthy();
    expect(screen.getByText("預設")).toBeTruthy();
    expect(screen.getByText("C:\\Users\\Test\\OpenSprite\\workspace\\Alpha")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "預設工作區 的工作區操作" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Alpha 的工作區操作" }));
    expect((await screen.findByRole("menuitem", { name: /移除/ })).getAttribute("aria-disabled")).toBe("true");
  });

  it.each([[1440, ".ant-modal"], [390, ".ant-drawer"]])("creates a managed Workspace at %ipx without asking for a root", async (width, selector) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    const onActivated = vi.fn();
    render(<WorkspacesSettings controller={controller} container={null} onActivated={onActivated} />);

    fireEvent.click(screen.getByRole("button", { name: "新增工作區" }));
    expect(document.querySelector(selector)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("工作區名稱"), { target: { value: "Beta" } });
    expect(screen.queryByLabelText("根目錄")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /儲.*存/ }));

    await waitFor(() => expect(create).toHaveBeenCalledWith("Beta"));
    expect(onActivated).toHaveBeenCalledWith(empty.id);
  });

  it("imports an existing first-level managed directory explicitly", async () => {
    render(<WorkspacesSettings controller={controller} container={null} onActivated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "加入既有目錄" }));
    expect(loadImportCandidates).toHaveBeenCalledWith(true);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /^加.*入$/ }));

    await waitFor(() => expect(importExisting).toHaveBeenCalledWith("Existing"));
  });

  it("adds an external mount with read-only as the default", async () => {
    render(<WorkspacesSettings controller={controller} container={null} onActivated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "新增掛載 Alpha" }));
    fireEvent.change(screen.getByLabelText("掛載名稱"), { target: { value: "Docs" } });
    fireEvent.change(screen.getByRole("textbox", { name: /外部目錄/ }), { target: { value: "D:\\Docs" } });
    fireEvent.click(screen.getByRole("button", { name: /儲.*存/ }));

    await waitFor(() => expect(addMount).toHaveBeenCalledWith(alpha, "Docs", "D:\\Docs", "read_only"));
  });

  it("explains a disabled legacy mount conflict", () => {
    const legacy = {
      ...alpha,
      mounts: [{
        id: "33333333-3333-4333-8333-333333333333",
        alias: "legacy-root",
        rootPath: "D:\\Legacy",
        rootHash: "a".repeat(64),
        accessMode: "read_write" as const,
        enabled: false,
        availability: "unavailable" as const,
        unavailableReason: "overlap" as const,
      }],
    };
    const legacyCatalog = { ...catalog, workspaces: [defaultWorkspace, legacy, empty] };
    render(<WorkspacesSettings controller={{ ...controller, catalog: legacyCatalog, activeWorkspace: legacy }} container={null} onActivated={vi.fn()} />);

    expect(screen.getByText("1 項異常")).toBeTruthy();
    const toggle = screen.getByRole("button", { name: "外部掛載（1）" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggle);
    expect(screen.getByText(/路徑與其他工作區重疊/)).toBeTruthy();
  });

  it.each([
    ["path", "D:\\NewDocs"],
    ["permission", "D:\\Docs"],
  ])("confirms a sensitive mount %s change before saving", async (change, path) => {
    const mounted = {
      ...alpha,
      mounts: [{
        id: "33333333-3333-4333-8333-333333333333",
        alias: "Docs",
        rootPath: "D:\\Docs",
        rootHash: "a".repeat(64),
        accessMode: "read_only" as const,
        enabled: true,
        availability: "available" as const,
        unavailableReason: null,
      }],
    };
    render(<WorkspacesSettings controller={{ ...controller, catalog: { ...catalog, workspaces: [defaultWorkspace, mounted, empty] }, activeWorkspace: mounted }} container={null} onActivated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "外部掛載（1）" }));
    fireEvent.click(screen.getByRole("button", { name: "編輯 Docs" }));
    if (change === "path") {
      fireEvent.change(screen.getByRole("textbox", { name: /外部目錄/ }), { target: { value: path } });
    } else {
      fireEvent.mouseDown(screen.getByRole("combobox", { name: /存取權限/ }));
      fireEvent.click((await screen.findByText("可讀寫")).closest(".ant-select-item-option")!);
    }
    fireEvent.click(screen.getByRole("button", { name: /儲.*存/ }));

    const confirmation = (await screen.findByText("確認掛載變更")).closest("[role='dialog']") as HTMLElement;
    expect(updateMount).not.toHaveBeenCalled();
    fireEvent.click(within(confirmation).getByRole("button", { name: /儲.*存/ }));

    await waitFor(() => expect(updateMount).toHaveBeenCalledWith(
      mounted,
      mounted.mounts[0].id,
      "Docs",
      path,
      change === "permission" ? "read_write" : "read_only",
      true,
    ));
  });
});
