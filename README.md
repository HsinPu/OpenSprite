# OpenSprite

OpenSprite 正在從乾淨的 repository 基礎重新設計。目前已建立可啟動的前端 Demo，用假資料驗證核心對話與設定流程；後端仍未開始實作。

## 目前狀態

- 前端：React、TypeScript、Vite、Ant Design，可啟動 Demo。
- Demo 畫面：AI 對話工作台、一般設定、AI 模型設定。
- Demo 資料：全部保存在瀏覽器記憶體，不會連線或永久保存。
- 後端：尚未建立，等待前端方向穩定後再規劃。
- CLI：不在新版本範圍內。
- API、WebSocket、安裝器：目前只有預留邊界，尚未實作。

## 資料夾

- `frontend/`：瀏覽器介面與前端測試。
- `backend/`：未來的 Python service。
- `contracts/`：未來的前後端通訊契約。
- `installers/`：未來的 Linux 與 Windows 安裝器。
- `docs/`：架構與逐步修改紀錄。
- `scripts/`：未來的驗證及維護自動化。

完整架構原則見 `docs/architecture/overview.md`。每次修改的證據見 `docs/changes/`。

舊版完整程式保存在 `codex/archive-main-before-refactor-20260820`，只能唯讀參考，不直接搬回新架構。
