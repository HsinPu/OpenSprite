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

async function chooseNoRecovery() {
  fireEvent.mouseDown(screen.getByRole("combobox", { name: "執行策略" }));
  fireEvent.click(await screen.findByText("不自動重試或續寫"));
}

describe("execution plugin settings", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue(settings);
    api.put.mockReset().mockImplementation(async (selection) => ({ ...settings, selection }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it.each([["zh-TW", "執行方式", "執行策略"], ["en", "Execution", "Execution policy"], ["ja", "実行方式", "実行ポリシー"]] as const)("shows the selection and read-only metadata in %s", async (locale, title, policy) => {
    render(<I18nProvider><Localized locale={locale} /></I18nProvider>);
    expect(await screen.findByRole("heading", { name: title })).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("combobox", { name: policy }).closest(".ant-select")?.classList.contains("ant-select-disabled")).toBe(false));
    expect(screen.getAllByText(/1\.0\.0/)).toHaveLength(2);
    expect(api.put).not.toHaveBeenCalled();
  });

  it("waits until active to load, and disables selects while loading", async () => {
    const pending = deferred<ExecutionData>();
    api.get.mockReturnValue(pending.promise);
    const view = render(<ExecutionSettings active={false} />);
    expect(api.get).not.toHaveBeenCalled();
    view.rerender(<ExecutionSettings active />);
    expect(screen.getByRole("status").textContent).toBe("正在讀取執行方式…");
    expect(screen.getAllByRole("combobox").every((item) => item.closest(".ant-select")?.classList.contains("ant-select-disabled"))).toBe(true);
    await act(async () => pending.resolve(settings));
  });

  it("retries an initial GET failure without writing defaults", async () => {
    api.get.mockRejectedValueOnce(new ExecutionSettingsApiError("settings_store_unavailable")).mockResolvedValueOnce(settings);
    render(<ExecutionSettings active />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("目前無法讀取或儲存執行方式。");
    fireEvent.click(within(alert).getByRole("button", { name: "重新讀取" }));
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(api.put).not.toHaveBeenCalled();
  });

  it("saves an atomic selection, disables controls until confirmed, and explains no recovery", async () => {
    const pending = deferred<ExecutionData>();
    api.put.mockReturnValue(pending.promise);
    render(<ExecutionSettings active />);
    await screen.findAllByText("版本 1.0.0");
    await chooseNoRecovery();
    expect(screen.getByText("不自動重試上下文超限，也不接續被截斷的模型輸出。一般工具呼叫與工具核准仍正常執行。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "儲存執行方式" }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith({ loopId: "standard", policyId: "no_recovery" }));
    expect(screen.getByRole("button", { name: "儲存執行方式" }).getAttribute("aria-busy")).toBe("true");
    expect(screen.getAllByRole("combobox").every((item) => item.closest(".ant-select")?.classList.contains("ant-select-disabled"))).toBe(true);
    await act(async () => pending.resolve({ ...settings, selection: { loopId: "standard", policyId: "no_recovery" } }));
    expect(screen.getByRole("status").textContent).toContain("已儲存");
    await waitFor(() => expect(screen.getByRole("button", { name: "儲存執行方式" }).hasAttribute("disabled")).toBe(true));
    expect(screen.getByRole("button", { name: "儲存執行方式" }).getAttribute("aria-busy")).toBe("false");
  });

  it.each(["reopen", "remount"] as const)("reads the confirmed selection after %s while a save is pending", async (transition) => {
    const actualApi = await vi.importActual<typeof import("../src/api/executionSettings")>("../src/api/executionSettings");
    api.get.mockImplementation(actualApi.getExecutionSettings);
    api.put.mockImplementation(actualApi.putExecutionSettings);
    const pending = deferred<Response>();
    let stored = settings;
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => init?.method === "PUT" ? pending.promise : Promise.resolve(new Response(JSON.stringify(stored))));
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<ExecutionSettings active />);
    try {
      await screen.findAllByText("版本 1.0.0");
      await chooseNoRecovery();
      fireEvent.click(screen.getByRole("button", { name: "儲存執行方式" }));
      await waitFor(() => expect(api.put).toHaveBeenCalledOnce());
      if (transition === "reopen") view.rerender(<ExecutionSettings active={false} />);
      else view.rerender(<div />);
      view.rerender(<ExecutionSettings active />);

      expect(screen.getByRole("status").textContent).toBe("正在讀取執行方式…");
      expect(screen.getAllByRole("combobox").every((item) => item.closest(".ant-select")?.classList.contains("ant-select-disabled"))).toBe(true);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      stored = { ...settings, selection: { loopId: "standard", policyId: "no_recovery" } };
      await act(async () => pending.resolve(new Response(JSON.stringify(stored))));
      await waitFor(() => expect(screen.queryByText("正在讀取執行方式…")).toBeNull());
      expect(screen.getByRole("combobox", { name: "執行策略" }).closest(".ant-select")?.textContent).toContain("不自動重試或續寫");
      expect(screen.getByRole("button", { name: "儲存執行方式" }).hasAttribute("disabled")).toBe(true);
      expect(fetchMock).toHaveBeenCalledTimes(3);
    } finally {
      await act(async () => pending.resolve(new Response(JSON.stringify({ ...settings, selection: { loopId: "standard", policyId: "no_recovery" } }))));
    }
  });


  it("keeps the unsaved selection after a PUT failure and supports retry", async () => {
    api.put.mockRejectedValueOnce(new ExecutionSettingsApiError("plugin_unavailable")).mockImplementationOnce(async (selection) => ({ ...settings, selection }));
    render(<ExecutionSettings active />);
    await screen.findAllByText("版本 1.0.0");
    await chooseNoRecovery();
    fireEvent.click(screen.getByRole("button", { name: "儲存執行方式" }));
    expect((await screen.findByRole("alert")).textContent).toContain("執行插件目前無法使用");
    expect(screen.getByRole("button", { name: "儲存執行方式" }).hasAttribute("disabled")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "儲存執行方式" }));
    await waitFor(() => expect(api.put).toHaveBeenCalledTimes(2));
    expect(api.put).toHaveBeenLastCalledWith({ loopId: "standard", policyId: "no_recovery" });
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("keeps removed IDs visible and requires available replacements", async () => {
    api.get.mockResolvedValue({ ...settings, selection: { loopId: "standard", policyId: "removed" } });
    render(<ExecutionSettings active />);
    expect(await screen.findByText("removed (無法使用)")).toBeTruthy();
    expect(screen.getByText("已選插件目前不在清單中，請選擇可用的替代插件。")).toBeTruthy();
    expect(screen.getByRole("button", { name: "儲存執行方式" }).hasAttribute("disabled")).toBe(true);
    await chooseNoRecovery();
    expect(screen.getByRole("button", { name: "儲存執行方式" }).hasAttribute("disabled")).toBe(false);
    const future = screen.getByText("Future policy (版本不相容)").closest(".ant-select-item-option");
    expect(future?.classList.contains("ant-select-item-option-disabled")).toBe(true);
  });

  it("ignores a stale GET after leaving the page", async () => {
    const pending = deferred<ExecutionData>();
    api.get.mockReturnValue(pending.promise);
    const view = render(<ExecutionSettings active />);
    view.rerender(<ExecutionSettings active={false} />);
    await act(async () => pending.resolve(settings));
    expect(screen.queryByText("版本 1.0.0")).toBeNull();
  });
});
