# 撰寫 Agent Loop 插件（Host API v5）

OpenSprite 0.21.38 的 Loop 負責完整模型輸入、摘要生成、重試與續寫。
examples/execution-plugin 是可建置的 0.5.0 範例，插件 ID example_review。
工作臺開發說明與下載 ZIP 使用相同來源。

## 最小流程

下面只回答一次。正式插件要自行處理 OUTPUT_LIMIT、上下文取捨與摘要。

~~~python
from opensprite_backend.agent.plugin import (
    ContextReadRequest, FinalOutput, InputSource, ModelMessage, StepRequest,
    ModelFinishReason, CompletionReason,
)

class MyLoop:
    async def execute(self, host):
        snapshot = await host.read_context(ContextReadRequest(limit=20))
        raw = (*snapshot.history, snapshot.current_user)
        messages = (ModelMessage("system", host.run.system_prompt),
                    *(ModelMessage(item.role, item.content) for item in raw))
        sources = tuple(InputSource(index+1, snapshot, (item.id,))
                        for index, item in enumerate(raw))
        step = await host.infer(StepRequest(messages,
            min(1024, host.run.model_limits.output_tokens), sources=sources))
        if step.error:
            return await host.finish(FinalOutput(error_step=step))
        reason = (CompletionReason.OUTPUT_LIMIT
                  if step.finish_reason is ModelFinishReason.OUTPUT_LIMIT
                  else CompletionReason.STOP)
        return await host.finish(FinalOutput(step.text, (step,), reason))

class Factory:
    api_version = 5
    def create(self):
        return MyLoop()

def create_factory():
    return Factory()
~~~

完整範例會執行 draft → review → final 三次真實推論。草稿與檢查不發布到聊天，
final 使用前兩步結果；InputSource.steps 記錄輸入來自哪個步驟。
每次 create 必須回傳新實例，不在 factory 中共用任務狀態。
範例僅示範最近 20 則原始訊息，不自動續写或摘要，也不保證使用整個長對話。
官方 StandardLoop 的獨立 wheel 提供完整長對話與自動續寫策略。

## 套件宣告

