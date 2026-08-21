import { describe, expect, it, vi } from "vitest";

import {
  ProviderApiError,
  deleteProviderConnection,
  listProviderConnections,
  providerErrorText,
  replaceProviderConnection,
  testProviderConnection,
} from "../src/api/providerConnections";

const catalog = {
  providers: [
    { id: "openai", name: "OpenAI", connected: true, status: "connected", credentialPreview: "••••1234", lastCheckedAt: "2026-08-20T08:30:00Z" },
    { id: "anthropic", name: "Anthropic", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
    { id: "openrouter", name: "OpenRouter", connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null },
  ],
};

const disconnectedOpenAi = {
  ...catalog.providers[0],
  connected: false,
  status: "disconnected",
  credentialPreview: null,
  lastCheckedAt: null,
};

describe("provider connection client", () => {
  it("validates the fixed catalog order and sends only the contracted request shapes", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog)))
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog.providers[0])))
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog.providers[0])))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listProviderConnections()).resolves.toEqual(catalog.providers);
    await expect(replaceProviderConnection("openai", "test-key")).resolves.toEqual(catalog.providers[0]);
    await expect(testProviderConnection("openai")).resolves.toEqual(catalog.providers[0]);
    await deleteProviderConnection("openai");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/providers", undefined);
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/providers/openai/connection", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ apiKey: "test-key" }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/providers/openai/connection/test", { method: "POST" });
    expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/providers/openai/connection", { method: "DELETE" });
  });

  it("fails closed on a malformed catalog and never exposes an error response message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ providers: [catalog.providers[1], catalog.providers[0], catalog.providers[2]] }))));
    await expect(listProviderConnections()).rejects.toMatchObject({ code: "malformed_response" });

    const safeText = providerErrorText(new ProviderApiError("invalid_credentials"));
    expect(safeText).toBe("API 金鑰無效或已失效。");
    expect(safeText).not.toContain("secret-from-server");
  });

  it.each([
    ["a disconnected OpenAI provider reported as connected with null metadata", { ...disconnectedOpenAi, status: "connected" }],
    ["a disconnected OpenAI provider that still carries a credential", { ...disconnectedOpenAi, credentialPreview: "••••1234" }],
    ["a disconnected OpenAI provider that still carries a timestamp", { ...disconnectedOpenAi, lastCheckedAt: "2026-08-20T08:30:00Z" }],
    ["a connected provider reported as disconnected", { ...catalog.providers[0], status: "disconnected", credentialPreview: null, lastCheckedAt: null }],
    ["an impossible leap-day timestamp", { ...catalog.providers[0], lastCheckedAt: "2026-02-30T08:30:00Z" }],
    ["a 24:00 timestamp", { ...catalog.providers[0], lastCheckedAt: "2026-08-20T24:00:00Z" }],
  ])("rejects %s", async (_description, malformedOpenAi) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ providers: [malformedOpenAi, catalog.providers[1], catalog.providers[2]] }))));
    await expect(listProviderConnections()).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("accepts a connected provider with a checked failure status and UTC metadata", async () => {
    const checkedFailure = { ...catalog.providers[0], status: "invalid_credentials" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ providers: [checkedFailure, catalog.providers[1], catalog.providers[2]] }))));
    await expect(listProviderConnections()).resolves.toEqual([checkedFailure, catalog.providers[1], catalog.providers[2]]);
  });

  it.each([
    ["GET", 201, catalog, () => listProviderConnections()],
    ["GET", 202, catalog, () => listProviderConnections()],
    ["PUT", 201, catalog.providers[0], () => replaceProviderConnection("openai", "test-key")],
    ["PUT", 202, catalog.providers[0], () => replaceProviderConnection("openai", "test-key")],
    ["POST", 201, catalog.providers[0], () => testProviderConnection("openai")],
    ["POST", 202, catalog.providers[0], () => testProviderConnection("openai")],
  ])("rejects unexpected %s %i success responses", async (_operation, status, body, request) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
    await expect(request()).rejects.toMatchObject({ code: "malformed_response" });
  });

  it.each([
    ["an extra error field", { error: { code: "invalid_credentials", message: "private", retryable: false, extra: true } }],
    ["a missing retryable field", { error: { code: "invalid_credentials", message: "private" } }],
    ["a client-only error code", { error: { code: "network_error", message: "private", retryable: false } }],
    ["a code that does not match its HTTP status", { error: { code: "invalid_credentials", message: "private", retryable: false } }],
  ])("rejects %s from a PUT response", async (_description, body) => {
    const status = _description === "a code that does not match its HTTP status" ? 400 : 422;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
    await expect(replaceProviderConnection("openai", "test-key")).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("requires connected success summaries for PUT and POST", async () => {
    const nonConnected = { ...catalog.providers[0], connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(nonConnected)))
      .mockResolvedValueOnce(new Response(JSON.stringify(nonConnected)));
    vi.stubGlobal("fetch", fetchMock);
    await expect(replaceProviderConnection("openai", "test-key")).rejects.toMatchObject({ code: "malformed_response" });
    await expect(testProviderConnection("openai")).rejects.toMatchObject({ code: "malformed_response" });
  });

  it.each([
    ["a successful DELETE body", new Response(JSON.stringify({ deleted: true }), { status: 200 })],
    ["an invalid DELETE error envelope", new Response(JSON.stringify({ error: { code: "unsupported_provider", message: "private" } }), { status: 404 })],
    ["a DELETE error code mismatched to its status", new Response(JSON.stringify({ error: { code: "credential_store_unavailable", message: "private", retryable: true } }), { status: 404 })],
  ])("rejects %s", async (_description, response) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    await expect(deleteProviderConnection("openai")).rejects.toMatchObject({ code: "malformed_response" });
  });
});
