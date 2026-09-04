import { afterEach, describe, expect, it, vi } from "vitest";

import {
  WorkspaceApiError,
  createWorkspace,
  deleteWorkspace,
  listWorkspaces,
  setActiveWorkspace,
  updateWorkspace,
  type Workspace,
  type WorkspaceCatalog,
} from "../src/api/workspaces";

const unassigned: Workspace = {
  id: "00000000-0000-4000-8000-000000000000",
  kind: "unassigned",
  name: "Unassigned workspace",
  rootPath: null,
  availability: "not_applicable",
  unavailableReason: null,
  revision: 1,
  createdAt: "1970-01-01T00:00:00Z",
  updatedAt: "1970-01-01T00:00:00Z",
  usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 },
};
const alpha: Workspace = {
  id: "11111111-1111-4111-8111-111111111111",
  kind: "directory",
  name: "Alpha",
  rootPath: "C:\\Projects\\Alpha",
  availability: "available",
  unavailableReason: null,
  revision: 1,
  createdAt: "2026-09-04T01:00:00Z",
  updatedAt: "2026-09-04T01:00:00Z",
  usage: { conversationCount: 2, scheduleCount: 1, activeRunCount: 0 },
};
const catalog: WorkspaceCatalog = { revision: 1, activeWorkspaceId: alpha.id, workspaces: [unassigned, alpha] };

afterEach(() => vi.unstubAllGlobals());

describe("Workspace API", () => {
  it("strictly parses the catalog and availability union", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(catalog))));

    await expect(listWorkspaces()).resolves.toEqual(catalog);
  });

  it("uses exact optimistic mutation requests", async () => {
    const updated = { ...alpha, name: "Renamed", revision: 2 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(updated)))
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog)))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await createWorkspace("Alpha", alpha.rootPath!, 0);
    await updateWorkspace(alpha, "Renamed", alpha.rootPath!);
    await setActiveWorkspace(alpha.id, 1);
    await deleteWorkspace(alpha);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Alpha", rootPath: alpha.rootPath, expectedRevision: 0 }) });
    expect(fetchMock).toHaveBeenNthCalledWith(2, `/api/workspaces/${alpha.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Renamed", rootPath: alpha.rootPath, expectedRevision: 1 }) });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/workspaces/active", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ workspaceId: alpha.id, expectedRevision: 1 }) });
    expect(fetchMock).toHaveBeenNthCalledWith(4, `/api/workspaces/${alpha.id}?expectedRevision=1`, { method: "DELETE" });
  });

  it("rejects malformed success and accepts only fixed errors", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...catalog, leaked: true })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "workspace_not_empty", message: "safe", retryable: false } }), { status: 409 })));

    await expect(listWorkspaces()).rejects.toEqual(new WorkspaceApiError("malformed_response"));
    await expect(deleteWorkspace(alpha)).rejects.toEqual(new WorkspaceApiError("workspace_not_empty"));
  });
});
