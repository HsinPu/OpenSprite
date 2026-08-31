import { describe, expect, it, vi } from "vitest";

import { AiSettingsApiError, aiSettingsErrorText, getAiSettings, putAiSettings } from "../src/api/aiSettings";

const selection = { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto", outputBudget: "auto" } as const;

describe("AI settings client", () => {
  it("uses the exact GET and PUT shapes", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ model: selection, responseMode: "deep", outputContinuation: "5", responseDelivery: "complete", logFullPrompts: false })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ model: null, responseMode: "default", outputContinuation: "off", responseDelivery: "stream", logFullPrompts: false })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAiSettings()).resolves.toEqual({ model: selection, responseMode: "deep", outputContinuation: "5", responseDelivery: "complete", logFullPrompts: false });
    await expect(putAiSettings({ model: null, responseMode: "default", outputContinuation: "off", responseDelivery: "stream", logFullPrompts: false })).resolves.toEqual({ model: null, responseMode: "default", outputContinuation: "off", responseDelivery: "stream", logFullPrompts: false });
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/settings/ai", undefined);
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/settings/ai", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: null, responseMode: "default", outputContinuation: "off", responseDelivery: "stream", logFullPrompts: false }),
    });
  });

  it.each([
    [{ model: { ...selection, extra: true }, responseMode: "balanced", outputContinuation: "2", responseDelivery: "stream", logFullPrompts: false }, 200],
    [{ model: { providerId: "openai", modelId: "   " }, responseMode: "balanced", outputContinuation: "2", responseDelivery: "stream", logFullPrompts: false }, 200],
    [{ model: { ...selection, contextBudget: "other" }, responseMode: "balanced", outputContinuation: "2", responseDelivery: "stream", logFullPrompts: false }, 200],
    [{ model: selection, responseMode: "other", outputContinuation: "2", responseDelivery: "stream", logFullPrompts: false }, 200],
    [{ model: selection, responseMode: "balanced", outputContinuation: "2", responseDelivery: "stream", logFullPrompts: false, extra: true }, 200],
    [{ model: selection, responseMode: "balanced", outputContinuation: "other", responseDelivery: "stream", logFullPrompts: false }, 200],
    [{ model: selection, responseMode: "balanced", outputContinuation: "2", responseDelivery: "other", logFullPrompts: false }, 200],
    [{ error: { code: "not_connected", message: "private", retryable: false } }, 500],
    [{ error: { code: "network_error", message: "private", retryable: false } }, 409],
  ])("fails closed on malformed or mismatched responses", async (body, status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
    await expect(status === 200 ? getAiSettings() : putAiSettings({ model: selection, responseMode: "balanced", outputContinuation: "2", responseDelivery: "stream", logFullPrompts: false })).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("maps only stable local error text", () => {
    const text = aiSettingsErrorText(new AiSettingsApiError("settings_store_unavailable"));
    expect(text).toBe("AI 設定暫時無法讀取或儲存。");
    expect(text).not.toContain("private");
  });
});
