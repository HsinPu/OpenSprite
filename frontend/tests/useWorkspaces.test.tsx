import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Workspace } from "../src/api/workspaces";
import { useWorkspaces } from "../src/features/workspaces/useWorkspaces";

const unassigned = { id: "00000000-0000-4000-8000-000000000000", kind: "unassigned", name: "Unassigned workspace", rootPath: null, availability: "not_applicable", unavailableReason: null, revision: 1, createdAt: "1970-01-01T00:00:00Z", updatedAt: "1970-01-01T00:00:00Z", usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 } };
const alphaRoot = "C:\\Projects\\Alpha";
const alpha: Workspace = { id: "11111111-1111-4111-8111-111111111111", kind: "directory", name: "Alpha", rootPath: alphaRoot, availability: "available", unavailableReason: null, revision: 1, createdAt: "2026-09-04T01:00:00Z", updatedAt: "2026-09-04T01:00:00Z", usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 } };
const beta = { ...alpha, id: "22222222-2222-4222-8222-222222222222", name: "Beta", rootPath: "C:\\Projects\\Beta" };
const initial = { revision: 1, activeWorkspaceId: unassigned.id, workspaces: [unassigned, alpha] };
const activated = { ...initial, revision: 2, activeWorkspaceId: alpha.id };
const created = { revision: 2, activeWorkspaceId: beta.id, workspaces: [unassigned, alpha, beta] };

function Harness() {
  const state = useWorkspaces();
  return <div><output>{state.activeWorkspace?.name ?? "none"}</output><output data-testid="error">{state.error?.code ?? ""}</output><output data-testid="loading">{String(state.loading)}</output><button onClick={() => void state.activate(alpha.id)}>activate</button><button onClick={() => void state.create("Beta", "C:\\Projects\\Beta")}>create</button><button onClick={() => void state.update(alpha, "Renamed", alphaRoot)}>update</button><button onClick={() => void state.reload()}>reload</button></div>;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

afterEach(() => vi.unstubAllGlobals());

describe("useWorkspaces", () => {
  it("loads once and applies the confirmed global active Workspace", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(initial)))
      .mockResolvedValueOnce(new Response(JSON.stringify(activated)));
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);

    await screen.findByText("Unassigned workspace");
    fireEvent.click(screen.getByRole("button", { name: "activate" }));
    await screen.findByText("Alpha");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenLastCalledWith("/api/workspaces/active", expect.objectContaining({ method: "PUT" }));
  });

  it("keeps a recoverable error when loading fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<Harness />);

    await waitFor(() => expect(screen.getByTestId("error").textContent).toBe("network_error"));
  });

  it("deduplicates concurrent reloads and clears the stale error while retrying", async () => {
    const retry = deferred<Response>();
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockReturnValueOnce(retry.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);
    await waitFor(() => expect(screen.getByTestId("error").textContent).toBe("network_error"));

    fireEvent.click(screen.getByRole("button", { name: "reload" }));
    fireEvent.click(screen.getByRole("button", { name: "reload" }));

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("error").textContent).toBe("");
    expect(screen.getByTestId("loading").textContent).toBe("true");
    retry.resolve(new Response(JSON.stringify(initial)));
    await screen.findByText("Unassigned workspace");
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
  });

  it("loads after the StrictMode effect remount simulation", async () => {
    const request = deferred<Response>();
    const fetchMock = vi.fn().mockReturnValueOnce(request.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<StrictMode><Harness /></StrictMode>);

    expect(fetchMock).toHaveBeenCalledOnce();
    request.resolve(new Response(JSON.stringify(initial)));

    await screen.findByText("Unassigned workspace");
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });

  it("does not let an older reload overwrite a successful mutation", async () => {
    const staleReload = deferred<Response>();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(initial)))
      .mockReturnValueOnce(staleReload.promise)
      .mockResolvedValueOnce(new Response(JSON.stringify(created), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);
    await screen.findByText("Unassigned workspace");

    fireEvent.click(screen.getByRole("button", { name: "reload" }));
    fireEvent.click(screen.getByRole("button", { name: "create" }));
    await screen.findByText("Beta");

    staleReload.resolve(new Response(JSON.stringify(initial)));
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));

    expect(screen.getByText("Beta")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("keeps the recoverable error when a post-mutation reload fails", async () => {
    const renamed = { ...alpha, name: "Renamed", revision: 2 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(initial)))
      .mockResolvedValueOnce(new Response(JSON.stringify(renamed)))
      .mockRejectedValueOnce(new Error("offline"));
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness />);
    await screen.findByText("Unassigned workspace");

    fireEvent.click(screen.getByRole("button", { name: "update" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(screen.getByTestId("error").textContent).toBe("network_error"));
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });
});
