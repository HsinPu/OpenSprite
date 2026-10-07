# 執行插件匯入與 Docker 部署核對

- 版本：`0.21.29` → `0.21.30`。
- 分支：`codex/execution-plugin-workbench`。
- 範圍：「執行方式」頁需要的套件匯入、部署材料、安裝身份核對與說明。

## 變更

- 新增 `contracts/execution-plugin-packages.openapi.json`：套件清單、單 wheel multipart 匯入、移除匯入快取、下載部署 ZIP。
- 10 MiB wheel 及有界解壓檢查只讀 metadata、entry points 與 RECORD/hash；拒絕不支援 API、原生套件、安裝腳本、路徑衝突、內建 ID、依賴／Python 不相容與現有非插件套件覆寫，不匯入插件程式碼。
- 快取使用 AppPaths 唯一資料根目錄下 `cache/execution-plugin-packages`；同 SHA 冪等，原子保存／刪除，程序中斷的有界 staging 與 tombstone 不會使其他已完成套件失效，損壞的已完成快取仍 fail closed。
- 部署包提供原 wheel、Dockerfile、Compose override、驗證程式與 README。離線安裝由 Docker 主機在 build 階段執行；後端不使用 Docker socket、不執行 pip，不虛構建置進度。最終容器沿用非 root 使用者。
- root-owned manifest 記錄原 wheel SHA 和檔案；runtime 再核對實際安裝內容，區分未安裝、未核對、內容不符與已確認，同 ID／版本不同 wheel 不會被誤認為已安裝此包。
- 產生的 Compose override 把下一次部署基底指向本次衍生映像，避免第二次安裝回到沒有現有插件的原始 base；Dockerfile 與 manifest 仍記錄本次使用的來源基底。相同 wheel 重建須保留既有來源映像及獨立回復參照。
- UI 與作者指南描述「匯入 → 下載部署包 → 主機重建／重啟 → 核對 → 草稿／套用」；移除匯入快取不解除安裝、不修改 Run 或保存預設。
- 詳情抽屜內下載失敗會在操作旁顯示可重試錯誤。關閉／重開設定時，尚未結束的套件操作保持可見忙碌狀態，舊請求結果不得觸發下載或覆蓋新畫面。
- 正式依賴新增已鎖定的 `packaging==26.3`；Docker runtime 使用明確環境設定，官方 Compose 基底預設與其 `opensprite:local` 映像一致。

## 驗證

2026-10-08 完成以下驗證：

- 套件 API／靜態檢查／快取／manifest／匯出驗證範圍 **86 passed**，包含真正登入 middleware、跨來源寫入拒絕、GET 不開放 CORS、特殊檔案立即拒絕與損壞快取 fail closed。
- 最終後端完整 Docker 回歸 **1,447 passed**，包含新增的 A → B 基底接續與同 wheel 自 tag 設定回歸；`compileall`、`uv lock --check --offline`、`uv pip check` 通過，共 43 個已安裝套件相容。
- 前端完整 Docker 回歸 **648 passed**（69 個測試檔），Execution 範圍 **71 passed**；TypeScript 與最終 runtime 前端建置通過。下載失敗與跨設定重開競態先重現失敗，再修正並驗證恢復互動。
- 最初前端全套為 645 passed／1 個既有焦點測試逾時。直接在舊映像重現同一錯誤，定位為 Vitest 首次懶載入 SettingsPage 的 transform/import 超過測試整體 5 秒；僅該焦點測試群組預載真實模組，保留產品懶載入行為、全部互動與原 timeout，沒有 mock 掉頁面或放寬全域時限。
- 使用真正 `opensprite-loop-plugins` 預覽 API multipart 匯入 4,460-byte 範例 wheel，先確認 `not_installed`、插件未出現在已安裝選單，再下載該 API 產生的部署包，以 `docker build --network none` 執行真正 pip 安裝與檔案身份驗證。
- 範例 wheel SHA-256：`c090552320c9e99dad22ea2c58359a9503ae5515049bc1734253546756a1d75d`。含連續部署說明的最終作者 ZIP SHA-256：`98e29e4776cd1f43330717ed73e4b3d7b528f0a494f311bdf492029a41910f32`。
- 衍生映像在全新非 root、無既有使用者資料、無對外網路的容器啟動：真 wheel 重複匯入維持同 UUID／匯入時間，manifest verified、package confirmed，兩個真 entry points 可選且版本為 `0.1.0`。
- 兩次不同 nonce 輸入建立真 Run，每次都執行正式 calculator 工具 `2 + 3`，HTTP Provider fixture 收到工具結果 `5` 後產生帶該次 nonce 的回覆；共 4 次模型 HTTP 請求，兩個 Run 完成並固定範例 Loop／policy `0.1.0`。
- 另以第二個真 wheel 驗證連續部署：先用 A 的真 API 部署 ZIP 完成 `FROM A`／輸出同 A tag 的重新建置，再從最新 A 下載 B 部署 ZIP 並建出 B。全新 B 容器的 A、B 都是 confirmed、manifest verified，四個 execution entry points 都可用；分別套用 A、B 各執行兩次不同 nonce Run，共 4 次 Run completed、4 次正式 calculator completed、8 次本機模型 HTTP 請求。原 A 映像另保留獨立 rollback tag。
- 最後 Docker 預覽 `http://localhost:18767` 使用 `opensprite:plugin-c090552320c9e99d`，映像 SHA 為 `aa22ce76510dd5579b8c420678dba59747413af3a6f34c352bd092ed854b477a`，健康狀態 healthy、產品版本 `0.21.30`；重新建立容器後原範例 Loop／policy 預設保留、package confirmed，下一次部署基底指向該已安裝 A 的映像。實際下載的作者 ZIP SHA 與提交檔案一致。正式環境 `localhost:8765` 未變更。
- 實際 Chrome 核對並保留草稿，從真實已安裝清單套用兩個範例插件，關閉／重開後預設仍保存。檢視繁中／英文／日文，以及桌面、768×1024 平板、390×844 手機的套件清單／詳情；上層內容不外溢，表格只在內部水平捲動。指南的五步部署流程與下載入口正常，觀測到的 warning 來自既有 Chrome 擴充功能，沒有應用程式 console error。
- 提交前重新檢查版本三處一致，從完成測試的 Docker runtime 對目前 `backend/` 唯讀掛載執行 `uv lock --check --offline` 通過，`git diff --check` 通過；最終唯讀審查未發現新的 P1／P2。

## 證據邊界

- 靜態檢查和部署身份確認不代表 Python 程式安全；信任確認與作者說明明確指出插件具有後端程序權限。
- 上述模型端是本機 HTTP 測試 fixture；沒有呼叫付費 LLM，也沒有驗證真實模型推理品質。工具、Run、安裝、factory 與 HTTP 接線使用正式執行路徑。
- 瀏覽器擴充功能未授權存取本機檔案，選檔自動化被阻擋；沒有改動瀏覽器權限。實際 wheel HTTP 匯入通過，元件選檔／信任／匯入狀態由測試驗證；不能宣稱完整瀏覽器選檔端到端通過。
- 本機可重查證據位於 `tmp/execution-workbench-stage2-backend-chain-fix.log`、`tmp/execution-workbench-stage2-frontend-final-verified.log`、`tmp/execution-workbench-final-proof/`、`tmp/execution-workbench-two-package-proof/` 與此任務 visualization 截圖。測試資料、映像與 volume 不提交至 Git。
