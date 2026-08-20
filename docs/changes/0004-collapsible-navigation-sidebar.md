# 0004 - Collapsible navigation sidebar

## Objective

讓左側主導覽在桌面可以收合成窄版工具列，同時維持手機抽屜選單與既有導覽行為。

## Changes

- 將桌面主導覽分為 276 px 展開狀態與 76 px 收合狀態。
- 收合後保留品牌標誌、新對話、工具與設定入口，並隱藏無法在窄版辨識的對話紀錄。
- 桌面收合狀態與手機選單開啟狀態分開管理，不共用同一個狀態。
- 補上收合控制、動態輔助標籤、控制目標與鍵盤焦點樣式。
- 手機抽屜支援 Escape 關閉、開啟後移動焦點、關閉後返回觸發按鈕，以及導覽後自動關閉。

## Public impact

只調整前端 Demo 的主導覽顯示與互動。沒有新增後端、資料、HTTP、WebSocket 或儲存契約，收合偏好不會跨重新整理保存。

## Verification

- `npm run typecheck` 通過。
- `npm run build` 通過。
- Chrome 驗證 1440 px 桌面導覽由 276 px 收合為 76 px。
- Chrome 驗證 834、390 與 320 px 的手機抽屜可用 Escape 關閉，焦點會正確移入並返回。
- 320 至 1440 px 實測沒有水平 overflow。
- `git diff --check` 通過。

## Remaining work

- 收合偏好目前只存在於當次畫面生命週期，不寫入瀏覽器儲存。
- 對話資料與工具連線仍為 Demo 假資料或停用入口。
