import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ConversationSettingsApiError,
  getConversationSettings,
  putConversationSettings,
} from "../src/api/conversationSettings";


afterEach(() => vi.unstubAllGlobals());


describe("conversation settings API", () => {
  it("reads and writes only the strict startup and send shape", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ startupView: "new", sendBehavior: "enter" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ startupView: "recent", sendBehavior: "modifier-enter" })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getConversationSettings()).resolves.toEqual({ startupView: "new", sendBehavior: "enter" });
    await expect(putConversationSettings({ startupView: "recent", sendBehavior: "modifier-enter" })).resolves.toEqual({ startupView: "recent", sendBehavior: "modifier-enter" });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/settings/conversation", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ startupView: "recent", sendBehavior: "modifier-enter" }),
    });
  });

  it.each([
    { startupView: "last", sendBehavior: "enter" },
    { startupView: "new", sendBehavior: "shift-enter" },
    { startupView: "new", sendBehavior: "enter", extra: true },
  ])("rejects malformed responses", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
    await expect(getConversationSettings()).rejects.toBeInstanceOf(ConversationSettingsApiError);
  });
});
