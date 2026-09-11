import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { listOpenRouterModels, listProviderConnections, type OpenRouterModel } from "../src/api/providerConnections";
import { useProviderCatalog } from "../src/features/ai-settings/useProviderCatalog";

vi.mock("../src/api/providerConnections", async (original) => ({
  ...await original<typeof import("../src/api/providerConnections")>(),
  listOpenRouterModels: vi.fn(), listProviderConnections: vi.fn(),
}));

const models: OpenRouterModel[] = [{ id: "vendor/model", name: "Model", contextWindowTokens: 8192, maxOutputTokens: 2048 }];

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listProviderConnections).mockResolvedValue([{ id: "openrouter", name: "OpenRouter", connected: true, status: "connected", credentialPreview: null, lastCheckedAt: null }]);
  vi.mocked(listOpenRouterModels).mockResolvedValue(models);
});

it("keeps loaded choices while refresh is pending and after failure", async () => {
  const { result } = renderHook(() => useProviderCatalog());
  await waitFor(() => expect(result.current.modelChoices).toHaveLength(1));
  let reject!: (error: Error) => void;
  vi.mocked(listOpenRouterModels).mockImplementationOnce(() => new Promise((_, fail) => { reject = fail; }));
  let refresh!: Promise<void>;
  act(() => { refresh = result.current.loadOpenRouterModels(true); });
  expect(result.current.openRouterModelLoadStatus).toBe("loading");
  expect(result.current.modelChoices[0].selection.modelId).toBe("vendor/model");
  await act(async () => { reject(new Error("offline")); await refresh; });
  expect(result.current.openRouterModelLoadStatus).toBe("error");
  expect(result.current.modelChoices[0].selection.modelId).toBe("vendor/model");
  expect(result.current.openRouterModelError).not.toBeNull();
});

it("still clears choices on explicit invalidation and ignores a stale refresh", async () => {
  const { result } = renderHook(() => useProviderCatalog());
  await waitFor(() => expect(result.current.modelChoices).toHaveLength(1));
  let resolve!: (value: OpenRouterModel[]) => void;
  vi.mocked(listOpenRouterModels).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
  let refresh!: Promise<void>;
  act(() => { refresh = result.current.loadOpenRouterModels(true); });
  act(() => {
    result.current.updateProviderSummary({ id: "openrouter", name: "OpenRouter", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null });
    result.current.invalidateOpenRouterModels();
  });
  await act(async () => { resolve(models); await refresh; });
  expect(result.current.modelChoices).toEqual([]);
  expect(result.current.openRouterModels).toBeNull();
});
