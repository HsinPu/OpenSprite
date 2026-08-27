import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { AgentChatApiError, agentChatErrorText } from "../src/api/agentChat";
import { AiSettingsApiError, aiSettingsErrorText } from "../src/api/aiSettings";
import { ProviderApiError, providerErrorText } from "../src/api/providerConnections";
import { GeneralSettings } from "../src/features/settings/GeneralSettings";
import { defaultDemoSettings, type DemoSettings } from "../src/features/settings/settingsState";
import { createTranslator } from "../src/i18n/catalog";
import { I18nProvider } from "../src/i18n/I18nProvider";

function GeneralSettingsHarness() {
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);
  return (
    <I18nProvider>
      <GeneralSettings
        settings={settings}
        onChange={(key, value) => setSettings((current) => ({ ...current, [key]: value }))}
      />
    </I18nProvider>
  );
}

describe("frontend internationalization", () => {
  afterEach(() => {
    document.documentElement.lang = "zh-TW";
  });

  it("switches the visible general settings and document language without persistence", async () => {
    render(<GeneralSettingsHarness />);

    fireEvent.change(screen.getByRole("combobox", { name: "介面語言" }), { target: { value: "en" } });
    await waitFor(() => expect(document.documentElement.lang).toBe("en"));
    expect(screen.getByRole("region", { name: "Language and region" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Interface language" })).toBeTruthy();

    fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "ja" } });
    await waitFor(() => expect(document.documentElement.lang).toBe("ja"));
    expect(screen.getByRole("region", { name: "言語と地域" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "表示言語" })).toBeTruthy();
  });

  it("translates stable API error codes without exposing upstream detail", () => {
    const english = createTranslator("en");
    const japanese = createTranslator("ja");

    expect(providerErrorText(new ProviderApiError("invalid_credentials"), english)).toBe("The API key is invalid or expired.");
    expect(aiSettingsErrorText(new AiSettingsApiError("settings_store_unavailable"), japanese)).toBe("AI 設定を現在読み取りまたは保存できません。");
    expect(agentChatErrorText(new AgentChatApiError("database_unavailable"), english)).toBe("Local conversation data is temporarily unavailable.");
  });
});
