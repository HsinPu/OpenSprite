# 自訂 Provider catalog 與加密儲存

## 範圍

- 新增 canonical UUIDv4 Provider ID，保留內建三家 ID。
- 新增 strict catalog、Provider／模型 revision、穩定模型 key 與 Base URL 驗證。
- 透過 AppPaths 對應 config/providers.json 與暫時交易紀錄。
- 自訂 API Key 沿用 AES-256-GCM，跨 catalog／credential 更新使用加密暫存與恢復紀錄。
- service 提供新增、編輯、刪除、手動模型與探索合併原語；本提交不單獨啟用 HTTP API。

## 驗證

catalog model/store/transaction、custom service/credentials 及相關契約測試合計 41 項通過。
完整 feature 的其他工作仍在後續提交，本紀錄不代表 0.21.0 已完成發布。
未 push、未更新已安裝 runtime。
