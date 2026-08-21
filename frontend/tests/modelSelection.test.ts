import { describe, expect, it, vi } from "vitest";

import { ModelSelectionApiError, getModelSelection, modelSelectionErrorText, putModelSelection } from "../src/api/modelSelection";

const selection = { providerId: "openai", modelId: "gpt-5.6" } as const;

describe("model selection client", () => {
  it("uses the exact GET and PUT shapes", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ selection })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ selection: null })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getModelSelection()).resolves.toEqual(selection);
    await expect(putModelSelection(null)).resolves.toBeNull();
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/settings/model", undefined);
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/settings/model", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ selection: null }),
    });
  });

  it.each([
    [{ selection: { ...selection, extra: true } }, 200],
    [{ selection: { providerId: "openai", modelId: "   " } }, 200],
    [{ error: { code: "not_connected", message: "private", retryable: false } }, 500],
    [{ error: { code: "network_error", message: "private", retryable: false } }, 409],
  ])("fails closed on malformed or mismatched responses", async (body, status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
    await expect(status === 200 ? getModelSelection() : putModelSelection(selection)).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("maps only stable local error text", () => {
    const text = modelSelectionErrorText(new ModelSelectionApiError("settings_store_unavailable"));
    expect(text).toBe("模型設定暫時無法讀取或儲存。");
    expect(text).not.toContain("private");
  });
});
