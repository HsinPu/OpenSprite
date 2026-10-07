import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExecutionSettingsApiError, type ExecutionSettings as ExecutionData } from "../src/api/executionSettings";
import { ExecutionSettings } from "../src/features/settings/ExecutionSettings";
import { I18nProvider, useI18n } from "../src/i18n/I18nProvider";
import type { Locale } from "../src/i18n/catalog";

const api = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
vi.mock("../src/api/executionSettings", async (original) => ({ ...await original<typeof import("../src/api/executionSettings")>(), getExecutionSettings: api.get, putExecutionSettings: api.put }));

const settings: ExecutionData = {
  selection: { loopId: "standard", policyId: "standard" },
  plugins: [
    { id: "standard", kind: "loop", name: "Standard Loop", description: "Default loop", version: "1.0.0", apiVersion: 1, status: "available" },
    { id: "standard", kind: "policy", name: "Standard", description: "Default recovery", version: "1.0.0", apiVersion: 1, status: "available" },
    { id: "no_recovery", kind: "policy", name: "No recovery", description: "No automatic recovery", version: "1.0.0", apiVersion: 1, status: "available" },
    { id: "future", kind: "policy", name: "Future policy", description: "Future API", version: "2.0.0", apiVersion: 2, status: "incompatible" },
  ],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function Localized({ locale }: { locale: Locale }) {
  const { setLocale } = useI18n();
  useEffect(() => setLocale(locale), [locale, setLocale]);
  return <ExecutionSettings active />;
}

const applyButton = () => screen.getByRole("button", { name: "套用至新任務" });
const savedRegion = () => screen.getByRole("region", { name: "新任務的已保存預設" });
async function loaded() { await screen.findByRole("radio", { name: "選為草稿：標準 Loop" }); }
async function chooseNoRecovery() {
  fireEvent.click(screen.getByRole("tab", { name: "執行策略" }));
  fireEvent.click(await screen.findByRole("radio", { name: "選為草稿：不自動重試或續寫" }));
}

describe("execution plugin workbench", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue(settings);
    api.put.mockReset().mockImplementation(async (selection) => ({ ...settings, selection }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it.each([
    ["zh-TW", "執行方式", "執行策略", "新任務的已保存預設", "選為草稿：標準 Loop", "開發說明", "下載範例專案"],
    ["en", "Execution", "Execution policy", "Saved defaults for new tasks", "Select draft: Standard Loop", "Developer guide", "Download example project"],
    ["ja", "実行方式", "実行ポリシー", "新規タスクの保存済み設定", "下書きに選択：標準 Loop", "開発ガイド", "サンプルをダウンロード"],
  ] as const)("shows saved defaults, comparison tabs and the real example download in %s", async (locale, title, policy, savedTitle, radio, guide, download) => {
    render(<I18nProvider><Localized locale={locale} /></I18nProvider>);
    expect(await screen.findByRole("heading", { name: title })).toBeTruthy();
    await screen.findByRole("radio", { name: radio });
    expect(screen.getByRole("tab", { name: policy })).toBeTruthy();
    expect(within(screen.getByRole("region", { name: savedTitle })).getAllByText(/1\.0\.0/)).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: guide }));
    const link = await screen.findByRole("link", { name: download });
    expect(link.getAttribute("href")).toBe("/execution-plugin-example.zip");
    expect(link.getAttribute("download")).toBe("execution-plugin-example.zip");
    expect(api.put).not.toHaveBeenCalled();
  });

  it("waits until active to load and prevents draft selection during loading", async () => {
    const pending = deferred<ExecutionData>();
    api.get.mockReturnValue(pending.promise);
    const view = render(<ExecutionSettings active={false} />);
    expect(api.get).not.toHaveBeenCalled();
    view.rerender(<ExecutionSettings active />);
    expect(screen.getByText("正在讀取執行方式…")).toBeTruthy();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(applyButton().hasAttribute("disabled")).toBe(true);
    await act(async () => pending.resolve(settings));
    expect(screen.getByRole("radio", { name: "選為草稿：標準 Loop" }).hasAttribute("disabled")).toBe(false);
  });

  it("retries an initial GET failure without writing defaults", async () => {
    api.get.mockRejectedValueOnce(new ExecutionSettingsApiError("settings_store_unavailable")).mockResolvedValueOnce(settings);
    render(<ExecutionSettings active />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("目前無法讀取或儲存執行方式。");
    fireEvent.click(within(alert).getByRole("button", { name: "重新讀取" }));
    await loaded();
    expect(api.get).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(api.put).not.toHaveBeenCalled();
  });

  it("keeps a draft separate from saved defaults and discards it without a write", async () => {
    render(<ExecutionSettings active />);
    await loaded();
    await chooseNoRecovery();
    expect(within(savedRegion()).getByText("標準策略")).toBeTruthy();
    expect(within(savedRegion()).queryByText("不自動重試或續寫")).toBeNull();
    expect(screen.getByText("有未套用的變更")).toBeTruthy();
    expect((screen.getByRole("radio", { name: "選為草稿：不自動重試或續寫" }) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "取消草稿" }));
    expect((screen.getByRole("radio", { name: "選為草稿：標準策略" }) as HTMLInputElement).checked).toBe(true);
    expect(applyButton().hasAttribute("disabled")).toBe(true);
    expect(api.put).not.toHaveBeenCalled();
  });

  it("saves both IDs atomically and updates saved defaults only after confirmation", async () => {
    const pending = deferred<ExecutionData>();
    api.put.mockReturnValue(pending.promise);
    render(<ExecutionSettings active />);
    await loaded();
    await chooseNoRecovery();
    fireEvent.click(applyButton());
    await waitFor(() => expect(api.put).toHaveBeenCalledWith({ loopId: "standard", policyId: "no_recovery" }));
    expect(applyButton().getAttribute("aria-busy")).toBe("true");
    expect(screen.getAllByRole("radio").every((item) => item.hasAttribute("disabled"))).toBe(true);
    expect(within(savedRegion()).getByText("標準策略")).toBeTruthy();
    await act(async () => pending.resolve({ ...settings, selection: { loopId: "standard", policyId: "no_recovery" } }));
    expect(within(savedRegion()).getByRole("status").textContent).toContain("已儲存");
    expect(within(savedRegion()).getByText("不自動重試或續寫")).toBeTruthy();
    expect(applyButton().hasAttribute("disabled")).toBe(true);
    expect(applyButton().getAttribute("aria-busy")).toBe("false");
  });

  it.each(["reopen", "remount"] as const)("reads the confirmed selection after %s while a write is pending", async (transition) => {
    const actualApi = await vi.importActual<typeof import("../src/api/executionSettings")>("../src/api/executionSettings");
    api.get.mockImplementation(actualApi.getExecutionSettings);
    api.put.mockImplementation(actualApi.putExecutionSettings);
    const pending = deferred<Response>();
    let stored = settings;
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => init?.method === "PUT" ? pending.promise : Promise.resolve(new Response(JSON.stringify(stored))));
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<ExecutionSettings active />);
    try {
      await loaded();
      await chooseNoRecovery();
      fireEvent.click(applyButton());
      await waitFor(() => expect(api.put).toHaveBeenCalledOnce());
      if (transition === "reopen") view.rerender(<ExecutionSettings active={false} />);
      else view.rerender(<div />);
      view.rerender(<ExecutionSettings active />);
      expect(screen.getByText("正在讀取執行方式…")).toBeTruthy();
      expect(screen.queryByRole("radio")).toBeNull();
      expect(within(savedRegion()).queryByText("標準策略")).toBeNull();
      expect(fetchMock).toHaveBeenCalledTimes(2);
      stored = { ...settings, selection: { loopId: "standard", policyId: "no_recovery" } };
      await act(async () => pending.resolve(new Response(JSON.stringify(stored))));
      await waitFor(() => expect(screen.queryByText("正在讀取執行方式…")).toBeNull());
      expect(within(savedRegion()).getByText("不自動重試或續寫")).toBeTruthy();
      expect(applyButton().hasAttribute("disabled")).toBe(true);
      expect(fetchMock).toHaveBeenCalledTimes(3);
    } finally {
      await act(async () => pending.resolve(new Response(JSON.stringify({ ...settings, selection: { loopId: "standard", policyId: "no_recovery" } }))));
    }
  });

  it("keeps the draft after a PUT failure and supports retry", async () => {
    api.put.mockRejectedValueOnce(new ExecutionSettingsApiError("plugin_unavailable")).mockImplementationOnce(async (selection) => ({ ...settings, selection }));
    render(<ExecutionSettings active />);
    await loaded();
    await chooseNoRecovery();
    fireEvent.click(applyButton());
    expect((await screen.findByRole("alert")).textContent).toContain("執行插件目前無法使用");
    expect(applyButton().hasAttribute("disabled")).toBe(false);
    expect(within(savedRegion()).getByText("標準策略")).toBeTruthy();
    expect((screen.getByRole("radio", { name: "選為草稿：不自動重試或續寫" }) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(applyButton());
    await waitFor(() => expect(api.put).toHaveBeenCalledTimes(2));
    expect(api.put).toHaveBeenLastCalledWith({ loopId: "standard", policyId: "no_recovery" });
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("keeps missing IDs visible and blocks incompatible or unavailable draft choices", async () => {
    api.get.mockResolvedValue({ ...settings, selection: { loopId: "standard", policyId: "removed" } });
    render(<ExecutionSettings active />);
    await loaded();
    expect(within(savedRegion()).getByText("removed", { selector: "strong" })).toBeTruthy();
    expect(applyButton().hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("tab", { name: "執行策略" }));
    const removed = screen.getByRole("radio", { name: "選為草稿：removed" });
    expect(removed.hasAttribute("disabled")).toBe(true);
    expect((removed as HTMLInputElement).checked).toBe(true);
    expect(screen.getByRole("radio", { name: "選為草稿：Future policy" }).hasAttribute("disabled")).toBe(true);
    await chooseNoRecovery();
    expect(applyButton().hasAttribute("disabled")).toBe(false);
    expect(within(savedRegion()).getByText("removed", { selector: "strong" })).toBeTruthy();
    expect(api.put).not.toHaveBeenCalled();
  });

  it("shows true catalog metadata in a Drawer and selects only a draft", async () => {
    render(<ExecutionSettings active />);
    await loaded();
    fireEvent.click(screen.getByRole("tab", { name: "執行策略" }));
    fireEvent.click(screen.getByRole("button", { name: "查看 不自動重試或續寫 詳情" }));
    const drawer = await screen.findByRole("dialog", { name: "插件詳情" });
    expect(within(drawer).getByText("不自動重試上下文超限，也不接續被截斷的模型輸出。一般工具呼叫與工具核准仍正常執行。")).toBeTruthy();
    expect(within(drawer).getByText("no_recovery")).toBeTruthy();
    expect(within(drawer).getByText("1.0.0")).toBeTruthy();
    fireEvent.click(within(drawer).getByRole("button", { name: "選為草稿" }));
    expect(within(savedRegion()).getByText("標準策略")).toBeTruthy();
    expect(applyButton().hasAttribute("disabled")).toBe(false);
    expect(api.put).not.toHaveBeenCalled();
  });

  it("shows unavailable details without fabricating a version or allowing selection", async () => {
    api.get.mockResolvedValue({ ...settings, selection: { loopId: "standard", policyId: "removed" } });
    render(<ExecutionSettings active />);
    await loaded();
    fireEvent.click(screen.getByRole("tab", { name: "執行策略" }));
    fireEvent.click(screen.getByRole("button", { name: "查看 removed 詳情" }));
    const drawer = await screen.findByRole("dialog", { name: "插件詳情" });
    expect(within(drawer).getAllByText("—")).toHaveLength(2);
    expect(within(drawer).getByText("已選插件目前不在清單中，請選擇可用的替代插件。")).toBeTruthy();
    expect(within(drawer).getByRole("button", { name: "選為草稿" }).hasAttribute("disabled")).toBe(true);
    expect(within(drawer).getByRole("alert").textContent).toContain("此插件目前無法選用。");
    expect(api.put).not.toHaveBeenCalled();
  });

  it("offers working build instructions and explains the API boundary without installing anything", async () => {
    render(<ExecutionSettings active />);
    await loaded();
    fireEvent.click(screen.getByRole("button", { name: "安裝說明" }));
    const drawer = await screen.findByRole("dialog", { name: "開發說明" });
    expect(within(drawer).getByText("uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin")).toBeTruthy();
    expect(drawer.textContent).toContain("opensprite_backend.agent_loops.v1");
    expect(drawer.textContent).toContain("COPY --from=uv /uv /usr/local/bin/uv");
    fireEvent.click(within(drawer).getByRole("tab", { name: "API v1 邊界" }));
    expect(within(drawer).getByRole("alert").textContent).toContain("程序內 API 不是安全沙箱");
    expect(within(drawer).getByText(/API v1 不提供修改 prompt/)).toBeTruthy();
    expect(api.put).not.toHaveBeenCalled();
  });

  it("clears stale defaults and the draft when a refresh fails", async () => {
    api.get.mockResolvedValueOnce(settings).mockRejectedValueOnce(new ExecutionSettingsApiError("settings_store_unavailable"));
    render(<ExecutionSettings active />);
    await loaded();
    await chooseNoRecovery();
    fireEvent.click(screen.getByRole("button", { name: "重新讀取" }));
    await screen.findByRole("alert");
    expect(within(savedRegion()).queryByText("標準策略")).toBeNull();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(applyButton().hasAttribute("disabled")).toBe(true);
    expect(api.put).not.toHaveBeenCalled();
  });

  it("ignores a stale GET after leaving the page", async () => {
    const pending = deferred<ExecutionData>();
    api.get.mockReturnValue(pending.promise);
    const view = render(<ExecutionSettings active />);
    view.rerender(<ExecutionSettings active={false} />);
    await act(async () => pending.resolve(settings));
    expect(screen.queryByRole("radio")).toBeNull();
    expect(within(savedRegion()).queryByText("標準策略")).toBeNull();
  });
});
