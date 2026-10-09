# Host API v5：完整輸入與摘要生成交由 Loop

- 版本：`0.21.34` → `0.21.35`。
- 唯一目標：讓可替換 Loop 決定上下文組裝、摘要生成、重試與自動續寫；Host 保留通用執行、來源核對、保存、取消及既有期限／硬上限。
- 起點：`codex/agent-loop-v4` 的 `6efac6fb3d17becaf6588f0dcc584d7465888dab`；新分支 `codex/host-loop-v5`。
- 驗證日期：2026-10-09（Asia/Taipei）。

## 實作與公開影響

- 公開入口升為 `opensprite_backend.agent_loops.v5`，factory `api_version = 5`。舊 API v1..v4 wheel 可檢視，但不能作為新任務入口或部署包；作者必須更新 SDK 使用方式並重建，不提供執行轉接別名。
- Host 提供 `run`、`checkpoint`、`read_context`、`estimate_input`、`infer`、`save_summary`、`finish`。`read_context` 回傳分頁原始歷史、獨立 current user、指定格式摘要及 cursor，固定接受任務時的訊息邊界；不選擇歷史或生成摘要。`infer` 接受 Loop 完整組裝的訊息與輸出預算，每次最多一次模型呼叫。`save_summary` 不呼叫模型。
- 從核心移除上下文 assembler、軟預算策略、摘要 prompt／生成流程。官方獨立 wheel `opensprite-standard-loop==0.2.0` 自行安排最近 12 則、75%／55% 選擇、摘要、符合條件的一次上下文恢復及續寫尾段。`no_recovery` 保留上下文準備，但不自動重試或續寫。
- 標準 Loop 在模型回傳 `OUTPUT_LIMIT` 時自動續寫，到 `FINAL`、重複截斷片段、無法恢復的上下文限制、取消或共用 Run 上限才停止。刪除全域續接次數設定與獨立 64 次續接限制；共用上限仍為 128 次實際模型請求、32 次摘要生成、600 秒、1,048,576 生成字元、2048 次 Host 操作。摘要、重試、續寫共用計數器。
- `InputSource`／`SummarySource` 核對 Host 所有權、來源 ID、摘要格式、連續範圍、canonical hash 與前一摘要 CAS。複製、偽造、修改或跨 Run 的快照／步驟不能作為來源。來源核對不保證模型摘要或變換後文字的語意正確。
- 摘要由 Loop 使用一般 draft 推論生成，明確保存後才生效。摘要列與完成事件在同一交易保存；相同 step 的相同寫入可重播，不重複完成事件，不同內容不能覆寫。草稿留在受保護步驟歷史，正式答案只能追加；Executor 保存唯一終止結果。
- SQLite 20／21／22 原子升為 23，保留原始欄位、文字、ID、歷史續寫選擇及封存額外表；增加摘要來源 step、起始 sequence 與前一摘要 ID。新 Run 的歷史續寫欄位保存 NULL。AI 設定 3..11 原子遷移至 12，移除 `outputContinuation`。升級後資料庫不能由舊後端寫入。
- 輸入 receipt 升為 schema 3，增加前置步驟 `stepIds`，保留 schema 2 歷史讀取。HTTP 契約、工作臺 parser、wheel 相容性、三語教學、作者文件與下載範例同步 API v5。設定頁的自動預算說明改為由目前 Loop 決定，避免替自訂插件預測標準策略。保留回應傳遞設定。
- 範例 `example_review==0.5.0` 提供完整 draft → review → final 輸入，後續請求引用先前 StepResult；前兩步不發布到聊天。範例只示範最近 20 則，不自行摘要或續寫。Windows／Linux 安裝驗證同步檢查新版官方 wheel 的實際載入。

## 測試與安裝驗證

