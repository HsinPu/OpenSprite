# Agent Loop API v4：流程決策移入插件

- 版本：`0.21.33` → `0.21.34`。
- 唯一目標：讓 Loop 插件完整安排多步文字推論、上下文選擇、摘要、重試及續寫，核心保留受限制的操作與 Run 終止權。
- 起點：`codex/unified-agent-loop` 的 `c216d03858fa2d51450d08ea74932d8736fbf72b`；新分支 `codex/agent-loop-v4`。
- 驗證日期：2026-10-09（Asia/Taipei）。

## 實作與公開影響

- API v4 factory 建立 fresh `execute(host)` 實例；唯一執行 entry point group 為 `opensprite_backend.agent_loops.v4`。移除 API v3 的恢復布林 callback、舊 `AgentLoop` 與核心內建 Loop 實作，不提供舊版執行轉接。
- `RunExecutor` 只負責接受後的執行生命週期、固定設定／Provider／工作區內容、期限、取消、錯誤映射與唯一終止交易。Host 提供 `checkpoint`、`context`、單次 `infer`、單次 `compact` 及 `finish`；不暗中執行摘要、重試或續寫。
- Loop 選擇歷史訊息、近期保留數、摘要門檻、摘要來源與格式、prompt、重試關係與多步順序。核心仍驗證來源、預算、摘要 coverage／hash、逐次操作、發佈文字前綴與結果所有權。
- 全 Run 上限包含最多 128 次實際模型請求、32 次摘要、2048 次 Host 操作；預設期限 600 秒，草稿與答案生成文字合計最多 1,048,576 字元。單次模型 transcript 最多 256 則。Host 與 RunContext 使用不可變資料及來源核對；這是可信任程序內插件契約，不是 Python 沙箱。
- 官方 `standard`／`no_recovery` 移到獨立 distribution `opensprite-standard-loop==0.1.0`，依一般 wheel entry point 載入。標準 Loop 自己實作近期 12 則、75%／55% 上下文選擇、摘要、一次上下文恢復與依使用者設定續寫。沒有官方 wheel 時不提供隱藏內建備援。
- 新 `run_steps` 保存每一步的 label、draft／answer、狀態、文字、用量與 retry 關係。草稿不進入聊天訊息；answer 串流與步驟文字在同一 SQLite transaction 中保存。已公開答案只可追加；要先修改答案的 Loop 應先使用 draft。
- SQLite schema 20／21 原子升級到 22：保留原始訊息、Run、事件與摘要；增加摘要產生插件、版本及格式，coverage 唯一性依格式分開。遷移失敗回滾版本與資料；重啟會中斷未完成 Run 及步驟。
- 新同源受保護 `GET /api/runs/{run_id}/steps`，每頁最多 100 步。工作臺診斷顯示草稿／正式答案、步驟狀態、錯誤、retry 來源及用量。設定頁解析器、wheel 相容性判斷與三語文案同步 API v4。
- 舊 API v2／v3 profile 與 API v1／v2／v3 匯入 metadata 仍可讀；舊 wheel 需要更新，不能作為新執行入口或部署包。SQLite 22 不能交回舊後端寫入，回復需要升級前完整敏感資料備份與原映像。
- Docker、Windows 安裝／release packaging 與 Linux 安裝都攜帶官方 Loop source project。範例 `example_review` 升級至 `0.4.0`，實際執行 draft → review → final，前兩步結果依序成為後續請求輸入。

## 自動、wheel 與安裝驗證

