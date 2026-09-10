import { fireEvent, render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it, vi } from "vitest";
import { ToolsSettings } from "../src/features/settings/ToolsSettings";
import type { ToolSettingsController } from "../src/features/tool-settings/useToolSettings";
import type { McpConnectionsController } from "../src/features/mcp-settings/useMcpConnections";
import { I18nProvider, useI18n } from "../src/i18n/I18nProvider";
import type { Locale } from "../src/i18n/catalog";

const tools: ToolSettingsController = {
  catalog: { items: [] }, settings: { enabled: false, enabledTools: ["calculator"] },
  loaded: true, saving: false, error: null, reload: vi.fn(async () => undefined),
  saveEnabled: vi.fn(async () => null), saveToolEnabled: vi.fn(async () => null),
};
const mcp: McpConnectionsController = {
  servers: [], tools: {}, loaded: true, error: null, busyServerId: null,
  reload: async () => undefined, create: async () => null, update: async () => null,
  remove: async () => null, test: async () => null, start: async () => null,
  stop: async () => null, loadTools: async () => null,
};
function Localized({ locale }: { locale: Locale }) {
  const { setLocale } = useI18n();
  useEffect(() => setLocale(locale), [locale, setLocale]);
  return <ToolsSettings controller={tools} mcpConnections={mcp} />;
}
describe("tools settings layout", () => {
  it.each([
    ["zh-TW", "內建工具", "MCP 連線", "規劃中功能"],
    ["en", "Built-in tools", "MCP connections", "Planned features"],
    ["ja", "内蔵ツール", "MCP 接続", "今後の機能"],
  ] as const)("groups settings and collapses planned features in %s", (locale, builtin, connections, planned) => {
    render(<I18nProvider><Localized locale={locale} /></I18nProvider>);
    expect(screen.getByRole("heading", { name: builtin })).toBeTruthy();
    expect(screen.getByRole("heading", { name: connections })).toBeTruthy();
    expect(screen.getByRole("status")).toBeTruthy();
    expect(screen.getByRole("button", { name: planned }).getAttribute("aria-expanded")).toBe("false");
  });
  it("changes only the global flag without discarding individual settings", () => {
    render(<ToolsSettings controller={tools} mcpConnections={mcp} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(tools.saveEnabled).toHaveBeenCalledWith(true);
    expect(tools.settings.enabledTools).toEqual(["calculator"]);
    expect(tools.saveToolEnabled).not.toHaveBeenCalled();
  });
});
