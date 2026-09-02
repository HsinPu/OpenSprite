import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useConversationSettings } from "../src/features/conversation-settings/useConversationSettings";
import { I18nProvider } from "../src/i18n/I18nProvider";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

function Harness() {
  const settings = useConversationSettings();
  return (
    <div>
      <output data-testid="loaded">{String(settings.loaded)}</output>
      <output data-testid="auto-scroll">{String(settings.settings.autoScroll)}</output>
      <output data-testid="execution-expanded">{String(settings.settings.executionPanelDefaultExpanded)}</output>
      <button type="button" onClick={() => void settings.saveAutoScroll(false)}>disable scroll</button>
      <button type="button" onClick={() => void settings.saveExecutionPanelDefaultExpanded(true)}>expand execution</button>
    </div>
  );
}

describe("useConversationSettings", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("merges rapid conversation preference saves into the latest snapshot", async () => {
    const firstPut = deferred<Response>();
    const secondPut = deferred<Response>();
    const payloads: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/conversation" && !init) {
        return Promise.resolve(new Response(JSON.stringify({
          startupView: "new",
          sendBehavior: "enter",
          autoScroll: true,
          executionPanelDefaultExpanded: false,
        })));
      }
      if (path === "/api/settings/conversation" && init?.method === "PUT") {
        const payload = JSON.parse(String(init.body)) as Record<string, unknown>;
        payloads.push(payload);
        return payloads.length === 1 ? firstPut.promise : secondPut.promise;
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><Harness /></I18nProvider>);

    await waitFor(() => expect(screen.getByTestId("loaded").textContent).toBe("true"));
    fireEvent.click(screen.getByRole("button", { name: "disable scroll" }));
    fireEvent.click(screen.getByRole("button", { name: "expand execution" }));

    await waitFor(() => expect(payloads).toHaveLength(1));
    expect(payloads[0]).toEqual({
      startupView: "new",
      sendBehavior: "enter",
      autoScroll: false,
      executionPanelDefaultExpanded: false,
    });
    firstPut.resolve(new Response(JSON.stringify(payloads[0])));
    await waitFor(() => expect(payloads).toHaveLength(2));
    expect(payloads[1]).toEqual({
      startupView: "new",
      sendBehavior: "enter",
      autoScroll: false,
      executionPanelDefaultExpanded: true,
    });
    secondPut.resolve(new Response(JSON.stringify(payloads[1])));

    await waitFor(() => {
      expect(screen.getByTestId("auto-scroll").textContent).toBe("false");
      expect(screen.getByTestId("execution-expanded").textContent).toBe("true");
    });
  });
});
