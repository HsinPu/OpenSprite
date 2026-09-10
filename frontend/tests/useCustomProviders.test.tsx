import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useCustomProviders } from "../src/features/ai-settings/useCustomProviders";
import { createCustomProvider, listCustomProviders } from "../src/api/customProviders";

vi.mock("../src/api/customProviders", async (original) => ({
  ...await original<typeof import("../src/api/customProviders")>(),
  listCustomProviders: vi.fn(), createCustomProvider: vi.fn(),
}));

beforeEach(() => vi.clearAllMocks());

it("loads only on demand when no custom providers exist", async () => {
  vi.mocked(listCustomProviders).mockResolvedValueOnce({ revision: 0, providers: [] });
  const { result } = renderHook(() => useCustomProviders(false));
  expect(listCustomProviders).not.toHaveBeenCalled();
  expect(result.current.catalog).toBeNull();
  await act(async () => { await result.current.reload(); });
  expect(listCustomProviders).toHaveBeenCalledTimes(1);
  expect(result.current.catalog?.revision).toBe(0);
});

it("preserves the previous catalog when refreshing fails", async () => {
  vi.mocked(listCustomProviders).mockResolvedValueOnce({ revision: 2, providers: [] }).mockRejectedValueOnce(new Error("offline"));
  const { result } = renderHook(() => useCustomProviders());
  await waitFor(() => expect(result.current.catalog?.revision).toBe(2));
  await act(async () => { await result.current.reload(); });
  expect(result.current.catalog?.revision).toBe(2);
  expect(result.current.error).toBe("network_error");
});

it("does not report an accepted create as failed when the follow-up read fails", async () => {
  vi.mocked(listCustomProviders).mockResolvedValueOnce({ revision: 0, providers: [] }).mockRejectedValueOnce(new Error("offline"));
  vi.mocked(createCustomProvider).mockResolvedValueOnce({} as Awaited<ReturnType<typeof createCustomProvider>>);
  const { result } = renderHook(() => useCustomProviders());
  await waitFor(() => expect(result.current.catalog).not.toBeNull());
  let saved = false;
  await act(async () => { saved = await result.current.create({ name: "Local", baseUrl: "https://example.com/v1", protocol: "openai_chat_completions", authMode: "none", allowInsecureLocal: false }); });
  expect(saved).toBe(true);
  expect(result.current.error).toBe("network_error");
  expect(createCustomProvider).toHaveBeenCalledTimes(1);
  expect(result.current.saving).toBe(false);
});
