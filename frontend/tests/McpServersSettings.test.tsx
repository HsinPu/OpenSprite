import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { McpServerSummary } from "../src/api/mcpConnections";
import { McpServersSettings } from "../src/features/settings/McpServersSettings";
import type { McpConnectionsController } from "../src/features/mcp-settings/useMcpConnections";
import type { ToolSettingsController } from "../src/features/tool-settings/useToolSettings";
import { I18nProvider } from "../src/i18n/I18nProvider";


const toolSettings: ToolSettingsController = {
  catalog: { items: [] },
  settings: { enabled: true, enabledTools: [] },
  loaded: true,
  saving: false,
  error: null,
  saveEnabled: async () => null,
  saveToolEnabled: async () => null,
  reload: async () => undefined,
};

afterEach(() => vi.unstubAllGlobals());

function controller(overrides: Partial<McpConnectionsController> = {}): McpConnectionsController {
  return {
    servers: [], tools: {}, loaded: true, error: null, busyServerId: null,
    reload: async () => undefined,
    create: async () => null,
    update: async () => null,
    remove: async () => null,
    test: async () => null,
    start: async () => null,
    stop: async () => null,
    loadTools: async () => null,
    ...overrides,
  };
}

const server: McpServerSummary = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Local Echo",
  enabled: false,
  startOnLaunch: false,
  transport: {
    type: "stdio",
    executable: "C:\\Python312\\python.exe",
    arguments: ["-m", "echo_server"],
    workingDirectory: null,
  },
  authentication: { type: "none" },
  status: "disabled",
  protocolVersion: null,
  errorCode: null,
  toolCount: 0,
  unsupportedToolCount: 0,
};

function renderSettings(value: McpConnectionsController) {
  return render(<I18nProvider><McpServersSettings controller={value} toolSettings={toolSettings} /></I18nProvider>);
}

