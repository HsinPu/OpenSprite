# OpenSprite Frontend

React、TypeScript、Ant Design 與 Vite 實作的 Agent 工作臺。模型連線、設定與對話透過同源 HTTP／SSE 連接本機服務，契約位於 [`../contracts/`](../contracts/README.md)。

## 本機開發

需要 Node.js `^20.19.0` 或 `>=22.12.0`。從本目錄執行：

```powershell
npm ci --ignore-scripts
npm run dev -- --host 127.0.0.1 --port 4173 --strictPort
```

另依 [後端說明](../backend/README.md) 在 `127.0.0.1:8765` 啟動 API。Vite 的 dev／preview proxy 轉送 `/api`，使用 `changeOrigin: false` 保留瀏覽器 Host／Origin；設定與金鑰不放入 localStorage 或網址。

## 工作流程

- 主導覽提供 AI 模型與設定，工作區選單切換對話範圍。
- `/#new-chat` 開啟空白對話；`/#chat=<uuid>` 保留已選對話，重新整理讀取持久化資料。
- 文字回覆由 SSE 更新，終止後重新讀取 Run／Message。可取消、查看本次或歷史執行；文字核心不提供工具操作。
- 設定提供一般、工作區、AI 模型、執行方式、隱私與關於。記憶及外觀是明確停用的 Demo。
- 執行方式使用 API v2，選擇先成為草稿，套用後才影響新任務。wheel 匯入不代表已安裝；部署後須核對 runtime 狀態。
- 繁中／英文／日文、時區、啟動目的地、Enter 或 Ctrl/Cmd + Enter 傳送、自動跟隨及面板偏好由後端保存。IME 組字不傳送。

「一次回答」只改變呈現，上游仍串流。Provider 金鑰只存在於密碼欄位的暫存狀態，送出、錯誤、取消或卸載時清除，不預填原始值。讀取設定失敗時提供重試，不以假預設覆寫已保存資料。

## 原始碼

| 目錄 | 職責 |
| --- | --- |
| `src/app/` | 工作臺組裝、導覽與面板 |
| `src/api/` | 型別化 HTTP／SSE client 與回應驗證 |
| `src/features/chat/` | 訊息、執行診斷、取消與歷史 |
| `src/features/settings/` | 設定、Loop／策略與 wheel 工作臺 |
| `src/features/*-settings/` | 持久化設定 controller |
| `src/i18n/` | 三語系 catalog 與 locale context |
| `tests/` | Vitest、React Testing Library 與瀏覽器檢查素材 |

Tools、Skills、Subagents、MCP 與排程的介面及 API client 已移除，不提供停用的舊入口。UI 變更遵守根目錄 [AGENTS.md](../AGENTS.md) 的設計與響應式檢查要求。

## 驗證

```powershell
npm test -- --run
npm run typecheck
npm run build
```

元件測試涵蓋載入／錯誤、保存、取消、焦點、鍵盤與非同步競爭；仍須啟動實際同源環境，檢查桌面、平板與手機畫面、console 與操作流程。
