# OpenSprite Harness

OpenSprite Harness 是以 TypeScript 核心、React 介面與 Electron 桌面外殼建立的本機 AI Agent 工作台。

**目前產品版本：0.1.0。階段 1 的首個 slice 提供桌面版骨架；安裝後點 OpenSprite Harness 圖示即可開啟獨立視窗，不需要開瀏覽器、終端或另外安裝 Node.js。**

正式產品名稱為 **OpenSprite Harness**；目前儲存庫資料夾 OpenSprite、文件檔名與 .opensprite 使用者資料路徑維持原值。

這個版本提供本機 Host 狀態、未設定模型提示與隱私政策說明。模型對話、Session、SQLite、工具與 Outbound Broker 尚未實作，訊息輸入與傳送明確停用。這是 OpenSprite Harness 自己的實作，不依賴參考專案的產品套件。

## Windows 桌面版

1. 取得本機打包產生的 `release/OpenSprite-Harness-0.1.0-Setup.exe`，雙擊啟動安裝精靈。
2. 使用目前 Windows 帳號安裝；NSIS 安裝包預設建立桌面與開始功能表捷徑。
3. 點 **OpenSprite Harness** 圖示，即開啟獨立工作台；本機 Host 自動啟動，關窗時一併退出。

這是**未簽署的開發測試版**，Windows 可能顯示發行者驗證提示。安裝包隨附 Electron 與執行環境；一般使用者不需要 Node.js、npm、Vite 或瀏覽器。也可從完整的 `release/win-unpacked/` 目錄直接雙擊 `OpenSprite Harness.exe`；不能只複製單一 exe 而省略其他 runtime 檔案。

安裝包由開發者執行下列命令產生，Git 原始碼不包含預先建置的安裝包。本次已在目前 Windows 使用者環境驗證實際安裝、桌面捷徑啟動與獨立視窗；乾淨 VM／新帳號、完整升級／解除安裝流程仍待另驗，尚未交付 Linux 安裝包。

## 開發與驗證

開發者需要符合 `package.json` 的 Node.js（`>=24.15.0 <27`）與 npm。相依版本由 `package-lock.json` 固定，請在儲存庫根目錄執行：

```powershell
npm ci
npm run typecheck
npm test
npm run test:desktop
npm start
```

`npm start` 建置後直接啟動 Electron，不啟動系統瀏覽器。`test:desktop` 會先建置，再以 Playwright 驗證真正的 Electron 視窗、Host 與程序邊界；測試使用隔離的暫存使用者資料目錄。

Windows 打包：

```powershell
npm run package:win
npm run dist:win
```

- `package:win`：產生可直接啟動的 `release/win-unpacked/` 目錄。
- `dist:win`：產生目前使用者安裝的 NSIS 安裝包與捷徑設定；不自動發布到遠端。

首次安裝開發依賴及取得打包工具可能需要連線到套件來源；這與安裝後產品的執行期連線分開。驗證範圍與限制見 [桌面骨架變更紀錄](docs/changes/2026-10-19-desktop-skeleton.md)。

## 本機邊界與隱私

- React 與資源隨包攜帶，只連目前 instance 的私有 Host；Host 綁定 `127.0.0.1` 的隨機連接埠，不提供公開網路服務。
- main 以私有 IPC 傳遞一次性 bootstrap token，再交換 `HttpOnly`、`SameSite=Strict` 的記憶體 session cookie；preload 只提供版本與平台資訊。
- renderer 啟用 sandbox、context isolation、CSP 與同源請求限制；不允許任意導航、新視窗或下載。
- bootstrap 使用停用 proxy 繼承的直接本機 HTTP agent；Host 環境使用明確允許清單，不繼承代理、供應商金鑰或 `NODE_OPTIONS`。
- 沒有 DeepSeek adapter、遙測、回饋／Session uploader、背景補送或自動更新器。
- Electron profile、session/cache 與本機 crash dump 位於 `.opensprite/desktop/`；目前尚未初始化 Session／SQLite／憑證儲存。解除安裝設定不刪除此資料根。

上述是目前自有程式與桌面程序的限制，**不等於已提供 OS／容器層的全面零網路保證**。任意 shell、MCP 與第三方工具仍未啟用。

## 規劃文件

- [Harness 架構提案](docs/architecture/harness-architecture.md)：模組、執行流程、資料模型、介面與失敗恢復。
- [資料外傳與權限政策](docs/architecture/data-egress-policy.md)：禁止原服務、供應商目的地、憑證、前端出口、程序隔離及驗收。
- [分階段路線圖](docs/plans/harness-roadmap.md)：第一個可用版本、各階段完成條件與後續擴充。

## 後續架構方向

1. Electron 桌面外殼與私有 Host 已落地，後續功能沿用此桌面入口。
2. 後續由一個本機 Host 管理 Agent、SQLite、工具政策與憑證，桌面 renderer 不直接呼叫模型供應商。
3. 明確介面與靜態組裝；不建立可執行 YAML／任意 Host 插件框架。
4. 本機事件保存與模型推論 payload 分開；不建立 telemetry、Session uploader、遠端 feedback sender 或歷史補送佇列。
5. 後續 Outbound Broker 的外連目的地預設不允許，明確設定與核准後才可使用；不回退雲端。
6. 後續加入模型出口時，額外拒絕已知 DeepSeek／原服務目的地；不能由一般設定、模型或工作區內容解除。
7. 任意工具程序需要另外的 OS／容器出口限制；Electron renderer sandbox 與 Host utility process 不代表工具已被隔離。

文件狀態：架構與路線圖 v0.4，2026-10-19。階段 1 首個 slice 為桌面骨架 v0.1.0；完整階段 1 與第一個可用 Harness 的後續門檻尚未全部完成。
