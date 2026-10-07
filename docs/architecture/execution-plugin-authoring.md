# 執行插件作者指南

本文對應已實作的 execution-plugin API v1。產品範圍與信任邊界以
[Agent 執行插件架構](agent-execution-plugins.md) 為準；這裡說明套件作者如何
撰寫、測試、建置及部署。範例來源在 `examples/execution-plugin/`，不是產品
業務邏輯、應用程式 CLI 或可直接匯入的 Agent／Skill 定義。

## 先選對擴充點

| 想改變的行為 | 擴充點 | 現有能力限制 |
| --- | --- | --- |
| 模型回合與工具回合的協調順序 | Loop Driver | 使用 Host API，不能自己替換模型請求、transcript 或工具核准 |
| 是否允許合乎核心條件的 Context 重試與輸出續寫 | 執行策略 | 只能否決；不能增加預算、回合、工具權限或恢復次數 |
| 子代理角色、背景、指定模型 | 自訂 Agent TOML | 是另一種功能，不能當作 Python 執行插件安裝 |
| 任務相關指引 | Skill | 是另一種功能，不能提供 Python Driver 或策略工廠 |

API v1 **沒有**追加 prompt、插入 verifier 工具、修改工具目錄、改寫 transcript、
讀取 repository／ToolRegistry／Provider 憑證的 Host 方法。不能把「先生成候選
答案，再另開模型回合驗收」宣稱為現在的通用插件能力：終止 turn 必須交給
`finish(turn)`，Host 不允許在未結算 turn 後直接呼叫 `next_turn()`；
`finish` 發出終止結果後不得再執行 Host 操作。需要這類產品能力時應先確認新的
前端流程與 Host／HTTP 契約，而不是存取 Host 私有屬性。

## 套件格式與相容性

使用一般 Python distribution；範例為 pure-Python wheel `py3-none-any`。
它仍有 Python 與 OpenSprite 版本限制，不代表所有環境都能安裝。
範例套件版本為 `0.1.0`，產品相依為 `opensprite-backend>=0.21.27,<0.22`，
Python 為 `>=3.12,<3.14`；套件版本、產品版本與插件 API 版本是三件不同的事。

`pyproject.toml` 註冊兩類 entry point：

```toml
[project.entry-points."opensprite_backend.agent_loops.v1"]
example_checkpointed = "opensprite_execution_example.plugin:create_loop_factory"

[project.entry-points."opensprite_backend.execution_policies.v1"]
example_main_retry_only = "opensprite_execution_example.plugin:create_policy_factory"
```

- Entry point 名稱就是插件 ID，格式 `[a-z][a-z0-9_.-]{0,63}`。
- 同一 kind 不能重複 ID；不能用 `standard` 等內建 ID 覆蓋核心。不同 kind 可以同 ID。
- Distribution `Version` 是顯示的插件版本；`Summary` 是外部插件的說明。
  目前外部名稱使用 entry point ID，不另外讀取自訂顯示名稱。
- `.v1` 表示 API v1。其他版本會列為不相容，不能選取。
- metadata discovery 不等於程式碼可成功載入；保存選擇及接受新任務時才載入並驗證工廠。
- API v1 沒有插件任意設定物件，執行設定只有 `loopId` 與 `policyId`。

Entry point 指向**不接受參數的工廠 provider 函式**。函式回傳具有整數
`api_version = 1` 與 `create()` 的 factory；不要回傳全域 Driver 實例。
`create()` 每次回傳新 Driver／策略，執行狀態留在該次實例，不能把前一任務的
turn、Host、工具結果或取消狀態帶入下一次執行。模組匯入和 provider 建立也應
保持無 I/O 副作用，避免在設定保存階段執行任務。

## Host API v1 的合法流程

| 方法 | 回傳／責任 |
| --- | --- |
| `await checkpoint()` | 讓核心檢查取消及執行狀態；不授予額外操作權限 |
| `await next_turn()` | 核心進行模型請求，回傳它擁有的 `ModelTurn` |
| `await execute_tools(turn)` | 核心結算該 turn 的工具，包含核准、取消、Skills 與子代理邊界 |
| `await finish(turn)` | 核心處理終止與受限續寫，回傳它擁有的 `DriverResult` |

範例 `CheckpointedDriver` 自行實作回合流程，不呼叫 `StandardDriver`，並在
工具 phase 前後增加 checkpoint。這是取消邊界示範；核心 Host 操作本身也會
檢查取消。工具 turn 必須結算後才能進入下一回合；沒有工具的 turn 由 `finish`
結算。範例不製造固定回答，也不證明終止答案已符合任務驗收。

```python
async def execute(self, host):
    await host.checkpoint()
    while True:
        turn = await host.next_turn()
        if not turn.tool_calls:
            return await host.finish(turn)
        await host.checkpoint()
        await host.execute_tools(turn)
        await host.checkpoint()
```

