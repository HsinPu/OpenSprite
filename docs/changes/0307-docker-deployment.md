# Docker deployment

## Objective

加入可建置、可啟動並可重現驗證的 Docker 部署。
產品版本：`0.21.22` → `0.21.23`。

## Changes

- 多階段 Dockerfile 以 npm lockfile 建置前端、以 uv locked sync 安裝後端，沿用 `create_installed_app` 的同源 runtime。
- 正式映像使用非 root UID/GID 10001、單一 Uvicorn worker、停用 proxy headers，提供 `/healthz` healthcheck。
- Python venv 使用 `--copies --without-pip`，保留 MCP stdio 不允許符號連結 executable 的既有政策，無需修改產品或既有測試。
- Compose 預設只發布 `127.0.0.1:8765`，支援 `OPENSPRITE_PORT`，提供 init、重啟策略與 graceful shutdown。
- 全部個人資料掛載到 named volume 的 `/home/opensprite/.opensprite`，首次啟動使用既有 `trusted_local` policy，不加入 CLI 或修改 HTTP 契約。
- `.dockerignore` 限制建置輸入，排除本機相依套件、環境、資料、憑證與快取。
- 提供前端／後端測試 targets 與獨立 Compose project 的 `scripts/test-docker.ps1`；測試完成停止容器、保留資料 volume。
- README 記錄部署、更新、連接埠、SSH tunnel、資料備份與容器環境限制。

## Public impact

新增 Docker 部署入口；既有桌面安裝與資料路徑契約維持。
Docker volume 與主機桌面資料分開，不可多個後端同時寫入相同 volume。
容器路徑、localhost、MCP stdio 執行檔與資料夾選擇器均屬容器環境。
此切片只支援 localhost／SSH tunnel，直接網域、LAN 或公開服務部署不包含在內。

## Verification

- `docker compose config --quiet` 通過。
- `docker build --target frontend-test -t opensprite:frontend-test .` 通過：65 個檔案、565 項測試、TypeScript 與 production build。
- 首次以預設 worker 數執行出現三項測試逾時／等待失敗；Docker test target 限制 `--maxWorkers=2` 後完整通過，未放寬測試 timeout 或修改功能。
- `./scripts/test-docker.ps1` 通過：health、前端／資產、API 版本、錯誤／缺少 Origin 拒絕、設定 PUT、UID 10001、AppPaths、force-recreate 後設定保留；測試 project 已停止且資料 volume 保留。
- 實際啟動曾發現 named volume 根目錄擁有者問題；Dockerfile 已明確設定根目錄及 config 的 UID/GID，再以全新 volume 完整驗證通過。
- Chrome 實際確認主畫面與設定頁，檢視桌面、768×1024 與 390×844 版面，手機分類導覽可切換「關於」並顯示 `0.21.23`；沒有應用程式 console error（擴充功能自身有警告）。
- `npm audit --omit=dev --json`：0 漏洞；完整 audit 回報既有開發相依套件 `source-map-js`、`undici` 的兩項 high，不在 runtime 映像中，未變更相依套件。
- `docker build --target backend-test -t opensprite:backend-test .` 通過：`pytest -W error` 1215 passed、compileall、`uv lock --check --offline` 與 `uv pip check`。
- 首次 Linux 後端測試因 venv Python 符號連結出現七項 MCP 失敗；改用實體 venv Python 後全套通過，沒有放寬 executable 政策或保留 fixture 修改。
- 最終 `docker compose up -d --build --wait --wait-timeout 120` 通過，`opensprite-opensprite-1` 為 healthy、只發布 `127.0.0.1:8765`；容器回報 `0.21.23`、`/healthz` 為 ok，venv Python `is_symlink()` 為 False，啟動後無日誌權限錯誤。
- 已有 QuantHelm 與 TradeBridge 容器仍正常執行；本次沒有停止或刪除其他專案容器／volume。

## Remaining work

不包含公開網域部署、TLS 反向代理、主機 GUI 整合或自動搬移桌面資料。
Docker source build 未產生 Git revision 的 `build-info.json`，關於頁沿用現有 development build 標示；產品版本來自已安裝套件。
