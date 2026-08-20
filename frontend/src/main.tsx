import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";

import { App } from "./app/App";
import "./app/app.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("OpenSprite root element was not found.");
}

createRoot(root).render(
  <StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#ff6545",
          colorSuccess: "#18a77b",
          colorText: "#202124",
          colorTextSecondary: "#6f7278",
          colorBorder: "#e5e3df",
          borderRadius: 12,
          fontFamily:
            'Inter, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif',
        },
        components: {
          Button: { controlHeight: 42 },
          Select: { controlHeight: 44 },
          Switch: { colorPrimary: "#ff6545" },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
);
