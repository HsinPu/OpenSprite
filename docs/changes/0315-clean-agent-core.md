# 乾淨的可替換 Agent 核心

- 版本：`0.21.30` → `0.21.31`。
- 分支：`codex/clean-agent-core`，從 `main` 的 `4dc081e589f8078c0b9f3bbf13981371509f6f29` 建立。
- 範圍：清除 Tools、核准、Skills、自訂 Agent／Subagent／delegation、MCP 與排程，保留正式文字聊天與可替換 Loop／執行策略。

## 變更

- 刪除上述後端執行套件、路由、組裝、生命週期及專用測試，移除對應前端 API、設定、操作與契約。Python 專用依賴、前端直接依賴 `fflate`／`yaml` 與 lockfile 同步清理；沒有隱藏停用開關或封存實作還原。`yaml` 仍可能由開發工具間接依賴。
- Host API v2 僅提供 `checkpoint()`、`next_turn()`、`finish(turn)`；內建插件版本 `2.0.0`。每次 Run 固定使用接受時的插件實例與版本，保留 Host 權限、順序、身份、取消、預算和唯一終止保護。
- Provider Adapter 只接受文字訊息。三種原生協定的 action／tool 回應皆拒絕；設定、模型能力、prompt、上下文 receipt v2 與事件不再攜帶工具或子代理欄位。
- 全新 SQLite v21 僅建立五張核心表；既有 v20 只在驗證結構後提高 schema version，保留其他表和原始歷史事件。讀取投影忽略已移除事件及 API v1 紀錄，仍使用原始 sequence 分頁，不改寫原始列。
- 保留 `.opensprite` 中的使用者資料與密文。舊 AI 設定和 Provider catalog 讀取時移除 retired 欄位，新保存寫入乾淨格式；舊 MCP 密文僅原值保留，公開操作拒絕其 ID。
- 既有 API v1 wheel metadata 可以查看／移除，但不能載入、套用、重新匯入或下載部署包。作者指南、範例 `0.2.0` wheel、下載 ZIP 與實際安裝驗證程式均同步至 API v2。
- 修正短文字串流要累積 4,096 字才顯示的問題：首段立即保存，後續按 100 ms 或長度批次輸出；完成／取消排空已收到文字，維持快速片段合併。
- 工作臺只保留模型與設定入口，快速程式碼範例改為解讀使用者貼上的內容。三語系說明、登入、工作區、安裝器摘要與架構文件反映文字核心。手機設定分類按鈕改用 Ant Design text 樣式，避免白色圖示落在白色按鈕背景。Linux shell 固定 LF，讓 Windows checkout 也能執行 Linux 檢查。

## 驗證

驗證於 `2026-10-08` 完成，使用隔離資料與產品實際流程。

### 自動檢查

- 後端 Docker 測試：`uv sync --locked --dev`、`pytest -W error` **998 passed**；`python -m compileall -q src tests`、`uv lock --check --offline`、`uv pip check` 全部通過，29 個已安裝套件相容。涵蓋核心 schema、新舊資料投影、原生協定拒絕 action、Loop Host 順序與取消、串流首段及批次保存、wheel 檢查與 HTTP 契約。
- 前端 Docker 檢查：50 個測試檔案、**446 passed**，TypeScript 與正式建置通過。最後的手機分類按鈕樣式調整另執行 `SettingsPage` **34 passed** 與 TypeScript 檢查，並重新建置實際預覽。
- 範例插件 **13 passed**。另將 wheel 真正安裝至隔離 runtime，確認載入路徑來自已安裝 distribution、兩個 entry point 與 API v2 profile，經核心執行變動輸入並驗證取消保留文字。
- Windows PowerShell 5 執行 `installers/windows/test.ps1` 通過：隔離含空白路徑、建置、加密資料保留、回復、bootstrap 與解除安裝。Node `24.19.0`、npm `10.7.0`、uv `0.12.23` 僅放在儲存庫 `tmp/`，PATH 僅於測試程序調整。
- WSL Ubuntu 非 root 帳號 `max` 執行 `installers/linux/test.sh` 通過：隔離含空白路徑、建置、存取輔助程式及 `systemd-analyze --user verify`。Node、uv、Python 與虛擬環境使用隔離工具路徑，沒有註冊或啟動真正的使用者服務。
- Windows 主機另以隔離 uv cache 執行 `uv lock --check --offline` 通過；產品版本在 `backend/pyproject.toml`、`backend/uv.lock` 與 `README.md` 一致。提交前執行 `git diff --check`。

