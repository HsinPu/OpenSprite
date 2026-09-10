# OpenSprite 0.21.0：自訂 Provider

## 交付內容

| 項目 | 實作與證據 |
| --- | --- |
| Provider 身分／協定分離 | 內建 ID 保留，自訂 UUIDv4；通用 Chat Completions 與 OpenRouter 擴充分離。 |
| catalog 與金鑰 | strict catalog、revision、加密 credential transaction；儲存及恢復測試。 |
| 模型管理 | 探索、手動新增、穩定 key 編輯／刪除、分頁；API／前端 adapter 測試。 |
| Run／排程／子代理 | 固定端點與模型能力快照、共用 mutation gate、引用與活躍執行阻擋；聊天與 RunManager 回歸。 |
| 既有資料 | SQLite v16；v15 遷移失敗 rollback，以及有內容資料逐表保留測試。 |
| 前端 | 設定管理、三語錯誤、label 關聯、Ant Radio 認證選擇、390px Drawer。 |
| 文件 | README、OpenAPI、Provider／Agent chat 架構與 local-data-layout。 |

## 驗證結果

- 完整後端：1074 passed、3 skipped；其後聊天隔離修正 17 項、額外有資料遷移 2 項通過。
- 完整前端：423 passed；提交前相關設定／Provider 套件再跑 43 項通過。
- TypeScript typecheck、production build、Python compileall、uv lock --check --offline、uv pip check 通過。
- Windows installer isolation 通過，隔離產物為 0.21.0。
- 真實 loopback HTTP 驗證請求路徑、Bearer、JSON 與 SSE，沒有使用真實金鑰或第三方帳號。
- 內嵌瀏覽器元件隔離頁驗證無認證切換、表單輸入、失敗保留內容、模型管理；
  CSS viewport 與 scrollWidth 均為 390，沒有水平溢出。
- git diff --check 通過。程式版號與 lockfile 已在 API 提交同步為 0.21.0。

## 驗證限制

- 未宣稱所有 OpenAI-compatible 服務完全相容；`/models` 成功不等於推論／工具能力已驗證。
- 瀏覽器測試使用隔離元件與模擬 API，不是已安裝產品的真實供應商 CRUD 測試。
- 真實 Linux GUI／systemd 未執行；沒有更改 Linux installer 行為。
- 既有 Vite 大型 chunk 警告與 JSDOM pseudo-element 警告仍存在。

## 提交

- `9d0a19d7`：catalog 與加密儲存。
- `79ed0d38`：API、執行整合與後端版本。
- `57c08204`：前端管理。
- 本提交：發布文件與有資料遷移回歸。

未 push，未更新使用者目前安裝的 OpenSprite。
