# 撰寫 Agent Loop 插件（API v4）

OpenSprite 0.21.34 的 Loop 自行掌握完整文字流程。只實作 async execute(host)，
不再實作兩個 bool 回呼。可建置範例為 examples/execution-plugin，套件 0.4.0，
插件 ID 為 example_review；工作臺「開發說明」提供相同程式碼及完整 ZIP。

## 最小插件

```python
from opensprite_backend.agent.plugin import FinalOutput, StepRequest

class MyLoop:
    async def execute(self, host):
        context = await host.context()
        step = await host.infer(StepRequest(context, label="answer"))
        if step.error:
            return await host.finish(FinalOutput(error_step=step))
        return await host.finish(FinalOutput(step.text, (step,)))

class Factory:
    api_version = 4
    def create(self):
        return MyLoop()

def create_factory():
    return Factory()
```

這個最小流程不處理輸出截斷；正式插件應檢查 finish_reason，選擇續寫，
或以 CompletionReason.OUTPUT_LIMIT 完成。每次 create 必須回傳新實例。
執行中的資料留在 Run 實例，避免兩次任務共用狀態。

pyproject.toml 的關鍵內容：

```toml
[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[project]
name = "my-opensprite-loop"
version = "0.1.0"
requires-python = ">=3.12,<3.14"
dependencies = ["opensprite-backend>=0.21.34,<0.22"]

[project.entry-points."opensprite_backend.agent_loops.v4"]
my_loop = "my_loop.plugin:create_factory"

[tool.hatch.build.targets.wheel]
packages = ["src/my_loop"]
```

插件 ID 以小寫英文字母開頭，允許小寫字母、數字、_、.、-，最多 64 字元。
standard/no_recovery 保留給官方套件。entry point 指向無參數 factory provider。
API group 是 metadata 名稱，不用建立同名 Python 模組。

## 設計你自己的流程

1. 用 context(ContextSpec) 選近期數量、歷史 ID、selection_tokens 與摘要格式。
   current user 一定保留。context 只組合資料，沒有偷偷呼叫模型。
2. 用 infer(StepRequest(..., channel="draft")) 產生草稿。StepResult 的 text
   可作為下一次 infer 的 user/assistant 訊息；instruction 可指定該階段任務。
3. 建立檢查／評估步驟，再用草稿及檢查結果產生 channel="answer" 的正式答案。
   範例 ReviewLoop 完整展示這三步，每一步真的呼叫一次模型。
4. 如果需要摘要，用 compaction_candidates 選最舊且連續的一段，傳給
   compact(CompactionSpec)。你決定觸發時機、instruction、summary_format 與輸出上限。
   摘要完成後重新 context，不重用已過時的 coverage。
5. 可恢復錯誤檢查 step.error.retryable。以 retry_of=failed_step 記錄重試來源，
   自行決定等待時間及次數；等待後 checkpoint。已串流部分答案不能重試同一步，
   應選草稿以支援可修訂／可重試的流程。
6. 自行檢查 ModelFinishReason.OUTPUT_LIMIT，組合續寫尾段及 instruction。
   標記 purpose="continuation"，遵守 host.run.output_continuation 的使用者上限。
7. finish(FinalOutput) 只呼叫一次，回傳原始 RunResult。可用 draft step 作為
   sources，在 finish 時發布選定答案。已發布 answer 只能追加，不能覆寫。

Host 掌管固定 Provider/model/reasoning、實際 token 預算、硬上限、取消與 SQLite。
不要直接使用 Provider、憑證、儲存庫或 Host 私有屬性。
所有 Host 操作依序 await；不可 parallel、修改／複製 ContextResult/StepResult/
RunResult、在 finish 後再次呼叫，或吞掉致命 Host 錯誤後假造成功。

不同摘要格式使用不同 summary_format。只有格式一致的摘要可共用 coverage；
變更不相容格式時提高名稱版本，不要把別的格式誤認為自己的資料。

