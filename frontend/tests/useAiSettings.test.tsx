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
      <output data-testid="response-mode">{settings.responseMode}</output>
      <output data-testid="output-continuation">{settings.outputContinuation}</output>
      <button type="button" onClick={() => void settings.reload()}>reload</button>
      <button type="button" onClick={() => void settings.saveResponseMode("deep")}>deep</button>
      <button type="button" onClick={() => void settings.saveOutputContinuation("5")}>five</button>
    </div>
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
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

  it("merges rapid saves into the latest AI settings snapshot", async () => {
    const firstPut = deferred<Response>();
    const secondPut = deferred<Response>();
    const payloads: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: null, responseMode: "default", outputContinuation: "2", responseDelivery: "stream", logFullPrompts: false })));
      if (path === "/api/settings/ai" && init?.method === "PUT") {
        const payload = JSON.parse(String(init.body)) as Record<string, unknown>;
        payloads.push(payload);
        return payloads.length === 1 ? firstPut.promise : secondPut.promise;
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><Harness /></I18nProvider>);

    await waitFor(() => expect(screen.getByTestId("loaded").textContent).toBe("true"));
    fireEvent.click(screen.getByRole("button", { name: "deep" }));
    fireEvent.click(screen.getByRole("button", { name: "five" }));

    await waitFor(() => expect(payloads).toHaveLength(1));
    expect(payloads[0]?.responseMode).toBe("deep");
    firstPut.resolve(new Response(JSON.stringify(payloads[0])));
    await waitFor(() => expect(payloads).toHaveLength(2));
    expect(payloads[1]?.responseMode).toBe("deep");
    expect(payloads[1]?.outputContinuation).toBe("5");
    secondPut.resolve(new Response(JSON.stringify(payloads[1])));

    await waitFor(() => {
      expect(screen.getByTestId("response-mode").textContent).toBe("deep");
      expect(screen.getByTestId("output-continuation").textContent).toBe("5");
    });
  });
});
