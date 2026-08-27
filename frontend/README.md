# Frontend

這裡是 OpenSprite 瀏覽器介面的唯一來源。目前提供 React、TypeScript、Vite、Ant Design 實作的真實本機介面；模型廠家連線、AI 設定與 Agent chat 都透過同源 HTTP／SSE 契約連接本機服務。

## 責任

- `src/app/`：應用外框、導覽、dialog 與 feature 組裝。
- `src/api/`：Provider、General/AI settings 與 Agent chat 的 HTTP／SSE client。
- `src/features/chat/`：Conversation 清單、Run 狀態、聊天畫面與 SSE 互動。
- `src/features/settings/`：設定視窗與尚未上線的一般偏好呈現。
- `src/features/general-settings/`：持久化語言、時區與日期時間格式。
- `src/i18n/`：typed locale catalog、React locale context 與繁中／英文／日文資源。
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

## 目前範圍

- `/` 或 `/#chat`：AI 對話工作台。
- `/#new-chat`：空白新對話。
- 設定由主導覽的「設定」按鈕開啟彈出視窗，不改變目前網址或對話。

對話清單、可見訊息、Run snapshot 與安全語意事件都來自本機服務；執行期間以 SSE 顯示增量文字與狀態，終止後重新讀取 durable Run 與 Messages。模型選擇與回應模式會透過同源 `GET`／`PUT /api/settings/ai` 以單一設定保存到本機服務；前端只處理 Provider ID、model ID 與 `default`／`fast`／`balanced`／`deep`，其中「預設」代表執行時不指定推理強度。前端不使用 localStorage、網址或瀏覽器 log 保存設定、動態模型清單或 API 金鑰。AI 模型設定會呼叫同源 `/api/providers`，由 Vite 的 dev/preview proxy 轉送到 `http://127.0.0.1:8765` 且保留 browser Host/Origin（`changeOrigin: false`）。API 金鑰只存在於連線 modal 的密碼欄位狀態，送出、錯誤、取消或卸載時會清除；前端不會儲存、預填或顯示原始金鑰。

OpenAI 與 Anthropic 目前使用前端固定模型清單。OpenRouter 連線後會透過 bodyless `POST /api/providers/openrouter/models` 載入帳戶可用模型；清單只在該次設定視窗工作階段的記憶體中重用，不寫入 localStorage、網址或 `.opensprite`。模型選單可用顯示名稱或完整模型 ID 搜尋。

「自動選擇可用模型」與「顯示模型名稱」目前只顯示為不可操作的
「未來上線」項目，不建立 session-only 假設定，也不影響現有模型流程。

介面語言支援 `zh-TW`、`en` 與 `ja`；時區支援系統設定、`Asia/Taipei` 與 `UTC`。
兩者透過同源 General Settings API 保存在本機服務。語言切換會同步 React、Ant Design、
API 錯誤文字與文件 `lang`；時區控制 Today 分組及 Execution 時間。前端不寫入
localStorage 或網址，繁體中文是固定 fallback。

聊天工作台上方與「AI 模型」設定頁共用同一份確認後的選擇。啟動時會讀取已保存的選擇與已連線的固定廠家；沒有選擇而有可用固定模型時，會保存固定順序中的第一個模型。儲存失敗會保留原選擇。OpenRouter 的暫時讀取失敗不會清除既有選擇；成功讀到模型清單後，才會處理已不存在模型的 fallback。

## 驗證

```powershell
npm run typecheck
npm test
npm run build
```

Vitest/jsdom 與 React Testing Library 會驗證 provider API 的嚴格回應
邊界、設定 dialog 的焦點回復、provider 操作併發與金鑰 modal 的安全互動。