不要複製、修改或重播 turn；`ModelTurn`／tool arguments 的內容即使技術上
可變，Host 仍核對原物件與內容簽章。不要自己建立 `DriverResult("答案", ...)`，
也不要複製 `finish` 回傳的結果。必須原樣返還由這個 Host 發出的結果。
Host 方法不得透過 `gather`、背景 task 或多執行緒並行呼叫。插件可改協調方式，
但核心仍擁有回合／工具／輸出大小上限、唯一終止交易、事件與部分輸出。

## 策略範例與真正的差異

策略提供兩個同步方法，**必須回傳真正的 `bool`**，不是 `1`、字串、
`None`、awaitable 或其他 truthy 值：

```python
def allow_context_retry(self, state):
    return state.phase == "main" and state.cause == "provider_context_limit"

def allow_output_continuation(self, state):
    return False
```

`MainRetryOnlyPolicy` 與內建策略的差異：

| 情況（核心仍先檢查資格） | `standard` | `no_recovery` | 範例策略 |
| --- | --- | --- | --- |
| 主模型的 provider context-limit 恢復 | 允許 | 拒絕 | 允許 |
| continuation phase 的 context 恢復 | 允許 | 拒絕 | 拒絕 |
| 自動 output continuation | 允許 | 拒絕 | 拒絕 |

回傳 `True` 不會讓本來不符合核心條件的重試執行，也不能覆蓋使用者關閉續寫的
設定。正常工具回合、核准與必要的歷史 Context 準備不受這個策略開關取代。

## 取消、失敗、權限與使用者資料

- 不捕捉 `BaseException`，不吞掉 Host 失敗或 `CancelledError`。若有插件自己的
  暫存資源，使用 `try/finally` 結束資源，再讓原例外傳遞；不要在 cleanup 發起新 Host 操作。
- 插件自己拋出取消例外不是使用者 Stop。核心區分真正的擁有者取消與插件失敗；
  不能用偽造例外把失敗偽裝成取消或成功。
- 所有 Python 插件都是受信任程式碼，擁有後端程序的權限。Host 的程序內契約
  檢查不是安全沙箱；static wheel／metadata 檢查也不是隔離執行或安全認證。
- 不存取原始 Provider 憑證、不自行連線模型、不寫機密到日誌，不繞過工具核准。
  如插件要求這些能力，它已超出此 API 的受控協調用途。
- 子代理使用相同執行插件 binding，但核心保留隔離 context、固定 workspace／
  工具／Skill catalog、禁止子代理要求新的 consequential-tool 核准等邊界。
- 範例沒有持久化。未來已核准的資料必須由 `AppPaths` 放在唯一 `.opensprite`
  根目錄，不在插件自行建立第二個家目錄資料位置。整個 `.opensprite` 視為敏感資料。

## 作者的驗證順序與證據範圍

以下指令適用完整 repository 根目錄：

```bash
uv sync --project backend --dev
uv run --project backend python -m pytest -c examples/execution-plugin/pyproject.toml
uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin
```

建置工具可以安裝 Python build backend；這是開發工具，不是新增產品 CLI。
有可用 cache 時可加 `--offline` 重現離線建置。`tmp/`、`dist/`、環境及快取
不提交；wheel 是交付／驗證產物，程式碼、測試及套件 manifest 才提交。

實際 wheel 安裝驗證，不用 source import 代替：

```bash
OPENSPRITE_PLUGIN_WHEEL="$(pwd)/tmp/execution-plugin-wheel/opensprite_execution_example-0.1.0-py3-none-any.whl" \
  uv run --project backend python scripts/verify_execution_plugin_wheel.py
```

PowerShell 用 `$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path ...).Path` 設定同一
絕對路徑。驗證腳本透過 `uv pip --target` 只安裝到暫存目錄，另開 Python process
以真實 metadata discovery 解析 factory，檢查模組來自已安裝 target，測試工具
phase／取消及策略差異，最後輸出 wheel SHA-256 與 profile。`--no-deps --no-index`
因範例只依賴已存在、版本相符的 core；不是通用依賴下載或產品安裝服務。

| 驗證 | 能證明 | 不能單獨證明 |
| --- | --- | --- |
| FakeHost unit tests | 範例工具結算、取消傳遞、原結果與策略語意 | 真 Provider／工具／資料庫／Run 的行為 |
| wheel target 安裝測試 | 真套件可安裝，entry points 可發現，版本、載入來源及 factory 正確 | 正式環境已安裝或部署成功 |
| 現有 backend integration tests | 核心對 selected Driver、acceptance、子代理及惡意 Driver 的邊界 | 使用者自己的外部套件正確 |
| Docker／本機實際新 Run | 該環境採用正確版本，真 Host 經模型與工具事件結束 | 任意任務的通用成果驗收 |

