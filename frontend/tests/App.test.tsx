import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/app/App";

beforeEach(() => {
  vi.unstubAllGlobals();
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
  window.history.replaceState(null, "", "/");
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
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

describe("mobile navigation accessibility", () => {
  it("removes the closed drawer from interaction and isolates page content while open", () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    const { container } = render(<App />);
    const sidebar = container.querySelector(".main-sidebar")!;
    const main = container.querySelector("main")!;

    expect(sidebar.hasAttribute("inert")).toBe(true);
    expect(sidebar.getAttribute("aria-hidden")).toBe("true");
    expect(main.hasAttribute("inert")).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "開啟主選單" }));
    expect(sidebar.hasAttribute("inert")).toBe(false);
    expect(sidebar.hasAttribute("aria-hidden")).toBe(false);
    expect(main.hasAttribute("inert")).toBe(true);

    fireEvent.click(screen.getAllByRole("button", { name: "關閉主選單" })[0]!);
    expect(sidebar.hasAttribute("inert")).toBe(true);
    expect(main.hasAttribute("inert")).toBe(false);
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
  it("uses compact General height and full Models height", () => {
    const { container } = render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "設定" }));
    const dialog = container.querySelector("dialog")!;
    expect(dialog.classList.contains("settings-dialog--general")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "AI 模型" }));
    expect(dialog.classList.contains("settings-dialog--models")).toBe(true);
  });

  it.each([[1440], [390]])("returns focus to the actual settings opener at %ipx after close", async (width) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    render(<App />);
    if (width <= 900) fireEvent.click(screen.getByRole("button", { name: "開啟主選單" }));
    const opener = screen.getByRole("button", { name: "設定" });
    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "關閉設定" }));

    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it.each([[1440], [390]])("returns focus to the opener after native-dialog Escape at %ipx", async (width) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    const { container } = render(<App />);
    if (width <= 900) fireEvent.click(screen.getByRole("button", { name: "開啟主選單" }));
    const opener = screen.getByRole("button", { name: "設定" });
    fireEvent.click(opener);
    const dialog = container.querySelector("dialog")!;
    const cancel = new Event("cancel", { cancelable: true });
    act(() => {
      dialog.dispatchEvent(cancel);
      if (!cancel.defaultPrevented) dialog.close();
    });

    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});

