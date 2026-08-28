import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentChatApiError, agentChatErrorText } from "../src/api/agentChat";
import { AiSettingsApiError, aiSettingsErrorText } from "../src/api/aiSettings";
import { ProviderApiError, providerErrorText } from "../src/api/providerConnections";
import { GeneralSettings } from "../src/features/settings/GeneralSettings";
import { defaultDemoSettings, type DemoSettings } from "../src/features/settings/settingsState";
import { createTranslator } from "../src/i18n/catalog";
import { I18nProvider } from "../src/i18n/I18nProvider";
import { useGeneralSettings } from "../src/features/general-settings/useGeneralSettings";

function GeneralSettingsHarness() {
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);
  const generalSettings = useGeneralSettings();
  return (
    <GeneralSettings
      settings={settings}
      generalSettings={generalSettings}
      onChange={(key, value) => setSettings((current) => ({ ...current, [key]: value }))}
    />
  );
}

function I18nHarness() {
  return <I18nProvider><GeneralSettingsHarness /></I18nProvider>;
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
    expect(screen.getByRole("region", { name: "Language and region" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Interface language" })).toBeTruthy();

    fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "ja" } });
    await waitFor(() => expect(document.documentElement.lang).toBe("ja"));
    expect(screen.getByRole("region", { name: "言語と地域" })).toBeTruthy();
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

    const timeZone = await screen.findByRole("combobox", { name: "日期與時間" });
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

  it("retries an initial General settings load failure", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "settings_store_unavailable", message: "private", retryable: true } }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ locale: "zh-TW", timeZone: "UTC" })));
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nHarness />);

    expect((await screen.findByRole("alert")).textContent).toContain("語言與時區設定暫時無法讀取或儲存");
    fireEvent.click(screen.getByRole("button", { name: "重試" }));

    await waitFor(() => expect((screen.getByRole("combobox", { name: "日期與時間" }) as HTMLSelectElement).value).toBe("UTC"));
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
