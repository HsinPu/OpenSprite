# Sidebar toggle on layout divider

## Objective

讓桌面版側邊欄切換按鈕固定在左側導覽與聊天區的分隔線上，並維持
手機版的漢堡選單行為。

## Changes

- 將側邊欄切換按鈕的狀態與渲染責任移至 `App` shell。
- 使用 Ant Design `Button`，保留繁中、英文、日文的可見標籤、tooltip、
  `aria-expanded` 與 `aria-controls`。
- 以 shell 的 248px 展開寬度與 76px 收合寬度 token 定位按鈕，收合時按鈕
  會跟著同一條分隔線移動。
- 桌面 ChatWorkspace 標題列只保留執行面板控制；手機版按鈕在 900px 以下
  隱藏，仍由固定頂部的漢堡選單開啟導航。

## Public impact

沒有後端、HTTP／SSE、SQLite 或持久化資料變更。只調整前端桌面版導航按鈕
的 DOM 所有權與視覺位置；側邊欄寬度、收合狀態與手機導航契約維持不變。

## Verification

- App shell 測試確認按鈕使用 Ant Design、位於 shell 而非 ChatWorkspace 標題列，
  並控制 `main-navigation-sidebar`。
- ChatWorkspace 測試確認不再渲染側欄按鈕，執行面板按鈕仍留在標題列。
- 完成前端 Vitest、TypeScript typecheck、production build、`git diff --check`
  與工作樹檢查後提交。

## Remaining work

不改變手機版導航互動、執行面板、對話資料流程或後端 API；本切片不包含新的
導航動畫、持久化偏好或瀏覽器端 E2E 自動化。
