# Agent workbench canvas and generated brand

## Objective

在改版分支建立完整、緊湊的 Agent 工作臺，產生正式 Logo，實際驗證後更新 Docker。
產品版本：`0.21.24` → `0.21.25`。

## Changes

- 左側使用石墨色資源列與工作區導覽，模型、Agents、Skills 及設定連到既有功能；對話清單加入最後一則訊息摘要。
- 頁面標頭依序顯示工作區與任務；新對話將工作目標、可編輯的任務範本及輸入區連成同一個工作畫布。
- 任務範本會追加到既有草稿並聚焦輸入區，不會自行送出訊息；模型入口沿用既有設定流程。
- 回覆採較平面的文件閱讀布局，保留 Markdown、程式碼、歷史執行、工具核准、面板縮放與手機抽屜。
- 設定依工作環境、Agent 能力及應用程式分組；一般設定、Agents、Skills、排程與登入頁同步沿用主題及較緊湊的表面。
- 共用 `BrandLogo` 將新圖片套用於資源列、助手訊息、執行資訊與登入頁；瀏覽器圖示使用同一份資產。
- 三種語言同步更新文案。未新增後端業務功能、外部模型憑證或第二套 UI 函式庫。
- 實際停止測試發現既有取消流程會在保存緩衝中的短回覆時誤判失敗；SQLite 現在允許 `running`／`cancelling` 狀態保存已接收的文字，再記錄 `cancelled`，所有終止狀態仍禁止追加。

## Logo provenance

- 模式：內建 `image_gen.imagegen`，新圖片生成，`transparent_background=true`。
- 提交資產：`frontend/public/brand/opensprite-logo.png`。
- 生成提示如下；實際交付以已檢視的 PNG 為準。

```text
Use case: logo-brand
Asset type: final raster application logomark for OpenSprite, a professional local AI agent workbench.
Primary request: create one original, polished, extremely simple geometric symbol. A compact open rounded-square frame with a precise S-like path flowing through its center, suggesting an agent turning intent into work. It must read strongly at 24px, with generous coherent stroke weight, crisp silhouette and disciplined spacing.
Style/medium: flat vector-like brand mark rendered as a clean raster with real transparent alpha.
Composition/framing: single centered mark, tightly framed with about 8 percent clear padding, square image. No wordmark or letters outside the symbol.
Color palette: muted jade/teal #2cc6ae with a darker teal #087f8c accent; works on both white and deep graphite #17242e. Two flat colors maximum.
Constraints: transparent background; one resolved mark only, no grid of options, no mockup. Distinctive quiet enterprise productivity identity. No gradients, shadows, glow, 3D, tiny lines, decorative sparkles, robot faces, brains, circuits, watermark, or text.
```

## Verification

- `docker build --target frontend-test -t opensprite:workbench-v2-frontend-tested .` 通過：65 個測試檔案、571 項測試、TypeScript 檢查及正式建置。
- 新增六項回歸測試，涵蓋範本追加／聚焦與桌面、手機資源入口的草稿及焦點保留；設定分類斷言同步至實際分組順序。
- 新增入口測試對實際延遲載入的設定頁使用五秒等待期限；保留分類、同一輸入元素、草稿及返回焦點斷言。
- Docker 後端建置環境中 `uv lock --check --offline`、`uv pip check` 通過。
- 新增取消時保存部分回覆與終止狀態拒絕寫入測試；舊程式確實重現兩項失敗，修正後 RunManager／SQLite 的 48 項測試通過。
- `docker build --target backend-test -t opensprite:workbench-v2-backend-tested .` 通過：1,221 項 `pytest -W error` 測試、Python 編譯、離線鎖檔檢查及相依套件檢查。
- Chrome 實際檢視 1440 × 900 桌面、768 × 1024 平板、390 × 844 手機及 844 × 390 短螢幕；平板及手機沒有頁面水平溢出，短螢幕多行輸入、送出控制及說明均在可視範圍。
- 實際確認資源／設定導覽、返回對話、手機主選單、執行抽屜、Escape 及草稿保留。
- 在獨立 `opensprite-workbench` Compose project 的專用資料卷中加入本機模擬 Provider；實際送出、SSE 回覆、Markdown 表格／清單／程式碼、重新整理持久化、歷史執行及診斷明細均已檢查。
- 停止回覆已在修正後重測：瀏覽器顯示「已停止」，部分文字及停止結果在重新整理後保留，沒有將此次取消誤判為失敗。
- 本機模擬 Provider 不使用憑證、不呼叫外部 API、不執行工具；用量是合成數值，驗證不代表外部模型或真實工具執行成功。fixture 僅位於忽略的 `tmp/`。
- Vite 保留既有 chunk-size 提示；測試保留既有 React act 及 jsdom pseudo-element 訊息。

## Docker delivery

- `docker compose up -d --build --wait` 成功更新既有 `opensprite-opensprite-1`；`http://localhost:8765/` 提供新版工作臺。
- `/healthz` 回應 `{"status":"ok"}`，Docker healthcheck 為 `healthy`，`/api/app-info` 確認 `0.21.25`。
- 部署映像：`sha256:8dd630608ddbd439b5ce9fb9b68bb33400d7617f2b9cf6d99754314f01462cd6`。
- 仍掛載 `opensprite_opensprite-data` 到 `/home/opensprite/.opensprite`；更新前後比較 `auth.json` 與 `config/credential.key` 的存在狀態及 SHA-256，結果一致，未讀出或記錄原始憑證。
- 舊版映像保留為 `opensprite:rollback-workbench-0.21.23`；沒有刪除資料卷或執行 Docker prune。
- HTTP 提供的 Logo 與提交資產 SHA-256 相同；重新開啟正式網址確認渲染的新畫面，瀏覽器沒有應用程式 error。
- 本機模擬 Provider 僅位於隔離預覽的資料卷，正式部署沒有加入測試供應商或測試對話。
- 驗證完成後已停止 `--rm` 模擬供應商 sidecar；預覽資料保留，沒有刪除使用者資料。
