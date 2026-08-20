import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiProxy = {
  target: "http://127.0.0.1:8765",
  changeOrigin: false,
};

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": apiProxy } },
  preview: { proxy: { "/api": apiProxy } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
});
