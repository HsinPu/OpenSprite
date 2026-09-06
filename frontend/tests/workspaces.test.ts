import { afterEach, describe, expect, it, vi } from "vitest";

import {
  WorkspaceApiError,
  addWorkspaceMount,
  createWorkspace,
  deleteWorkspace,
  deleteWorkspaceMount,
  importWorkspace,
  listWorkspaceImportCandidates,
  listWorkspaces,
  setActiveWorkspace,
  updateWorkspace,
  updateWorkspaceMount,
  type Workspace,
  type WorkspaceCatalog,
} from "../src/api/workspaces";

const defaultWorkspace: Workspace = {
  id: "00000000-0000-4000-8000-000000000000",
  kind: "default",
  name: "Default workspace",
  directoryName: "default",
  rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\default",
  availability: "available",
  unavailableReason: null,
  mounts: [],
  revision: 1,
  createdAt: "1970-01-01T00:00:00Z",
  updatedAt: "1970-01-01T00:00:00Z",
  usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 },
};
const alpha: Workspace = {
  ...defaultWorkspace,
  id: "11111111-1111-4111-8111-111111111111",
  kind: "managed",
  name: "Alpha",
  directoryName: "Alpha",
  rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\Alpha",
  usage: { conversationCount: 2, scheduleCount: 1, activeRunCount: 0 },
};
const mounted: Workspace = {
  ...alpha,
  revision: 2,
  mounts: [{
    id: "22222222-2222-4222-8222-222222222222",
    alias: "Docs",
    rootPath: "D:\\Docs",
    rootHash: "a".repeat(64),
    accessMode: "read_only",
    enabled: true,
    availability: "available",
    unavailableReason: null,
  }],
};
const catalog: WorkspaceCatalog = { revision: 1, activeWorkspaceId: alpha.id, workspaces: [defaultWorkspace, alpha] };

afterEach(() => vi.unstubAllGlobals());

describe("Workspace API", () => {
  it("accepts relocation failures without discarding the workspace catalog", async () => {
    const unavailable = { ...defaultWorkspace, rootPath: "C:\\Users\\Test\\.opensprite\\workspace\\default", availability: "unavailable", unavailableReason: "migration_failed" };
    const response = { ...catalog, workspaces: [unavailable, alpha] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(response))));
    await expect(listWorkspaces()).resolves.toEqual(response);
  });
  it("strictly parses managed roots, mounts and availability", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...catalog, workspaces: [defaultWorkspace, mounted] }))));

    await expect(listWorkspaces()).resolves.toEqual({ ...catalog, workspaces: [defaultWorkspace, mounted] });
  });

  it("uses exact optimistic mutation requests", async () => {
    const updated = { ...alpha, name: "Renamed", revision: 2 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ candidates: [{ directoryName: "Existing", rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\Existing" }], nextCursor: null })))
      .mockResolvedValueOnce(new Response(JSON.stringify(updated)))
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify(mounted), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(mounted)))
      .mockResolvedValueOnce(new Response(JSON.stringify(alpha)))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await createWorkspace("Alpha", 0);
    await importWorkspace("Existing", 1);
    await listWorkspaceImportCandidates();
    await updateWorkspace(alpha, "Renamed");
    await setActiveWorkspace(alpha.id, 1);
    await addWorkspaceMount(alpha, "Docs", "D:\\Docs");
    await updateWorkspaceMount(mounted, mounted.mounts[0]!.id, "Docs", "D:\\Docs", "read_write", false);
    await deleteWorkspaceMount(mounted, mounted.mounts[0]!.id);
    await deleteWorkspace(alpha);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Alpha", expectedRevision: 0 }) });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/workspaces/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ directoryName: "Existing", expectedRevision: 1 }) });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/workspaces/import-candidates?limit=100", undefined);
    expect(fetchMock).toHaveBeenNthCalledWith(4, `/api/workspaces/${alpha.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Renamed", expectedRevision: 1 }) });
    expect(fetchMock).toHaveBeenNthCalledWith(6, `/api/workspaces/${alpha.id}/mounts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ alias: "Docs", rootPath: "D:\\Docs", accessMode: "read_only", enabled: true, expectedRevision: 1 }) });
    expect(fetchMock).toHaveBeenNthCalledWith(9, `/api/workspaces/${alpha.id}?expectedRevision=1`, { method: "DELETE" });
  });

  it("rejects malformed success and accepts only fixed errors", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...catalog, leaked: true })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "overlapping_root", message: "safe", retryable: false } }), { status: 409 })));

    await expect(listWorkspaces()).rejects.toEqual(new WorkspaceApiError("malformed_response"));
    await expect(addWorkspaceMount(alpha, "Docs", "D:\\Docs")).rejects.toEqual(new WorkspaceApiError("overlapping_root"));
  });
});
