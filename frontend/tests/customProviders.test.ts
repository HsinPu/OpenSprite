import { describe, expect, it, vi } from "vitest";
import { listCustomProviders } from "../src/api/customProviders";
import { createCustomProvider, getCustomProvider, listCustomModels, refreshCustomModels, updateCustomProvider, deleteCustomProvider, updateCustomModel, deleteCustomModel } from "../src/api/customProviders";

const id = "11111111-1111-4111-8111-111111111111";
const model = { key: "22222222-2222-4222-8222-222222222222", model_id: "local", name: "Local", context_limit: 32000, output_limit: 4000, tools: false, source: "manual" };
const provider = { id, name: "Local", revision: 1, protocol: "openai_chat_completions", base_url: "https://example.com/v1", auth_mode: "none", allow_insecure_local: false, created_at: "2026-09-10T00:00:00+00:00", updated_at: "2026-09-10T00:00:00+00:00", models: [model] };

describe("custom provider API", () => {
  it("accepts provider tool policy and rejects malformed flags", async () => {
    const configured = { ...provider, tools_enabled: false, non_streaming_tools: true };
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(configured)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...configured, tools_enabled: "true" }))));
    await expect(getCustomProvider(id)).resolves.toEqual(configured);
    await expect(getCustomProvider(id)).rejects.toThrow("malformed_response");
  });
  it("collects model pages and rejects revisions changing between pages", async () => {
    const nextModel = { ...model, key: "33333333-3333-4333-8333-333333333333", model_id: "second" };
    const page = (revision: number, entries: unknown[], nextCursor: string | null) => new Response(JSON.stringify({ revision, models: entries, nextCursor }));
    const fetch = vi.fn().mockResolvedValueOnce(page(2, [model], "2:1"))
      .mockResolvedValueOnce(page(2, [nextModel], null));
    vi.stubGlobal("fetch", fetch);
    await expect(listCustomModels(id)).resolves.toEqual({ revision: 2, models: [model, nextModel] });
    expect(fetch.mock.calls[1][0]).toBe(`/api/providers/${id}/models?cursor=2%3A1`);
    fetch.mockResolvedValueOnce(page(2, [model], "2:1")).mockResolvedValueOnce(page(3, [nextModel], null));
    await expect(listCustomModels(id)).rejects.toThrow("revision_conflict");
  });
  it("collects revision-consistent pages and rejects repeated cursors", async () => {
    const second = { ...provider, id: "33333333-3333-4333-8333-333333333333" };
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 2, providers: [provider], nextCursor: "2:1" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 2, providers: [second], nextCursor: null })));
    vi.stubGlobal("fetch", fetch);
    await expect(listCustomProviders()).resolves.toEqual({ revision: 2, providers: [provider, second] });
    expect(fetch.mock.calls[1][0]).toBe("/api/providers/catalog?cursor=2%3A1");
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ revision: 2, providers: [provider], nextCursor: "2:9" })));
    await expect(listCustomProviders()).rejects.toThrow("malformed_response");
  });
  it("sends guarded updates and deletions with stable keys and revisions", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(provider)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 2, models: [model] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 3, models: [] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ deleted: true })));
    vi.stubGlobal("fetch", fetch);
    await updateCustomProvider(id, { name: "Local", baseUrl: provider.base_url, protocol: "openai_chat_completions", authMode: "bearer", allowInsecureLocal: false, expectedRevision: 1 });
    expect(JSON.parse(fetch.mock.calls[0][1].body)).not.toHaveProperty("apiKey");
    await updateCustomModel(id, model.key, { modelId: "local", name: "Local", contextLimit: 32000, outputLimit: 4000, tools: false, expectedRevision: 1 });
    expect(fetch.mock.calls[1][0]).toBe(`/api/providers/${id}/models/${model.key}`);
    expect(fetch.mock.calls[1][1].method).toBe("PUT");
    await deleteCustomModel(id, model.key, 2);
    expect(fetch.mock.calls[2][0]).toBe(`/api/providers/${id}/models/${model.key}?expectedRevision=2`);
    await deleteCustomProvider(id, 3);
    expect(fetch.mock.calls[3][0]).toBe(`/api/providers/${id}?expectedRevision=3`);
    expect(fetch.mock.calls[3][1].method).toBe("DELETE");
  });

  it("creates with the exact revision and reads registered metadata", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(provider), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(provider)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 1, models: [model], nextCursor: null })));
    vi.stubGlobal("fetch", fetch);
    const draft = { name: "Local", baseUrl: "https://example.com/v1", protocol: "openai_chat_completions" as const, authMode: "none" as const, allowInsecureLocal: false, expectedRevision: 0 };
    await expect(createCustomProvider(draft)).resolves.toEqual(provider);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(draft);
    await expect(getCustomProvider(id)).resolves.toEqual(provider);
    await expect(listCustomModels(id)).resolves.toEqual({ revision: 1, models: [model] });
  });

  it("rejects duplicate models and unknown response fields", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 1, models: [model, model], nextCursor: null })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...provider, apiKey: "unexpected" }))));
    await expect(listCustomModels(id)).rejects.toThrow("malformed_response");
    await expect(getCustomProvider(id)).rejects.toThrow("malformed_response");
  });

  it("reports refresh revision conflicts without returning a replacement list", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "revision_conflict", message: "Conflict", retryable: false } }), { status: 409 }));
    vi.stubGlobal("fetch", fetch);
    await expect(refreshCustomModels(id, 3)).rejects.toThrow("revision_conflict");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ expectedRevision: 3 });
  });
});