- Docker 後端 `pytest -W error`：**1007 passed**。涵蓋所有權、raw context 分頁／接受邊界、草稿與唯一完成、來源缺口／current user 拒絕、摘要冪等與交易回滾、舊 schema 20／21／22 原子遷移、重試、取消、期限與共用上限。
- 續寫協定 fixture 驗證 1／3／5／10／20／50／70 次模型請求、自動超過 5 次、重複片段停止與 128 次硬上限；使用可變 UUID 片段與實際 Host／SQLite。協定 fixture 明確不是付費模型。
- Docker 前端：**51 files / 466 passed**；TypeScript 與正式 Vite build 通過。移除未使用舊策略文案後，隔離 Node 24 的三語測試另 **6 passed**。
- 作者範例 **3 passed**。真 wheel 離線隔離安裝驗證使用實際 Host、SQLite、Native Provider adapter 及每次不同 UUID 的協定資料，核對三步輸入依賴、草稿私有、正式答案與取消保存。
- 範例 wheel SHA-256：`e75ed2849b131bf3c051885e6d68a290856a168b662d9a7c7df60b01b0c9b4b3`。來源 ZIP 含 8 檔、33,114 bytes，可重現 SHA-256：`229a42cce5b079cee40d41c0460a76ca5d4f5be1c2c237961a544be7131a3252`。
- Windows PowerShell 5 + 隔離 Node 24／uv：完整 `installers/windows/test.ps1` 通過，包括真安裝後載入 API v5 wheel、解除安裝保留測試資料。PowerShell 7 的既有 process policy fixture 不一致以指定 PowerShell 5 排除，沒有修改持久系統政策。
- Linux UID **10002** 隔離安裝通過 uninstall tests、access helper、含空白路徑的建置、安裝後官方 wheel 載入及 `systemd-analyze --user verify`。沒有啟動真正使用者服務。
- Python compileall、版本同步、`uv lock --check --offline`、`uv pip check`、`git diff --check` 通過。初次原生前端測試的 sandbox spawn／系統 Node 20 問題，使用允許子程序的隔離 Node 24 PATH 後通過。

## 實際 Docker、模型與畫面

- 獨立 Compose project `opensprite-host-loop-v5-proof`、volume `opensprite-host-loop-v5-proof-data`，網址 `http://localhost:18770`。版本 `0.21.35`、官方 wheel `0.2.0`、範例 wheel `0.5.0`，容器 UID **10001**，健康回應 `{"status":"ok"}`。
- 經正式產品 HTTP 匯入 wheel，確認只存快取且尚未安裝；下載五檔部署包、核對 wheel bytes、離線 no-deps 安裝、pip check 與 distribution 檔案 provenance。部署後工作臺顯示「已確認此 wheel」，API v5 插件可選。
- 測試憑證使用既有已授權測試環境的相符密文與 Provider state；沒有輸出或持久化明文 Provider key。密文及 credential key 為 UID 10001、0600。預覽保留 `password_required`，經正式初始化／登入流程建立隔離測試帳號。直接修改存取政策曾被自動審核拒絕，該操作沒有執行。
- 實際 OpenRouter 模型目錄選 `openrouter/auto`，完整 prompt 日誌關閉。每個 Run 使用不同 UUID 與算式，核對實際回覆、SSE、profile API v5、步驟 channel、聊天只含使用者訊息和正式答案、同 clientRequestId 重送。

| 插件 | 真實 Run ID | 模型請求 | 實際 input／output tokens |
| --- | --- | --- | --- |
| standard | e0f88604-4284-495c-a315-796659f9c3d9 | 1 | 401／58 |
| no_recovery | f37e4cfe-1a88-4ef0-b566-568eb3f74bbf | 1 | 401／23 |
| example_review | 7d53c59b-76ff-480b-9368-7f7ea86a7f14 | 3 | 1283／202 |

- 共 **3 個真實模型 Run／5 次模型請求**，不是預寫模型答案；此次小型真模型 smoke test 不代表長對話摘要品質或供應商品質評分。
- Docker 重建／重啟後，逐筆核對上述三個 Run、五個步驟、正式文字與全部事件不變；已保存 `standard` 選擇及 exact wheel confirmed 狀態保留。
- 實際瀏覽器檢視 **1280×720** 桌面、**768×1024** 平板、**390×844** 手機。執行方式表格使用局部水平捲動，教學抽屜、API 邊界、安裝步驟及下載控制項可操作，沒有頁面水平溢出或 console error；已還原視窗尺寸。
- 圖片：[實際 Host API v5 工作臺](../screenshots/host-loop-v5.jpg)。詳細本機證據位於忽略的 `tmp/v5-*`，不是發佈檔案。

## 剩餘範圍與後續方向

本次只調整文字 Host／Loop 邊界，不加入工具、Skill、Subagent、MCP、平行推論或 Python 程序隔離。第三方插件仍是可信任程序內 Python，取消／期限需要合作式 await，不能宣稱可強制終止任意插件。交付位於新分支和隔離預覽；尚未合併 main 或替換正式 8765 服務。

後續優先建立固定任務集比較各 Loop 的答案品質、總 token、延遲、續寫與摘要恢復效果，再依數據改善長對話記憶、結構化摘要驗證、重試退避和停止策略。需要載入不可信第三方插件時，另行規劃程序隔離與權限能力；不要再把這些流程決策搬回 Host。
