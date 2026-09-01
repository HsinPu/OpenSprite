# Execution toggle on layout divider

## Objective

將桌面版「本次執行」切換按鈕從聊天標題列移到聊天內容與執行面板之間的分隔線，
並讓它在分隔線上垂直置中。

## Changes

- 保留 `ChatWorkspace` 既有執行面板狀態、歷史 Run 與切換處理，僅改變桌面控制按鈕的渲染位置。
- 使用三軌 CSS Grid：聊天內容、零寬度分隔線控制軌、執行面板；展開與 68px 收合狀態都共用實際欄位邊界。
- 桌面按鈕維持 Ant Design、40×40 觸控尺寸、方向圖示、`aria-expanded`、`aria-controls`、tooltip 與既有翻譯。
- 900px 以下隱藏桌面按鈕，手機版仍使用既有執行 Drawer。

## Public impact

沒有後端、HTTP／SSE、SQLite、Context、對話資料或持久化設定變更；只調整桌面前端執行面板控制的 DOM 位置與樣式。

## Verification

- App 與 ChatWorkspace 測試確認側欄控制仍由 shell 擁有、執行控制不在聊天標題列且位於同一個工作區。
- 完整前端 Vitest、TypeScript typecheck、production build、`git diff --check` 與瀏覽器桌面／手機版檢查通過。

## Remaining work

不改變手機 Drawer、執行面板內容、歷史 Run 選取或任何 API 契約；本切片不新增位置偏好設定。
