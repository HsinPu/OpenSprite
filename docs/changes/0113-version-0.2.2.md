# Version 0.2.2

## Objective

識別包含桌面側欄與執行面板分隔線控制調整的 OpenSprite 本機版本。

## Changes

- 將 authoritative backend package 與產品版號從 `0.2.1` 升級為 `0.2.2`。
- 同步 `backend/uv.lock` 與 build-info／app-info 驗證使用的 package metadata。
- 保持前端 private package 版本與 HTTP、SQLite、Provider、Context 及使用者資料格式不變。

## Public impact

設定「關於」頁與 `GET /api/app-info` 顯示產品版本 `0.2.2`；沒有 API、資料庫、憑證或前端 payload contract 變更。

## Verification

- 版本一致性測試、前端驗證與 Windows installer build-info 版本檢查通過。
- `uv lock --check --offline`、`uv pip check`、`git diff --check` 與工作樹檢查通過。

## Remaining work

這是本機版本識別更新；不建立 release artifact、不建立遠端 tag，也不在本切片推送遠端。
