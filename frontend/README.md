# Frontend

這裡是 OpenSprite 瀏覽器介面的唯一來源。目前提供 React、TypeScript、Vite、Ant Design 實作的前端 Demo；模型廠家連線會透過本機 Provider Connections HTTP API 管理。

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

對話與執行資訊仍為假資料，只存在目前瀏覽器工作階段。預設模型選擇則會透過同源 `GET`／`PUT /api/settings/model` 保存到本機服務；前端只處理 Provider ID 與 model ID，不使用 localStorage、網址或瀏覽器 log 保存選擇、動態模型清單或 API 金鑰。AI 模型設定會呼叫同源 `/api/providers`，由 Vite 的 dev/preview proxy 轉送到 `http://127.0.0.1:8765` 且保留 browser Host/Origin（`changeOrigin: false`）。API 金鑰只存在於連線 modal 的密碼欄位狀態，送出、錯誤、取消或卸載時會清除；前端不會儲存、預填或顯示原始金鑰。

OpenAI 與 Anthropic 目前使用前端固定模型清單。OpenRouter 連線後會透過 bodyless `POST /api/providers/openrouter/models` 載入帳戶可用模型；清單只在該次設定視窗工作階段的記憶體中重用，不寫入 localStorage、網址或 `.opensprite`。模型選單可用顯示名稱或完整模型 ID 搜尋。

聊天工作台上方與「AI 模型」設定頁共用同一份確認後的選擇。啟動時會讀取已保存的選擇與已連線的固定廠家；沒有選擇而有可用固定模型時，會保存固定順序中的第一個模型。儲存失敗會保留原選擇。OpenRouter 的暫時讀取失敗不會清除既有選擇；成功讀到模型清單後，才會處理已不存在模型的 fallback。

## 驗證

```powershell
npm run typecheck
npm test
npm run build
```

Vitest/jsdom 與 React Testing Library 會驗證 provider API 的嚴格回應
邊界、設定 dialog 的焦點回復、provider 操作併發與金鑰 modal 的安全互動。
