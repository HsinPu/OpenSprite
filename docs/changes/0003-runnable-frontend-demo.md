# 0003 - Runnable frontend demo

## Objective

把已確認的前端概念圖實作成可啟動、可操作且只使用假資料的 React Demo，不建立後端或通訊契約。

## Changes

- 建立 Vite HTML 與 React 應用入口。
- 建立固定主導覽、對話紀錄、新對話與設定頁切換。
- 建立 AI 對話工作台、執行過程、本次執行資訊與假訊息回覆。
- 建立一般設定與 AI 模型設定，所有控制項只修改本機 React state。
- 加入 `dev`、`typecheck`、`build` scripts 與可直接開啟畫面的 hash 路徑。
- 加入桌面與窄螢幕版面；手機版主導覽改為可開關的側邊選單。
- 更新 repository 與 frontend 使用說明。

## Public impact

新增可啟動的瀏覽器 Demo。沒有 HTTP、WebSocket、後端、真實憑證儲存、資料庫或 installer 行為；畫面內容不得視為前後端契約。

## Verification

- `npm install --package-lock-only --ignore-scripts` 通過，audit 為 0 vulnerabilities。
- `npm run typecheck` 通過。
- `npm run build` 通過，Vite 成功產生 production assets。
- 本機 Vite server 回傳 HTTP 200，HTML 包含 React root 與 module entry。
- Chrome 實際載入對話工作台、一般設定與 AI 模型設定桌面畫面。
- Chrome DevTools Protocol 驗證設定分類切換、hash 狀態與假訊息送出回覆。
- 390 px viewport 實測沒有水平 overflow；修正聊天 header 與訊息卡片在窄螢幕的寬度問題。
- `git diff --check` 通過。

## Remaining work

- 使用者確認 Demo 的畫面與操作方向。
- 補上其他設定分類與工具連線畫面。
- 選定測試工具後加入元件與瀏覽器自動化測試。
- 畫面穩定後才設計前後端 contracts 與 backend。
