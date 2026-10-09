# 核心停止原因與限制證據

- 版本：`0.21.35` → `0.21.36`。
- 唯一目標：將核心限制原因及有效上限／已用量保存並顯示，不改變 Loop 策略或公開 Host API v5。
- 分支：`codex/core-runtime-hardening`，起點 `e88e34f73f3a30433b597c0258a6da6fdcea91aa`。
- 日期：2026-10-09（Asia/Taipei）。

## 行為

期限、模型請求、摘要請求、生成字元與 Host 操作各有固定公開錯誤碼。`run.failed` 可攜帶 `limit: {kind, maximum, used}`，與失敗狀態在同一 SQLite 交易保存。時間單位為秒；其他為已接受的整數計數，拒絕的下一次請求／操作／完整文字 delta 不計入。既有上限不變，重試、摘要、續寫共用 Run 上限。

HTTP 契約、錯誤白名單、步驟事件、三語提示、前端嚴格 parser 及既有診斷抽屜同步。診斷匯出只接受結構完整且原因相符的限制證據。舊 `agent_limit_reached` 可讀，沒有可用證據時不補造細分原因或計數。

Host 對自己發出的例外保存身分與內容簽章，包含限制證據；已登記物件不能重新簽章，避免插件修改錯誤後再次 checkpoint 取得認可。`PublicRunError` 仍只有 code／message／retryable，SDK factory 與資料欄位不變。

## 驗證

- 原生後端聚焦回歸：**88 passed**，包含真 SQLite 的五種限制、拒絕請求不送出、持久化重讀、摘要共用上限、舊紀錄及例外防偽。
- 原生前端：**4 files / 50 passed**，包含全部五種事件、錯誤欄位／單位／原因不符拒絕、診斷抽屜呈現及匯出。
- TypeScript 與 Vite 正式 build 通過；既有大型 chunk 提示仍存在。
- 作者來源 ZIP 已重新產生（8 檔、33,880 bytes），與架構文件一致。
- `uv lock --check --offline` 及 `git diff --check` 通過。

完整跨階段回歸、實際瀏覽器與隔離 Docker／故障驗證記錄於此目標最後階段；本階段未替換正式服務。
