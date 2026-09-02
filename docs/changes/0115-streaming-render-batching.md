# 0115 - Streaming render batching

## Objective

降低長回覆串流時的前端重繪成本，避免每個 assistant delta 都同步觸發整個聊天工作區更新，同時維持原有 SSE、事件順序、自動滾動與回覆呈現模式。

## Changes

- `useConversationRun` 將高頻 `assistant.delta` 事件與串流文字排入同一個 animation-frame queue；非 delta 語意事件會先 flush，終端事件會立即提交完整文字。
- 對話切換、重新載入、卸載與關閉串流時清除待處理 frame，避免舊對話的延遲更新污染目前畫面。
- `ChatWorkspace` 對固定歷史 Markdown 訊息使用 memoized renderer，並 memoize provider model choice 分組；串流中的訊息仍會隨新內容更新。
- 新增 hook 回歸測試，證明連續 delta 會合併成單一畫面更新，並保留 complete delivery 與 terminal refresh 行為。
- 更新 `docs/architecture/agent-chat.md` 與 `docs/architecture/overview.md`。

## Public impact

沒有修改 HTTP、SSE、SQLite、Provider、Run event payload 或設定契約。使用者仍可選擇 stream／complete；stream 模式只調整畫面更新節奏，complete 模式仍在終端事件顯示完整回覆。

## Verification

- Frontend Vitest：25 個測試檔、199 tests passed（分批執行）。
- Frontend `npm run typecheck`：passed。
- Frontend `npm run build`：passed；保留既有 Vite single-chunk 約 938 kB advisory。
- 瀏覽器本機驗證：390px 顯示手機執行按鈕、右側 Drawer 開啟且無水平溢位；1440px 顯示桌面執行控制、手機按鈕隱藏且無水平溢位。
- `git diff --check`：passed。

## Remaining work

本切片不加入虛擬列表、網路請求取消、設定頁 code splitting 或新的瀏覽器測試依賴；這些維持後續獨立切片，避免擴大目前變更範圍。
