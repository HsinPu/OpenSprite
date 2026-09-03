# OpenSprite

OpenSprite 正在從乾淨的 repository 基礎重新設計。目前已建立可啟動的 React 前端與 Python 本機服務，提供真實的 Provider 連線、AI 設定、Conversation、Run、SSE 串流與 bounded Agent loop。

Windows 可從 repository root 執行 `./installers/windows/install.ps1`，安裝後以
`http://localhost:8765/` 使用。程式位於 `%LOCALAPPDATA%\OpenSprite\app`，使用者資料固定在
`%USERPROFILE%\.opensprite`。

## 目前狀態

- 前端：React、TypeScript、Vite、Ant Design，透過同源 `/api` 與本機服務溝通。
- 對話：Conversation、Message、Run 與安全語意事件保存於 `.opensprite/data/opensprite.db`，前端以 HTTP 與 SSE 消費。
- AI：固定支援 OpenAI、Anthropic、OpenRouter；模型、Context／輸出上限、推理模式、續接次數、回覆顯示方式與 Prompt log 偏好保存於 `.opensprite/config/settings.json`。
- 金鑰：只以 AES-256-GCM ciphertext 保存於 `.opensprite/auth.json`，每次安裝使用獨立的 `config/credential.key`。
- Agent：所有使用者訊息進入同一個 Token-budgeted Agent loop；舊對話只做可重建摘要，原始訊息不刪除。執行事件與 Context 用量可由前端即時／歷史查看；production Tool Registry 目前包含安全的唯讀計算器。
- CLI：不在新版本範圍內。
- API：Provider、AI settings 與 Agent chat HTTP/SSE 契約已實作；未使用 WebSocket。
- 安裝器：Windows 安裝器已實作並使用 `%LOCALAPPDATA%\OpenSprite\app`；Linux 安裝器位置已預留，尚未實作。

## 資料夾

- `frontend/`：瀏覽器介面與前端測試。
- `backend/`：Python FastAPI 本機服務、Agent、Provider、加密憑證與 SQLite persistence。
- `contracts/`：authoritative OpenAPI HTTP/SSE 契約。
- `installers/`：Windows 安裝與啟動流程；Linux 安裝器待後續切片建立。
- `docs/`：架構與逐步修改紀錄。
- `scripts/`：未來的驗證及維護自動化。

完整架構原則見 `docs/architecture/overview.md`。每次修改的證據見 `docs/changes/`。

舊版完整程式保存在 `codex/archive-main-before-refactor-20260820`，只能唯讀參考，不直接搬回新架構。
