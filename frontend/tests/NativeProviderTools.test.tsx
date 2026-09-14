import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { NativeProviderTools } from "../src/features/settings/NativeProviderTools";
import { getAiSettings, putProviderToolPolicy } from "../src/api/aiSettings";
vi.mock("../src/api/aiSettings", async importOriginal => ({ ...await importOriginal<typeof import("../src/api/aiSettings")>(), getAiSettings: vi.fn(), putProviderToolPolicy: vi.fn() }));
beforeEach(() => { vi.clearAllMocks(); vi.mocked(getAiSettings).mockResolvedValue({ model:null,responseMode:"default",outputContinuation:"5",responseDelivery:"stream",logFullPrompts:false }); });
it("loads legacy defaults and saves a provider-only tool policy", async () => {
  render(<NativeProviderTools provider="openai" name="OpenAI" />);
  fireEvent.click(screen.getByRole("button", {name:"工具設定"}));
  await waitFor(() => expect((screen.getByRole("checkbox", {name:"允許模型使用工具"}) as HTMLInputElement).disabled).toBe(false));
  expect((screen.getByRole("checkbox", {name:"允許模型使用工具"}) as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByRole("checkbox", {name:"允許模型使用工具"}));
  fireEvent.click(screen.getByRole("button", {name:/儲/}));
  await waitFor(() => expect(putProviderToolPolicy).toHaveBeenCalledWith("openai", {toolsEnabled:false,transport:"stream",disabledModels:[]}));
});
it("shows a load failure and does not allow saving unknown settings", async () => {
  vi.mocked(getAiSettings).mockRejectedValue(new Error("offline"));
  render(<NativeProviderTools provider="anthropic" name="Anthropic" />);
  fireEvent.click(screen.getByRole("button", {name:"工具設定"}));
  expect(await screen.findByRole("alert")).not.toBeNull();
  expect((screen.getByRole("button", {name:/儲/}) as HTMLButtonElement).disabled).toBe(true);
});