### wheel 與 Docker 整合

- 新建獨立 Compose project `opensprite-clean-core-proof`、資料 volume `opensprite-clean-core-proof-data`，僅綁定 `127.0.0.1:18768`。合成 Provider sidecar 在相同網路命名空間內提供真實串流 HTTP 回應。
- 透過正式 multipart API 匯入 wheel：確認匯入尚未安裝；重複匯入保留相同 ID／時間；下載正式部署 ZIP 並核對其中 wheel 的原始位元組與 SHA-256。
- 從實際下載的部署 ZIP 建置衍生 Docker 映像，離線安裝 wheel、檢查依賴及 runtime manifest。重啟後套件狀態為 `confirmed`、manifest 為 `verified`，選取 `example_checkpointed`／`example_main_retry_only`，版本均為 `0.2.0`、API v2。
- 兩個不同 nonce 的正式文字任務都完成，回覆包含各自實際輸入，SSE 重播一致；Provider 真正送出 `tool_calls` 串流時，Run 以 `invalid_provider_response` 拒絕且未產出 action。短串流取消前已保存 8 字，取消後仍保留部分文字。
- 強制重建容器並保留隔離 volume，確認插件預設、套件確認狀態及兩筆 Run 文字／profile 保持；重啟後的新串流任務仍完成。
- 最終預覽映像 `opensprite:plugin-9140a97d7dbbd9fd` 為 `sha256:e22fc9d609cf50a9fb2f58446379520fe04b72b8f164ba2e919ab2d0f0e3cebf`，健康檢查通過，`/api/app-info` 回報 `0.21.31`。
- 原有 `localhost:8765` 容器仍為 `0.21.30`，映像 `sha256:66fdeae348eca9aa49ca2f076be77dfa598f3d07ebb7f8b71e4a55cf07c6b99d`，健康檢查通過；其資料 volume 未變更。

| 產物 | SHA-256 |
| --- | --- |
| 範例 wheel `opensprite_execution_example-0.2.0-py3-none-any.whl`（3,579 bytes） | `9140a97d7dbbd9fd3feaa7957db17b75a3cf5fb7d4d167076ae7c478d308d41d` |
| 作者範例 ZIP `frontend/public/execution-plugin-example.zip` | `428f68bb53e407192b269ff1efc7deb076ceeda5ce919b1bde8f0d7eeaf21ae4` |
| HTTP 下載的部署 ZIP | `ad2b4df0c945b6cfb4c99541eb4d6a9020873205d6c2ce55a3d307d63fad95c3` |

### 瀏覽器與證據檔案

- 實際檢視桌面 `1440 × 900`、平板 `768 × 1024`、手機 `390 × 844` 的設定與聊天：外層無水平溢出，套件表格於自身範圍捲動；API v2 指南、Escape 關閉與焦點回復、手機分類抽屜操作正常，console error 為空。
- 瀏覽器真正送出 `瀏覽器整合驗證：nonce-muz35qwn`，收到含對應輸入的完成回覆，執行詳細資訊顯示已安裝插件 profile；容器重建後重新整理仍保留該對話。手機選單按鈕修正後再檢視對比。
- 自動檢查 log 在 `tmp/clean-core-{backend-final,frontend-final,settings-final,wheel-final,windows-installer-final,linux-installer}.log`；HTTP 證據在 `tmp/clean-core-http-proof/{prepare,installed,restart}-evidence.json`。
- 桌面／平板／手機截圖及 `clean-core-ui-proof.json` 在 `C:/Users/win10/.codex/visualizations/2026/10/07/01a1141b-c536-7bd0-95d2-ea65cd2ab5e7/`。上述本機 log、fixture 紀錄、工具及隔離產物不提交。

## 證據邊界

- Python wheel 是受信任的後端程式碼；API 邊界與雜湊核對不代表程序沙箱或程式安全審查。
- 模型測試使用合成協定 fixture，沒有呼叫付費模型，也沒有驗證真實模型推理品質。正式 Run、SQLite、Provider Adapter、SSE、wheel 匯入、安裝與插件選取使用產品流程。
- 檔案選擇器的整段瀏覽器上傳未執行；匯入由正式 multipart HTTP 與前端元件測試驗證。Linux 安裝器驗證隔離建置與服務單元，未驗證真正使用者服務的完整啟停生命週期。
- 此階段保留新分支，正式 `main`／`localhost:8765` 不更新。使用者資料未刪除；較舊的 SQLite 資料須先由 `0.21.30` 升至 v20。