## 測試與證據

測試至少包含：

| 層次 | 驗證 |
| --- | --- |
| 單元流程 | 每次不同輸入、request 順序、上一階段結果進入下一請求、fresh instance |
| 真 Host/SQLite | 多步數量、草稿不在 chat、正式答案、retry_of、摘要來源/coverage/格式 |
| 故障控制 | context/rate limit/timeout、部分答案、致命認證、取消、超時、上限、finish 後操作 |
| 安裝 | 真 wheel、隔離 Python 進程、dist-info/模組路徑、actual entry point |
| 部署 | Docker 非 root、健康/API、工作臺切換、重啟後歷史、原 volume 相容升級 |
| 真模型 | OpenRouter auto 等實際供應商、多個實際請求；另記費用及結果，不以 fixture 冒充 |

從儲存庫根目錄：

```powershell
uv sync --project backend --dev
uv run --project backend python -m pytest -c examples/execution-plugin/pyproject.toml examples/execution-plugin/tests -W error
uv build --wheel --out-dir tmp/v4-wheels examples/execution-plugin
$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path tmp/v4-wheels/opensprite_execution_example-0.4.0-py3-none-any.whl).Path
uv run --project backend python scripts/verify_execution_plugin_wheel.py
```

驗證腳本離線安裝範例 wheel 到新的暫存目錄，另起隔離 Python。
實際 Host、SQLite、原生 Provider adapter 以 UUID 協定 fixture 跑三個請求，
確認 draft→review→final 依賴、只保存正式聊天答案，另驗證實際 Host 取消。
此 fixture 可證明流程与封裝；它不是付費模型測試。自己的插件須設計相應驗收。

## 工作臺匯入、安裝及選擇

1. 審查程式碼並建置純 Python wheel。匯入只做靜態檢查、保存快取。
2. Docker 下載部署包，用 API v4 基底建置。相依套件需已存在；離線
   --no-index --no-deps 不自動下載，部署包驗證實際 installed files。
3. 按包內 README 沿用 Compose project、volume 與設定，先完成／取消 active Run，
   再重啟唯一後端。不要 down -v。
4. 返回「核對部署狀態」，確認 manifest、SHA-256、entry point 與實際檔案。
5. 選為草稿，再「套用至新任務」。目前 active Run 維持已接受的版本。

Windows 桌面安裝：停止唯一後端，選實際程式安裝環境：

```powershell
$taskBackendPython = 'D:/ABS/opensprite/backend/.venv/Scripts/python.exe'
uv pip install --python $taskBackendPython --offline --no-deps --force-reinstall ./tmp/v4-wheels/opensprite_execution_example-0.4.0-py3-none-any.whl
uv pip check --python $taskBackendPython
```

Linux 改用 /ABS/opensprite/backend/.venv/bin/python。重啟後重新讀取已安裝清單。
沒有部署 manifest 的本機安裝顯示來源未驗證；不能宣稱已核對 exact wheel。
刪除匯入快取不會解除安裝或切換目前插件。

## API v3 升級與回復

移除 allow_context_retry/allow_output_continuation。把原本交給 next_turn 的
摘要、retry、continuation 改成 execute 內明確呼叫 context/infer/compact，
以 FinalOutput 結束。只把 metadata 數字改成 4 不能完成升級。
API v1/v2/v3 沒有相容執行入口；舊 metadata/cache/history 留存只供讀取。

標準選擇維持同一 ID，現在由官方 wheel 提供。外部插件先重寫、測試與重建，
再明確選擇 API v4。升級前停服務並備份整個敏感 .opensprite，
一併保存 auth.json 與 config/credential.key。SQLite 22 不能交由舊版寫入；
回復需要原映像及升級前的完整備份。

插件使用後端程序權限；wheel 檢查不提供沙箱。取消／時間限制是合作式 async
契約，不會強制隔離任意 Python。這一版沒有工具、Skill、Subagent、MCP 執行能力。
