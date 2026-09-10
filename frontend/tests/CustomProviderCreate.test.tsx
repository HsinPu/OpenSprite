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
    expect(screen.getByLabelText("Model ID")).toBeTruthy();
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
});
