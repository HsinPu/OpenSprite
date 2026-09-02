import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentChatApiError, agentChatErrorText } from "../src/api/agentChat";
import { AiSettingsApiError, aiSettingsErrorText } from "../src/api/aiSettings";
import { ProviderApiError, providerErrorText } from "../src/api/providerConnections";
import { GeneralSettings } from "../src/features/settings/GeneralSettings";
import { createTranslator } from "../src/i18n/catalog";
import { I18nProvider } from "../src/i18n/I18nProvider";
import { useGeneralSettings } from "../src/features/general-settings/useGeneralSettings";
import type { ConversationSettingsController } from "../src/features/conversation-settings/useConversationSettings";

const conversationSettings: ConversationSettingsController = {
  settings: { startupView: "new", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: false },
  loaded: true,
  saving: false,
  error: null,
  saveStartupView: async () => null,
  saveSendBehavior: async () => null,
  saveAutoScroll: async () => null,
  saveExecutionPanelDefaultExpanded: async () => null,
  reload: async () => undefined,
};

function GeneralSettingsHarness() {
  const generalSettings = useGeneralSettings();
  return <GeneralSettings generalSettings={generalSettings} conversationSettings={conversationSettings} />;
}

function I18nHarness() {
  return <I18nProvider><GeneralSettingsHarness /></I18nProvider>;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

describe("frontend internationalization", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.lang = "zh-TW";
  });

  it("persists confirmed language changes and updates the document language", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/general" && !init) return Promise.resolve(new Response(JSON.stringify({ locale: "zh-TW", timeZone: "system" })));
      if (path === "/api/settings/general" && init?.method === "PUT") return Promise.resolve(new Response(init.body));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nHarness />);

    await waitFor(() => expect((screen.getByRole("combobox", { name: "介面語言" }) as HTMLSelectElement).disabled).toBe(false));

    fireEvent.change(screen.getByRole("combobox", { name: "介面語言" }), { target: { value: "en" } });
    await waitFor(() => expect(document.documentElement.lang).toBe("en"));
    expect(screen.getByRole("region", { name: "Language and time" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Interface language" })).toBeTruthy();

    fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "ja" } });
    await waitFor(() => expect(document.documentElement.lang).toBe("ja"));
    expect(screen.getByRole("region", { name: "言語と時間" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "表示言語" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/general", expect.objectContaining({ method: "PUT" }));
  });

  it("saves the canonical IANA time-zone value from the General settings UI", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/general" && !init) return Promise.resolve(new Response(JSON.stringify({ locale: "zh-TW", timeZone: "system" })));
      if (path === "/api/settings/general" && init?.method === "PUT") return Promise.resolve(new Response(init.body));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nHarness />);

    const timeZone = await screen.findByRole("combobox", { name: "時區" });
    await waitFor(() => expect((timeZone as HTMLSelectElement).disabled).toBe(false));
    fireEvent.change(timeZone, { target: { value: "Asia/Taipei" } });

    await waitFor(() => expect((timeZone as HTMLSelectElement).value).toBe("Asia/Taipei"));
    expect(fetchMock).toHaveBeenCalledWith("/api/settings/general", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale: "zh-TW", timeZone: "Asia/Taipei" }),
    });
  });

  it("keeps the confirmed locale when persistence fails", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/general" && !init) return Promise.resolve(new Response(JSON.stringify({ locale: "zh-TW", timeZone: "system" })));
      if (path === "/api/settings/general" && init?.method === "PUT") return Promise.resolve(new Response(JSON.stringify({ error: { code: "settings_store_unavailable", message: "private", retryable: true } }), { status: 503 }));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nHarness />);

    const language = await screen.findByRole("combobox", { name: "介面語言" });
    await waitFor(() => expect((language as HTMLSelectElement).disabled).toBe(false));
    fireEvent.change(language, { target: { value: "en" } });

    expect((await screen.findByRole("alert")).textContent).toContain("語言與時區設定暫時無法讀取或儲存");
    expect((language as HTMLSelectElement).value).toBe("zh-TW");
    expect(document.documentElement.lang).toBe("zh-TW");
  });

  it("merges rapid locale and time-zone saves into one latest snapshot", async () => {
    const firstPut = deferred<Response>();
    const secondPut = deferred<Response>();
    const payloads: Array<Record<string, string>> = [];
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/settings/general" && !init) return Promise.resolve(new Response(JSON.stringify({ locale: "zh-TW", timeZone: "system" })));
      if (path === "/api/settings/general" && init?.method === "PUT") {
        const payload = JSON.parse(String(init.body)) as Record<string, string>;
        payloads.push(payload);
        return payloads.length === 1 ? firstPut.promise : secondPut.promise;
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nHarness />);

    const language = await screen.findByRole("combobox", { name: "介面語言" });
    const timeZone = screen.getByRole("combobox", { name: "時區" });
    await waitFor(() => expect((language as HTMLSelectElement).disabled).toBe(false));
    fireEvent.change(language, { target: { value: "en" } });
    fireEvent.change(timeZone, { target: { value: "UTC" } });

    await waitFor(() => expect(payloads).toHaveLength(1));
    expect(payloads[0]).toEqual({ locale: "en", timeZone: "system" });
    firstPut.resolve(new Response(JSON.stringify(payloads[0])));
    await waitFor(() => expect(payloads).toHaveLength(2));
    expect(payloads[1]).toEqual({ locale: "en", timeZone: "UTC" });
    secondPut.resolve(new Response(JSON.stringify(payloads[1])));

    await waitFor(() => {
      expect(document.documentElement.lang).toBe("en");
      expect((timeZone as HTMLSelectElement).value).toBe("UTC");
    });
  });

  it("retries an initial General settings load failure", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "settings_store_unavailable", message: "private", retryable: true } }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ locale: "zh-TW", timeZone: "UTC" })));
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nHarness />);

    expect((await screen.findByRole("alert")).textContent).toContain("語言與時區設定暫時無法讀取或儲存");
    fireEvent.click(screen.getByRole("button", { name: "重試" }));

    await waitFor(() => expect((screen.getByRole("combobox", { name: "時區" }) as HTMLSelectElement).value).toBe("UTC"));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("translates stable API error codes without exposing upstream detail", () => {
    const english = createTranslator("en");
    const japanese = createTranslator("ja");

    expect(providerErrorText(new ProviderApiError("invalid_credentials"), english)).toBe("The API key is invalid or expired.");
    expect(aiSettingsErrorText(new AiSettingsApiError("settings_store_unavailable"), japanese)).toBe("AI 設定を現在読み取りまたは保存できません。");
    expect(agentChatErrorText(new AgentChatApiError("database_unavailable"), english)).toBe("Local conversation data is temporarily unavailable.");
  });
});
