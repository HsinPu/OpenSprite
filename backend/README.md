# OpenSprite Backend

Python 3.12–3.13 / FastAPI 的本機文字 Agent 服務。HTTP／SSE 的權威契約位於 [`../contracts/`](../contracts/README.md)。

## 職責與邊界

- `application/`：接受文字任務、模型／工作區／插件快照與取消。
- `agent/`：Host API v3、單一 Agent Loop、上下文預算、摘要及輸出續寫；依賴 persistence 與 Provider 介面。
- `inference/`：OpenAI Responses、Anthropic Messages、OpenRouter／compatible Chat Completions 的文字串流；拒絕工具或 action 回應。
- `conversations/`：SQLite v21 的對話、訊息、Run、事件與摘要。新資料庫只有五張核心表。
- `providers/` 與 `credentials/`：Provider 設定、能力快照與 AES-256-GCM 密文。
- `execution_plugins/`：wheel 的靜態檢查、快取、部署包與已安裝內容核對。
- `api/`：薄 HTTP 路由；`runtime.py` 組裝單次 lifespan 的依賴並在結束時關閉。
- `app_paths.py`：唯一 `.opensprite` 路徑配置。工作區路徑只提供中繼資料，不賦予文字核心檔案存取能力。

Tools、Skills、Subagents、自訂 Agent、MCP、核准與排程的執行模組及路由已移除。既有資料僅保留在磁碟，不重新組裝舊功能。詳見 [乾淨核心設計](../docs/architecture/clean-agent-core.md)。

## 本機開發

先用平台安裝器初始化本機存取設定，並停止其背景後端；同一資料根目錄不能同時啟動兩個程序。從本目錄執行：

```powershell
uv sync --dev
uv run uvicorn opensprite_backend.runtime:create_system_app --factory --host 127.0.0.1 --port 8765 --workers 1 --no-proxy-headers
```

這是 API 開發入口；同源前端由 Vite proxy 或安裝後的 `installed_runtime` 提供。套件沒有應用程式 CLI。

本機安全層只接受 localhost Host，修改請求須有相同 Origin；不信任 proxy headers、不啟用跨來源 CORS。Vite 使用 `changeOrigin: false` 保留瀏覽器 Host／Origin。缺少存取設定時預設密碼保護，開發入口不自動產生 bootstrap；首次設定請使用平台安裝器產生的一次性網址，詳見 [本機存取設計](../docs/architecture/local-authentication.md)。

## 持久化

唯一資料根目錄為 Windows `%USERPROFILE%\.opensprite` 或 Linux `~/.opensprite`。同一根目錄只能由一個後端程序寫入，不使用多 worker 或 reload。

| 資料 | 位置與行為 |
| --- | --- |
| 供應商憑證 | `auth.json` 密文及 `config/credential.key` 的隨機金鑰；API 不回傳原始金鑰 |
| AI 設定 | `config/settings.json`，schema v11；新保存不包含工具政策 |
| 對話與執行 | `data/opensprite.db`；首段文字立即保存，後續批次保存 |
| 執行插件 | `config/execution.json` 及 AppPaths 管理的快取／套件中繼資料 |
| 診斷與 Prompt receipt | `logs/`；敏感 Provider 資料不寫入公開事件 |

需要資料時才建立目錄。一般讀取缺少的設定不寫入檔案；套件匯入不安裝或載入程式碼。備份整個資料根目錄前先停止服務；同時取得密文與金鑰可解密，備份必須受保護。

SQLite v20 經結構核對後升至 v21，不刪除舊表或原始事件；歷史讀取只投影目前支援的事件。更早版本先使用 `0.21.30` 升級。詳見 [資料配置](../docs/architecture/local-data-layout.md)。

## 驗證

```powershell
uv run pytest -W error
uv run python -m compileall -q src tests
uv lock --check --offline
uv pip check
```

測試使用隔離資料根目錄、協定 fixture 與 `httpx.MockTransport`；通過不代表真實模型推理品質已驗證。插件另需 [實際 wheel 安裝驗證](../docs/architecture/execution-plugin-authoring.md)。