~~~toml
[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[project]
name = "my-opensprite-loop"
version = "0.1.0"
requires-python = ">=3.12,<3.14"
dependencies = ["opensprite-backend>=0.21.35,<0.22"]

[project.entry-points."opensprite_backend.agent_loops.v5"]
my_loop = "my_loop.plugin:create_factory"

[tool.hatch.build.targets.wheel]
packages = ["src/my_loop"]
~~~

插件 ID 以小寫字母開頭，允許小寫字母、數字、_、.、-，最多 64 字元。
standard/no_recovery 是官方 ID。entry point 指向無參數 factory provider，
group 是 metadata 名稱，不是 Python 模組。

## 上下文與摘要

1. read_context 回傳原始資料；以 after_sequence 從最舊端逐頁讀取，
   或以 before_sequence 從最新端讀取。每頁最多 200 則，current_user 另外提供。
2. Loop 決定歷史排序、裁切、引用標記、摘要格式與模型 prompt。可呼叫
   estimate_input 做保守估算，選擇較小 input_limit_tokens 與 max_output_tokens。
   這些值不能超過 Host 固定的模型／使用者限制。
3. 每個 InputSource 宣告對應 messages 的位置及來源。可合併／轉換來源，
   Host 核對所有權並記錄實際输入 hash，不判斷語意是否忠實。
4. 摘要生成使用一般 infer，設定 purpose="compaction"、channel="draft"，
   並提供 SummarySource。來源必須從第 1 則開始，或接續同格式上次摘要的 coverage；
   不可跳過舊頁、重複摘要已覆盖部分、摘要 current_user 或引用別的 Run。
5. 生成後由 Loop 評估 StepResult；可拒絕、轉換文字，或呼叫
   save_summary(SummaryWriteRequest(step, text))。Host 不插入摘要 prompt。
   同一 step 相同保存可重播，不重複產生完成事件；不同文字不可覆寫。
6. 保存後重新讀取快照。summary_format 可使用自訂版本，例如 my.json.v1；
   不相容格式升版本。Host 以來源 hash、連續範圍和前一摘要 CAS 防止過期寫入，
   不核對摘要內容的事實正確性。

## 重試、續寫與結果

infer 每次最多一個 Provider 請求。可恢復錯誤查看 step.error.retryable；
retry_of=failed_step 記錄重試來源，等待後 checkpoint。已發布部分答案不可
重播原步驟；需要修訂時先使用 draft。

OUTPUT_LIMIT 後的提示、尾段長度與停止條件由 Loop 決定。
purpose="continuation" 用於觀察，不構成額外續接次數限制。所有模型請求仍共同
計入 128 次、600 秒、32 次摘要及總生成字數上限。StandardLoop 自動續寫，
遇到重复截斷片段停止；這是停止判斷，不會刪除已發布文字。
deadline/checkpoint 是合作式機制，可信任 Python 插件不是沙箱。

finish 只呼叫一次並原樣回傳 RunResult。draft 可以在 finish 時選定、轉換後
發布；answer 已發布內容必須保留為最終文字前綴。避免自行連線 Provider、
讀憑證、寫資料庫、引用 Host 私有屬性、平行 Host 操作或吞掉致命錯誤。

## 測試与安装

| 層次 | 必須核對 |
| --- | --- |
| 流程 | 不同輸入、請求順序、上一階段輸出進入下一請求、每 Run 新實例 |
| 真 Host/SQLite | 草稿私有、正式答案、來源所有權、跨頁與無缺口摘要、CAS／冪等 |
| 故障 | 可恢復錯誤、部分答案、致命認證、取消、期限／請求／字數上限、finish 後操作 |
| 安裝 | 真 wheel、隔離 Python、dist-info 與模組路徑、metadata entry point |
| 部署 | Docker 非 root、健康/API、工作臺切換、同 volume 重啟歷史、舊資料升級 |
| 真模型 | 實際 Provider 的多次請求與动态輸出；不得把 protocol fixture 當成真模型 |

從儲存庫根目錄執行：

~~~powershell
uv sync --project backend --dev
uv run --project backend python -m pytest -c examples/execution-plugin/pyproject.toml examples/execution-plugin/tests
uv build --wheel --out-dir tmp/v5-wheels examples/execution-plugin
$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path tmp/v5-wheels/opensprite_execution_example-0.5.0-py3-none-any.whl).Path
uv run --project backend python scripts/verify_execution_plugin_wheel.py
~~~

驗證脚本离線安裝真 wheel 到隔離目錄，使用實際 Host、SQLite、原生 Provider
adapter 與每次不同的協定資料，再驗證取消。另行記錄付費真模型驗證。

工作臺「執行方式 → 匯入 wheel」只保存經檢查的套件，不立即執行或選用。
Docker 下載部署包，保留原 compose 專案／volume／連接埠設定，以 API v5 基底
建置並重啟，確認部署狀態後再套用 Loop。部署包的離線 no-deps 安裝要求
相依套件已在基底中。Windows/Linux 桌面使用同一 backend Python 安裝 wheel、
uv pip check 後重啟單一後端；工作臺確認 metadata 與實際檔案相符後再套用。

API v1..v4 必須重新撰寫與建置，不提供舊接口執行別名。升級真實資料前停止服務，
備份整個敏感 .opensprite（包含 auth.json 與 config/credential.key）。
SQLite 23 無法由舊 backend 寫入；回退需舊程式與升級前備份配對。

## v5 穩定資料契約

作者一律從 `opensprite_backend.agent.plugin` 匯入型別與 enum。公開欄位、
順序、預設值、方法與 factory 由 `contracts/agent-loop-v5.sdk.json` 固定；
Host 會將內部儲存／供應商資料轉成獨立的 frozen SDK 物件。不要依賴
`conversations.models` 或 `inference.models` 的 class 身分，也不要取得 Host
私有依賴。核心 patch 升級須通過未重建 wheel 的相容性驗證。SDK v5
的相容起點仍為 0.21.35，範例依賴範圍保持 `>=0.21.35,<0.22`。
