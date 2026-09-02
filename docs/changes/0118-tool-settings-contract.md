# Tool Settings Contract

## Objective

建立獨立、可持久化的 production Tool 目錄與可用性設定，讓工具是否提供給模型不再是固定行為。

## Changes

- 新增 `GET /api/tools` 與 `GET/PUT /api/settings/tools`。
- 新增 strict schema-v1 `config/tools.json`、1 MiB 上限、duplicate key 拒絕與 atomic write。
- 新增 `AppPaths.tool_settings_file`，缺少設定檔時預設啟用 Calculator 且讀取不建立目錄。
- 每個 Run 取得一次工具可用性快照；模型廣告與 Registry 執行共同使用該快照。
- `model.started` event 記錄本輪提供的工具 ID，不記錄參數、結果或秘密。
- 同步更新 Agent Chat OpenAPI 與前端 strict event parser，保留既有 legacy event 相容性。

## Public impact

新增工具目錄與工具設定 HTTP contract。沒有 SQLite migration、credential、CLI、環境變數或 browser storage。

## Verification

- Tool settings、Registry、Agent loop 與 SQLite 聚焦測試：82 passed。
- Tool settings OpenAPI 靜態契約測試通過。
- Backend 完整 pytest：537 passed、2 skipped。
- Backend compileall、offline lock check 與 dependency check：passed。
- 瀏覽器驗證曾捕捉 `toolNames` producer／consumer 不一致；修正後停用與重新啟用 Run 均可正常讀取事件。

## Remaining work

本切片不加入 MCP、外部連線、動態 Plugin 或有副作用工具的人工批准。
