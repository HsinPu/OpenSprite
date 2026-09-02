# Version 0.2.3

## Objective

讓本機 OpenSprite 版本識別跟隨本輪前端串流效能與 runtime 可靠性修正，方便測試時確認實際執行版本。

## Changes

- 將 authoritative backend package 與產品版號從 `0.2.2` 升級為 `0.2.3`。
- 同步 `backend/uv.lock` 的 editable package metadata。
- 更新 `/api/app-info`、build-info 驗證與版本一致性測試的預期值。

## Public impact

設定「關於」頁與 `GET /api/app-info` 會顯示產品版本 `0.2.3`。沒有 API、資料庫、憑證、Provider 或使用者資料格式變更。

## Verification

- Backend 版本、app-info、build-info 測試通過。
- `uv lock --check --offline` 通過。

## Remaining work

這是本機版本識別更新；不建立 release artifact、不建立遠端 tag，也不推送遠端。
