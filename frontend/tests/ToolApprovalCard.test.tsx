import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RunEvent } from "../src/api/agentChat";
import { ToolApprovalCard } from "../src/features/chat/ToolApprovalCard";
import { I18nProvider } from "../src/i18n/I18nProvider";


const approvalId = "33333333-3333-4333-8333-333333333333";
const runId = "11111111-1111-4111-8111-111111111111";
const conversationId = "22222222-2222-4222-8222-222222222222";
const serverId = "44444444-4444-4444-8444-444444444444";
const events: RunEvent[] = [{
  sequence: 1,
  type: "tool.approval_requested",
  runId,
  conversationId,
  createdAt: "2026-09-02T08:00:00Z",
  data: { approvalId, toolName: "mcp_44444444_echo_abcdef12", toolDisplayName: "Echo", serverId, argumentHash: "a".repeat(64), expiresAt: "2026-09-02T08:10:00Z" },
}];

afterEach(() => vi.unstubAllGlobals());

describe("ToolApprovalCard", () => {
  it("shows exact arguments and allows one call", async () => {
    const detail = { id: approvalId, runId, conversationId, toolId: "mcp_44444444_echo_abcdef12", toolName: "Echo", serverId, arguments: { value: "hello" }, argumentHash: "a".repeat(64), createdAt: "2026-09-02T08:00:00Z", expiresAt: "2026-09-02T08:10:00Z" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(detail)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: approvalId, decision: "allow_once" })));
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><ToolApprovalCard events={events} /></I18nProvider>);

    expect(await screen.findByText(/"value": "hello"/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "允許這一次" }));
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(`/api/tool-approvals/${approvalId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision: "allow_once" }) }));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "需要工具確認" })).toBeNull());
  });

  it("does not reopen an approval after a matching decided event", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<I18nProvider><ToolApprovalCard events={[...events, { ...events[0]!, sequence: 2, type: "tool.approval_decided", data: { approvalId, decision: "deny" } }]} /></I18nProvider>);
    expect(screen.queryByRole("heading", { name: "需要工具確認" })).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });
});