describe("McpServersSettings", () => {
  it("requires a second confirmation that exposes the exact command before saving", async () => {
    const create = vi.fn(async () => null);
    renderSettings(controller({ create }));

    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));
    expect(screen.getByRole("switch", { name: "OpenSprite 啟動時自動啟動或連線" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.change(await screen.findByLabelText("顯示名稱"), { target: { value: "Local Echo" } });
    fireEvent.change(screen.getByLabelText("Executable 絕對路徑"), { target: { value: "C:\\Python312\\python.exe" } });
    fireEvent.change(screen.getByLabelText("Arguments（每行一個）"), { target: { value: "-m\necho_server" } });
    fireEvent.click(screen.getByRole("button", { name: /繼\s*續/ }));

    const confirmation = (await screen.findByText("確認 MCP Server 設定")).closest("[role='dialog']") as HTMLElement;
    expect(confirmation).toBeTruthy();
    expect(create).not.toHaveBeenCalled();
    expect(within(confirmation).getByText(/C:\\Python312\\python\.exe/)).toBeTruthy();
    expect(within(confirmation).getByText(/-m/)).toBeTruthy();
    fireEvent.click(within(confirmation).getByRole("button", { name: /儲\s*存\s*設\s*定/ }));

    await waitFor(() => expect(create).toHaveBeenCalledWith({
      name: "Local Echo",
      startOnLaunch: true,
      transport: {
        type: "stdio",
        executable: "C:\\Python312\\python.exe",
        arguments: ["-m", "echo_server"],
        workingDirectory: null,
      },
      authentication: { type: "none" },
    }));
  });

  it("does not start a configured process before explicit command confirmation", async () => {
    const start = vi.fn(async () => null);
    renderSettings(controller({ servers: [server], start }));

    fireEvent.click(screen.getByRole("button", { name: /啟\s*動/ }));
    const confirmation = await screen.findByRole("dialog", { name: "確認啟動 MCP Server" });
    expect(start).not.toHaveBeenCalled();
    expect(confirmation.textContent).toContain("C:\\Python312\\python.exe");
    fireEvent.click(within(confirmation).getByRole("button", { name: /啟\s*動/ }));
    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    expect(start).toHaveBeenCalledWith(server.id);
  });

  it("switches to a network-only form and confirms the exact endpoint", async () => {
    const create = vi.fn(async () => null);
    renderSettings(controller({ create }));

    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));
    fireEvent.change(await screen.findByLabelText("顯示名稱"), { target: { value: "Remote MCP" } });
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "連線方式" }));
    fireEvent.click((await screen.findByText("網路位址")).closest(".ant-select-item-option")!);
    await screen.findByLabelText("MCP Endpoint URL");
    expect(screen.queryByLabelText("Executable 絕對路徑")).toBeNull();
    fireEvent.change(screen.getByLabelText("MCP Endpoint URL"), { target: { value: "https://mcp.example.com/mcp" } });
    fireEvent.click(screen.getByRole("button", { name: /繼\s*續/ }));

    const confirmation = (await screen.findByText("確認 MCP Server 設定")).closest("[role='dialog']") as HTMLElement;
    expect(confirmation.textContent).toContain("https://mcp.example.com/mcp");
    expect(confirmation.textContent).toContain("請勿將 Token、密碼或其他憑證放入 URL");
    fireEvent.click(within(confirmation).getByRole("button", { name: /儲\s*存\s*設\s*定/ }));

    await waitFor(() => expect(create).toHaveBeenCalledWith({
      name: "Remote MCP",
      startOnLaunch: true,
      transport: { type: "streamable-http", url: "https://mcp.example.com/mcp" },
      authentication: { type: "none" },
    }));
  });

  it("saves a Bearer token without exposing it in confirmation", async () => {
    const create = vi.fn(async () => null);
    renderSettings(controller({ create }));

    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));
    fireEvent.change(await screen.findByLabelText("顯示名稱"), { target: { value: "Protected MCP" } });
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "連線方式" }));
    fireEvent.click((await screen.findByText("網路位址")).closest(".ant-select-item-option")!);
    fireEvent.change(screen.getByLabelText("MCP Endpoint URL"), { target: { value: "https://mcp.example.com/mcp" } });
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "認證方式" }));
    fireEvent.click((await screen.findByText("Bearer Token")).closest(".ant-select-item-option")!);
    fireEvent.change(screen.getByPlaceholderText("輸入 Token"), { target: { value: "secret-token-value" } });
    fireEvent.click(screen.getByRole("button", { name: /繼\s*續/ }));

    const confirmation = (await screen.findByText("確認 MCP Server 設定")).closest("[role='dialog']") as HTMLElement;
    expect(confirmation.textContent).not.toContain("secret-token-value");
    expect(confirmation.textContent).toContain("請勿將 Token、密碼或其他憑證放入 URL");
    fireEvent.click(within(confirmation).getByRole("button", { name: /儲\s*存\s*設\s*定/ }));

    await waitFor(() => expect(create).toHaveBeenCalledWith({
      name: "Protected MCP",
      startOnLaunch: true,
      transport: { type: "streamable-http", url: "https://mcp.example.com/mcp" },
      authentication: { type: "bearer-token", token: "secret-token-value" },
    }));
  });

  it("preserves an existing Bearer token when the edit field stays blank", async () => {
    const update = vi.fn(async () => null);
    const protectedServer: McpServerSummary = {
      ...server,
      transport: { type: "streamable-http", url: "https://mcp.example.com/mcp" },
      authentication: { type: "bearer-token", configured: true },
    };
    renderSettings(controller({ servers: [protectedServer], update }));

    fireEvent.click(screen.getByRole("button", { name: /編\s*輯/ }));
    expect(screen.getByRole("switch", { name: "OpenSprite 啟動時自動啟動或連線" }).getAttribute("aria-checked")).toBe("false");
    const token = await screen.findByPlaceholderText("留空以保留目前的 Token");
    expect(token.getAttribute("placeholder")).toBe("留空以保留目前的 Token");
    fireEvent.click(screen.getByRole("button", { name: /繼\s*續/ }));
    const confirmation = (await screen.findByText("確認 MCP Server 設定")).closest("[role='dialog']") as HTMLElement;
    fireEvent.click(within(confirmation).getByRole("button", { name: /儲\s*存\s*設\s*定/ }));

    await waitFor(() => expect(update).toHaveBeenCalledWith(
      protectedServer.id,
      expect.objectContaining({
        authentication: { type: "bearer-token", token: null },
      }),
    ));
  });

  it("fills executable and directory fields from the native picker", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ path: "C:\\Tools\\server.exe" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ path: "C:\\Tools" })));
    vi.stubGlobal("fetch", fetchMock);
    renderSettings(controller());

    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));
    fireEvent.click(await screen.findByRole("button", { name: /瀏覽執行檔/ }));
    await waitFor(() => expect((screen.getByLabelText("Executable 絕對路徑") as HTMLInputElement).value).toBe("C:\\Tools\\server.exe"));
    fireEvent.click(screen.getByRole("button", { name: /瀏覽資料夾/ }));
    await waitFor(() => expect((screen.getByLabelText("工作目錄（選填）") as HTMLInputElement).value).toBe("C:\\Tools"));
  });

  it("keeps manual input when native selection is cancelled", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    renderSettings(controller());

    fireEvent.click(screen.getByRole("button", { name: "新增 MCP Server" }));
    const input = await screen.findByLabelText("Executable 絕對路徑") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "C:\\Manual\\server.exe" } });
    fireEvent.click(screen.getByRole("button", { name: /瀏覽執行檔/ }));
    await waitFor(() => expect(input.value).toBe("C:\\Manual\\server.exe"));
  });
});
