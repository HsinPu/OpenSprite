# Frontend

這裡是 OpenSprite 瀏覽器介面的唯一來源。目前只建立 React、TypeScript、Vite、Ant Design 的依賴與設定，不包含應用入口或執行程式碼。

## 預定責任

- `src/app/`：應用組裝、路由與全域 provider。
- `src/api/`：未來的 HTTP 與 WebSocket client。
- `src/features/`：依使用者功能劃分的畫面、狀態與互動。
- `src/shared/`：不含業務邏輯的共用 UI 與基礎工具。
- `tests/`：前端測試。

目前只能驗證依賴與工具版本；在下一階段加入應用入口前，不宣稱 dev server、typecheck 或 build 可用。
