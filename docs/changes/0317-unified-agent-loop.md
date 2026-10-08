# 單一 Agent Loop 插件、設定與部署

- 版本：`0.21.32` → `0.21.33`。
- 目標：將可替換 Loop 與恢復策略合成一個完整插件，更新執行方式、wheel 匯入與作者指南，驗證後 commit／push 新分支。
- 起點：`main` 的 `a1ac4cede66e414ef66aebead006e3b688bb772d`；工作分支 `codex/unified-agent-loop`。
- 完成驗證日期：2026-10-09（Asia/Taipei）。

## 實作

- 新公開契約 `opensprite_backend.agent.plugin`：一個 Run-local 實例實作 async `execute(host)` 與同步 `allow_context_retry`、`allow_output_continuation`；一個 factory `create()` 建立完整實例。唯一執行 entry point group 為 `opensprite_backend.agent_loops.v3`。
- 移除原 driver／standard_driver／strategies 模組與雙選擇契約。內建 `standard` 與 `no_recovery` 均使用新契約；外部範例 `example_main_retry_only` wheel 升級至 `0.3.0`。
- 設定與目錄只讀 metadata，接受新 Run 時才解析 factory。同一實例負責執行及恢復判斷；核心 Host 保留 Provider、上下文、預算、重試上限、續寫上限、SSE、取消和持久化權限。未增加工具、Skills、Subagent、MCP、排程或任意多回合規劃。
- 新 Run 的 `execution.selected` 使用單一 `pluginId`／`pluginVersion`／`apiVersion: 3`，與接受 Run 在同一 SQLite transaction 中保存。相同 clientRequestId 重送先讀原 Run，不重新綁定或呼叫模型。
- `config/execution.json` 使用 schema 2 與 `expectedRevision`：並行寫入衝突回傳 409。舊內建組合自動原子遷移；舊外部組合保留原檔並提示明確選擇 API v3，阻止未完成遷移的新 Run。API v2 原始歷史事件保留及可讀，不提供舊版執行轉接。
- 執行方式使用單一緊湊插件表格與已保存摘要，保留草稿／取消／套用、詳情、安裝和開發說明。衝突保留草稿，重新讀取後才可套用；繁中／英文／日文文案同步。
- 新 wheel 匯入只接受 pure-Python API v3，維持 metadata／RECORD／相依套件與路徑檢查。新快取與 manifest schema 2，舊 cache schema 1 仍唯讀可用；舊 API wheel 顯示 `needs_update`，不能下載部署包。
- 補上錯誤 async factory／create 的拒絕與 coroutine 關閉，避免未 await 警告；恢復判斷要求真正 bool，異常與自行取消均遮蔽插件私有訊息。作者指南、契約、README、實際範例、ZIP 與安裝驗證腳本同步。

## 自動與部署驗證

- 最終後端 Docker test target：`pytest -W error` **1,012 passed**；compileall、`uv lock --check --offline`、`uv pip check` 通過，29 個安裝套件相容。輸出：本機 `tmp/unified-backend-full.log`。
- 前端 Docker test target：50 個檔案、**457 passed**，TypeScript 與正式 build 通過。輸出：本機 `tmp/unified-frontend-full.log`。jsdom 的 pseudo-element CSS 提示及既有 Vite chunk-size 提示不影響實際瀏覽器操作。
- 範例 **13 passed**；從不同 cwd、isolated Python 與安裝後 wheel 實際核對單一 entry point、版本依賴、實例分離、Host／Provider adapter、動態 UUID 回覆與取消。wheel SHA-256：`05d589c1680be71d1cd051e6d3f9e2313c7426e900f31ee3143644f0d3e7f37d`。輸出：本機 `tmp/unified-wheel-verification.log`。
- Windows PowerShell + 隔離 Node 24／uv：完整 `installers/windows/test.ps1` 通過。首次使用 PowerShell 7 的 policy test 及舊系統 Node 環境檢查未通過，換成安裝器指定執行環境後通過；未修改系統政策或共享工具。輸出：`tmp/unified-windows-installer-final.log`。
- Ubuntu `max` 非 root 帳號：完整 Linux 隔離建置、資料保留／uninstall tests、access helper 與 `systemd-analyze --user verify` 通過。輸出：`tmp/unified-linux-installer.log`。沒有啟動真正使用者服務或宣稱完成真實服務生命週期測試。
- 實際介面選檔／匯入 wheel、下載五個檔案的 Docker 部署包，核對 wheel bytes；最終部署包使用 API v3 base，`--network=none` 建置、`pip check`、全部 distribution files 與 provenance 驗證通過。import 不會自動安裝或套用。
- 原測試 volume 保留，升級前完整備份 34 個檔案並逐檔 hash 核對。升級後 **188 個原始 event rows 完整相同**，**25 個 API v2 profile** 保留；新事件為 API v3，SQLite integrity 為 ok。輸出：`tmp/unified-data-audit.json`。
- 實際 HTTP 合成 Provider：三種插件各執行不同 UUID 輸入、核對確切可變回覆、單一 profile、SSE replay 和同 requestId 重送；收到部分文字後取消與上游 tool_calls 拒絕通過。控制流程證據：`tmp/unified-http-proof/fixture.json`；明確標為合成，未用於真實模型聲明。
- 重新啟動容器後，六個合成／真實 Run 的狀態、文字、SSE/profile、選擇設定、auto 模型與已確認 wheel 均保留。證據：`tmp/unified-http-proof/restart.json`。

