# Agent Loop 與執行策略插件化

- 版本：`0.21.26` → `0.21.27`。
- 分支：`codex/agent-loop-plugins`。
- 目標：工作臺可選擇 Agent Loop 與執行策略，主代理及子代理共用可替換 Driver 契約，保留核心核准、取消及限制。

## 實作

- StandardDriver 與 Run-local ExecutionHost 分離，核心保留模型、工具及 Run 持久化；拒絕未結算 turn、偽造結果、重播操作及插件冒用核心例外或取消訊號。
- 受信任 Python entry point 插件 metadata discovery、API v1 相容性與 ID 衝突檢查；內建 standard loop 和 standard／no_recovery 策略。
- 新接受任務固定插件選擇，子代理沿用同一 binding、取得新 Driver；執行開始記錄版本事件。
- 新增契約、原子設定持久化與 Ant Design 執行方式頁面；歷史記錄顯示執行插件。
- SQLite schema 19 → 20 在單一交易中更新 run_events 事件約束，保留既有資料；失敗時回滾。新增 `GET/PUT /api/settings/execution` 與 `execution.selected` 事件契約。
- 詳細邊界及開發契約見 `docs/architecture/agent-execution-plugins.md`。

## 驗證

2026-10-07 完成以下驗證：

- `docker build --target backend-test -t opensprite:execution-plugins-backend-tested .`：`pytest -W error` 共 **1,340 passed**；`compileall`、`uv lock --check --offline`、`uv pip check` 通過。
- `docker build --target frontend-test -t opensprite:execution-plugins-frontend-tested .`：67 個測試檔、**604 passed**；`tsc --noEmit` 通過。前端建置階段使用 `npm ci --ignore-scripts` 與 `npm run build`，成功產生正式資產。
- 提交前以唯讀掛載目前 `backend/`、停用網路的 Docker 容器再執行 `uv lock --check --offline`：通過；三處產品版本一致為 `0.21.27`。
- 替換測試使用真實 Python distribution metadata 與另一個 Driver，驗證延遲載入、API 不相容、ID 碰撞、主／子代理綁定、設定變更不影響已接受任務、idempotency replay、取消、核准與模型硬限制。Migration 測試驗證歷史保留、事件驗證與交易回滾。
- 最終 runtime 映像 `opensprite:execution-plugins-preview` SHA-256：`70544793983329fc755b4672cdb8e9e3a3c0e5c8998c7a40b5310ee6c7c389f7`。獨立 Compose project `opensprite-loop-plugins` 與獨立資料 volume，預覽 `http://localhost:18767`；容器 healthy、`/healthz` 回傳 `ok`、`/api/app-info` 回傳 `0.21.27`。
- 使用本機無憑證模擬 Provider，透過真實工作臺送出任務。標準策略 Run `cf6a5439-4e83-4157-a917-9c0109577f89`：2 次模型呼叫、1 次續寫、`completed / stop`，回覆兩段。`no_recovery` Run `308b4d0c-2a81-43a9-825e-af97ae6a3756`：1 次模型呼叫、0 次續寫、`completed / output_limit`，保留第一段；兩次歷史事件均記錄正確插件 ID 與版本，改設定後前次歷史不變。
- Chrome 實際檢查桌面 1864×901、平板 768×1024、手機 390×844：設定導覽、選擇、儲存、重新載入持久化、對話送出及執行詳細資訊可操作，無水平溢出；完成後還原瀏覽器尺寸。檢查未發現應用程式 console error/warning。桌面設定內容寬 720px、平板 480px、手機 358px。
- 專用驗證紀錄保留在忽略的 `tmp/execution-plugins-backend-tests-final.log`、`tmp/execution-plugins-frontend-tests-final-pass.log`、`tmp/execution-plugins-smoke.json`；桌面／平板／手機截圖位於此次 Codex visualization 目錄。測試資料、模擬 Provider 與容器資料不提交。

此階段提供受信任、程序內的 Loop／策略擴充介面；外部插件需預先安裝在應用程式環境或 Docker 映像。預覽保留測試用 `no_recovery` 選擇。本次於新分支交付，未合併 main。
