import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// Real UI with deterministic transport substitutes; never connects to user data.
export default defineConfig({
  plugins: [react(), {
    name: "isolated-chat-hooks",
    enforce: "pre",
    resolveId(source, importer) {
      if (importer?.endsWith("/ChatWorkspace.tsx") && ["./useConversationRun", "./useRunInspection"].includes(source)) {
        return fileURLToPath(new URL("./chatHooks.ts", import.meta.url));
      }
    },
  }],
  server: { host: "127.0.0.1", port: 8877, strictPort: true },
});