## 真實 OpenRouter auto

使用者授權提供的專用 key 只經隱藏輸入傳入隔離測試服務，保存於 `.opensprite/auth.json` 的 AES-256-GCM 密文。加密 key 檔存在；掃描測試資料根目錄 51 個檔案，未發現明文 API key。未把憑證寫入程式、文件、Git 或驗證日誌；完整敏感備份與使用者資料保留於本機。

透過產品正式模型目錄選定 `openrouter/auto`，stream 模式、輸出預算 8k、續寫 off、完整 prompt 日誌關閉。每個 Run 使用新 UUID 與隨機整數算式，沒有預寫模型回覆：

| 插件 | Run ID | 完成／動態回覆／profile／SSE／重送 |
| --- | --- | --- |
| standard | c311f186-f1c0-4be7-87bb-b4ce4e94f58f | 通過 |
| no_recovery | ffc1e945-7786-4979-b099-f789bcb316c1 | 通過 |
| example_main_retry_only | 428ebb75-85cd-4219-ac15-a0b1b8658b0d | 通過 |

每個 Run 恰有一次開始與一次完成的主模型 attempt，全部 stop 完成；input/output tokens 分別為 402/79、401/79、401/24。證據：本機 `tmp/unified-http-proof/openrouter-auto.json`。這驗證真實文字推論與插件整合，不代表已涵蓋模型品質或真實服務的所有上下文超限情境；可控制的錯誤／取消／恢復邊界使用自動測試和合成 Provider 驗證。

## 瀏覽器與交付邊界

- 1440×900、768×1024、390×844 實際視覺與互動檢查：單一選擇、已保存摘要、詳情、API v3 指南、手機 Drawer、Escape 關閉、取消草稿與套用均可操作；整頁沒有橫向溢出，窄版表格使用內部捲動。舊 API v2 對話仍顯示原 Loop／策略版本，真實 auto Run 顯示單一外部插件與保存回覆。
- 故意以另一頁修改設定，實際取得 409；介面顯示衝突、保留外部插件草稿且禁止再套用。重新讀取後保留草稿，確認後成功套用，再取消另一個草稿並恢復標準預設。最終瀏覽器 error／warn 記錄為空。
- 最終本機隔離預覽：[localhost:18768](http://localhost:18768/)，`0.21.33`，單一非 root backend writer，健康檢查通過；映像 `sha256:ad117585b7a7a7c5797914a8223081bed4fcdff3ae63fb5a5696ef559ba2bc2c`，manifest 已驗證。這是提交前 development image，沒有宣稱提交後 release revision。
- 原本 `localhost:8765` 實際仍為 `0.21.30`；本次交付新分支，沒有合併 main 或替換正式資料 volume。
- 原舊 wheel 快取與歷史資料保留；本次測試產生且已被更新的舊 API v3 範例快取可從備份復原。沒有刪除使用者資料或憑證。
- 新插件只能否決核心允許的恢復，不能擴大核心權限；API v3 仍只有一個主 `next_turn`。trusted in-process 插件不是沙盒；核心透過協作式取消終止任務，不能在同一程序內強制中止任意第三方 Python。
- 提交前版本同步、Windows backend offline lock check、Git diff check 與不含憑證的檔案核對通過。歷史變更版本保留原值。

相關文件：[架構](../architecture/agent-execution-plugins.md)、[插件撰寫與安裝](../architecture/execution-plugin-authoring.md)。
