import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspacesSettings } from "../src/features/settings/WorkspacesSettings";
import type { WorkspaceController } from "../src/features/workspaces/useWorkspaces";

const unassigned = { id: "00000000-0000-4000-8000-000000000000", kind: "unassigned" as const, name: "Unassigned workspace", rootPath: null, availability: "not_applicable" as const, unavailableReason: null, revision: 1, createdAt: "1970-01-01T00:00:00Z", updatedAt: "1970-01-01T00:00:00Z", usage: { conversationCount: 3, scheduleCount: 0, activeRunCount: 0 } };
const alpha = { id: "11111111-1111-4111-8111-111111111111", kind: "directory" as const, name: "Alpha", rootPath: "C:\\Projects\\Alpha", availability: "available" as const, unavailableReason: null, revision: 1, createdAt: "2026-09-04T01:00:00Z", updatedAt: "2026-09-04T01:00:00Z", usage: { conversationCount: 1, scheduleCount: 0, activeRunCount: 0 } };
const empty = { ...alpha, id: "22222222-2222-4222-8222-222222222222", name: "Empty", rootPath: "C:\\Projects\\Empty", usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 } };
const catalog = { revision: 2, activeWorkspaceId: alpha.id, workspaces: [unassigned, alpha, empty] };
const create = vi.fn(async () => ({ ...catalog, revision: 3, activeWorkspaceId: empty.id }));
const update = vi.fn(async (item) => item);
const remove = vi.fn(async () => undefined);
const controller: WorkspaceController = {
  catalog,
  activeWorkspace: alpha,
  loaded: true,
  loading: false,
  saving: false,
  error: null,
  reload: async () => catalog,
  create,
  update,
  activate: async () => catalog,
  remove,
};

beforeEach(() => {
  create.mockClear();
  update.mockClear();
  remove.mockClear();
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
});

describe("Workspace settings", () => {
  it("shows usage and disables removal until a Workspace is empty", () => {
    render(<WorkspacesSettings controller={controller} container={null} onActivated={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Alpha" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "移除 Alpha" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "移除 Empty" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it.each([[1440, ".ant-modal"], [390, ".ant-drawer"]])("uses a responsive create editor at %ipx", async (width, selector) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    const onActivated = vi.fn();
    const { container } = render(<WorkspacesSettings controller={controller} container={null} onActivated={onActivated} />);

    fireEvent.click(screen.getByRole("button", { name: "新增工作區" }));
    expect(document.querySelector(selector)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("工作區名稱"), { target: { value: "Beta" } });
    fireEvent.change(screen.getByLabelText("根目錄"), { target: { value: "C:\\Projects\\Beta" } });
    fireEvent.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => expect(create).toHaveBeenCalledWith("Beta", "C:\\Projects\\Beta"));
    expect(onActivated).toHaveBeenCalledWith(empty.id);
    expect(container).toBeTruthy();
  });
});
