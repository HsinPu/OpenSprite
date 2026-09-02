# Tool Management Settings

## Objective

將設定中的 Demo「工具與連線」改為可操作的獨立「工具」頁。

## Changes

- 新增全域工具開關與 Calculator 個別開關。
- 顯示工具來源、權限效果、可用狀態與本地化說明。
- 儲存成功後才套用確認值；失敗保留舊值，快速操作採序列化保存。
- 繁中、英文、日文將分類統一命名為「工具」。
- MCP、自訂工具與第三方服務保留為不可操作的未來項目。

## Public impact

設定頁現在能管理新 Run 的工具可用性。既有對話、歷史 Run 與工具事件不會因停用而刪除。

## Verification

- 工具 API、Hook、設定頁與 App 聚焦 Vitest：4 files、55 tests passed。
- TypeScript typecheck 通過。
- Frontend 完整 Vitest：27 files、209 tests passed。
- Frontend production build：passed；保留既有 Vite single-chunk advisory。
- 本機安裝版瀏覽器驗證：全域與 Calculator 開關可保存；停用 Run 不提供工具，重新啟用後 Calculator 成功執行並回覆正確結果。

## Remaining work

外部工具、連線憑證、細部權限、人工批准與操作 receipt 尚未實作。