- 最新核心、測試與契約掛入 Linux Docker：`pytest -W error -q --tb=short -p no:cacheprovider` **991 passed**。API v4 取代已移除的 API v3 callback 測試，保留上下文、取消、錯誤、續寫與持久化的行為驗證。
- 前端 Docker test target：**51 files / 466 passed**；TypeScript、正式 Vite build 通過。實際瀏覽器檢查補到兩個 v3 相容性判斷遺漏，修正後重新執行全套。
- Python compileall、`uv lock --check --offline`、`uv pip check` 與 `git diff --check` 通過；產品 canonical version、lock 與 README 都是 `0.21.34`。
- 作者範例 **3 passed**。實際 wheel 驗證以隔離 Python 載入 dist-info／模組／entry point，使用真實 Host、SQLite、Native Provider adapter 與不同 UUID 的協定 fixture 完成三步；驗證結果依賴、草稿隔離與取消保留。fixture 明確不是付費模型測試。
- 範例 wheel SHA-256：`7bd87f1d51801568f44c071d3dce92e4639b7c8312c97b25c1b725272290158f`；官方 wheel SHA-256：`314a9f344a5f18ada44abd3cd16b56a8041ef0b85281ef0332d629f55e34d1f4`。
- 8 個檔案的來源 ZIP 可重現，SHA-256：`f6e9b390307778350f202022bf8067ec8319cd6016adae9009ea69393f2a21e6`。來源、作者文件、工作臺範例與驗證腳本同步。
- Windows PowerShell 5 + 隔離 Node 24／uv：完整 `installers/windows/test.ps1` 通過，包括 package 包含官方 Loop、實際安裝後可載入官方 wheel、解除安裝保留資料。過舊系統 Node 與 PowerShell 7 policy fixture 問題以指定執行環境排除，未修改系統工具或政策。
- Linux UID 10002 的完整隔離安裝：6 項 uninstall tests、access helper、含空白暫存路徑的建置、安裝後官方 wheel 及 `systemd-analyze --user verify` 通過。測試使用 `uv run --project backend`；Docker 測試映像補齊 source README 並使用 Git 的 LF 換行格式。未啟動真正 Linux 使用者服務。

## 實際 Docker、模型與畫面

- 獨立 Compose project `opensprite-loop-v4-proof`、volume `opensprite-loop-v4-proof-data`，網址 `http://localhost:18769`。容器 UID **10001**，版本 `0.21.34`，官方 wheel `0.1.0` 與範例 wheel `0.4.0`；健康回應為 `{"status":"ok"}`。
- 經產品 HTTP 匯入 wheel，確認只存快取且尚未安裝；從產品下載五檔部署包，核對 wheel bytes，再以 `--no-index --no-deps` 安裝、`pip check` 及 distribution files／provenance validator 建置。工作臺顯示「已確認此 wheel」，實際選取草稿及套用 `example_review` 成功。
- 測試憑證來自先前已授權的測試 volume，以唯讀來源複製密文 `auth.json`、`config/credential.key` 及相符 Provider state。未輸出或寫入明文 key；新 volume 檔案 UID 10001／0600，目錄 0700。正式 `8765` 容器仍為 `0.21.30`。
- 實際 OpenRouter 模型目錄選 `openrouter/auto`；stream、8k output、continuation off、完整 prompt 日誌關閉。三個 Run 使用各自 UUID 與可變算式，結果符合 nonce 與整數答案；SSE、profile、同 clientRequestId 重送、聊天只含使用者訊息和正式答案皆通過。

| 插件 | 真實 Run ID | 模型請求 | 實際 input／output tokens |
| --- | --- | --- | --- |
| standard | b9a85745-5c16-4092-8c8f-65e0370ee66f | 1 | 403／113 |
| no_recovery | 633dcdc1-b5e8-4234-bf95-99bb313aeaf4 | 1 | 400／22 |
| example_review | da1ed7a3-ae39-4256-9b4c-a2c0547557a6 | 3 | 1325／187 |

- 共 **5 次真模型請求**，三步插件各步皆 completed，draft／draft／answer 正確保存；沒有預寫供應商答案。用量來自 Provider usage，不是費用或模型品質評分。
- 重啟後保留三個 Run、五個步驟、正式文字、已保存 `example_review` 選擇及 exact wheel confirmed 狀態。
- 實際檢視 1280×720 桌面、768×1024 平板、390×844 手機的設定與步驟詳情；表格局部水平捲動、手機抽屜、草稿展開、最終答案及用量可操作。控制台沒有 error。
- 圖片：[API v4 真實三步診斷](../screenshots/agent-loop-v4.jpg)。本機忽略的詳細證據位於 `tmp/v4-*` 及 `tmp/v4-http-proof/`；它們不是發佈檔案。

## 範圍與後續

本階段沒有加入工具、Skill、Subagent、MCP、平行模型請求或程序隔離。API v4 插件仍必須合作式 await／取消；不可宣稱可強制終止任意第三方 Python。外部 v3 作者需重寫流程並重新建置 wheel，不能只改 metadata 數字。

本次交付在新分支及獨立本機 Docker 預覽，未合併 `main` 或替換正式 `8765` 服務。
