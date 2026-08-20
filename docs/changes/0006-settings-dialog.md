# 0006 - Settings dialog

## Objective

直接重用現有設定內容，將設定從取代對話區的頁面切換改為不打斷工作內容的彈出視窗。

## Changes

- 移除 `settings` 的 App view 與 `#settings-general`、`#settings-models` hash 流程。
- 主內容始終保留目前的聊天工作區，開啟或關閉設定不會重建對話元件。
- 使用原生 modal dialog 承載同一個 `SettingsPage`，不複製設定分類、表單或狀態。
- 設定視窗支援關閉按鈕、Escape、背景點擊、焦點移入與關閉後焦點返回。
- 桌面使用置中的大型視窗；767 px 以下改為全螢幕設定介面，分類可水平捲動、內容獨立垂直捲動。
- 設定資料與目前分類仍由 `App` 管理，所有控制維持 Demo 本機狀態與自動儲存提示。

## Public impact

設定入口改為彈出視窗，不再改變 URL 或替換聊天畫面。沒有新增後端、HTTP、WebSocket、資料庫或持久化契約。

## Verification

- `npm run typecheck` 通過。
- `npm run build` 通過。
- Chrome 驗證桌面設定 dialog 可開啟、切換一般與 AI 模型、用 Escape 或關閉按鈕關閉。
- Chrome 驗證開啟與關閉設定後，未送出的聊天草稿與原本 chat hash 都保持不變。
- Chrome 驗證 390 px 使用 390 × 844 px 全螢幕設定介面，沒有水平 overflow。
- 桌面關閉後焦點返回設定入口；手機關閉後焦點返回可見的主選單按鈕。
- `git diff --check` 通過。

## Remaining work

- 設定內容仍為前端 Demo，不代表未來後端或儲存格式。
- 尚未加入持久化設定與自動化瀏覽器測試套件。
