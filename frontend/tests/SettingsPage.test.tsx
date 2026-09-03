import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode, useState, type ComponentProps } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsPage as ProductionSettingsPage } from "../src/features/settings/SettingsPage";
import type { SettingsSection } from "../src/features/settings/settingsState";
import type { ResponseDelivery, ResponseMode } from "../src/api/aiSettings";
import { modelLabel, type ModelSelection } from "../src/features/ai-settings/modelCatalog";
import { useProviderCatalog } from "../src/features/ai-settings/useProviderCatalog";
import type { GeneralSettingsController } from "../src/features/general-settings/useGeneralSettings";
import type { ConversationSettingsController } from "../src/features/conversation-settings/useConversationSettings";
import type { ToolSettingsController } from "../src/features/tool-settings/useToolSettings";
import type { McpConnectionsController } from "../src/features/mcp-settings/useMcpConnections";

const generalSettings: GeneralSettingsController = {
  settings: { locale: "zh-TW", timeZone: "system" },
  loaded: true,
  saving: false,
  error: null,
  saveLocale: async () => null,
  saveTimeZone: async () => null,
  reload: async () => undefined,
};

const saveStartupView = vi.fn(async () => null);
const saveSendBehavior = vi.fn(async () => null);
const saveAutoScroll = vi.fn(async () => null);
const saveExecutionPanelDefaultExpanded = vi.fn(async () => null);
const conversationSettings: ConversationSettingsController = {
  settings: { startupView: "new", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: false },
  loaded: true,
  saving: false,
  error: null,
  saveStartupView,
  saveSendBehavior,
  saveAutoScroll,
  saveExecutionPanelDefaultExpanded,
  reload: async () => undefined,
};

const saveToolsEnabled = vi.fn(async () => null);
const saveToolEnabled = vi.fn(async () => null);
const toolSettings: ToolSettingsController = {
  catalog: { items: [{ id: "calculator", source: "builtin", effect: "read_only", available: true }] },
  settings: { enabled: true, enabledTools: ["calculator"] },
  loaded: true,
  saving: false,
  error: null,
  saveEnabled: saveToolsEnabled,
  saveToolEnabled,
  reload: async () => undefined,
};

const mcpConnections: McpConnectionsController = {
  servers: [], tools: {}, loaded: true, error: null, busyServerId: null,
  reload: async () => undefined, create: async () => null, update: async () => null,
  remove: async () => null, test: async () => null, start: async () => null,
  stop: async () => null, loadTools: async () => null,
};

function SettingsPage(props: Omit<ComponentProps<typeof ProductionSettingsPage>, "toolSettings" | "mcpConnections">) {
  return <ProductionSettingsPage {...props} toolSettings={toolSettings} mcpConnections={mcpConnections} />;
}

