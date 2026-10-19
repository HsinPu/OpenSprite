# OpenSprite Harness

OpenSprite Harness 正在規劃自己的本機 AI Agent Harness。

**已確認：TypeScript 核心＋React 前端，第一版就是桌面應用程式；點 OpenSprite Harness 圖示開啟獨立視窗，不需要開瀏覽器。不得帶入向 DeepSeek 或參考專案服務傳送資料的機制。**

正式產品名稱為 **OpenSprite Harness**；目前儲存庫資料夾 OpenSprite、文件檔名與 .opensprite 使用者資料路徑維持原值。

目前儲存庫只有規劃文件，尚無可執行應用程式。這不是既有 DeepSeek Harness 的 fork、套件組裝或設定改名。

## 規劃文件

- [Harness 架構提案](docs/architecture/harness-architecture.md)：模組、執行流程、資料模型、介面與失敗恢復。
- [資料外傳與權限政策](docs/architecture/data-egress-policy.md)：禁止原服務、供應商目的地、憑證、前端出口、程序隔離及驗收。
- [分階段路線圖](docs/plans/harness-roadmap.md)：第一個可用版本、各階段完成條件與後續擴充。

## 本次規劃的核心方向

1. 第一版以 Electron 為建議桌面外殼，隨安裝包攜帶 React 介面與 Host runtime；使用者不必安裝 Node、開終端或輸入本機網址。
2. 一個本機 Host 管理 Agent、SQLite、工具政策與憑證，桌面 renderer 不直接呼叫模型供應商。
3. 明確介面與靜態組裝；不建立可執行 YAML／任意 Host 插件框架。
4. 本機事件保存與模型推論 payload 分開；不建立 telemetry、Session uploader、遠端 feedback sender 或歷史補送佇列。
5. 所有外連目的地預設不允許，明確設定與核准後才可使用；沒有供應商時報錯，不回退雲端。
6. 已知 DeepSeek／原服務目的地額外拒絕；不能由一般設定、模型或工作區內容解除。
7. 任意工具程序需要另外的 OS／容器出口限制；Electron renderer sandbox 與 Host utility process 不代表工具已被隔離。

文件狀態：架構提案 v0.3，2026-10-19。使用者已確認技術語言、第一版桌面入口與禁止原服務傳送；Electron 選型及其他細節為建議方向，尚未實作、驗證、commit 或 push。
