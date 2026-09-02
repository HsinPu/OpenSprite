import { afterEach, describe, expect, it, vi } from "vitest";

import { createMcpServer, listMcpServers, listMcpTools, McpApiError, startMcpServer, type McpServerDraft } from "../src/api/mcpConnections";


const server = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Fixture",
  enabled: false,
  startOnLaunch: false,
  transport: { type: "stdio", executable: "C:\\Python\\python.exe", arguments: ["server.py"], workingDirectory: "C:\\Mcp" },
  authentication: { type: "none" },
  status: "disabled",
  protocolVersion: null,
  errorCode: null,
  toolCount: 0,
  unsupportedToolCount: 0,
};
const draft: McpServerDraft = { name: server.name, startOnLaunch: false, transport: { ...server.transport, type: "stdio" }, authentication: { type: "none" } };

afterEach(() => vi.unstubAllGlobals());

describe("MCP connections API", () => {
  it("lists, creates, and starts strict stdio server records", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ servers: [server] })))
      .mockResolvedValueOnce(new Response(JSON.stringify(server), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...server, enabled: true, status: "connected", protocolVersion: "2026-07-28" })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listMcpServers()).resolves.toHaveLength(1);
    await expect(createMcpServer(draft)).resolves.toMatchObject({ name: "Fixture" });
    await expect(startMcpServer(server.id)).resolves.toMatchObject({ status: "connected" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/mcp/servers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) });
  });

  it("rejects malformed Tool catalogs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ tools: [{ id: "bad tool" }] }))));
    await expect(listMcpTools(server.id)).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("accepts the strict Streamable HTTP transport with no authentication", async () => {
    const remote = {
      ...server,
      transport: { type: "streamable-http", url: "https://mcp.example.com/mcp" },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ servers: [remote] }))));

    await expect(listMcpServers()).resolves.toMatchObject([{
      transport: { type: "streamable-http", url: "https://mcp.example.com/mcp" },
    }]);
  });

  it("sends a Bearer token only in the write request and accepts masked state", async () => {
    const remote = {
      ...server,
      transport: { type: "streamable-http", url: "https://mcp.example.com/mcp" },
      authentication: { type: "bearer-token", configured: true },
    };
    const bearerDraft: McpServerDraft = {
      name: "Protected MCP",
      startOnLaunch: false,
      transport: { type: "streamable-http", url: "https://mcp.example.com/mcp" },
      authentication: { type: "bearer-token", token: "secret-token" },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(remote), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createMcpServer(bearerDraft)).resolves.toMatchObject({
      authentication: { type: "bearer-token", configured: true },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/mcp/servers",
      expect.objectContaining({ body: JSON.stringify(bearerDraft) }),
    );
  });

  it("rejects a server response that exposes a Bearer token", async () => {
    const unsafe = {
      ...server,
      authentication: {
        type: "bearer-token",
        configured: true,
        token: "must-not-be-returned",
      },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ servers: [unsafe] })),
    ));

    await expect(listMcpServers()).rejects.toMatchObject({
      code: "malformed_response",
    });
  });

  it("maps only fixed MCP errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "server_timeout", message: "private", retryable: true } }), { status: 504 })));
    const error = await startMcpServer(server.id).catch((value: unknown) => value);
    expect(error).toBeInstanceOf(McpApiError);
    expect(error).toMatchObject({ code: "server_timeout" });
  });
});
