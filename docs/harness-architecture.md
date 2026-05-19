# OpenSprite Harness Architecture

OpenSprite 的 Agent runtime 已經具備多個 AI Agent Harness 元件。本文件將現有模組整理成一套明確的 Harness 架構，作為後續調整、測試與產品化的共同語言。

## 核心精神

Harness 的目的不是讓模型「裸跑」，而是提供一套可控流程，讓模型在正確上下文、工具、限制與驗證中完成任務。

OpenSprite 的目標流程是：

```text
User Input
-> Task Intent
-> Harness Profile
-> Work Plan
-> Context
-> Tool Execution
-> Evidence
-> Verification
-> Completion Gate
-> Auto Continue / Final Response
-> Memory / Trace
```

## 現有模組對應

| Harness 層 | 現有模組 | 說明 |
|------------|----------|------|
| Task Intent | `TaskIntentService` | 判斷使用者訊息的任務類型與是否期待程式碼變更。 |
| Work Plan | `WorkProgressService`、`WorkPlan` | 建立任務進度與續跑預算。 |
| Context | `FileContextBuilder`、`PromptBudgetService` | 組裝 bootstrap、workspace、skills、subagents、memory、recent summary，並控管 token budget。 |
| Tools | `ToolRegistry`、`ExecutionEngine` | 註冊與執行 filesystem、web、media、MCP、verification 等工具。 |
| Permissions | `ToolPermissionPolicy`、`PermissionRequestManager` | 控制工具可見性、風險等級與 approval flow。 |
| Evidence | `TaskContractService`、`EvidenceGateService` | 定義任務需要的工具證據，並檢查是否已產生。 |
| Quality | `QualityGateService` | 檢查回答品質，例如來源引用、artifact、回答長度與 workspace grounding。 |
| Completion | `CompletionGateService` | 判斷任務是否完成、需要驗證、需要 review、被阻塞或等待使用者。 |
| Auto Continue | `AutoContinueService` | 在 bounded budget 內針對 incomplete / needs verification / needs review 進行續跑。 |
| Memory | `MemoryStore`、`RecentSummaryStore`、`LearningLedger`、`CuratorService` | 維持長期記憶、近期摘要、使用者偏好與可重用學習。 |
| Observability | `RunTraceRecorder`、Web `RunTraceViewer` | 記錄 run lifecycle、tool calls、artifacts、events 與完成狀態。 |

## Harness Profile

`HarnessProfile` 是後續新增的協調層，用來描述不同任務應套用的工具、證據、驗證、續跑與權限策略。

初始 profile：

| Profile | 適用情境 | 主要策略 |
|---------|----------|----------|
| `chat` | 一般問答、閒聊、低風險說明 | 不強制工具，不強制驗證。 |
| `research` | 網路搜尋、資料查證、需要來源的回答 | 需要 web evidence、source artifact、來源引用。 |
| `coding` | 檔案、程式碼、測試、錯誤、repo 任務 | 需要 workspace evidence；若改檔，應嘗試 focused verification。 |
| `media` | 圖片、音訊、影片分析或轉錄 | 需要 media artifact 與具體結果。 |
| `ops` | 設定、credential、排程、外部副作用 | 權限較嚴格，外部副作用優先要求 approval。 |

## Profile 驅動流程

加入 `HarnessProfile` 後，流程調整為：

```text
TaskIntent
-> HarnessProfile
-> WorkPlan
-> TaskContract
-> EvidenceGate / QualityGate
-> CompletionGate
-> AutoContinue
```

這代表 OpenSprite 不再只依任務意圖判斷完成，而是依 profile 套用更明確的完成標準。

## Context 分層

OpenSprite 的 context 應維持分層策略：

| 層級 | 例子 | 載入時機 |
|------|------|----------|
| Always loaded | identity、runtime paths、bootstrap、USER profile | 每次 LLM call。 |
| Task triggered | workspace task guidance、retrieval guidance、planning mode | 依當前訊息啟用。 |
| On demand | full skill content、subagent prompts、file contents | 透過工具按需讀取。 |
| Retrieved | history search、knowledge search、user overlay snippets | 與任務相關時檢索。 |
| Durable memory | MEMORY.md、recent summary、active task | 以摘要形式載入，避免塞入完整歷史。 |

## Verification 策略

不同 profile 的驗證標準應不同：

| Profile | 驗證方向 |
|---------|----------|
| `chat` | 不強制外部驗證，但回答不可空泛。 |
| `research` | 必須有來源 artifact，回答要引用 gathered source。 |
| `coding` | 改檔後應跑 focused test、verify tool、build 或說明未驗證原因。 |
| `media` | 必須產生 image/audio/video artifact。 |
| `ops` | 需要 approval、設定驗證或明確 rollback / audit trail。 |

## Observability 事件

後續 run trace 應逐步加入以下事件：

```text
harness_profile.selected
task_contract.created
verification_policy.selected
completion_gate.evaluated
auto_continue.decided
```

這些事件可以讓 Web UI 顯示 Agent 為何可信、失敗在哪一層，以及下一步應如何修正。

## 最小實作順序

1. 新增 `HarnessProfile` 與 `HarnessProfileService`。
2. 在 `AgentTurnRunner` 選取 profile，並 emit `harness_profile.selected`。
3. 讓 `TaskContractService` 參考 profile 補強 requirements 與 acceptance criteria。
4. 讓 `WorkProgressService`、`CompletionGateService`、`AutoContinueService` 逐步參考 profile。
5. 在 Web UI 將 profile、contract、evidence、verification、completion 狀態整理成 Harness dashboard。

## 設計原則

- 小步整合，不重寫現有 Agent loop。
- Harness profile 是協調層，不是新的平行 runtime。
- 完成判斷優先依 deterministic evidence，不只相信模型文字。
- 上下文要分層與按需載入，避免長 context 造成干擾。
- 外部副作用必須有明確權限與 trace。
