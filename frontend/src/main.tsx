import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import enUS from "antd/locale/en_US";
import jaJP from "antd/locale/ja_JP";
import zhTW from "antd/locale/zh_TW";

import { App } from "./app/App";
import { AuthGate } from "./features/auth/AuthGate";
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
          colorPrimary: "#087f8c",
          colorSuccess: "#18a77b",
          colorText: "#25313e",
          colorTextSecondary: "#687787",
          colorBorder: "#dce3e9",
          borderRadius: 6,
          fontFamily:
            'Inter, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif',
        },
        components: {
          Button: { controlHeight: 32 },
          Select: { controlHeight: 32 },
          Switch: { colorPrimary: "#087f8c" },
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
        <AuthGate><App /></AuthGate>
      </LocalizedConfig>
    </I18nProvider>
  </StrictMode>,
);
