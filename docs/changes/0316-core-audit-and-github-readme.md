# 核心與工作臺核對、GitHub README

- 版本：`0.21.31` → `0.21.32`。
- 目標：確認文字核心邊界與 Agent 工作臺流程，修正發現的問題，整理 GitHub 首頁及開發說明，通過驗證後合併至 `main` 並推送。
- 起點：`codex/clean-agent-core` 的 `dab4cceac058e7b6d84de093a5ca6f808df2d31d`；合併前 `main` 為 `4dc081e589f8078c0b9f3bbf13981371509f6f29`。

## 修正與文件

- 移除架構測試中對已刪除 `tools/` 目錄的空掃描，改成掃描目前整個 Python runtime 的 retired feature 依賴，要求掃描結果非空。ImportFrom 同時解析相對匯入與 `from . import module`，System Prompt 的依賴檢查也使用解析後的名稱。
- 精確比對 application 的模組邊界，避免將 `opensprite_backend.application` 誤判為 `opensprite_backend.app`。
- 實際瀏覽器發現：新工作區／新對話的第一個工作範例未填入草稿。範例現在以目前可見草稿直接更新，保留父層對舊非同步提交的識別保護；新增完整 App 導覽 regression，核對新對話與工作區切換後的首次範例、聚焦、不自動傳送及舊草稿隔離。
- 重寫根 README：既有品牌 logo、真實工作臺截圖、快速入口、功能表、Docker／Windows／Linux 安裝、工作流程、插件契約與安裝、資料保留、開發檢查和文件導覽。
- 同步重寫前後端 README，清除先前仍描述 MCP／工具路由及舊 schema 的過時內容。保留目前支援的流程與測試證據邊界。
- 沒有新增核心執行能力或還原已移除功能；工作範例的互動修正延續既有流程，版本、lockfile 與產品說明同步。

## 驗證

- 後端 Docker test target：`pytest -W error` **998 passed**，compileall、offline lock check 與 `uv pip check` 通過；29 個已安裝套件相容。完整輸出：本機 `tmp/core-main-backend-tests.log`。
- 前端最終 Docker test target：50 個檔案、**447 passed**，TypeScript 與正式 build 通過。完整輸出：本機 `tmp/core-main-frontend-final.log`。
- 工作範例的兩個回歸情境在舊實作均失敗；修正後 App／ChatWorkspace **59 passed**，typecheck 通過。驗證新對話及工作區切換的首次填入、聚焦、草稿隔離、不自動送出，並保留現有非同步草稿測試。
- 實際 Python runtime 匯入掃描檢查 2,319 個匯入項目，沒有 retired feature 依賴；三個故意加入的違規（相對 `tools`、相對 `mcp`、絕對 `skills`）均被目前的 guard 拒絕。三份 README 的 32 個本機連結／錨點、版本同步、Markdown fence 與 JPEG 1440×900 均核對通過。
- 實際瀏覽器：建立並切換隔離工作區、Shift+Enter 換行／Enter 傳送、文字回覆與歷史執行、標準與範例插件、設定草稿取消／套用、真正的 wheel 選檔與匯入／核對、API v2 開發指南與 Escape 關閉／焦點回復均通過。修正後第一個工作範例填入且追加既有草稿。瀏覽器 error／warn 記錄為空。
- 響應式：1440×900 桌面、768×1024 平板、390×844 手機，實際檢視聊天、設定與執行資訊；整頁沒有橫向溢出，插件表格使用內部水平捲動，手機導覽與執行抽屜可以開啟／關閉。README 截圖來自最終 `0.21.32` 隔離介面。
- `0.21.32` 真實 HTTP：兩個 UUID 動態輸入產生不同回覆、所選 API v2 插件版本事件、SSE replay、上游 `tool_calls` 拒絕、收到部分文字後取消串流，以及重建容器後插件、設定與兩個 Run 保存／再次執行均通過。證據：本機 `tmp/core-main-http-proof/installed-evidence.json`、`restart-evidence.json`。此檢查使用合成 Provider，沒有付費模型呼叫。
- 隔離預覽 `localhost:18768`：runtime image `sha256:b080ba52cd77e126ef5d167953182b80d52196ed906fd13ee60e5f70b1b5f889`、API 版本 `0.21.32`、健康檢查通過；範例 wheel `0.2.0` 的部署 manifest 已驗證。這是提交前的 development build，未宣稱包含提交後的 release revision。
- 提交前再次於 Windows `backend/` 執行 `uv lock --check --offline`，並核對 `git diff --check` 通過。既有 Windows／非 root Linux 隔離安裝器的通過紀錄見 [0315](0315-clean-agent-core.md)；本階段沒有修改安裝器，未重跑其完整生命週期。

## 證據邊界

- 工作臺使用獨立 Compose project／volume 與合成 HTTP Provider，不呼叫付費模型，不代表真實模型品質已驗證。
- 本次合併與推送原始碼；原有 `localhost:8765` 容器和使用者資料不變更。既有升級與插件信任邊界延續 [0315](0315-clean-agent-core.md)。
- 合併前實際核對正式容器仍是 `0.21.30`，image `sha256:66fdeae348eca9aa49ca2f076be77dfa598f3d07ebb7f8b71e4a55cf07c6b99d`，健康檢查通過。使用者資料沒有移除；舊表、原始歷史列與密文保留屬於升級資料契約，不能據此視為舊功能仍在核心執行。
