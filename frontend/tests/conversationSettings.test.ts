import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ConversationSettingsApiError,
  getConversationSettings,
  putConversationSettings,
} from "../src/api/conversationSettings";


afterEach(() => vi.unstubAllGlobals());


describe("conversation settings API", () => {
  it("reads and writes only the strict conversation preference shape", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ startupView: "new", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: false })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ startupView: "recent", sendBehavior: "modifier-enter", autoScroll: false, executionPanelDefaultExpanded: true })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getConversationSettings()).resolves.toEqual({ startupView: "new", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: false });
    await expect(putConversationSettings({ startupView: "recent", sendBehavior: "modifier-enter", autoScroll: false, executionPanelDefaultExpanded: true })).resolves.toEqual({ startupView: "recent", sendBehavior: "modifier-enter", autoScroll: false, executionPanelDefaultExpanded: true });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/settings/conversation", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ startupView: "recent", sendBehavior: "modifier-enter", autoScroll: false, executionPanelDefaultExpanded: true }),
    });
  });

  it.each([
    { startupView: "last", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: false },
    { startupView: "new", sendBehavior: "shift-enter", autoScroll: true, executionPanelDefaultExpanded: false },
    { startupView: "new", sendBehavior: "enter", autoScroll: true },
    { startupView: "new", sendBehavior: "enter", autoScroll: "yes", executionPanelDefaultExpanded: false },
    { startupView: "new", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: "yes" },
    { startupView: "new", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: false, extra: true },
  ])("rejects malformed responses", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
    await expect(getConversationSettings()).rejects.toBeInstanceOf(ConversationSettingsApiError);
  });
});
