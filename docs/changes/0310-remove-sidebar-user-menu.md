# Remove sidebar user menu

## Objective

移除使用者指出的側欄底部「使用者」區塊及分隔線。
產品版本：`0.21.25` → `0.21.26`。

## Changes

- 移除固定的使用者文字、重複設定選單及其未使用元件、樣式與三語文案。
- 設定維持左側資源列的齒輪入口；關於頁仍在設定分類內，返回對話及 Escape 的焦點回到實際入口。
- 密碼登入模式的單一 Session 登出移到「設定 → 隱私 → 登入狀態」，沿用既有登出 API；本機信任模式不顯示登入操作。
- 更新既有 App 導覽測試，移除已刪除選單的測試，驗證單一 Session 登出會回到登入畫面且不撤銷其他 Session。

## Verification

- Docker 前端建置通過；App／PrivacySettings 兩個測試檔案的 41 項測試通過。
- 現有測試確認桌面與手機的設定入口、草稿／輸入元素保留、Escape／返回焦點；重新展開側欄時沒有「使用者」按鈕。
- 單一 Session 登出呼叫 `/api/auth/logout` 並回到登入畫面，不呼叫 `/api/auth/logout-all`；本機信任模式沒有登出操作。
- Docker 後端建置環境中的 `uv lock --check --offline`、`uv pip check` 通過；三份產品版本一致。
- 完整 Docker 前端驗證通過：64 個測試檔案、570 項測試、TypeScript 檢查及正式建置。測試數量變化來自刪除兩項舊選單測試、增加一項 Session 登出測試。
- `docker compose up -d --build --wait` 更新至 `0.21.26`；`/healthz` 正常、Docker 為 `healthy`，仍使用 `opensprite_opensprite-data`，加密檔案更新前後摘要一致。
- Chrome 實際確認桌面與 390 × 844 手機側欄不再有「使用者」區塊或分隔線，齒輪入口可用，手機沒有水平溢出。
- 實際檢查設定／隱私／Escape／返回對話；未送出草稿在更新及檢查後保留，瀏覽器沒有應用程式 error。
- 部署映像：`sha256:ca205a6db445587330b0e70b7342e5dcfa54296322bd9f08a556d29d98fa804a`。舊版映像保留為 `opensprite:rollback-workbench-0.21.25`，沒有刪除資料卷。
