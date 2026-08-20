# 0005 - Collapsible execution panel

## Objective

讓右側「本次執行」資訊可以收合，避免執行細節長期占用對話空間。

## Changes

- 桌面與平板的執行面板可由完整內容收合為 68 px 工具列。
- 收合按鈕配置在右側面板標題左方，與左側導覽的控制形成鏡像關係。
- 收合內容使用原生隱藏語意，不會留在鍵盤或螢幕閱讀器操作順序。
- 收合控制提供動態標籤、`aria-expanded` 與唯一控制目標。
- 手機初次載入預設收合，顯示狀態、模型與步驟摘要，展開後呈現完整內容。
- 收合狀態由執行面板自己管理，不改動 `ChatWorkspace` 公開輸入或建立全域狀態。

## Public impact

只調整前端 Demo 的資訊呈現。沒有改變假資料內容，也沒有新增後端、執行流程、API 或持久化行為。

## Verification

- `npm run typecheck` 通過。
- `npm run build` 通過。
- Chrome 驗證 1440 px 面板由約 361 px 收合為 68 px，內容正確隱藏。
- Chrome 驗證 834 px 收合後不再壓縮主要對話區。
- Chrome 驗證 390 與 320 px 初次載入預設顯示收合摘要，且可重新展開完整內容。
- 320 至 1440 px 實測沒有水平 overflow。
- `git diff --check` 通過。

## Remaining work

- 收合偏好目前不跨重新整理或不同對話保存。
- 本次執行內容仍為 Demo 假資料，不代表未來後端契約。
