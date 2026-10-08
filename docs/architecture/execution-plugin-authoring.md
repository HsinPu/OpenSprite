# 撰寫 Agent Loop 插件（API v3）

OpenSprite 0.21.33 使用單一 Agent Loop 插件。執行流程與兩個恢復判斷必須在同一實例，沒有獨立 Policy entry point。範例套件版本 0.3.0，可從工作臺下載完整專案。

## 可建置的最小實作

建立 `src/opensprite_execution_example/plugin.py`：

```python
"""A single API v3 Loop coordinates flow and decides eligible recovery."""
from opensprite_backend.agent.plugin import (
    CompletionState, ContextRetryState, DriverResult, ExecutionHost,
)


class MainRetryOnlyLoop:
    async def execute(self, host: ExecutionHost) -> DriverResult:
        await host.checkpoint()
        turn = await host.next_turn()
        await host.checkpoint()
        return await host.finish(turn)

    def allow_context_retry(self, state: ContextRetryState) -> bool:
        return state.phase == "main" and state.cause == "provider_context_limit"

    def allow_output_continuation(self, state: CompletionState) -> bool:
        return False


class MainRetryOnlyFactory:
    api_version = 3

    def create(self) -> MainRetryOnlyLoop:
        return MainRetryOnlyLoop()


def create_plugin_factory() -> MainRetryOnlyFactory:
    return MainRetryOnlyFactory()
```

範例在模型前後檢查取消，只允許主模型遭 Provider 上下文超限時的核心合格重試，不自動續寫。同步判斷方法快速回傳真正的 bool；不可讀取憑證、呼叫外部服務、寫入日誌或修改模型設定。每次 `create()` 必須建立新插件，避免 Run 共用可變狀態。

建立 `pyproject.toml`：

```toml
[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[project]
name = "opensprite-execution-example"
version = "0.3.0"
description = "Single OpenSprite Agent Loop with checkpointed execution and main-context recovery"
readme = "README.md"
requires-python = ">=3.12,<3.14"
dependencies = ["opensprite-backend>=0.21.33,<0.22"]

[project.entry-points."opensprite_backend.agent_loops.v3"]
example_main_retry_only = "opensprite_execution_example.plugin:create_plugin_factory"

[tool.hatch.build.targets.wheel]
packages = ["src/opensprite_execution_example"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
filterwarnings = ["error"]
```

換成你自己的 distribution、Python 模組和插件 ID。ID 為小寫英文字母開頭，後續可含小寫字母、數字、`_`、`.`、`-`，最多 64 字元；不可使用 `standard` 或 `no_recovery`。entry point 指向無參數的 factory provider，不是插件實例。`agent_loops.v3` 是 metadata 群組名稱，不需要建立同名 Python 模組。

## Host 契約與測試

API v3 一次只提供一個主要 `next_turn()`，Host 內部管理重試與續寫，不支援任意多回合規劃。操作依序 await，不可並行、修改或複製 turn/result，且 finish 後不可再請求模型。回傳 Host 的原始結果，讓 Host 失敗和取消向上傳遞。

先用多組變動文字測試原始 turn/result、不同回覆、模型前後取消、Host 失敗、新實例與恢復判斷。再用實際核心測試 Provider 上下文超限及輸出截斷，斷言真正的請求次數、SQLite 狀態與 SSE。固定協定 fixture 可驗證控制流程；不能當成真實模型驗證。

從專案根目錄、相容的後端開發環境執行：

```powershell
uv run --project backend python -m pytest examples/execution-plugin/tests -W error
uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin
$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path tmp/execution-plugin-wheel/opensprite_execution_example-0.3.0-py3-none-any.whl).Path
uv run --project backend python scripts/verify_execution_plugin_wheel.py
```

驗證腳本離線安裝 wheel 到暫存 target，另起隔離 Python、不同工作目錄，檢查實際 distribution、entry point 與模組來源。透過真實 Host、SQLite、Provider adapter 使用 UUID 輸入；最後檢查回覆、API v3 記錄和取消。驗證腳本專為此範例；自己的插件需要自己的行為驗收。

## 匯入與安裝

1. 審查插件程式碼，建置純 Python wheel。工作臺「匯入 wheel」只檢查 metadata、ZIP 限制、相依套件與 RECORD，保存快取，不執行 Python。
2. Docker 下載部署包，從含 API v3 的 OpenSprite 映像建置。需要的相依套件先存在基底；部署使用 `--no-index --no-deps`，不自動下載。
3. 依包內 README 沿用原 Compose project、設定與 volume。先結束或取消活躍 Run，再替換唯一後端。不要執行 `down -v`。
4. 重啟後返回「核對部署狀態」。確認 manifest、wheel SHA-256、entry point 及實際安裝檔案一致。選擇已安裝的 Agent Loop 作為草稿，再套用至新任務。

本機安裝則先停止唯一後端，將 wheel 安裝到實際程式安裝目錄的 Python 環境。例如 Windows：

```powershell
$taskBackendPython = 'D:/ABS/opensprite/backend/.venv/Scripts/python.exe'
uv pip install --python $taskBackendPython --offline --no-deps --force-reinstall ./tmp/execution-plugin-wheel/opensprite_execution_example-0.3.0-py3-none-any.whl
uv pip check --python $taskBackendPython
```

Linux 使用 `/ABS/opensprite/backend/.venv/bin/python`。替換為真實位置，重啟後端再讀取清單。本機沒有部署 manifest 時顯示來源未驗證，不能宣稱已核對 exact wheel；選擇仍根據已安裝 metadata。

## 從 API v2 升級與回復

把 Driver 的 execute 與 Policy 的兩個方法合在同一類別，factory 改為 API 3，保留一個 agent_loops.v3 entry point，再完整測試與重建 wheel。只改版本數字不足以完成升級。沒有自動包裝器、相容別名或舊版執行入口。

標準/標準與標準/no_recovery 設定自動映射到新內建插件；外部組合保留原檔，必須明確選擇 API v3 插件後才可開始新任務。API v2 的歷史事件與舊 wheel 快取不被刪除。舊快取顯示需要更新，無法下載部署包。

升級前停止服務並備份整個敏感 `.opensprite`，一起保存 `auth.json` 和 `config/credential.key`。新版 execution.json 為 schema 2，舊版不理解；回復時使用原映像與相容的完整備份，不能直接讓舊後端寫新設定。移除匯入快取不會解除安裝。

插件在後端程序內執行，靜態檢查不提供安全沙箱；只安裝受信任套件。取消是合作式契約，不是強制隔離任意 Python 的機制。
