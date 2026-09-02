import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useToolSettings } from "../src/features/tool-settings/useToolSettings";
import { I18nProvider } from "../src/i18n/I18nProvider";


function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

function Harness() {
  const controller = useToolSettings();
  return <div>
    <output data-testid="loaded">{String(controller.loaded)}</output>
    <output data-testid="global">{String(controller.settings.enabled)}</output>
    <output data-testid="calculator">{String(controller.settings.enabledTools.includes("calculator"))}</output>
    <button type="button" onClick={() => void controller.saveEnabled(false)}>disable all</button>
    <button type="button" onClick={() => void controller.saveToolEnabled("calculator", false)}>disable calculator</button>
  </div>;
}

describe("useToolSettings", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("loads the catalog and serializes rapid saves into the latest snapshot", async () => {
    const firstPut = deferred<Response>();
    const secondPut = deferred<Response>();
    const payloads: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/tools") return Promise.resolve(new Response(JSON.stringify({ items: [{ id: "calculator", source: "builtin", effect: "read_only", available: true }] })));
      if (path === "/api/settings/tools" && !init) return Promise.resolve(new Response(JSON.stringify({ enabled: true, enabledTools: ["calculator"] })));
      if (path === "/api/settings/tools" && init?.method === "PUT") {
        const payload = JSON.parse(String(init.body)) as Record<string, unknown>;
        payloads.push(payload);
        return payloads.length === 1 ? firstPut.promise : secondPut.promise;
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><Harness /></I18nProvider>);

    await waitFor(() => expect(screen.getByTestId("loaded").textContent).toBe("true"));
    fireEvent.click(screen.getByRole("button", { name: "disable all" }));
    fireEvent.click(screen.getByRole("button", { name: "disable calculator" }));

    await waitFor(() => expect(payloads).toHaveLength(1));
    expect(payloads[0]).toEqual({ enabled: false, enabledTools: ["calculator"] });
    firstPut.resolve(new Response(JSON.stringify(payloads[0])));
    await waitFor(() => expect(payloads).toHaveLength(2));
    expect(payloads[1]).toEqual({ enabled: false, enabledTools: [] });
    secondPut.resolve(new Response(JSON.stringify(payloads[1])));

    await waitFor(() => {
      expect(screen.getByTestId("global").textContent).toBe("false");
      expect(screen.getByTestId("calculator").textContent).toBe("false");
    });
  });

  it("keeps confirmed settings after a save failure", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/tools") return Promise.resolve(new Response(JSON.stringify({ items: [{ id: "calculator", source: "builtin", effect: "read_only", available: true }] })));
      if (path === "/api/settings/tools" && !init) return Promise.resolve(new Response(JSON.stringify({ enabled: true, enabledTools: ["calculator"] })));
      return Promise.resolve(new Response(JSON.stringify({ error: { code: "settings_store_unavailable", message: "private", retryable: true } }), { status: 503 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><Harness /></I18nProvider>);

    await waitFor(() => expect(screen.getByTestId("loaded").textContent).toBe("true"));
    fireEvent.click(screen.getByRole("button", { name: "disable all" }));
    await waitFor(() => expect(screen.getByTestId("global").textContent).toBe("true"));
  });
});
