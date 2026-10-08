import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExecutionPackageApiError, MAX_EXECUTION_PACKAGE_BYTES, type ExecutionPackage, type ExecutionPackageCatalog } from "../src/api/executionPluginPackages";
import { ExecutionPackageManager } from "../src/features/settings/ExecutionPackageManager";
import { I18nProvider, useI18n } from "../src/i18n/I18nProvider";
import type { Locale } from "../src/i18n/catalog";

const api = vi.hoisted(() => ({ get: vi.fn(), import: vi.fn(), remove: vi.fn(), download: vi.fn() }));
vi.mock("../src/api/executionPluginPackages", async (original) => ({ ...await original<typeof import("../src/api/executionPluginPackages")>(), getExecutionPackages: api.get, importExecutionPackage: api.import, removeExecutionPackage: api.remove, downloadExecutionDeployment: api.download }));
const wheel: ExecutionPackage = {
  id: "c5800245-3695-4823-823e-f926e5b1528f", fileName: "example_plugin-0.1.0-py3-none-any.whl", distributionName: "example-plugin", version: "0.1.0", sha256: "a".repeat(64), sizeBytes: 4000, importedAt: "2026-10-08T00:00:00Z", requiresPython: ">=3.12,<3.14", requiresDist: ["opensprite-backend>=0.21.27,<0.22"], plugins: [{ id: "example_loop", kind: "loop", apiVersion: 2, entryPoint: "example_plugin:create_loop_factory" }], runtimeStatus: "not_installed",
};
const empty: ExecutionPackageCatalog = { packages: [], runtime: { kind: "docker", baseImage: "opensprite:local", manifestStatus: "missing" } };
const populated: ExecutionPackageCatalog = { ...empty, packages: [wheel] };
const refresh = vi.fn(async () => {});
const guide = vi.fn();
function Manager({ active = true, catalogBusy = false }: { active?: boolean; catalogBusy?: boolean }) { return <ExecutionPackageManager active={active} catalogBusy={catalogBusy} onRefreshCatalog={refresh} onGuide={guide} />; }
function Localized({ locale }: { locale: Locale }) {
  const { setLocale } = useI18n();
  useEffect(() => setLocale(locale), [locale, setLocale]);
  return <Manager />;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
async function loaded() { await screen.findByText("example-plugin"); }
async function pick(file = new File(["wheel bytes"], wheel.fileName)) {
  fireEvent.click(screen.getByRole("button", { name: "匯入 wheel" }));
  const modal = await screen.findByRole("dialog", { name: "匯入執行插件套件" });
  fireEvent.change(modal.querySelector<HTMLInputElement>('input[type="file"]')!, { target: { files: [file] } });
  if (file.size <= MAX_EXECUTION_PACKAGE_BYTES && file.size && file.name.endsWith(".whl")) await within(modal).findByText(file.name);
  return modal;
}
function trust(modal: HTMLElement) { fireEvent.click(within(modal).getByRole("checkbox")); }
function confirmImport(modal: HTMLElement) { fireEvent.click(within(modal).getByRole("button", { name: "確認匯入" })); }

describe("execution package workflow", () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue(populated);
    api.import.mockReset().mockResolvedValue(populated);
    api.remove.mockReset().mockResolvedValue(undefined);
    api.download.mockReset().mockResolvedValue(new Blob(["ZIP"], { type: "application/zip" }));
    refresh.mockClear(); guide.mockClear();
  });
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("shows an old cached API as incompatible and prevents deployment", async () => {
    const retired = { ...wheel, plugins: wheel.plugins.map(plugin => ({ ...plugin, apiVersion: 1 })) };
    api.get.mockResolvedValue({ ...empty, packages: [retired] });
    render(<Manager />);
    await screen.findByText("插件 API 不相容；需要 API v2");
    const download = screen.getByRole("button", { name: /下載.*example-plugin/ });
    expect(download.hasAttribute("disabled")).toBe(true);
    fireEvent.click(download);
    expect(api.download).not.toHaveBeenCalled();
  });

  it.each([
    ["zh-TW", "匯入套件", "匯入 wheel", "尚未安裝"],
    ["en", "Imported packages", "Import wheel", "Not installed"],
    ["ja", "インポート済みパッケージ", "wheel をインポート", "未導入"],
  ] as const)("shows actual package metadata and status in %s", async (locale, title, importLabel, status) => {
    render(<I18nProvider><Localized locale={locale} /></I18nProvider>);
    const section = await screen.findByRole("region", { name: title });
    await within(section).findByText(status);
    expect(within(section).getByText(wheel.fileName)).toBeTruthy();
    expect(within(section).getByRole("button", { name: importLabel })).toBeTruthy();
    expect(api.import).not.toHaveBeenCalled();
    expect(api.download).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("loads only when active and provides an empty state without an install action", async () => {
    api.get.mockResolvedValue(empty);
    const view = render(<Manager active={false} />);
    expect(api.get).not.toHaveBeenCalled();
    view.rerender(<Manager />);
    await screen.findByText("沒有匯入套件。");
    expect(screen.queryByRole("button", { name: /安裝套件|立即安裝/ })).toBeNull();
    expect(api.import).not.toHaveBeenCalled();
  });

  it("isolates inventory errors and can retry the real GET", async () => {
    api.get.mockRejectedValueOnce(new ExecutionPackageApiError("packages_store_unavailable")).mockResolvedValueOnce(populated);
    render(<Manager />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("目前無法讀取或保存匯入套件");
    fireEvent.click(within(alert).getByRole("button", { name: "重新讀取" }));
    await loaded();
    expect(api.get).toHaveBeenCalledTimes(2);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("requires both a valid wheel and trust confirmation before importing", async () => {
    api.get.mockResolvedValue(empty);
    render(<Manager />);
    await screen.findByText("沒有匯入套件。");
    const modal = await pick();
    expect(within(modal).getByRole("button", { name: "確認匯入" }).hasAttribute("disabled")).toBe(true);
    expect(api.import).not.toHaveBeenCalled();
    trust(modal); confirmImport(modal);
    await waitFor(() => expect(api.import).toHaveBeenCalledOnce());
    expect(api.import.mock.calls[0][0]).toBeInstanceOf(File);
    await screen.findByText("已保存套件。匯入不會安裝或切換執行方式。");
    expect(screen.getByText("尚未安裝")).toBeTruthy();
    expect(refresh).not.toHaveBeenCalled();
  });

  it.each([
    ["invalid type", () => new File(["zip"], "source.zip"), "wheel 格式或執行插件 metadata 不支援"],
    ["empty", () => new File([], wheel.fileName), "wheel 格式或執行插件 metadata 不支援"],
    ["oversized", () => new File([new Uint8Array(MAX_EXECUTION_PACKAGE_BYTES + 1)], wheel.fileName), "wheel 不可超過 10 MiB"],
  ] as const)("rejects %s files before POST", async (_kind, create, message) => {
    render(<Manager />); await loaded();
    const modal = await pick(create());
    await waitFor(() => expect(within(modal).getAllByRole("alert").some((item) => item.textContent?.includes(message))).toBe(true));
    expect(within(modal).getByRole("button", { name: "確認匯入" }).hasAttribute("disabled")).toBe(true);
    expect(api.import).not.toHaveBeenCalled();
  });

  it("keeps a failed import review for retry and blocks duplicate submissions while pending", async () => {
    const pending = deferred<ExecutionPackageCatalog>();
    api.import.mockRejectedValueOnce(new ExecutionPackageApiError("incompatible_package")).mockReturnValueOnce(pending.promise);
    render(<Manager />); await loaded();
    const modal = await pick(); trust(modal); confirmImport(modal);
    await waitFor(() => expect(within(modal).getAllByRole("alert").some((item) => item.textContent?.includes("版本不相容"))).toBe(true));
    expect((within(modal).getByRole("checkbox") as HTMLInputElement).checked).toBe(true);
    confirmImport(modal);
    await waitFor(() => expect(api.import).toHaveBeenCalledTimes(2));
    expect(within(modal).getByRole("button", { name: "確認匯入" }).hasAttribute("disabled")).toBe(true);
    expect(within(modal).getByRole("button", { name: "取消" }).hasAttribute("disabled")).toBe(true);
    await act(async () => pending.resolve(populated));
    await screen.findByText("已保存套件。匯入不會安裝或切換執行方式。");
  });

  it("shows full provenance and dependency details without offering draft selection", async () => {
    api.get.mockResolvedValue({ ...populated, packages: [{ ...wheel, runtimeStatus: "unverified" }] });
    render(<Manager />); await loaded();
    fireEvent.click(screen.getByRole("button", { name: "查看 example-plugin 詳情" }));
    const drawer = await screen.findByRole("dialog", { name: "套件詳情" });
    expect(within(drawer).getByText(wheel.sha256)).toBeTruthy();
    expect(within(drawer).getByText(wheel.requiresDist[0])).toBeTruthy();
    expect(within(drawer).getByText(wheel.plugins[0].entryPoint)).toBeTruthy();
    expect(within(drawer).getByText(wheel.requiresPython!)).toBeTruthy();
    expect(within(drawer).getByText(/相同 ID 或版本不代表來源相同/)).toBeTruthy();
    expect(within(drawer).queryByRole("button", { name: "選為草稿" })).toBeNull();
  });

  it.each(["local", "missing base"] as const)("disables bundle download with a clear %s explanation", async (kind) => {
    api.get.mockResolvedValue({ ...populated, runtime: { ...empty.runtime, kind: kind === "local" ? "local" : "docker", baseImage: null } });
    render(<Manager />); await loaded();
    expect(screen.getByRole("button", { name: "下載 example-plugin 部署包" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(kind === "local" ? /本機環境請依安裝說明手動安裝/ : /尚未設定可用的 Docker 基底映像/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "安裝說明" }));
    expect(guide).toHaveBeenCalledOnce();
    expect(api.download).not.toHaveBeenCalled();
  });

  it("downloads the API Blob with an attached anchor and revokes its URL after the click", async () => {
    const create = vi.fn(() => "blob:deployment-proof");
    const revoke = vi.fn();
    const OriginalURL = URL;
    vi.stubGlobal("URL", class extends OriginalURL { static createObjectURL = create; static revokeObjectURL = revoke; });
    let clicked = false;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicked = true;
      expect(this.download).toBe("opensprite-execution-plugin-deployment.zip");
      expect(this.href).toBe("blob:deployment-proof");
      expect(document.body.contains(this)).toBe(true);
    });
    render(<Manager />); await loaded();
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "下載 example-plugin 部署包" }));
    await act(async () => {});
    expect(api.download).toHaveBeenCalledWith(wheel.id);
    expect(create).toHaveBeenCalledWith(expect.any(Blob));
    expect(clicked).toBe(true);
    expect(revoke).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1000));
    expect(revoke).toHaveBeenCalledWith("blob:deployment-proof");
    expect(refresh).not.toHaveBeenCalled();
  });

  it("reports a bundle error without pretending deployment succeeded", async () => {
    api.download.mockRejectedValueOnce(new ExecutionPackageApiError("deployment_unavailable"));
    render(<Manager />); await loaded();
    fireEvent.click(screen.getByRole("button", { name: "下載 example-plugin 部署包" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Docker 部署包目前無法產生");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("keeps a failed details download visible in the Drawer footer", async () => {
    api.download.mockRejectedValueOnce(new ExecutionPackageApiError("network_error"));
    render(<Manager />); await loaded();
    fireEvent.click(screen.getByRole("button", { name: "查看 example-plugin 詳情" }));
    const drawer = await screen.findByRole("dialog", { name: "套件詳情" });
    fireEvent.click(within(drawer).getByRole("button", { name: "下載 example-plugin 部署包" }));
    const alert = await within(drawer).findByRole("alert");
    expect(alert.textContent).toContain("無法連線至後端，請確認服務後重試。");
    expect(alert.closest(".ant-drawer-footer")).not.toBeNull();
    expect(within(drawer).getByRole("button", { name: "下載 example-plugin 部署包" }).hasAttribute("disabled")).toBe(false);
    expect(api.download).toHaveBeenCalledWith(wheel.id);
  });

  it("keeps an in-flight download busy across reopen and discards its stale result", async () => {
    const actualApi = await vi.importActual<typeof import("../src/api/executionPluginPackages")>("../src/api/executionPluginPackages");
    api.get.mockImplementation(actualApi.getExecutionPackages); api.download.mockImplementation(actualApi.downloadExecutionDeployment);
    const pending = deferred<Response>();
    const fetchMock = vi.fn((path: string) => path.endsWith("/deployment-bundle") ? pending.promise : Promise.resolve(new Response(JSON.stringify(populated))));
    vi.stubGlobal("fetch", fetchMock);
    const create = vi.fn();
    const OriginalURL = URL;
    vi.stubGlobal("URL", class extends OriginalURL { static createObjectURL = create; });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const view = render(<Manager />);
    try {
      await loaded();
      fireEvent.click(screen.getByRole("button", { name: "下載 example-plugin 部署包" }));
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
      view.rerender(<Manager active={false} />); view.rerender(<Manager />);
      await loaded();
      expect(fetchMock).toHaveBeenCalledTimes(3);
      const download = screen.getByRole("button", { name: "下載 example-plugin 部署包" });
      expect(download.hasAttribute("disabled")).toBe(true);
      expect(download.classList.contains("ant-btn-loading")).toBe(true);
      expect(screen.getByRole("button", { name: "核對部署狀態" }).hasAttribute("disabled")).toBe(true);
      expect(screen.getByRole("button", { name: "匯入 wheel" }).hasAttribute("disabled")).toBe(true);
      await act(async () => pending.resolve(new Response("ZIP", { headers: { "Content-Type": "application/zip" } })));
      await waitFor(() => expect(screen.getByRole("button", { name: "匯入 wheel" }).hasAttribute("disabled")).toBe(false));
      expect(screen.getByRole("button", { name: "核對部署狀態" }).hasAttribute("disabled")).toBe(false);
      expect(create).not.toHaveBeenCalled(); expect(click).not.toHaveBeenCalled();
      expect(screen.queryByRole("status")).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: "匯入 wheel" }));
      expect(await screen.findByRole("dialog", { name: "匯入執行插件套件" })).toBeTruthy();
      expect(api.import).not.toHaveBeenCalled(); expect(refresh).not.toHaveBeenCalled();
    } finally { await act(async () => pending.resolve(new Response("ZIP", { headers: { "Content-Type": "application/zip" } }))); }
  }, 10000);

  it("confirms the exact cache target and deletes without changing execution defaults", async () => {
    api.get.mockResolvedValueOnce(populated).mockResolvedValueOnce(empty);
    render(<Manager />); await loaded();
    fireEvent.click(screen.getByRole("button", { name: `移除 ${wheel.fileName} 快取` }));
    expect(await screen.findByText(`移除 ${wheel.fileName} 的匯入快取？`)).toBeTruthy();
    expect(screen.getByText("只刪除此 wheel 的匯入快取，不會解除安裝插件或更改已保存的執行方式。")).toBeTruthy();
    expect(api.remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "移除快取" }));
    await waitFor(() => expect(api.remove).toHaveBeenCalledWith(wheel.id));
    await screen.findByText("沒有匯入套件。");
    expect(refresh).not.toHaveBeenCalled();
    expect(api.import).not.toHaveBeenCalled();
  });

  it("manually refreshes both package provenance and installed catalog after restart", async () => {
    render(<Manager />); await loaded();
    fireEvent.click(screen.getByRole("button", { name: "核對部署狀態" }));
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    expect(refresh).toHaveBeenCalledOnce();
  });

  it("retries only inventory reading when deletion succeeds but its refresh fails", async () => {
    api.get.mockResolvedValueOnce(populated).mockRejectedValueOnce(new ExecutionPackageApiError("packages_store_unavailable")).mockResolvedValueOnce(empty);
    render(<Manager />); await loaded();
    fireEvent.click(screen.getByRole("button", { name: `移除 ${wheel.fileName} 快取` }));
    fireEvent.click(await screen.findByRole("button", { name: "移除快取" }));
    const alert = await screen.findByRole("alert");
    expect(api.remove).toHaveBeenCalledOnce();
    expect(screen.queryByText("example-plugin")).toBeNull();
    fireEvent.click(within(alert).getByRole("button", { name: "重新讀取" }));
    await screen.findByText("沒有匯入套件。");
    expect(api.remove).toHaveBeenCalledOnce();
    expect(api.get).toHaveBeenCalledTimes(3);
    expect(refresh).not.toHaveBeenCalled();
  });

  it.each(["reopen", "remount"] as const)("waits for a real in-flight POST before GET after %s", async (transition) => {
    const actualApi = await vi.importActual<typeof import("../src/api/executionPluginPackages")>("../src/api/executionPluginPackages");
    api.get.mockImplementation(actualApi.getExecutionPackages); api.import.mockImplementation(actualApi.importExecutionPackage);
    let stored = empty;
    const pending = deferred<Response>();
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => init?.method === "POST" ? pending.promise : Promise.resolve(new Response(JSON.stringify(stored))));
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<Manager />);
    try {
      await screen.findByText("沒有匯入套件。");
      const modal = await pick(); trust(modal); confirmImport(modal);
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
      if (transition === "reopen") view.rerender(<Manager active={false} />);
      else view.rerender(<div />);
      view.rerender(<Manager />);
      expect(screen.getByText("正在讀取匯入套件…")).toBeTruthy();
      expect(fetchMock).toHaveBeenCalledTimes(2);
      stored = populated;
      await act(async () => pending.resolve(new Response(JSON.stringify(populated))));
      await loaded();
      expect(fetchMock).toHaveBeenCalledTimes(3);
      expect(screen.getByRole("button", { name: "匯入 wheel" }).hasAttribute("disabled")).toBe(false);
      expect(api.import).toHaveBeenCalledOnce();
      expect(refresh).not.toHaveBeenCalled();
    } finally { await act(async () => pending.resolve(new Response(JSON.stringify(populated)))); }
  });

  it("waits for a real in-flight DELETE before reading the cache on reopen", async () => {
    const actualApi = await vi.importActual<typeof import("../src/api/executionPluginPackages")>("../src/api/executionPluginPackages");
    api.get.mockImplementation(actualApi.getExecutionPackages); api.remove.mockImplementation(actualApi.removeExecutionPackage);
    let stored = populated;
    const pending = deferred<Response>();
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => init?.method === "DELETE" ? pending.promise : Promise.resolve(new Response(JSON.stringify(stored))));
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<Manager />);
    try {
      await loaded();
      fireEvent.click(screen.getByRole("button", { name: `移除 ${wheel.fileName} 快取` }));
      fireEvent.click(await screen.findByRole("button", { name: "移除快取" }));
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
      view.rerender(<Manager active={false} />); view.rerender(<Manager />);
      expect(screen.queryByText("example-plugin")).toBeNull();
      expect(fetchMock).toHaveBeenCalledTimes(2);
      stored = empty;
      await act(async () => pending.resolve(new Response(null, { status: 204 })));
      await screen.findByText("沒有匯入套件。");
      expect(fetchMock).toHaveBeenCalledTimes(3);
      expect(screen.getByRole("button", { name: "匯入 wheel" }).hasAttribute("disabled")).toBe(false);
    } finally { await act(async () => pending.resolve(new Response(null, { status: 204 }))); }
  });
});
