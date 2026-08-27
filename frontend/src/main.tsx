import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import enUS from "antd/locale/en_US";
import jaJP from "antd/locale/ja_JP";
import zhTW from "antd/locale/zh_TW";

import { App } from "./app/App";
import { I18nProvider, useI18n } from "./i18n/I18nProvider";
import "./app/app.css";

const antdLocales = { "zh-TW": zhTW, en: enUS, ja: jaJP } as const;

function LocalizedConfig({ children }: { children: ReactNode }) {
  const { locale } = useI18n();
  return (
    <ConfigProvider
      locale={antdLocales[locale]}
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
      {children}
    </ConfigProvider>
  );
}

const root = document.getElementById("root");

if (!root) {
  throw new Error("OpenSprite root element was not found.");
}

createRoot(root).render(
  <StrictMode>
    <I18nProvider>
      <LocalizedConfig>
        <App />
      </LocalizedConfig>
    </I18nProvider>
  </StrictMode>,
);
