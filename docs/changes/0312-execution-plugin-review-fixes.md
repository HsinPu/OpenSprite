# 執行插件複查與回歸修正

- 版本：`0.21.27` → `0.21.28`。
- 分支：`codex/agent-loop-plugins`。
- 目標：複查執行插件的漏接與失敗邊界，修正已重現的任務、載入及歷史資訊問題。

## 問題與修正

- 插件自行拋出 `asyncio.CancelledError` 時，RunManager 丟棄任務但 Run 仍停在 queued／running。核對核心執行 task 的真實取消請求，將插件取消例外轉成安全的 internal_error；使用者取消、關閉與 timeout 保留既有語意。
- 取消要求已被接受、完成交易才開始時，Run 可能被標成 failed。僅在最新儲存狀態證實已取消或正在取消時，收斂為 cancelled。
- 快取的合法工廠若也有 `load()` 方法，第二次解析會誤認為 entry point。工廠快取與 entry point 來源明確區分。
- 首次選取插件在設定 PUT 同步載入套件，會阻塞事件迴圈。驗證及載入移至背景執行緒。
- Entry point 匯入或工廠 provider 自行拋出取消例外，也會安全標成 `plugin_unavailable`，不取消 HTTP 請求。
- 異常套件 metadata 可讓整個插件設定回應失效。將失敗限於該插件，內建插件繼續可用；metadata discovery 不匯入未選取的套件。
- 事件超過 500 筆時，前端會丟掉 `execution.selected`。共用事件保留器固定保留當次執行的插件資訊，供即時與歷史面板使用。
- 儲存尚未完成時關閉並重開設定，舊 GET 結果可能被當成目前選擇。此設定 API 等待在途 PUT 結束後再讀取，保存失敗也會重新取得真正的儲存狀態。
- 補驗排程任務使用選定策略，並在設定已損壞時仍可重送先前接受的排程請求。

## 驗證

2026-10-07 完成驗證：

- 修正前以隔離 Docker 重現卡住的 Run、已接受 Stop 被結算為 failed、工廠快取誤呼 `load()`、載入阻塞事件迴圈、空版本 metadata 使內建設定失效，以及前端事件截斷／讀寫競態。對應回歸測試修正後通過。
- 核心範圍 99 passed；catalog／設定／acceptance／integration 範圍 67 passed；排程 acceptance／coordinator 範圍 9 passed；前端五檔範圍 70 passed。涵蓋 shutdown、timeout、非取消儲存錯誤、失敗 PUT 清理、多寫入反序完成、等待期間新增寫入、500 事件上限與最新 Context 保留。
- `docker build --target backend-test -t opensprite:execution-plugins-backend-tested .`：**1,358 passed**（`pytest -W error`），`compileall`、`uv lock --check --offline`、`uv pip check` 通過。
- `docker build --target frontend-test -t opensprite:execution-plugins-frontend-tested .`：**610 passed / 67 files**，TypeScript 通過；正式 `npm run build` 通過。完整前端測試在後端完整驗證完成後單獨執行。
- 版本三處一致為 `0.21.28`；提交前再以目前 `backend/` 的唯讀掛載、停用網路容器執行 `uv lock --check --offline`：通過。`git diff --check` 通過。
- Docker 分支預覽 `http://localhost:18767` 保持獨立 Compose project／volume；runtime image SHA-256：`760c553317eb4c551f97a91ebae58b6c2fe9787d4bb928a51d3ae269e5dc3808`。容器 healthy、健康 API `ok`、app-info `0.21.28`；更新後仍可載入先前歷史與設定。
- Chrome 實際儲存標準策略、關閉／重開設定，確認已保存的選擇；本機無憑證模擬 Provider Run `76493eba-6138-417f-9375-476413e103a1` 完成，2 次模型呼叫、1 次續寫、`completed / stop`，歷史保留 `standard 1.0.0 / standard 1.0.0`。此次未呼叫付費模型。
- 實際檢視桌面 1864×901、平板 768×1024、手機 390×844 的執行面板／抽屜，確認插件資訊可讀、控制項可操作且無水平溢出；檢查無應用程式 console error/warning，完成後還原瀏覽器尺寸。
- 忽略的本機驗證檔：`tmp/execution-plugins-review-backend-final.log`、`tmp/execution-plugins-review-frontend-final.log`、`tmp/execution-plugins-review-runtime-final.log`、`tmp/execution-plugins-review-smoke.json`。實際工作臺截圖保存於此次 Codex visualization 目錄，不提交測試資料或容器 volume。
