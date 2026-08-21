import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode, useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { defaultDemoSettings, SettingsPage, type DemoSettings, type SettingsSection } from "../src/features/settings/SettingsPage";
import { modelLabel, type ModelSelection } from "../src/features/settings/modelCatalog";

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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function SettingsHarness({ initialSettings = defaultDemoSettings, initialSelection = { providerId: "openai", modelId: "gpt-5.6" } }: { initialSettings?: DemoSettings; initialSelection?: ModelSelection | null }) {
  const [settings, setSettings] = useState<DemoSettings>(initialSettings);
  const [selection, setSelection] = useState<ModelSelection | null>(initialSelection);
  const [choices, setChoices] = useState<ReadonlyArray<{ selection: ModelSelection; label: string }>>([]);
  return <><SettingsPage section="models" onSectionChange={() => undefined} settings={settings} onSettingsChange={setSettings} modelSelection={selection} modelSelectionSaving={false} modelSelectionError={null} onModelSelectionChange={async (next) => { setSelection(next); return null; }} onModelChoicesChange={setChoices} onClose={() => undefined} /><output data-testid="selected-model">{modelLabel(selection, choices.filter((choice) => choice.selection.providerId === "openrouter").map((choice) => ({ id: choice.selection.modelId, label: choice.label })))}</output></>;
}

function GuardedDialogHarness() {
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);
  const [selection, setSelection] = useState<ModelSelection | null>({ providerId: "openai", modelId: "gpt-5.6" });
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  return <dialog open onCancel={(event) => { if (providerModalOpen) event.preventDefault(); }}><SettingsPage section="models" onSectionChange={() => undefined} settings={settings} onSettingsChange={setSettings} modelSelection={selection} modelSelectionSaving={false} modelSelectionError={null} onModelSelectionChange={async (next) => { setSelection(next); return null; }} onModelChoicesChange={() => undefined} onClose={() => undefined} onProviderModalChange={setProviderModalOpen} /></dialog>;
}

function ToggleSectionHarness() {
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);
  const [selection, setSelection] = useState<ModelSelection | null>({ providerId: "openrouter", modelId: "missing" });
  const [section, setSection] = useState<SettingsSection>("models");
  return <><button type="button" onClick={() => setSection("general")}>show general</button><button type="button" onClick={() => setSection("models")}>show models</button><SettingsPage section={section} onSectionChange={setSection} settings={settings} onSettingsChange={setSettings} modelSelection={selection} modelSelectionSaving={false} modelSelectionError={null} onModelSelectionChange={async (next) => { setSelection(next); return null; }} onModelChoicesChange={() => undefined} onClose={() => undefined} /></>;
}

describe("provider settings", () => {
  beforeEach(() => vi.unstubAllGlobals());

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
    expect(screen.queryByText("Claude Sonnet 4")).toBeNull();
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

    pendingModels.resolve(new Response(JSON.stringify({ models: [{ id: "acme/fast", name: "Acme Fast" }] })));
    const modelSelect = screen.getByLabelText("模型");
    await waitFor(() => expect(modelSelect.closest(".ant-select")?.className).not.toContain("ant-select-disabled"));
    fireEvent.mouseDown(modelSelect);
    expect(await screen.findByText("Acme Fast")).toBeTruthy();
  });

  it("accepts OpenRouter models after the StrictMode remount simulation", async () => {
    const fetchMock = vi.fn(async (path: string | URL | Request) => {
      if (path === "/api/providers") return new Response(JSON.stringify(connectedOpenRouterCatalog));
      if (path === "/api/providers/openrouter/models") {
        return new Response(JSON.stringify({ models: [{ id: "acme/fast", name: "Acme Fast" }] }));
      }
      throw new Error(`Unexpected request: ${String(path)}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<StrictMode><SettingsHarness initialSelection={null} /></StrictMode>);

    const modelSelect = await screen.findByLabelText("模型");
    await waitFor(() => expect(modelSelect.closest(".ant-select")?.className).not.toContain("ant-select-disabled"));
    expect(screen.queryByText("正在讀取 OpenRouter 可用模型…")).toBeNull();
  });

  it("loads connected OpenRouter models once, exposes a searchable selection, and retries an isolated catalog error", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenRouterCatalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "provider_timeout", message: "private", retryable: true } }), { status: 504 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [{ id: "acme/fast", name: "Acme Fast" }, { id: "acme/reasoning", name: "Acme Reasoning" }] })));
    vi.stubGlobal("fetch", fetchMock);
    render(<SettingsHarness initialSelection={{ providerId: "openrouter", modelId: "missing" }} />);

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
    render(<SettingsHarness initialSelection={{ providerId: "openai", modelId: "gpt-5.6" }} />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("模型").closest(".ant-select")?.className).not.toContain("ant-select-disabled");
    pendingModels.resolve(new Response(JSON.stringify({ error: { code: "provider_timeout", message: "private", retryable: true } }), { status: 504 }));
    await screen.findByRole("alert");
    expect(screen.getByTestId("selected-model").textContent).toBe("GPT-5.6");
  });

  it("keeps the OpenRouter catalog cache across a general/models section toggle", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(connectedOpenRouterCatalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [{ id: "acme/fast", name: "Acme Fast" }] })));
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
    render(<SettingsHarness initialSelection={{ providerId: "openrouter", modelId: "old/model" }} />);

    const openRouterActions = await screen.findByRole("group", { name: "OpenRouter 操作" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    fireEvent.click(within(openRouterActions).getByRole("button", { name: "移除" }));
    const confirmation = await screen.findByText("移除 OpenRouter 的已儲存 API 金鑰？");
    const popover = confirmation.closest(".ant-popover")!;
    fireEvent.click(within(popover as HTMLElement).getByRole("button", { name: /移\s*除/ }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(screen.getByTestId("selected-model").textContent).toBe("GPT-5.6"));

    pendingModels.resolve(new Response(JSON.stringify({ models: [{ id: "stale/model", name: "Stale model" }] })));
    await waitFor(() => expect(screen.queryByText("Stale model")).toBeNull());
    expect(screen.getByTestId("selected-model").textContent).toBe("GPT-5.6");
  });

});
