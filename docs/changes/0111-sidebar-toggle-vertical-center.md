# Vertically center sidebar toggle

## Objective

將桌面版側邊欄切換按鈕在同一條分隔線上垂直置中，讓它不再固定在聊天標題列高度。

## Changes

- 保留 shell 依 248px／76px sidebar width 定位的水平錨點。
- 將按鈕的垂直錨點改為 app shell 的 50% 高度，並以自身尺寸反向位移置中。
- 保留按下縮放、focus ring、900px 以下隱藏與手機漢堡選單行為。

## Public impact

沒有後端、HTTP／SSE、SQLite、資料格式或持久化設定變更；只調整桌面前端按鈕的視覺位置。

## Verification

- 前端完整 Vitest、TypeScript typecheck 與 production build 通過。
- 瀏覽器檢查展開與收合狀態的按鈕水平中心仍分別對齊 248px／76px 分隔線，
  並確認垂直中心位於 app shell 中央。
- `git diff --check` 與工作樹檢查通過。

## Remaining work

不改變手機版導航、執行面板、對話流程或 backend；本切片不新增位置偏好設定。
