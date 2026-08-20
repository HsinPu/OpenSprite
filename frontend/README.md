# Frontend

這裡是 OpenSprite 瀏覽器介面的唯一來源。目前提供 React、TypeScript、Vite、Ant Design 實作的前端 Demo，使用假資料呈現核心對話與設定流程。

## 責任

- `src/app/`：應用組裝、路由與全域 provider。
- `src/api/`：未來的 HTTP 與 WebSocket client。
- `src/features/`：依使用者功能劃分的畫面、狀態與互動。
- `src/shared/`：不含業務邏輯的共用 UI 與基礎工具。
- `tests/`：前端測試。

## 啟動

```powershell
npm ci --ignore-scripts
npm run dev
```

預設由 Vite 顯示本機網址。若預設連接埠已被占用，可以指定其他連接埠：

```powershell
npm run dev -- --host 127.0.0.1 --port 4173 --strictPort
```

## Demo 範圍

- `/` 或 `/#chat`：AI 對話工作台。
- `/#new-chat`：空白新對話。
- 設定由主導覽的「設定」按鈕開啟彈出視窗，不改變目前網址或對話。

所有對話、執行資訊、模型服務、憑證遮蔽值與設定狀態都是假資料，只存在目前瀏覽器工作階段。沒有 HTTP、WebSocket 或後端連線。

## 驗證

```powershell
npm run typecheck
npm run build
```

目前尚未加入自動化前端測試。
