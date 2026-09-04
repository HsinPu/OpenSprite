import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useWorkspaces } from "../src/features/workspaces/useWorkspaces";

const unassigned = { id: "00000000-0000-4000-8000-000000000000", kind: "unassigned", name: "Unassigned workspace", rootPath: null, availability: "not_applicable", unavailableReason: null, revision: 1, createdAt: "1970-01-01T00:00:00Z", updatedAt: "1970-01-01T00:00:00Z", usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 } };
const alpha = { id: "11111111-1111-4111-8111-111111111111", kind: "directory", name: "Alpha", rootPath: "C:\\Projects\\Alpha", availability: "available", unavailableReason: null, revision: 1, createdAt: "2026-09-04T01:00:00Z", updatedAt: "2026-09-04T01:00:00Z", usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 } };
const initial = { revision: 1, activeWorkspaceId: unassigned.id, workspaces: [unassigned, alpha] };
const activated = { ...initial, revision: 2, activeWorkspaceId: alpha.id };

function Harness() {
  const state = useWorkspaces();
  return <div><output>{state.activeWorkspace?.name ?? "none"}</output><output data-testid="error">{state.error?.code ?? ""}</output><button onClick={() => void state.activate(alpha.id)}>activate</button><button onClick={() => void state.reload()}>reload</button></div>;
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
});
