# Agent 執行插件 API v1

OpenSprite 的 Agent Loop 分成固定核心 Host、可替換 Driver、執行策略。工作臺「設定 → Agent 能力 → 執行方式」選擇已安裝的 Loop 與策略；主代理和子代理使用相同契約。

## 核心與插件的邊界

`AgentLoop` 負責 Run 啟動與唯一終止結果。每次執行建立獨立 Host 和 Driver；`StandardDriver` 透過 `checkpoint`、`next_turn`、`execute_tools(turn)`、`finish(turn)` 控制回合順序。Host 持有模型串流、transcript、工具核准、取消、上下文、Skills、子代理及預算，不把 repository 或 ToolRegistry 作為插件 API。

Host 核對 turn 的物件來源與內容、工具是否已結算及回傳結果來源，禁止偽造結果、重播 turn、略過工具或並行執行 Host 操作。主模型回合、一般工具、輸出大小、續寫次數的既有硬限制仍由核心執行；Skills 和 delegation 保留原本的專用限制。策略只能否決符合核心條件的 Context 重試或輸出續寫，不能放寬限制。`no_recovery` 關閉這兩項自動恢復，保留正常工具回合與必要的上下文準備。

插件自行拋出的 `asyncio.CancelledError` 不代表 Run 的擁有者已被取消。核心核對擁有者 task 的取消狀態，將插件錯誤結算為安全失敗；真正的 shutdown／timeout 仍傳遞取消，使用者 Stop 保留取消結果。若 Stop 已先提交到儲存庫，隨後的完成交易不能將它改成失敗。

這些是程序內的契約防護。Python 插件是受信任程式碼，擁有後端程序權限，API 不是安全沙箱；只應在應用程式環境或 Docker 映像安裝審查過的套件。本階段沒有網路下載、安裝器、CLI 或市集。

## 註冊與版本

外部套件使用 Python distribution entry points：

```toml
[project.entry-points."opensprite_backend.agent_loops.v1"]
my_loop = "my_package.loop:create_factory"

[project.entry-points."opensprite_backend.execution_policies.v1"]
my_policy = "my_package.policy:create_factory"
```

Entry point 的名稱就是插件 ID（`[a-z][a-z0-9_.-]{0,63}`），distribution version 是插件版本。`create_factory()` 不接收參數，回傳包含整數 `api_version = 1` 與 `create()` 的工廠。Loop 工廠的 `create()` 回傳具有 `async execute(host) -> DriverResult` 的新 Driver；策略工廠回傳提供 `allow_context_retry(ContextRetryState)` 與 `allow_output_continuation(CompletionState)` 的新策略。

插件清單只讀取已安裝套件 metadata；選取時才載入 entry point。其他 API 版本顯示不相容，不載入。相同 kind 和 ID 的碰撞顯示不可用，不能取代內建插件。載入失敗只公開固定錯誤碼，不公開插件例外。

Entry point 來源與成功載入的工廠分開辨識；工廠額外的 `load()` 方法不影響快取。缺漏、空白、超過 64 字元或無法讀取的套件版本 metadata 只停用該插件。設定 PUT 的選擇驗證與套件載入在背景執行緒進行。

內建插件版本獨立為 `1.0.0`：Loop `standard`，策略 `standard`、`no_recovery`。API v1 沒有任意插件設定物件；目前的設定 shape 就是兩個 ID。

## 選擇、記錄與持久化

`GET/PUT /api/settings/execution` 由 `contracts/execution-settings.openapi.json` 定義。成功 PUT 首次建立 `.opensprite/config/execution.json`，AppPaths 管理路徑，原子寫入固定 schema。GET 不載入插件且允許呈現不可用的既有選擇；PUT 和新任務接受時必須驗證選擇。

新任務在接受前固定解析工廠與版本，RunManager 將 binding 傳給主代理，ParentDelegation 將同一 binding 傳給子代理。每個主／子執行仍建立新 Driver 和策略；後續設定修改只影響新接受的任務。已接受請求的重送沿用 idempotency 結果，不重新載入設定。執行開始後、第一次模型呼叫前，持久化 `execution.selected` 事件，其資料只有 Loop／策略 ID、版本與 API 版本，工作臺歷史顯示實際使用的插件。

前端此設定 API 的 GET 會等待在途 PUT 完成後讀取，避免保存時關閉、重開設定出現舊選擇。即時與歷史事件集合維持 500 筆上限，並固定保留 Run 啟動、執行插件及最新 Context 資訊。

Queued 任務因程序中斷仍按既有方式標成 interrupted，不自動恢復；未啟動的任務沒有 execution.selected 事件。本次不新增工具結果全文持久化或可恢復的模型 transcript。模型完成仍表示執行結束，沒有新增通用的任務驗收引擎。
