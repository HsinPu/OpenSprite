import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import { App } from "../../src/app/App";
import { I18nProvider } from "../../src/i18n/I18nProvider";
import "../../src/app/app.css";

// All requests are intercepted; this fixture cannot reach installed user data.
const id = "00000000-0000-4000-8000-000000000000";
window.fetch = async (input) => {
  const url = String(input);
  let body: unknown = {};
  if (url === "/api/workspaces") body = { revision: 1, activeWorkspaceId: id, workspaces: [{ id, kind: "default", name: "Default workspace", directoryName: "default", rootPath: "C:/fixture/default", mounts: [], availability: "available", unavailableReason: null, revision: 1, createdAt: "2026-09-10T00:00:00Z", updatedAt: "2026-09-10T00:00:00Z", usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 } }] };
  else if (url.startsWith("/api/conversations?")) body = { conversations: [], nextCursor: null };
  else if (url === "/api/settings/conversation") body = { startupView: "new", sendBehavior: "enter", autoScroll: true, executionPanelDefaultExpanded: false };
  else if (url === "/api/settings/general") body = { locale: "zh-TW", timeZone: "system" };
  else if (url === "/api/providers") body = { providers: ["openai", "anthropic", "openrouter"].map(id => ({ id, name: id, connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null })) };
  else if (url.includes("/subagents")) body = { subagents: [], nextCursor: null };
  else return new Response(JSON.stringify({ error: { code: "internal_error", message: "fixture", retryable: false } }), { status: 503 });
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
};
createRoot(document.getElementById("root")!).render(<ConfigProvider theme={{ token: { colorPrimary: "#ff6545", borderRadius: 12 } }}><I18nProvider><App /></I18nProvider></ConfigProvider>);
