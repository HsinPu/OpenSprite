# Frontend

這裡是 OpenSprite 瀏覽器介面的唯一來源。目前提供 React、TypeScript、Vite、Ant Design 實作的真實本機介面；模型廠家連線、AI 設定與 Agent chat 都透過同源 HTTP／SSE 契約連接本機服務。

## 責任

- `src/app/`：應用外框、導覽、dialog 與 feature 組裝。
- `src/api/`：Provider、General/AI settings 與 Agent chat 的 HTTP／SSE client。
- `src/features/conversation-settings/`：持久化啟動目的地與鍵盤傳送偏好。
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

每則使用者與 AI 訊息下方會顯示建立時間，依確認後的介面語言與時區格式化到分鐘；
資料來源仍是訊息契約的 UTC `createdAt`，不另存一份前端時間。
AI 回覆的時間旁可開啟該回覆對應的歷史 Run；沒有 AI 回覆的終止 Run 則從使用者
訊息旁開啟。歷史 snapshot 與 events 使用既有 Run API/SSE 即時讀取，與目前 Agent
Run 使用不同的前端狀態，因此查看歷史不會停止或取代目前執行。

OpenAI 與 Anthropic 目前使用前端固定模型清單。OpenRouter 連線後會透過 bodyless `POST /api/providers/openrouter/models` 載入帳戶可用模型；清單只在該次設定視窗工作階段的記憶體中重用，不寫入 localStorage、網址或 `.opensprite`。模型選單可用顯示名稱或完整模型 ID 搜尋。

設定視窗以「一般」與「AI 模型」作為可操作分類。未實作的模型偏好、
通知、記憶、工具、外觀與隱私功能以停用的 `Demo` 分類或「未來上線」資訊列呈現，
方便追蹤規劃，但不建立 session-only 假狀態或可操作控制項。

介面語言支援 `zh-TW`、`en` 與 `ja`；時區支援系統設定、`Asia/Taipei` 與 `UTC`。
兩者透過同源 General Settings API 保存在本機服務。語言切換會同步 React、Ant Design、
API 錯誤文字與文件 `lang`；時區控制 Today 分組及 Execution 時間。前端不寫入
localStorage 或網址，繁體中文是固定 fallback。

「啟動與對話」設定透過獨立 Conversation Settings API 保存。啟動時若網址已有有效的
`#chat=<uuid>` 或 `#new-chat`，網址優先；否則可選擇開啟新對話或最近更新的對話。
訊息可設定為 Enter 傳送（Shift + Enter 換行），或 Ctrl/Cmd + Enter 傳送（Enter 換行）；
IME 組字期間不會誤送。
同一設定也可關閉聊天輸出自動跟隨。開啟時，送出訊息會定位最新內容；AI 串流僅在
使用者仍靠近底部時跟隨，主動往上閱讀會暫停，回到底部後恢復。載入較早訊息會補償
插入高度以維持原閱讀位置；關閉時送出及串流均不改變目前位置。

聊天工作台上方與「AI 模型」設定頁共用同一份確認後的選擇。啟動時會讀取已保存的選擇與已連線的固定廠家；沒有選擇而有可用固定模型時，會保存固定順序中的第一個模型。儲存失敗會保留原選擇。OpenRouter 的暫時讀取失敗不會清除既有選擇；成功讀到模型清單後，才會處理已不存在模型的 fallback。

## 驗證

```powershell
npm run typecheck
npm test
npm run build
```

Vitest/jsdom 與 React Testing Library 會驗證 provider API 的嚴格回應
邊界、設定 dialog 的焦點回復、provider 操作併發與金鑰 modal 的安全互動。
