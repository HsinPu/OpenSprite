# 執行方式工作臺與插件作者範例

- 版本：`0.21.28` → `0.21.29`。
- 分支：`codex/execution-plugin-workbench`。
- 範圍：僅設定中的「執行方式」、其作者說明與範例；使用既有 GET／PUT 契約。

## 變更

- 分開顯示已套用預設與選取草稿，使用 Loop／策略表格比較插件、查看詳細資料，再以一次 PUT 套用完整選擇。
- 支援還原草稿、載入失敗重試、已保存插件移除或不可用、保存中關閉／重開的讀写競態；保留每個新 Run 接受時固定插件版本的語意。
- 提供插件開發 Drawer 與完整下載專案：獨立 CheckpointedDriver、MainRetryOnlyPolicy、entry points、作者測試及真 wheel 安裝驗證腳本。
- 原始範例存於 `examples/execution-plugin/`，可重現的 ZIP 由維護腳本產生；指南明確說明 Host API v1 能力、信任與測試證據邊界。
- 本階段尚未新增 wheel 匯入 HTTP API；後續階段接入匯入與 Docker 部署身份核對。

## 驗證

2026-10-08 完成以下驗證：

- 既有 GET／PUT API 與新版 UI 範圍 **38 passed**；TypeScript 通過，正式前端 Docker 建置通過。
- 範例從下載 ZIP 解壓到沒有 backend 目錄的隔離位置：**11 passed**，離線 wheel 建置與真正 target 安裝通過；兩個 entry points、fresh factory、工具結算、取消與 Host 原結果均核對。
- 指南中的完整 wheel 檔名 COPY／離線安裝指令另以真 Docker 衍生映像驗證，39 個相依套件相容。
- 實際 Chrome 保存策略、關閉／重開設定，確認預設保持；草稿不會預先寫入。檢視桌面、768×1024 平板、390×844 手機與指南 Drawer；修正表格 intrinsic grid width 導致手機摘要被裁切，復驗後上方文字正常換行，只有表格內水平捲動。
- 真瀏覽器下載 ZIP 與原始静態 ZIP SHA-256 相同：`be70e2324e59de36e3dc08cc0c57007b014fe460169d3eac5e5ff175018595f7`。下載不是 wheel 安裝，也沒有呼叫付費模型。
- 使用目前 backend 檔案唯讀掛載、停用網路執行 `uv lock --check --offline` 通過；版本三處同步 `0.21.29`；Python 驗證脚本 compileall、`git diff --check` 通過。
- 保留獨立 `opensprite-loop-plugins` project／volume，在 `http://localhost:18767` 更新本階段 runtime，健康檢查通過。完整產品回歸將於 HTTP 套件匯入整合階段執行。
- 本機證據：`tmp/execution-plugin-standalone-test.log`、`tmp/execution-workbench-stage1-runtime-final.log`；桌面截圖存於此任務 visualization 目錄，不提交個人資料或測試 volume。
