# Version 0.2.4

## Objective

讓本機 OpenSprite 版本識別包含工具設定頁與 Run 工具可用性快照，方便確認安裝版本。

## Changes

- 將 authoritative backend package 與產品版號從 `0.2.3` 升級為 `0.2.4`。
- 同步 `backend/uv.lock`、`/api/app-info` 與版本一致性測試。

## Public impact

設定「關於」頁與 `GET /api/app-info` 顯示產品版本 `0.2.4`。不建立 release artifact 或遠端 tag。

## Verification

- Backend 版本、app-info 與 build-info 測試通過。
- `uv lock --check --offline` 通過。
- Windows installer isolation test 通過並安裝 backend `0.2.4`。

## Remaining work

正式 Release、tag 與發佈流程不在本切片範圍。
