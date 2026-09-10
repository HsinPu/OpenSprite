import { fireEvent, render, screen, within } from "@testing-library/react";
import { useEffect } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GeneralSettings } from "../src/features/settings/GeneralSettings";
import { I18nProvider, useI18n } from "../src/i18n/I18nProvider";
import type { Locale } from "../src/i18n/catalog";
import type { GeneralSettingsController } from "../src/features/general-settings/useGeneralSettings";
import type { ConversationSettingsController } from "../src/features/conversation-settings/useConversationSettings";

const general: GeneralSettingsController = {
  settings: { locale: "zh-TW", timeZone: "system" }, loaded: true, saving: false, error: null,
  saveLocale: vi.fn(async () => null), saveTimeZone: vi.fn(async () => null), reload: vi.fn(async () => undefined),
};
const conversation: ConversationSettingsController = {
  settings: { startupView: "new", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: false },
  loaded: true, saving: false, error: null, saveStartupView: vi.fn(async () => null),
  saveSendBehavior: vi.fn(async () => null), saveAutoScroll: vi.fn(async () => null),
  saveExecutionPanelDefaultExpanded: vi.fn(async () => null), reload: vi.fn(async () => undefined),
};
function Localized({ locale }: { locale: Locale }) {
  const { setLocale } = useI18n();
  useEffect(() => setLocale(locale), [locale, setLocale]);
  return <GeneralSettings generalSettings={general} conversationSettings={conversation} />;
}
describe("general settings groups", () => {
  beforeEach(() => vi.clearAllMocks());
  it.each([
    ["zh-TW", "語言與時間", "對話偏好", "執行面板", "規劃中功能"],
    ["en", "Language and time", "Conversation preferences", "Execution panel", "Planned features"],
    ["ja", "言語と時間", "会話の設定", "実行パネル", "今後の機能"],
  ] as const)("shows all controls and collapsed plans in %s", (locale, language, preferences, panel, planned) => {
    render(<I18nProvider><Localized locale={locale} /></I18nProvider>);
    expect(screen.getAllByRole("heading").map(item => item.textContent)).toEqual([language, preferences, panel]);
    expect(screen.getAllByRole("combobox")).toHaveLength(4);
    expect(screen.getAllByRole("switch")).toHaveLength(2);
    expect(screen.getByRole("button", { name: planned }).getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: planned }));
    expect(general.saveLocale).not.toHaveBeenCalled();
    expect(conversation.saveStartupView).not.toHaveBeenCalled();
  });
  it("retains locale and timezone saves through Ant Design selects", () => {
    render(<GeneralSettings generalSettings={general} conversationSettings={conversation} />);
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "介面語言" }));
    fireEvent.click(screen.getByText("English"));
    expect(general.saveLocale).toHaveBeenCalledWith("en");
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "時區" }));
    fireEvent.click(screen.getByText("UTC"));
    expect(general.saveTimeZone).toHaveBeenCalledWith("UTC");
  });
  it("allows reload after initial failure and keeps the other settings group available", () => {
    render(<GeneralSettings generalSettings={{ ...general, loaded: false, error: "Cannot read language" }} conversationSettings={conversation} />);
    const error = screen.getByRole("alert");
    fireEvent.click(within(error).getByRole("button", { name: "重新讀取" }));
    expect(general.reload).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("combobox", { name: "介面語言" }).closest(".ant-select")?.classList.contains("ant-select-disabled")).toBe(true);
    expect(screen.getByRole("switch", { name: "自動捲動至最新訊息" }).getAttribute("disabled")).toBeNull();
  });
  it("shows one shared error for conversation and panel settings", () => {
    render(<GeneralSettings generalSettings={general} conversationSettings={{ ...conversation, loaded: false, error: "Cannot read conversation" }} />);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByText("對話偏好與執行面板設定發生問題")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "重新讀取" }));
    expect(conversation.reload).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("switch").every(item => item.hasAttribute("disabled"))).toBe(true);
  });
});
