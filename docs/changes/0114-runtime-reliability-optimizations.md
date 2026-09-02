# 0114 - Runtime reliability and context-flow optimizations

## Objective

修正目前前後端檢視到的三類執行可靠性問題：快速連續保存設定時避免新值互相覆蓋、長對話可依 token 預算持續壓縮，以及降低串流文字寫入 SQLite 與 SSE 空輪詢成本。

## Changes

- AI、General、Conversation 三組前端設定 hook 各自維護已確認值與最新意圖值；連續保存會在最新意圖上合併欄位，失敗時回復最後一次確認的完整 snapshot。
- Agent Context 以 200 則作為 repository page size，正常執行不再固定最多 8 批 compaction；會持續讀取與壓縮到 token 預算能覆蓋必要的最近訊息，Provider context retry 仍維持一次額外壓縮的安全界線。
- Agent 將快速收到的 assistant text delta 以約 4K 字元批次落盤，並在模型回合、工具事件、完成、錯誤與取消前 flush；SQLite schema、事件順序與 partial text 語意不變。
- 新增程序內 `RunEventNotifier`。SQLite transaction commit 後通知 SSE consumer；有通知時立即 replay 新事件，閒置時不再每 50ms 查詢 SQLite，保留 bounded fallback wait 以容忍未經 notifier 的外部寫入。
- 更新 `docs/architecture/agent-chat.md`，記錄 Context page、delta flush 與 notifier 的責任邊界。

## Public impact

沒有新增或修改 HTTP／SSE payload、SQLite schema、Provider、憑證、Context budget enum 或前端可見設定欄位。Run event 仍以 durable sequence replay，重新連線與 `Last-Event-ID` 行為不變。

## Verification

- Backend full pytest with warnings as errors and workspace-local basetemp：495 passed, 2 skipped。
- Frontend Vitest：25 test files, 198 tests passed（分批執行以符合本機測試時間上限）。
- Frontend `npm run typecheck`：passed。
- Frontend `npm run build`：passed；保留既有 Vite single-chunk >500 kB advisory。
- Backend `python -m compileall -q src tests`：passed。

## Remaining work

這是單一程序本機 runtime 的可靠性與效能修正；沒有新增多程序同步、跨程序 broker、tokenizer billing 精算或 HTTP contract migration。
