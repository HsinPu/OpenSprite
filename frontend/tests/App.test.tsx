import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/app/App";

beforeEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value(this: HTMLDialogElement) { this.open = true; },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value(this: HTMLDialogElement) {
      this.open = false;
      this.dispatchEvent(new Event("close"));
    },
  });
});

const connectedOpenAi = {
  providers: [
    { id: "openai", name: "OpenAI", connected: true, status: "connected", credentialPreview: "••••1234", lastCheckedAt: "2026-08-20T08:30:00Z" },
    { id: "anthropic", name: "Anthropic", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
    { id: "openrouter", name: "OpenRouter", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
  ],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("settings dialog focus restoration", () => {
  it.each([[1440], [390]])("returns focus to the actual settings opener at %ipx after close", async (width) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    render(<App />);
    const opener = screen.getByRole("button", { name: "設定" });
    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "關閉設定" }));

    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it.each([[1440], [390]])("returns focus to the opener after native-dialog Escape at %ipx", async (width) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    const { container } = render(<App />);
    const opener = screen.getByRole("button", { name: "設定" });
    fireEvent.click(opener);
    const dialog = container.querySelector("dialog")!;
    const cancel = new Event("cancel", { cancelable: true });
    dialog.dispatchEvent(cancel);
    if (!cancel.defaultPrevented) dialog.close();

    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});

describe("persisted AI settings", () => {
  it("chooses the first available model when no selection exists", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: null, responseMode: "balanced" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/settings/ai" && init?.method === "PUT") return Promise.resolve(new Response(init.body));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    const modelPicker = await screen.findByRole("combobox", { name: /目前模型 GPT-5.6/ });
    expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6"]));
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/ai", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6" }, responseMode: "balanced" }),
    });
  });

  it("ignores a late hydration result after a newer model save", async () => {
    const hydration = deferred<Response>();
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return hydration.promise;
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/settings/ai" && init?.method === "PUT") return Promise.resolve(new Response(init.body));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    const modelPicker = await screen.findByRole("combobox", { name: /尚未選擇模型/ });
    fireEvent.change(modelPicker, { target: { value: JSON.stringify(["openai", "gpt-5.6-mini"]) } });
    await waitFor(() => expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6-mini"])));
    hydration.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6" }, responseMode: "deep" })));

    await waitFor(() => expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6-mini"])));
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/ai", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6-mini" }, responseMode: "default" }),
    });
  });

  it("hydrates the saved model and changes it only after the PUT succeeds", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6" }, responseMode: "balanced" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/settings/ai" && init?.method === "PUT") return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6-mini" }, responseMode: "balanced" })));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    const modelPicker = await screen.findByRole("combobox", { name: /目前模型 GPT-5.6/ });
    expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6"]));
    fireEvent.click(screen.getByRole("button", { name: "設定" }));
    fireEvent.click(screen.getByRole("button", { name: "AI 模型" }));
    await screen.findAllByText("OpenAI");
    await waitFor(() => expect(screen.getByRole("option", { name: "GPT-5.6 mini" })).toBeTruthy());
    fireEvent.change(modelPicker, { target: { value: JSON.stringify(["openai", "gpt-5.6-mini"]) } });
    await waitFor(() => expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6-mini"])));
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/ai", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6-mini" }, responseMode: "balanced" }) });
  });

  it("keeps the confirmed model when the PUT fails", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6" }, responseMode: "balanced" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/settings/ai" && init?.method === "PUT") return Promise.resolve(new Response(JSON.stringify({ error: { code: "not_connected", message: "private", retryable: false } }), { status: 409 }));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    const modelPicker = await screen.findByRole("combobox", { name: /目前模型 GPT-5.6/ });
    fireEvent.click(screen.getByRole("button", { name: "設定" }));
    fireEvent.click(screen.getByRole("button", { name: "AI 模型" }));
    await screen.findAllByText("OpenAI");
    await waitFor(() => expect(screen.getByRole("option", { name: "GPT-5.6 mini" })).toBeTruthy());
    fireEvent.change(modelPicker, { target: { value: JSON.stringify(["openai", "gpt-5.6-mini"]) } });
    expect((await screen.findByRole("alert")).textContent).toContain("尚未連線");
    expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6"]));
  });

  it("hydrates and persists the response mode with the confirmed model", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6" }, responseMode: "deep" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/settings/ai" && init?.method === "PUT") return Promise.resolve(new Response(init.body));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "設定" }));
    fireEvent.click(screen.getByRole("button", { name: "AI 模型" }));
    const deep = await screen.findByRole("button", { name: "深入" });
    expect(deep.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "快速" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "快速" }).getAttribute("aria-pressed")).toBe("true"));
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/ai", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6" }, responseMode: "fast" }),
    });
  });

  it("keeps the confirmed response mode when saving fails", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6" }, responseMode: "balanced" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/settings/ai" && init?.method === "PUT") return Promise.resolve(new Response(JSON.stringify({ error: { code: "settings_store_unavailable", message: "private", retryable: true } }), { status: 503 }));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "設定" }));
    fireEvent.click(screen.getByRole("button", { name: "AI 模型" }));
    const balanced = await screen.findByRole("button", { name: "平衡" });
    await waitFor(() => expect(balanced.getAttribute("aria-pressed")).toBe("true"));
    fireEvent.click(screen.getByRole("button", { name: "深入" }));

    expect((await screen.findByRole("alert")).textContent).toContain("AI 設定暫時無法讀取或儲存");
    expect(balanced.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "深入" }).getAttribute("aria-pressed")).toBe("false");
  });
});

describe("conversation navigation", () => {
  it("renders backend conversations and uses only their UUID in the URL hash", async () => {
    const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6" }, responseMode: "default" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/conversations?limit=50") return Promise.resolve(new Response(JSON.stringify({
        conversations: [{
          id: conversationId,
          title: "回顧進度",
          latestMessagePreview: "整理本週完成項目",
          createdAt: "2026-08-22T08:00:00Z",
          updatedAt: "2026-08-22T08:30:00Z",
        }],
        nextCursor: null,
      })));
      if (path === `/api/conversations/${conversationId}/messages?limit=100`) return Promise.resolve(new Response(JSON.stringify({ messages: [], nextBeforeSequence: null })));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "回顧進度" }));

    await waitFor(() => expect(window.location.hash).toBe(`#chat=${conversationId}`));
    expect(screen.getByRole("heading", { level: 1, name: "回顧進度" })).toBeTruthy();
    expect(window.location.hash).not.toContain("回顧進度");

    fireEvent.click(screen.getByRole("button", { name: "新對話" }));
    expect(window.location.hash).toBe("#new-chat");
    expect(screen.getByRole("heading", { level: 1, name: "新對話" })).toBeTruthy();
  });
});
