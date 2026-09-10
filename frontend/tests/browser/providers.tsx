import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import { CustomProviderCreate } from "../../src/features/settings/CustomProviderCreate";
import { I18nProvider } from "../../src/i18n/I18nProvider";
import "../../src/app/app.css";

const fixture = {
  id: "11111111-1111-4111-8111-111111111111", name: "Local compatible provider", revision: 1,
  protocol: "openai_chat_completions", base_url: "http://127.0.0.1:11434/v1", auth_mode: "none",
  allow_insecure_local: true, created_at: "2026-09-10T00:00:00+00:00", updated_at: "2026-09-10T00:00:00+00:00",
  models: [{ key: "22222222-2222-4222-8222-222222222222", model_id: "local-model", name: "Local model",
    context_limit: 8192, output_limit: 2048, tools: false, source: "manual" }],
};
window.fetch = async (input, options) => {
  const path = String(input);
  if (path === "/api/providers/catalog") return Response.json({ revision: 1, providers: [fixture], nextCursor: null });
  if (options?.method === "POST" || options?.method === "PUT" || options?.method === "DELETE") {
    return Response.json({ error: { code: "provider_busy", message: "Safe fixture error", retryable: false } }, { status: 409 });
  }
  throw new Error(`Unexpected fixture request: ${path}`);
};
createRoot(document.getElementById("root")!).render(<I18nProvider>
  <ConfigProvider theme={{ token: { colorPrimary: "#ff6545", borderRadius: 12 } }}>
    <main style={{ maxWidth: 820, margin: "20px auto", padding: 16 }}>
      <h1>自訂 Provider · 隔離測試</h1>
      <CustomProviderCreate onChanged={async () => undefined} container={null} hasCustomProviders />
    </main>
  </ConfigProvider>
</I18nProvider>);
