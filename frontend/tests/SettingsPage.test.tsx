import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { defaultDemoSettings, SettingsPage, type DemoSettings } from "../src/features/settings/SettingsPage";

const disconnectedCatalog = {
  providers: [
    { id: "openai", name: "OpenAI", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
    { id: "anthropic", name: "Anthropic", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
  ],
};

const connectedCatalog = {
  providers: [
    { id: "openai", name: "OpenAI", connected: true, status: "connected", credentialPreview: "••••1234", lastCheckedAt: "2026-08-20T08:30:00Z" },
    disconnectedCatalog.providers[1],
  ],
};

const connectedBothCatalog = {
  providers: [
    connectedCatalog.providers[0],
    { id: "anthropic", name: "Anthropic", connected: true, status: "connected", credentialPreview: "••••5678", lastCheckedAt: "2026-08-20T08:30:00Z" },
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

function SettingsHarness() {
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);
  return <SettingsPage section="models" onSectionChange={() => undefined} settings={settings} onSettingsChange={setSettings} onClose={() => undefined} />;
}

function GuardedDialogHarness() {
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  return <dialog open onCancel={(event) => { if (providerModalOpen) event.preventDefault(); }}><SettingsPage section="models" onSectionChange={() => undefined} settings={settings} onSettingsChange={setSettings} onClose={() => undefined} onProviderModalChange={setProviderModalOpen} /></dialog>;
}

describe("provider settings", () => {
  beforeEach(() => vi.unstubAllGlobals());

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
    const checkedFailure = { providers: [{ ...connectedCatalog.providers[0], status: "invalid_credentials" }, disconnectedCatalog.providers[1]] };
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
    expect((screen.getByLabelText("預設模型") as HTMLSelectElement).disabled).toBe(false);
    expect(Array.from((screen.getByLabelText("預設模型") as HTMLSelectElement).options).map((option) => option.text)).not.toContain("Claude Sonnet 4");
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

});
