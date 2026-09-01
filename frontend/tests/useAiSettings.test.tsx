import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAiSettings } from "../src/features/ai-settings/useAiSettings";
import { I18nProvider } from "../src/i18n/I18nProvider";


function Harness() {
  const settings = useAiSettings(null, []);
  return (
    <div>
      <output data-testid="loaded">{String(settings.loaded)}</output>
      <output data-testid="error">{settings.error ?? ""}</output>
      <button type="button" onClick={() => void settings.reload()}>reload</button>
    </div>
  );
}


beforeEach(() => {
  vi.unstubAllGlobals();
});


describe("useAiSettings", () => {
  it("exposes a retryable loading state when the initial read fails", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "settings_store_unavailable", message: "private", retryable: true } }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ model: null, responseMode: "default", outputContinuation: "2", responseDelivery: "stream", logFullPrompts: false })));
    vi.stubGlobal("fetch", fetchMock);

    render(<I18nProvider><Harness /></I18nProvider>);

    await waitFor(() => expect(screen.getByTestId("loaded").textContent).toBe("false"));
    expect(screen.getByTestId("error").textContent).toContain("AI 設定暫時無法讀取或儲存");
    fireEvent.click(screen.getByRole("button", { name: "reload" }));

    await waitFor(() => expect(screen.getByTestId("loaded").textContent).toBe("true"));
    expect(screen.getByTestId("error").textContent).toBe("");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
