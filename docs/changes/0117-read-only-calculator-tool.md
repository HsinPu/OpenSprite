# Read-only Calculator Tool

## Objective

加入 OpenSprite 第一個 production Tool，驗證既有 Provider tool calling、Tool Registry、Agent loop、Run event 與前端執行紀錄的完整路徑，同時維持唯讀與最小權限。

## Changes

- 新增明確註冊的 `calculator` built-in Tool。
- 使用 Python AST 白名單與 Decimal 運算，只接受有限算術，不使用 `eval`、shell、網路、檔案或秘密。
- 限制運算式長度、AST 節點與深度、指數、數值範圍、timeout 與輸出長度。
- 新增 production Tool Registry composition，runtime 只透過該 composition 註冊 Calculator。
- 保留既有 strict input schema、ReadOnlyToolPolicy、取消、ToolResult 與 `tool.started/completed/failed` event 契約。
- 明確指定 OpenRouter 模型且帶 Tools 時設定 `provider.require_parameters=true`；`openrouter/auto` 交由 Auto Router 依請求能力選擇上游，避免額外篩選造成請求失敗。
- Provider 請求失敗時只記錄 HTTP status 或例外類型，不記錄 response body、Prompt、headers、URL 或金鑰。
- 前端以穩定 Tool ID 將 Calculator 顯示為繁中、英文與日文名稱；未知 Tool ID 仍回退顯示原始名稱。

## Public impact

模型現在可以在一般 Agent Run 中呼叫 Calculator。沒有新增 HTTP API、設定欄位、SQLite migration、credential、MCP、動態 plugin discovery 或寫入權限。

## Verification

- Calculator、Tool Registry 與 Agent loop focused backend tests：25 passed。
- Backend full pytest with warnings as errors：514 passed, 2 skipped。
- Frontend Vitest：25 個測試檔、200 tests passed。
- Frontend typecheck 與 production build：passed；保留既有 Vite single-chunk advisory。
- Backend compileall、offline lock check 與 dependency check：passed。

## Remaining work

本切片不加入 Tool 啟用開關、Local file、Search、MCP、外部連線或任何寫入型 Tool。具有副作用的 Tool 必須先建立獨立的人工批准與操作 receipt 流程。