const disconnectedCatalog = {
  providers: [
    { id: "openai", name: "OpenAI", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
    { id: "anthropic", name: "Anthropic", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
    { id: "openrouter", name: "OpenRouter", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
  ],
};

const connectedCatalog = {
  providers: [
    { id: "openai", name: "OpenAI", connected: true, status: "connected", credentialPreview: "••••1234", lastCheckedAt: "2026-08-20T08:30:00Z" },
    disconnectedCatalog.providers[1],
    disconnectedCatalog.providers[2],
  ],
};

const connectedBothCatalog = {
  providers: [
    connectedCatalog.providers[0],
    { id: "anthropic", name: "Anthropic", connected: true, status: "connected", credentialPreview: "••••5678", lastCheckedAt: "2026-08-20T08:30:00Z" },
    disconnectedCatalog.providers[2],
  ],
};

const connectedOpenRouterCatalog = {
  providers: [
    disconnectedCatalog.providers[0],
    disconnectedCatalog.providers[1],
    { id: "openrouter", name: "OpenRouter", connected: true, status: "connected", credentialPreview: "••••9999", lastCheckedAt: "2026-08-20T08:30:00Z" },
  ],
};

const connectedOpenAiAndOpenRouterCatalog = {
  providers: [
    connectedCatalog.providers[0],
    disconnectedCatalog.providers[1],
    connectedOpenRouterCatalog.providers[2],
  ],
};

const dynamicModel = (id: string, name: string) => ({
  id,
  name,
  contextWindowTokens: 131_072,
  maxOutputTokens: 8_192,
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function SettingsHarness({ initialSelection = { providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto", outputBudget: "auto" }, aiSettingsLoaded = true }: { initialSelection?: ModelSelection | null; aiSettingsLoaded?: boolean }) {
  const [selection, setSelection] = useState<ModelSelection | null>(initialSelection);
  const [responseMode, setResponseMode] = useState<ResponseMode>("default");
  const [responseDelivery, setResponseDelivery] = useState<ResponseDelivery>("stream");
  const [outputContinuation, setOutputContinuation] = useState<"off" | "1" | "2" | "3" | "5" | "10" | "20" | "50" | "unlimited">("5");
  const providerCatalog = useProviderCatalog();
  return <><SettingsPage section="models" onSectionChange={() => undefined} modelSelection={selection} responseMode={responseMode} outputContinuation={outputContinuation} responseDelivery={responseDelivery} logFullPrompts={false} aiSettingsLoaded={aiSettingsLoaded} aiSettingsSaving={false} aiSettingsError={null} onAiSettingsReload={async () => undefined} onModelSelectionChange={async (next) => { setSelection(next); return null; }} onResponseModeChange={async (next) => { setResponseMode(next); return null; }} onOutputContinuationChange={async (next) => { setOutputContinuation(next); return null; }} onResponseDeliveryChange={async (next) => { setResponseDelivery(next); return null; }} onLogFullPromptsChange={async () => null} providerCatalog={providerCatalog} generalSettings={generalSettings} conversationSettings={conversationSettings} onClose={() => undefined} /><output data-testid="selected-model">{modelLabel(selection, providerCatalog.modelChoices.filter((choice) => choice.selection.providerId === "openrouter").map((choice) => ({ id: choice.selection.modelId, label: choice.label })))}</output><output data-testid="selected-output">{selection?.outputBudget ?? "none"}</output><output data-testid="output-continuation">{outputContinuation}</output><output data-testid="response-delivery">{responseDelivery}</output></>;
}

function GuardedDialogHarness() {
  const [selection, setSelection] = useState<ModelSelection | null>({ providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto", outputBudget: "auto" });
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const providerCatalog = useProviderCatalog();
  return <dialog open onCancel={(event) => { if (providerModalOpen) event.preventDefault(); }}><SettingsPage section="models" onSectionChange={() => undefined} modelSelection={selection} responseMode="balanced" outputContinuation="2" responseDelivery="stream" logFullPrompts={false} aiSettingsLoaded aiSettingsSaving={false} aiSettingsError={null} onAiSettingsReload={async () => undefined} onModelSelectionChange={async (next) => { setSelection(next); return null; }} onResponseModeChange={async () => null} onOutputContinuationChange={async () => null} onResponseDeliveryChange={async () => null} onLogFullPromptsChange={async () => null} providerCatalog={providerCatalog} generalSettings={generalSettings} conversationSettings={conversationSettings} onClose={() => undefined} onProviderModalChange={setProviderModalOpen} /></dialog>;
}

function ToggleSectionHarness() {
  const [selection, setSelection] = useState<ModelSelection | null>({ providerId: "openrouter", modelId: "missing", contextBudget: "auto", outputBudget: "auto" });
  const [section, setSection] = useState<SettingsSection>("models");
  const providerCatalog = useProviderCatalog();
  return <><button type="button" onClick={() => setSection("general")}>show general</button><button type="button" onClick={() => setSection("models")}>show models</button><SettingsPage section={section} onSectionChange={setSection} modelSelection={selection} responseMode="balanced" outputContinuation="2" responseDelivery="stream" logFullPrompts={false} aiSettingsLoaded aiSettingsSaving={false} aiSettingsError={null} onAiSettingsReload={async () => undefined} onModelSelectionChange={async (next) => { setSelection(next); return null; }} onResponseModeChange={async () => null} onOutputContinuationChange={async () => null} onResponseDeliveryChange={async () => null} onLogFullPromptsChange={async () => null} providerCatalog={providerCatalog} generalSettings={generalSettings} conversationSettings={conversationSettings} onClose={() => undefined} /></>;
}

function GeneralSettingsPageHarness({ saving = false, section = "general" }: { saving?: boolean; section?: SettingsSection }) {
  const providerCatalog = useProviderCatalog();
  return <SettingsPage section={section} onSectionChange={() => undefined} modelSelection={null} responseMode="default" outputContinuation="2" responseDelivery="stream" logFullPrompts={false} aiSettingsLoaded aiSettingsSaving={false} aiSettingsError={null} onAiSettingsReload={async () => undefined} onModelSelectionChange={async () => null} onResponseModeChange={async () => null} onOutputContinuationChange={async () => null} onResponseDeliveryChange={async () => null} onLogFullPromptsChange={async () => null} providerCatalog={providerCatalog} generalSettings={{ ...generalSettings, saving }} conversationSettings={conversationSettings} onClose={() => undefined} />;
}

describe("provider settings", () => {
  it("changes and explains the selected model context budget", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(connectedCatalog))));
    render(<SettingsHarness initialSelection={{ providerId: "openai", modelId: "gpt-5.6", contextBudget: "128k", outputBudget: "auto" }} />);

    expect(await screen.findByText("模型支援上限：1.05M · 目前使用上限：128K")).toBeTruthy();
    expect(screen.getByText("模型輸出上限：125K · 本次最高：32K")).toBeTruthy();
    const contextSelect = screen.getByLabelText("對話內容上限");
    fireEvent.mouseDown(contextSelect);
    const option = await screen.findByText("256K");
    fireEvent.click(option.closest(".ant-select-item-option")!);

    await waitFor(() => expect(screen.getByText("模型支援上限：1.05M · 目前使用上限：256K")).toBeTruthy());
  });

  it("returns an unavailable output budget to auto when Context changes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(connectedCatalog))));
    render(<SettingsHarness initialSelection={{ providerId: "openai", modelId: "gpt-5.6", contextBudget: "128k", outputBudget: "64k" }} />);

    await screen.findByText("模型輸出上限：125K · 本次最高：64K");
    const contextSelect = screen.getByLabelText("對話內容上限");
    fireEvent.mouseDown(contextSelect);
    fireEvent.click((await screen.findByText("32K")).closest(".ant-select-item-option")!);

    await waitFor(() => expect(screen.getByText("模型輸出上限：125K · 本次最高：8K")).toBeTruthy());
  });

  it("returns to auto when refreshed model capability lowers the output maximum", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenRouterCatalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [dynamicModel("acme/fast", "Acme Fast")] })));
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness initialSelection={{ providerId: "openrouter", modelId: "acme/fast", contextBudget: "128k", outputBudget: "64k" }} />);

    await waitFor(() => expect(screen.getByTestId("selected-output").textContent).toBe("auto"));
    expect(screen.getByText("模型輸出上限：8K · 本次最高：8K")).toBeTruthy();
  });

  beforeEach(() => {
    vi.unstubAllGlobals();
    saveStartupView.mockClear();
    saveSendBehavior.mockClear();
    saveAutoScroll.mockClear();
    saveExecutionPanelDefaultExpanded.mockClear();
    saveToolsEnabled.mockClear();
    saveToolEnabled.mockClear();
  });

  it("presents provider default plus the three explicit response modes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(disconnectedCatalog))));
    render(<SettingsHarness />);

    const group = screen.getByRole("group", { name: "回應模式" });
    expect(within(group).getByRole("button", { name: "預設" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(within(group).getByRole("button", { name: "深入" }));
    await waitFor(() => expect(within(group).getByRole("button", { name: "深入" }).getAttribute("aria-pressed")).toBe("true"));
  });

  it("keeps AI settings controls disabled until the initial settings load finishes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(connectedCatalog))));
    render(<SettingsHarness aiSettingsLoaded={false} />);

    expect(await screen.findByText("正在讀取 AI 設定…")).toBeTruthy();
    const responseModes = screen.getByRole("group", { name: "回應模式" });
    expect(responseModes.querySelectorAll("button:not(:disabled)")).toHaveLength(0);
    expect(screen.getByRole("combobox", { name: "回覆顯示方式" }).closest(".ant-select")?.classList.contains("ant-select-disabled")).toBe(true);
    expect(screen.getByRole("combobox", { name: "自動續接過長回覆" }).closest(".ant-select")?.classList.contains("ant-select-disabled")).toBe(true);
    expect(screen.getByRole("switch", { name: "記錄完整送出 Prompt" }).classList.contains("ant-switch-disabled")).toBe(true);
  });

  it("selects stream or complete response delivery", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(disconnectedCatalog))));
    render(<SettingsHarness />);

    const select = await screen.findByRole("combobox", { name: "回覆顯示方式" });
    expect(select.parentElement?.textContent).toContain("串流");
    fireEvent.mouseDown(select);
    expect(screen.getByText("一次回答").closest(".ant-select-item-option")).toBeTruthy();
    fireEvent.click(screen.getByText("一次回答").closest(".ant-select-item-option")!);

    await waitFor(() => expect(screen.getByTestId("response-delivery").textContent).toBe("complete"));
    expect(screen.getByText("等待本次回答完成後一次顯示")).toBeTruthy();
  });

  it("selects bounded or unlimited output continuation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(connectedCatalog))));
    render(<SettingsHarness />);

    const select = await screen.findByRole("combobox", { name: "自動續接過長回覆" });
    fireEvent.mouseDown(select);
    expect((await screen.findAllByText("5 次（預設）")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("10 次")).toBeTruthy();
    expect(screen.getByText("20 次")).toBeTruthy();
    expect(screen.getByText("50 次")).toBeTruthy();
    fireEvent.click(screen.getByText("不限制").closest(".ant-select-item-option")!);

    await waitFor(() => expect(screen.getByTestId("output-continuation").textContent).toBe("unlimited"));
    expect(screen.getByText("持續續接直到完成；仍受 Context、字數與安全上限保護")).toBeTruthy();
  });

  it("shows speculative model preferences as non-interactive future items", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(disconnectedCatalog))));
    render(<SettingsHarness />);

    expect(screen.getAllByText("未來上線")).toHaveLength(2);
    expect(screen.getByText("自動選擇可用模型")).toBeTruthy();
    expect(screen.getByText("顯示模型名稱")).toBeTruthy();
    expect(screen.queryByRole("checkbox", { name: "自動選擇可用模型" })).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "顯示模型名稱" })).toBeNull();
    await waitFor(() => expect((screen.getAllByRole("button", { name: "連接" })[0] as HTMLButtonElement).disabled).toBe(false));
  });

  it("shows the planned settings inventory without fake controls", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    render(<GeneralSettingsPageHarness />);

    const categoryRail = screen.getByRole("navigation", { name: "設定分類" });
    expect(within(categoryRail).getAllByRole("button").map((button) => button.textContent)).toEqual(["一般", "AI 模型", "記憶與資料Demo", "工具", "外觀Demo", "隱私", "關於"]);
    expect(screen.getByRole("region", { name: "語言與時間" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "時區" })).toBeTruthy();
    expect(screen.getAllByText("Demo")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "啟動與對話" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "通知" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "啟動時開啟" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "訊息傳送方式" })).toBeTruthy();
    const autoScroll = screen.getByRole("switch", { name: "自動捲動至最新訊息" });
    const executionPanel = screen.getByRole("switch", { name: "預設展開執行資訊" });
    expect(autoScroll.getAttribute("aria-checked")).toBe("true");
    expect(executionPanel.getAttribute("aria-checked")).toBe("false");
    expect(screen.getAllByText("未來上線")).toHaveLength(1);
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByText("已儲存")).toBeNull();
    fireEvent.change(screen.getByRole("combobox", { name: "啟動時開啟" }), { target: { value: "recent" } });
    fireEvent.change(screen.getByRole("combobox", { name: "訊息傳送方式" }), { target: { value: "modifier-enter" } });
    fireEvent.click(autoScroll);
    fireEvent.click(executionPanel);
    expect(saveStartupView).toHaveBeenCalledWith("recent");
    expect(saveSendBehavior).toHaveBeenCalledWith("modifier-enter");
    expect(saveAutoScroll).toHaveBeenCalledWith(false);
    expect(saveExecutionPanelDefaultExpanded).toHaveBeenCalledWith(true);
  });

  it("shows save progress and hides the completed receipt after two seconds", () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    try {
      const { rerender } = render(<GeneralSettingsPageHarness />);
      rerender(<GeneralSettingsPageHarness saving />);
      expect(screen.getByText("儲存中…")).toBeTruthy();

      rerender(<GeneralSettingsPageHarness />);
      expect(screen.getByText("已儲存")).toBeTruthy();
      act(() => vi.advanceTimersByTime(2001));
      expect(screen.queryByText("已儲存")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows the real tool controls and keeps external tools as future items", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    render(<GeneralSettingsPageHarness section="tools" />);

    expect(screen.getByRole("heading", { name: "工具" })).toBeTruthy();
    const globalSwitch = screen.getByRole("switch", { name: "允許 AI 使用工具" });
    const calculatorSwitch = screen.getByRole("switch", { name: "啟用工具：計算器" });
    expect(globalSwitch.getAttribute("aria-checked")).toBe("true");
    expect(calculatorSwitch.getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("內建 · 唯讀")).toBeTruthy();
    expect(screen.getByText("可使用")).toBeTruthy();
    expect(screen.getAllByText("未來上線")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "MCP Server" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "新增 MCP Server" })).toBeTruthy();
    expect(screen.getByText("自訂工具")).toBeTruthy();
    expect(screen.getByText("第三方服務")).toBeTruthy();

    fireEvent.click(globalSwitch);
    fireEvent.click(calculatorSwitch);
    expect(saveToolsEnabled).toHaveBeenCalledWith(false);
    expect(saveToolEnabled).toHaveBeenCalledWith("calculator", false);
  });

  it("keeps the MCP transport dropdown inside the settings surface and accepts pointer selection", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    render(<GeneralSettingsPageHarness section="tools" />);

    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));
    const transport = await screen.findByRole("combobox", { name: "連線方式" });
    fireEvent.mouseDown(transport);
    const option = (await screen.findByText("網路位址")).closest(".ant-select-item-option")!;
    expect(document.querySelector(".settings-page")?.contains(option)).toBe(true);
    fireEvent.click(option);

    expect(await screen.findByLabelText("MCP Endpoint URL")).toBeTruthy();
    expect(screen.queryByLabelText("Executable 絕對路徑")).toBeNull();
  });

  it("renders OpenRouter as the third provider with the OR badge and normal connection actions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(disconnectedCatalog))));
    render(<SettingsHarness />);

    const card = await screen.findByLabelText("OpenRouter 連線");
    expect(within(card).getByText("OR")).toBeTruthy();
    expect((within(card).getByRole("button", { name: "連接" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("chooses the first connected static model when no saved selection exists", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(connectedCatalog))));
    render(<SettingsHarness initialSelection={null} />);

    await waitFor(() => expect(screen.getByTestId("selected-model").textContent).toBe("GPT-5.6"));
  });

  it("shows a safe catalog error and retries the initial GET", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "credential_store_unavailable", message: "private server text", retryable: true } }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(disconnectedCatalog)));
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness />);

    expect((await screen.findByRole("alert")).textContent).toContain("安全憑證儲存服務暫時無法使用。");
    expect(screen.queryByText("private server text")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "重試" }));
    await screen.findByText("OpenAI");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("connects through an accessible password modal and clears the API key after errors and success", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(disconnectedCatalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "invalid_credentials", message: "secret-from-server", retryable: false } }), { status: 422 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedCatalog.providers[0])));
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness />);
    await screen.findByText("OpenAI");
    fireEvent.click(screen.getAllByRole("button", { name: "連接" })[0]);
    const keyInput = await screen.findByLabelText("API 金鑰");

    fireEvent.change(keyInput, { target: { value: "top-secret-key" } });
    fireEvent.submit(keyInput.closest("form")!);
    expect((await screen.findByRole("alert")).textContent).toContain("API 金鑰無效或已失效。");
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.queryByText("OpenAI：API 金鑰無效或已失效。")).toBeNull();
    expect(screen.queryByText("OpenAI 正在驗證並儲存連線。")).toBeNull();
    expect((keyInput as HTMLInputElement).value).toBe("");
    expect(document.body.textContent).not.toContain("top-secret-key");

    fireEvent.change(keyInput, { target: { value: "replacement-key" } });
    fireEvent.submit(keyInput.closest("form")!);
    await screen.findByText("OpenAI 已連線。");
    await waitFor(() => expect(screen.queryByLabelText("API 金鑰")).toBeNull());
    expect(document.body.textContent).not.toContain("replacement-key");
  });

  it("refreshes persisted status after a failed connection test and keeps unavailable models disabled", async () => {
    const checkedFailure = { providers: [{ ...connectedCatalog.providers[0], status: "invalid_credentials" }, disconnectedCatalog.providers[1], disconnectedCatalog.providers[2]] };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedCatalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "invalid_credentials", message: "never render", retryable: false } }), { status: 422 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(checkedFailure)));
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness />);
    await screen.findAllByText("測試連線");
    fireEvent.click(screen.getByRole("button", { name: "測試連線" }));
    expect(await screen.findByText("API 金鑰無效")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect((screen.getByLabelText("模型") as HTMLInputElement).closest(".ant-select")?.className).not.toContain("ant-select-disabled");
    fireEvent.mouseDown(screen.getByLabelText("模型"));
    expect(screen.queryByText("Claude Sonnet 4.6")).toBeNull();
  });

  it("keeps per-provider operations independent and ignores a stale failed-test refresh", async () => {
    const openAiTest = deferred<Response>();
    const anthropicTest = deferred<Response>();
    const staleOpenAiRefresh = deferred<Response>();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedBothCatalog)))
      .mockImplementationOnce(() => openAiTest.promise)
      .mockImplementationOnce(() => anthropicTest.promise)
      .mockImplementationOnce(() => staleOpenAiRefresh.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness />);

    await screen.findAllByText("測試連線");
    const openAiActions = screen.getByRole("group", { name: "OpenAI 操作" });
    const anthropicActions = screen.getByRole("group", { name: "Anthropic 操作" });
    fireEvent.click(within(openAiActions).getByRole("button", { name: "測試連線" }));
    fireEvent.click(within(openAiActions).getByRole("button", { name: "處理中…" }));
    fireEvent.click(within(anthropicActions).getByRole("button", { name: "測試連線" }));

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(openAiActions.getAttribute("aria-busy")).toBe("true");
    expect(anthropicActions.getAttribute("aria-busy")).toBe("true");
    expect(screen.getAllByText("OpenAI 正在測試連線。")).toHaveLength(1);
    expect(document.querySelector(".settings-provider-announcement")?.getAttribute("aria-atomic")).toBeNull();

    anthropicTest.resolve(new Response(JSON.stringify({ ...connectedBothCatalog.providers[1], credentialPreview: "••••9999" })));
    await screen.findByText("••••9999");
    expect(anthropicActions.getAttribute("aria-busy")).toBe("false");

    openAiTest.resolve(new Response(JSON.stringify({ error: { code: "invalid_credentials", message: "private", retryable: false } }), { status: 422 }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    staleOpenAiRefresh.resolve(new Response(JSON.stringify({ providers: [
      { ...connectedBothCatalog.providers[0], status: "invalid_credentials" },
      connectedBothCatalog.providers[1],
      connectedBothCatalog.providers[2],
    ] })));

    await screen.findByText("API 金鑰無效");
    expect(screen.getByText("••••9999")).toBeTruthy();
    expect(openAiActions.getAttribute("aria-busy")).toBe("false");
  });

  it("keeps the password dialog in its settings container, blocks duplicate submits and clears a failed secret", async () => {
    const put = deferred<Response>();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(disconnectedCatalog)))
      .mockImplementationOnce(() => put.promise);
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(<GuardedDialogHarness />);

    await screen.findByText("OpenAI");
    fireEvent.click(screen.getAllByRole("button", { name: "連接" })[0]);
    const keyInput = await screen.findByLabelText("API 金鑰");
    const form = keyInput.closest("form")!;
    const nativeDialog = container.querySelector("dialog")!;
    expect(nativeDialog.contains(document.querySelector(".provider-connection-modal"))).toBe(true);
    fireEvent.change(keyInput, { target: { value: "top-secret-key" } });
    fireEvent.submit(form);
    fireEvent.submit(form);
    fireEvent.keyDown(keyInput, { key: "Escape" });
    const cancel = new Event("cancel", { cancelable: true });
    nativeDialog.dispatchEvent(cancel);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(cancel.defaultPrevented).toBe(true);
    expect(screen.getByLabelText("API 金鑰")).toBeTruthy();
    put.resolve(new Response(JSON.stringify({ error: { code: "invalid_credentials", message: "private", retryable: false } }), { status: 422 }));

    const alert = await screen.findByRole("alert");
    expect(alert.getAttribute("id")).toBe("provider-key-error");
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(keyInput.getAttribute("aria-invalid")).toBe("true");
    expect(keyInput.getAttribute("aria-errormessage")).toBe("provider-key-error");
    expect(screen.queryByText("OpenAI：API 金鑰無效或已失效。")).toBeNull();
    expect(screen.queryByText("OpenAI 正在驗證並儲存連線。")).toBeNull();
    expect((keyInput as HTMLInputElement).value).toBe("");
    expect(document.body.textContent).not.toContain("top-secret-key");
  });

  it("clears a cancelled password value without issuing a request", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(disconnectedCatalog))));
    render(<SettingsHarness />);
    await screen.findByText("OpenAI");
    fireEvent.click(screen.getAllByRole("button", { name: "連接" })[0]);
    const keyInput = await screen.findByLabelText("API 金鑰");
    fireEvent.change(keyInput, { target: { value: "cancel-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(screen.queryByLabelText("API 金鑰")).toBeNull());
    expect(document.body.textContent).not.toContain("cancel-secret");
  });

  it("associates both model selects with their stable helper text", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(disconnectedCatalog))));
    render(<SettingsHarness />);
    await screen.findByText("OpenAI");
    expect(document.getElementById("settings-model-provider")?.getAttribute("aria-describedby")).toBe("settings-model-helper");
    expect(document.getElementById("settings-default-model")?.getAttribute("aria-describedby")).toBe("settings-model-helper");
  });

  it("shows the sole connected OpenRouter provider while its dynamic models load", async () => {
    const pendingModels = deferred<Response>();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenRouterCatalog)))
      .mockImplementationOnce(() => pendingModels.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness initialSelection={null} />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(document.getElementById("settings-model-provider")?.closest(".ant-select")?.textContent).toContain("OpenRouter");
    expect(screen.getByText("正在讀取 OpenRouter 可用模型…")).toBeTruthy();
    expect(screen.getByLabelText("模型").closest(".ant-select")?.className).toContain("ant-select-disabled");

    pendingModels.resolve(new Response(JSON.stringify({ models: [dynamicModel("acme/fast", "Acme Fast")] })));
    const modelSelect = screen.getByLabelText("模型");
    await waitFor(() => expect(modelSelect.closest(".ant-select")?.className).not.toContain("ant-select-disabled"));
    fireEvent.mouseDown(modelSelect);
    expect((await screen.findAllByText("Acme Fast")).length).toBeGreaterThan(0);
  });

  it("accepts OpenRouter models after the StrictMode remount simulation", async () => {
    const fetchMock = vi.fn(async (path: string | URL | Request) => {
      if (path === "/api/providers") return new Response(JSON.stringify(connectedOpenRouterCatalog));
      if (path === "/api/providers/openrouter/models") {
        return new Response(JSON.stringify({ models: [dynamicModel("acme/fast", "Acme Fast")] }));
      }
      throw new Error(`Unexpected request: ${String(path)}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<StrictMode><SettingsHarness initialSelection={null} /></StrictMode>);

    const modelSelect = await screen.findByLabelText("模型");
    await waitFor(() => expect(modelSelect.closest(".ant-select")?.className).not.toContain("ant-select-disabled"));
    expect(screen.queryByText("正在讀取 OpenRouter 可用模型…")).toBeNull();
  });

  it("renders provider and model popup menus inside the settings surface", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenRouterCatalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [
        dynamicModel("acme/fast", "Acme Fast"),
        dynamicModel("acme/reasoning", "Acme Reasoning"),
      ] })));
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(<SettingsHarness initialSelection={{ providerId: "openrouter", modelId: "acme/fast", contextBudget: "auto", outputBudget: "auto" }} />);

    const settingsSurface = container.querySelector(".settings-page")!;
    const providerSelect = document.getElementById("settings-model-provider")!;
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    fireEvent.mouseDown(providerSelect);
    const providerOption = await screen.findByRole("option", { name: "OpenRouter" });
    expect(settingsSurface.contains(providerOption)).toBe(true);
    fireEvent.keyDown(providerSelect, { key: "Escape" });

    const modelSelect = screen.getByLabelText("模型");
    fireEvent.mouseDown(modelSelect);
    const modelOptionLabel = await screen.findByText("Acme Reasoning");
    const modelDropdown = modelOptionLabel.closest(".ant-select-dropdown");
    expect(modelDropdown).toBeTruthy();
    expect(settingsSurface.contains(modelDropdown)).toBe(true);
  });

  it("loads connected OpenRouter models once, exposes a searchable selection, and retries an isolated catalog error", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenRouterCatalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "provider_timeout", message: "private", retryable: true } }), { status: 504 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [dynamicModel("acme/fast", "Acme Fast"), dynamicModel("acme/reasoning", "Acme Reasoning")] })));
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness initialSelection={{ providerId: "openrouter", modelId: "missing", contextBudget: "auto", outputBudget: "auto" }} />);

    expect((await screen.findByRole("alert")).textContent).toContain("模型廠家回應逾時");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("selected-model").textContent).toBe("missing");
    fireEvent.click(screen.getByRole("button", { name: "重試讀取模型" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    await waitFor(() => expect(screen.getByTestId("selected-model").textContent).toBe("Acme Fast"));
    const modelSelect = screen.getByLabelText("模型");
    fireEvent.mouseDown(modelSelect);
    fireEvent.change(modelSelect, { target: { value: "Reasoning" } });
    await waitFor(() => expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["acme/reasoning"]));
    fireEvent.change(modelSelect, { target: { value: "acme\/fast" } });
    await waitFor(() => expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["acme/fast"]));
  });

  it("keeps an OpenRouter selection on catalog failure while an OpenAI picker stays available during loading", async () => {
    const pendingModels = deferred<Response>();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenAiAndOpenRouterCatalog)))
      .mockImplementationOnce(() => pendingModels.promise);
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness initialSelection={{ providerId: "openai", modelId: "gpt-5.6", contextBudget: "auto", outputBudget: "auto" }} />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("模型").closest(".ant-select")?.className).not.toContain("ant-select-disabled");
    pendingModels.resolve(new Response(JSON.stringify({ error: { code: "provider_timeout", message: "private", retryable: true } }), { status: 504 }));
    await screen.findByRole("alert");
    expect(screen.getByTestId("selected-model").textContent).toBe("GPT-5.6");
  });

  it("keeps the OpenRouter catalog cache across a general/models section toggle", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenRouterCatalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [dynamicModel("acme/fast", "Acme Fast")] })));
    vi.stubGlobal("fetch", fetchMock);
    render(<ToggleSectionHarness />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByLabelText("模型").closest(".ant-select")?.className).not.toContain("ant-select-disabled"));
    fireEvent.click(screen.getByRole("button", { name: "show general" }));
    fireEvent.click(screen.getByRole("button", { name: "show models" }));
    expect(fetchMock.mock.calls.filter(([path]) => path === "/api/providers/openrouter/models")).toHaveLength(1);
  });

  it("ignores a stale OpenRouter model response after disconnect and falls back to OpenAI", async () => {
    const pendingModels = deferred<Response>();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenAiAndOpenRouterCatalog)))
      .mockImplementationOnce(() => pendingModels.promise)
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness initialSelection={{ providerId: "openrouter", modelId: "old/model", contextBudget: "auto", outputBudget: "auto" }} />);

    const openRouterActions = await screen.findByRole("group", { name: "OpenRouter 操作" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    fireEvent.click(within(openRouterActions).getByRole("button", { name: "移除" }));
    const confirmation = await screen.findByText("移除 OpenRouter 的已儲存 API 金鑰？");
    const popover = confirmation.closest(".ant-popover")!;
    expect(document.querySelector(".settings-page")?.contains(popover)).toBe(true);
    fireEvent.click(within(popover as HTMLElement).getByRole("button", { name: /移\s*除/ }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(screen.getByTestId("selected-model").textContent).toBe("GPT-5.6"));

    pendingModels.resolve(new Response(JSON.stringify({ models: [dynamicModel("stale/model", "Stale model")] })));
    await waitFor(() => expect(screen.queryByText("Stale model")).toBeNull());
    expect(screen.getByTestId("selected-model").textContent).toBe("GPT-5.6");
  });

});
