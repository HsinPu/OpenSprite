# 執行插件作者指南

## 契約與專案

OpenSprite 0.21.31 只接受 **Host API v2** 的文字 Loop／執行策略。
下載工作臺的「範例專案」，或使用 `examples/execution-plugin`；其中包含完整 manifest、原始碼與測試，套件版本為 0.2.0。
`src/opensprite_execution_example/plugin.py` 的 entry point 必須指向「無參數、回傳 factory」的函式，不直接指向 Driver 實例。

```toml
[project]
name = "my-execution-plugin"
version = "0.1.0"
requires-python = ">=3.12,<3.14"
dependencies = ["opensprite-backend>=0.21.31,<0.22"]

[project.entry-points."opensprite_backend.agent_loops.v2"]
my_loop = "my_plugin.plugin:create_loop_factory"

[project.entry-points."opensprite_backend.execution_policies.v2"]
my_policy = "my_plugin.plugin:create_policy_factory"
```

只提供一種插件時移除另一組。使用不與內建重複的 ID；factory 的 `api_version = 2`，每次 `create()` 建立新實例。

## 寫 Loop

```python
from opensprite_backend.agent.driver import DriverResult, ExecutionHost

class MyDriver:
    async def execute(self, host: ExecutionHost) -> DriverResult:
        await host.checkpoint()
        turn = await host.next_turn()
        await host.checkpoint()
        return await host.finish(turn)

class MyFactory:
    api_version = 2
    def create(self):
        return MyDriver()

def create_loop_factory():
    return MyFactory()
```

`ModelTurn` 只有 `text` 與 `finish_reason`；Host 自行完成符合設定的上下文恢復與輸出續寫。
Host 操作必須順序 await，不得同時呼叫、複製／修改／重放 turn、自造 DriverResult，或在 finish 後再次推論。
必須原樣回傳 finish 的物件；不要吞掉 Host 失敗或 `CancelledError`。有臨時資源時用 finally 收尾，不在 cleanup 發起新操作。
任務完成只表示流程終止，不保證答案品質或任意成果已通過驗收。

## 寫策略

策略實作兩個同步方法並回傳真正的 bool：

```python
def allow_context_retry(self, state):
    return state.phase == "main" and state.cause == "provider_context_limit"

def allow_output_continuation(self, state):
    return False
```

True 不放寬核心資格、使用者設定、重試或大小限制；False 只否決恢復。
範例允許合格的主模型 context-limit 重試，但否決 continuation 階段重試與自動續寫。
模型、憑證、transcript、事件、預算、取消和持久化仍由核心管理。插件是受信任的同程序 Python，這個契約不是安全沙箱。

## 測試與 wheel

從完整 repository 根目錄執行：

```bash
uv sync --project backend --dev
uv run --project backend python -m pytest -c examples/execution-plugin/pyproject.toml examples/execution-plugin/tests
uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin
```

單元測試必須覆蓋原回合與結果、不同輸出、模型前後取消、失敗傳遞、新實例及策略的允許／否決。
再安裝真正 wheel 驗證，不用 source import 代替：

```powershell
$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path tmp/execution-plugin-wheel/opensprite_execution_example-0.2.0-py3-none-any.whl).Path
uv run --project backend python scripts/verify_execution_plugin_wheel.py
```

腳本在暫存 target 離線安裝 wheel，另起隔離 Python 讀取真實 metadata、驗證載入來源，並透過真實 AgentLoop、SQLite 與 Provider adapter 回傳每次不同輸入的文字及 API v2 執行事件。
此處的 Provider 是協定測試伺服器，驗證資料流與核心；不能宣稱任何付費模型或外部服務已測試。
wheel 的 SHA-256、安裝版本及 profile 會輸出為 JSON。套件測試通過也不表示正式服務已安裝。

## 工作臺與 Docker

1. 在「設定 → 執行方式」匯入已審查的純 Python wheel，核對檔名、版本、API 與 SHA-256。
2. 下載部署包到獨立目錄，閱讀 README，確認基底是含 API v2 的實際映像。
3. 先備份完整使用者資料與當前映像，等待現有任務結束。
4. 設定 `OPENSPRITE_PLUGIN_BUNDLE_DIR` 為部署包的絕對路徑，以既有 Compose project 和資料 volume 建置／重啟。
5. 重新讀取部署狀態；必須確認 wheel identity 與實際安裝檔案一致，再選擇插件並套用至新任務。
6. 送出不同文字的真 HTTP Run，核對動態結果、execution.selected 的 API／版本、取消及重新啟動後的讀取。

匯入只做靜態檢查與保存，不在運行中的 backend pip install，不執行 Docker，也不熱替換已接受任務。
API v1 要修改 entry point 群組與 factory，移除 execute_tools 等舊行為後重新建置，不能只改版本號。
本機安裝須停止 backend，將 wheel 安裝至真正的 backend Python 環境，檢查依賴後再啟動；仍使用單一 `.opensprite` 寫入者。
回復使用原映像／安裝環境和升級前完整資料備份，不刪除使用者資料或把舊程式直接套在新 schema。

## 驗證證據

| 驗證 | 證明範圍 |
| --- | --- |
| 範例 Host 單元測試 | 插件協調順序、結果物件、取消與策略 |
| wheel 安裝腳本 | 實際套件來源、entry points、真核心與變動輸入資料流 |
| 核心 integration tests | 接受、冪等、恢復、取消、Host 權威與錯誤清理 |
| 獨立 Docker HTTP 任務 | 部署檔案、執行插件綁定、串流、持久化與取消 |
| 瀏覽器桌面／平板／手機 | 實際操作、排版與錯誤／空白狀態 |

未覆蓋的真實 Provider、插件或工作成果需另行驗證。此版其他擴充先不實作；新的能力要另訂需求、契約與測試。
