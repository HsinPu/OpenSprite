# Repository scripts

這個目錄只放可重現的儲存庫驗證與維護自動化。

`test-docker.ps1` 在獨立 Compose project 與資料 volume 中驗證 Docker runtime。
從 repository 根目錄執行 `./scripts/test-docker.ps1`；`-Port` 可調整預設的 `18765`。
測試會建置映像、啟動服務、檢查 API／前端／Origin 保護、寫入設定，並重建容器確認持久化。
結束時停止測試容器，保留資料 volume 並列出名稱，不刪除資料或接觸正式部署。