describe("Ant Design shell controls", () => {
  it("uses Ant Design buttons and icons for both collapse controls", () => {
    render(<App />);

    const sidebarToggle = screen.getByRole("button", { name: "收合側邊欄" });
    const executionToggle = screen.getByRole("button", { name: "收合本次執行" });
    expect(sidebarToggle.classList.contains("ant-btn")).toBe(true);
    expect(sidebarToggle.querySelector(".anticon-left")).toBeTruthy();
    expect(executionToggle.classList.contains("ant-btn")).toBe(true);
    expect(executionToggle.querySelector(".anticon-right")).toBeTruthy();
  });

  it("does not show the inactive tools and connections shortcut", () => {
    render(<App />);

    expect(screen.queryByRole("button", { name: "工具與連線" })).toBeNull();
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
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto" }, responseMode: "balanced" }),
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
    fireEvent.change(modelPicker, { target: { value: JSON.stringify(["openai", "gpt-5.6-luna"]) } });
    await waitFor(() => expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6-luna"])));
    hydration.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "128k" }, responseMode: "deep" })));

    await waitFor(() => expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6-luna"])));
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/ai", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6-luna", contextBudget: "auto" }, responseMode: "default" }),
    });
  });

  it("hydrates the saved model and changes it only after the PUT succeeds", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto" }, responseMode: "balanced" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/settings/ai" && init?.method === "PUT") return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6-luna", contextBudget: "auto" }, responseMode: "balanced" })));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    const modelPicker = await screen.findByRole("combobox", { name: /目前模型 GPT-5.6/ });
    expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6"]));
    fireEvent.click(screen.getByRole("button", { name: "設定" }));
    fireEvent.click(screen.getByRole("button", { name: "AI 模型" }));
    await screen.findAllByText("OpenAI");
    await waitFor(() => expect(screen.getByRole("option", { name: "GPT-5.6 Luna" })).toBeTruthy());
    fireEvent.change(modelPicker, { target: { value: JSON.stringify(["openai", "gpt-5.6-luna"]) } });
    await waitFor(() => expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6-luna"])));
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/ai", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6-luna", contextBudget: "auto" }, responseMode: "balanced" }) });
  });

  it("keeps the confirmed model when the PUT fails", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto" }, responseMode: "balanced" })));
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
    await waitFor(() => expect(screen.getByRole("option", { name: "GPT-5.6 Luna" })).toBeTruthy());
    fireEvent.change(modelPicker, { target: { value: JSON.stringify(["openai", "gpt-5.6-luna"]) } });
    expect((await screen.findByRole("alert")).textContent).toContain("尚未連線");
    expect((modelPicker as HTMLSelectElement).value).toBe(JSON.stringify(["openai", "gpt-5.6"]));
  });

  it("hydrates and persists the response mode with the confirmed model", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "256k" }, responseMode: "deep" })));
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
      body: JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "256k" }, responseMode: "fast" }),
    });
  });

  it("keeps the confirmed response mode when saving fails", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto" }, responseMode: "balanced" })));
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
  it.each([
    ["#new-chat", null],
    ["#chat=49d6c5e3-1724-44a7-9e69-0c0103176461", "49d6c5e3-1724-44a7-9e69-0c0103176461"],
  ])("keeps an explicit startup URL instead of applying the recent preference (%s)", async (hash, explicitConversationId) => {
    window.history.replaceState(null, "", hash);
    const fetchMock = vi.fn((path: string) => {
      if (path === "/api/settings/conversation") return Promise.resolve(new Response(JSON.stringify({ startupView: "recent", sendBehavior: "enter", autoScroll: true })));
      if (path === "/api/settings/general") return Promise.resolve(new Response(JSON.stringify({ locale: "zh-TW", timeZone: "system" })));
      if (path === "/api/settings/ai") return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto" }, responseMode: "default" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/conversations?limit=50") return Promise.resolve(new Response(JSON.stringify({ conversations: [{ id: "c7d17356-d2e6-4a5f-bbd7-7b5d6ac37875", title: "最近對話", latestMessagePreview: "最近內容", createdAt: "2026-08-22T08:00:00Z", updatedAt: "2026-08-22T08:30:00Z" }], nextCursor: null })));
      if (explicitConversationId && path === `/api/conversations/${explicitConversationId}/messages?limit=100`) return Promise.resolve(new Response(JSON.stringify({ messages: [], nextBeforeSequence: null })));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await screen.findByText("最近對話");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/settings/conversation", undefined));
    expect(window.location.hash).toBe(hash);
    expect(window.location.hash).not.toContain("c7d17356");
  });

  it("opens the most recently updated conversation when startup preference is recent", async () => {
    const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/conversation") return Promise.resolve(new Response(JSON.stringify({ startupView: "recent", sendBehavior: "enter", autoScroll: true })));
      if (path === "/api/settings/general") return Promise.resolve(new Response(JSON.stringify({ locale: "zh-TW", timeZone: "system" })));
      if (path === "/api/settings/ai") return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto" }, responseMode: "default" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/conversations?limit=50") return Promise.resolve(new Response(JSON.stringify({ conversations: [{ id: conversationId, title: "最近對話", latestMessagePreview: "最近內容", createdAt: "2026-08-22T08:00:00Z", updatedAt: "2026-08-22T08:30:00Z" }], nextCursor: null })));
      if (path === `/api/conversations/${conversationId}/messages?limit=100`) return Promise.resolve(new Response(JSON.stringify({ messages: [], nextBeforeSequence: null })));
      throw new Error(`unexpected request ${path} ${init?.method ?? "GET"}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await waitFor(() => expect(window.location.hash).toBe(`#chat=${conversationId}`));
    expect(screen.getByRole("heading", { level: 1, name: "最近對話" })).toBeTruthy();
  });

  it("renders backend conversations and uses only their UUID in the URL hash", async () => {
    const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
    const olderConversationId = "c7d17356-d2e6-4a5f-bbd7-7b5d6ac37875";
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/ai" && !init) return Promise.resolve(new Response(JSON.stringify({ model: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto" }, responseMode: "default" })));
      if (path === "/api/providers") return Promise.resolve(new Response(JSON.stringify(connectedOpenAi)));
      if (path === "/api/conversations?limit=50") return Promise.resolve(new Response(JSON.stringify({
        conversations: [{
          id: conversationId,
          title: "回顧進度",
          latestMessagePreview: "整理本週完成項目",
          createdAt: "2026-08-22T08:00:00Z",
          updatedAt: "2026-08-22T08:30:00Z",
        }],
        nextCursor: "older-cursor",
      })));
      if (path === "/api/conversations?limit=50&before=older-cursor") return Promise.resolve(new Response(JSON.stringify({
        conversations: [{
          id: olderConversationId,
          title: "較早的對話",
          latestMessagePreview: "舊內容",
          createdAt: "2026-08-01T08:00:00Z",
          updatedAt: "2026-08-01T08:30:00Z",
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

    fireEvent.click(screen.getByRole("button", { name: "載入更多對話" }));
    expect(await screen.findByRole("button", { name: "較早的對話" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "新對話" }));
    expect(window.location.hash).toBe("#new-chat");
    expect(screen.getByRole("heading", { level: 1, name: "新對話" })).toBeTruthy();
  });
});
