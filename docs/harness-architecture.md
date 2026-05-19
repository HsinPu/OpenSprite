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

## Harness Policy Matrix

`HarnessPolicyService` 會把 profile 轉成每回合的工具可見性、risk level 與 approval 規則。Profile 決定任務語意，policy 決定 runtime 可以暴露與執行哪些工具。

| Profile | Task type | Runtime policy | 可用工具 / risk | Approval 風險 | Contract 重點 |
|---------|-----------|----------------|-----------------|---------------|---------------|
| `chat` | `question`、`conversation` 等低風險回答 | `chat_read_policy` | 僅允許 `read` risk；可暴露宣告為 read-only 的工具。 | 無預設 approval。 | `pure_answer` 可無工具完成。 |
| `research` | `web_research` | `research_source_policy` | 允許 read / network；暴露 read-only、`web_search`、`web_fetch`、`web_research` 與 browser read tools。 | `external_side_effect`。 | 需要 `web_research` tool evidence、source artifact、source detail 與 source reference。 |
| `coding` | `workspace_analysis` | `workspace_analysis_policy` | 允許 read / network / delegation；禁止 write、execute、configuration、memory、MCP。 | 無預設 approval。 | 需要 workspace evidence 與 substantive final answer。 |
| `coding` | `workspace_change` | `workspace_change_policy` | 允許除 MCP 外的 workspace tool risks；可 edit 與 verify。 | `external_side_effect`、`configuration`。 | 需要 workspace read、file change，且需要 verification 或 explicit verification gap。 |
| `media` | `media_extraction` | `media_artifact_policy` | 允許 read / network / external_side_effect；暴露 image/audio/video extraction 與 media send tools。 | 無預設 approval。 | 有附件時需要 media artifact、resource coverage 與 substantive final answer。 |
| `ops` | `operations` | `operations_approval_policy` | 允許完整 risk set，但高風險操作進入 approval flow。 | `external_side_effect`、`configuration`、`mcp`。 | 需要 operation report、validation 或 remaining-risk 說明。 |

目前 selector 的優先序是 `ops` -> `media` -> `coding` -> `research` -> `chat`。這避免「更新 MCP 設定並重啟」被誤判成一般 coding task，也避免有附件的 OCR 任務被 web/coding marker 搶走。

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

run trace 會記錄以下 Harness 事件與 durable parts：

```text
harness_profile.selected
harness_policy.selected
task_contract.created
completion_gate.evaluated
work_progress.updated
harness_checkpoint.recorded
harness_checkpoint run part
auto_continue.scheduled / auto_continue.completed
```

這些事件可以讓 Web UI 顯示 Agent 為何可信、失敗在哪一層，以及下一步應如何修正。`harness_checkpoint` 同步保存成 run part，因此即使 trace event 被 compaction，仍能從 durable parts 找到最新 profile、policy、contract、completion 與 next action。

## 目前落地順序

1. 新增 `HarnessProfile` 與 `HarnessProfileService`。
2. 在 `AgentTurnRunner` 選取 profile，並 emit `harness_profile.selected`。
3. 讓 `TaskContractService` 參考 profile 補強 requirements 與 acceptance criteria。
4. 讓 `WorkProgressService`、`CompletionGateService`、`AutoContinueService` 參考 profile。
5. 讓 `HarnessPolicyService` 依 profile 套用 tool visibility、risk level 與 approval 規則。
6. 將 `harness_checkpoint.recorded` 同步保存成 durable `harness_checkpoint` run part。
7. 在 Web UI 將 profile、policy、contract、evidence、verification、completion 狀態整理成 Harness dashboard。

## 設計原則

- 小步整合，不重寫現有 Agent loop。
- Harness profile 是協調層，不是新的平行 runtime。
- 完成判斷優先依 deterministic evidence，不只相信模型文字。
- 上下文要分層與按需載入，避免長 context 造成干擾。
- 外部副作用必須有明確權限與 trace。