核心 integration 沿用 `backend/tests/test_execution_plugin_integration.py`、
`test_execution_plugin_acceptance.py`、`test_agent_drivers.py` 及
`test_execution_plugin_catalog.py`；不要在範例內再複製完整核心測試套件。
插件驗證應加入它自己改變的行為與失敗情況，最後使用實際部署的 catalog、
選擇保存回應及 `execution.selected` 事件核對採用版本。

工作臺下載的範例 ZIP 沒有 `backend/` 或預裝 Python 環境。解壓縮根目錄
保留 `examples/`、`docs/` 與驗證腳本 `scripts/verify_execution_plugin_wheel.py`；
以 `uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin`
建置，再使用已備妥的相容 backend 開發／測試 Python 跑 pytest 與驗證腳本。
完整的獨立下載指令見[範例 README](../../examples/execution-plugin/README.md)。
不要對下載 ZIP 執行 `uv sync --project backend`，也不要為了測試向正式產品
環境安裝開發工具。

範例下載檔由 repository 維護腳本 `python scripts/build_execution_plugin_example.py`
從明確的來源清單產生；使用固定 ZIP metadata 與 UTF-8／LF 文字，排除環境、
build 產物、快取及使用者資料。修改作者範例或指南後要重新產生並檢查內容。

## 安裝到本機後端環境

使用真正啟動後端的 Python 環境，不能安裝到另一個全域 Python 後就宣稱產品
已安裝。先停止該後端以避免混用載入中的版本，保留使用者資料，以下是
範例 wheel 的環境安裝指令（把絕對路徑換成實際值）：

```bash
uv pip install --python /ABS/opensprite/backend/.venv/bin/python --no-index --no-deps /ABS/opensprite_execution_example-0.1.0-py3-none-any.whl
uv pip check --python /ABS/opensprite/backend/.venv/bin/python
```

Windows 的 interpreter 例子是 `D:/ABS/opensprite/backend/.venv/Scripts/python.exe`。
本機 installer 所建立的安裝環境不一定是 repository 的 `backend/.venv`，應先
核對它的服務設定。一般第三方插件若還有相依套件，需另外準備並檢查符合目標
Python／平台的依賴；不能把範例的 `--no-deps` 當成已安裝所有依賴。

重啟同一後端後，工作臺「執行方式」讀取已安裝 catalog，再選取兩個範例 ID
並保存。安裝成功不等於已套用；保存失敗保留舊選擇。Catalog 在後端啟動時
建立，前端重新讀取不會熱發現剛放入環境的套件。新任務及其子代理固定使用
接受時的 binding；已接受任務不因之後改設定而切換版本。

## 安裝到 Docker 映像

現有 runtime 用 UID 10001 執行、沒有 Docker socket 或 root 安裝能力。
插件應在 Docker 主機建置映像時安裝，最終仍用原本非 root 使用者啟動。
不要在執行中的容器修改核心環境，也不要掛入 Docker socket 作為安裝捷徑。

在獨立 build context 放已驗證的範例 wheel 與下列 Dockerfile：

```dockerfile
FROM opensprite:local
USER root
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
COPY opensprite_execution_example-0.1.0-py3-none-any.whl /tmp/execution-plugins/
RUN uv pip install --python /app/backend/.venv/bin/python --no-index --no-deps /tmp/execution-plugins/opensprite_execution_example-0.1.0-py3-none-any.whl \
    && uv pip check --python /app/backend/.venv/bin/python
USER opensprite
```

此例的 base 必須是 `>=0.21.27,<0.22` 的既有 OpenSprite 映像。
`USER root` 只用於 build 層；成品保留原 CMD、healthcheck、HOME 與 runtime UID。
固定 base image digest 與 wheel SHA-256 可保留更精確的部署來源。

```bash
docker build -t opensprite:with-execution-example /ABS/plugin-build-context
```

使用原本 Compose service、project 與資料 volume，另外的 override 只改 image：

```yaml
services:
  opensprite:
    image: opensprite:with-execution-example
```

```bash
docker compose -p YOUR_EXISTING_PROJECT -f compose.yaml -f compose.execution-example.yaml up -d --no-build --wait
```

project、compose 檔案、環境與 port 必須換成目前部署的實際值；不能換 project
後把新的空資料 volume 當作原部署，也不要使用 `down -v`。
重建前記錄原映像，失敗可用同一 project／資料 volume 重新指定原映像回復。

健康檢查通過後仍要核對 backend catalog 的兩個 ID／`0.1.0`／API v1，
成功保存選擇，再建立新 Run 並核對 `execution.selected`。容器啟動、wheel 上傳
或 metadata 檢查都不能單獨證明插件已安裝並採用。

這個直接建置流程使用已有機制，不代表工作臺已提供套件上傳、下載、安裝器或
Docker 控制。後續若加入匯入 cache／部署 bundle，應以當時實作契約描述
「已匯入／待部署／已安裝／已套用」，並區分來源 wheel 雜湊與實際安裝檔案的
manifest 身份；不把 static 檢查當作安全隔離或實際部署證據。
