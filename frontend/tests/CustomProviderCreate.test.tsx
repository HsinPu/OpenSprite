import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CustomProviderCreate } from "../src/features/settings/CustomProviderCreate";
import { useCustomProviders } from "../src/features/ai-settings/useCustomProviders";
import type { CustomProvider } from "../src/api/customProviders";

vi.mock("../src/features/ai-settings/useCustomProviders");

const provider: CustomProvider = {
  id: "00000000-0000-4000-8000-000000000001", name: "Local AI", revision: 1, protocol: "openai_chat_completions",
  base_url: "http://localhost:1234/v1", auth_mode: "none", allow_insecure_local: true,
  created_at: "2026-09-10T00:00:00Z", updated_at: "2026-09-10T00:00:00Z", models: [],
};
const controller = {
  catalog: { revision: 1, providers: [provider] }, loading: false, saving: false, error: null,
  reload: vi.fn(async () => null), create: vi.fn(async () => true), update: vi.fn(async () => true),
  remove: vi.fn(async () => true), refreshModels: vi.fn(async () => true), addModel: vi.fn(async () => true),
  editModel: vi.fn(async () => true), removeModel: vi.fn(async () => true),
};
const changed = vi.fn(async () => undefined);
const setup = () => render(<CustomProviderCreate onChanged={changed} container={document.body} hasCustomProviders />);

describe("compact custom provider operations", () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(useCustomProviders).mockReturnValue(controller); });

  it("keeps management visible and places refresh in the provider menu", async () => {
    setup();
    expect(screen.getByRole("button", { name: /管\s*理/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "重新抓取模型" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Local AI 操作" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "重新抓取模型" }));
    await waitFor(() => expect(controller.refreshModels).toHaveBeenCalledWith(provider));
    await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  });

  it("retains model editing from the menu", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Local AI 操作" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "模型管理" }));
    expect(screen.queryByLabelText("Model ID")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "新增模型" }));
    expect(screen.getByLabelText("Model ID")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /取\s*消/ }));
    expect(screen.queryByLabelText("Model ID")).toBeNull();
    expect(controller.remove).not.toHaveBeenCalled();
  });

  it("requires confirmation before removing a custom provider", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Local AI 操作" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "移除" }));
    const dialog = await screen.findByRole("dialog");
    expect(controller.remove).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: /移\s*除/ }));
    await waitFor(() => expect(controller.remove).toHaveBeenCalledWith(provider));
    await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  });

  it("searches models and saves explicit capacity without changing the provider", async () => {
    const populated = { ...provider, models: [{ key: "model-1", model_id: "glm-5.3", name: "GLM", context_limit: 8192, output_limit: 2048, tools: false, source: "discovered" as const }] };
    vi.mocked(useCustomProviders).mockReturnValue({ ...controller, catalog: { revision: 1, providers: [populated] } });
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Local AI 操作" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "模型管理" }));
    expect(screen.getByText("暫用預設容量，尚未確認")).toBeTruthy();
    const search = screen.getByLabelText("搜尋名稱或 Model ID");
    fireEvent.change(search, { target: { value: "missing" } });
    expect(screen.getByText("沒有符合的模型")).toBeTruthy();
    fireEvent.change(search, { target: { value: "GLM" } });
    fireEvent.click(screen.getByRole("button", { name: /編\s*輯/ }));
    fireEvent.change(screen.getByLabelText("Context 上限"), { target: { value: "1000000" } });
    fireEvent.click(screen.getByRole("button", { name: /儲\s*存/ }));
    await waitFor(() => expect(controller.editModel).toHaveBeenCalledWith(populated, "model-1", expect.objectContaining({ contextLimit: 1000000, outputLimit: 2048 })));
    expect(controller.update).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByLabelText("Model ID")).toBeNull());
  });
});
