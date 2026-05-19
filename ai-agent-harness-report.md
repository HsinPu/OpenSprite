# AI Agent Harness 研究報告

## 摘要

AI Agent Harness 指的是包在大型語言模型（LLM）外圍的一整套系統設計，用來把模型的原始能力轉化為可靠、可驗證、可維護的工作成果。它不是單一 prompt，也不是單一工具，而是由迴圈、工具、上下文、記憶、驗證、限制、安全、觀測性與部署機制共同組成的工程系統。

近年的共識逐漸從「哪個模型更強」轉向「模型外面的系統是否設計得好」。同一個模型在不同 Harness 下，可能呈現完全不同的可靠性、速度、成本與成果品質。

## 核心觀點

- 模型是引擎，Harness 是整台車。
- Agent 的可靠性不只取決於模型能力，也取決於它能看到什麼、能做什麼、如何驗證結果、失敗後如何恢復。
- 長上下文不等於好上下文，過多資訊可能讓模型忽略關鍵內容或做出錯誤推理。
- 工具越多不一定越好，工具介面、工具描述、權限邊界與錯誤回饋會直接影響 Agent 表現。
- 多 Agent 系統不是萬靈丹，適合可平行探索的讀取型任務，但在需要一致決策的寫入型任務中容易出現衝突。
- Production Agent 需要可觀測性、checkpoint、sandbox、eval、policy 與人工介入點。

## Harness 的主要組成

| 層次 | 說明 | 代表問題 |
|------|------|----------|
| Loop | 觀察、計畫、行動、驗證、修正的循環 | Agent 要如何決定下一步？ |
| Tools | 讀檔、寫檔、搜尋、執行指令、call API、操作瀏覽器 | Agent 能不能取得真實環境回饋？ |
| Context | 控制模型看到哪些資訊 | 哪些內容應該進 prompt？哪些應該按需載入？ |
| Memory | 跨步驟、跨任務、跨對話保存狀態 | Agent 如何不忘記計畫、決策與歷史？ |
| Verification | 測試、lint、build、引用檢查、LLM judge、人工 review | 如何確認 Agent 真的完成任務？ |
| Constraints | 權限、成本、路徑、工具、架構邊界 | 如何防止 Agent 做危險或不必要的事？ |
| Observability | traces、logs、metrics、tool call history | 出錯時如何知道原因？ |
| Durable Execution | checkpoint、resume、replay、idempotency | 長任務中斷後如何恢復？ |
| Safety | prompt injection 防護、sandbox、approval、policy | 外部內容或工具輸出是否可信？ |

## 文章與工程資料

### OpenAI：Harness Engineering

- 來源：[Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- 日期：2026-02-11
- 重點：OpenAI 團隊用 Codex 建立一個上百萬行程式碼的內部產品，強調工程師角色從「手寫程式」轉向「設計環境、規格與回饋迴圈」。
- 與 Harness 的關係：這是最直接使用 Harness Engineering 概念的一手案例，包含 repository knowledge、AGENTS.md、架構 lint、結構測試、瀏覽器驗證、observability、agent review loop 與週期性清理 agent。

### Anthropic：Building Effective Agents

- 來源：[Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- 日期：2024-12-19
- 重點：區分 workflows 與 agents，整理 prompt chaining、routing、parallelization、orchestrator-workers、evaluator-optimizer 與 autonomous agents。
- 與 Harness 的關係：提供 Agent loop 與 workflow pattern 的基礎分類，強調簡單、透明、工具介面清楚，以及有明確 stopping condition。

### Anthropic：Multi-Agent Research System

- 來源：[How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system)
- 日期：2025-06-13
- 重點：Claude Research 使用 lead agent 與 subagents 平行研究，並透過 memory、citation agent、tool tracing、eval 與 checkpoint 提升可靠性。
- 與 Harness 的關係：展示長任務、多 Agent、上下文壓縮、來源引用、durable execution 與 eval rubric 的 production 設計。

### Martin Fowler / Thoughtworks：Context Engineering

- 來源：[Context Engineering for Coding Agents](https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html)
- 日期：2026-02-05
- 重點：Context engineering 是「策劃模型看到什麼」。文章整理 reusable prompts、rules、skills、subagents、MCP servers、hooks 與 workspace files。
- 與 Harness 的關係：說明 Harness 的上下文層不是把所有資訊塞進 prompt，而是透過按需載入、規則作用域與工具介面管理資訊。

### Martin Fowler / Thoughtworks：Harness Engineering Memo

- 來源：[Harness Engineering - first thoughts](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering-memo.html)
- 日期：2026-02-17
- 重點：分析 OpenAI 的 Harness Engineering 案例，將其拆成 context engineering、architectural constraints 與 garbage collection。
- 與 Harness 的關係：指出好 Harness 不是一堆 Markdown 規則，而是文件、架構約束、deterministic checks 與週期性維護的組合。

### Cognition：Don’t Build Multi-Agents

- 來源：[Don’t Build Multi-Agents](https://cognition.ai/blog/dont-build-multi-agents)
- 日期：2025-06-12
- 重點：主張多 Agent 系統容易因上下文切割與隱性決策衝突而變脆弱。
- 與 Harness 的關係：提供重要反面觀點，提醒多 Agent 不是越多越好，必須處理 trace sharing、context compression 與 conflicting decisions。

### LangChain：How and When to Build Multi-Agent Systems

- 來源：[How and when to build multi-agent systems](https://blog.langchain.com/how-and-when-to-build-multi-agent-systems/)
- 日期：2025-06-16
- 重點：整理 Anthropic 與 Cognition 兩種觀點，指出讀取型任務比寫入型任務更適合多 Agent。
- 與 Harness 的關係：強調 context engineering、durable execution、observability 與 eval 是 multi-agent production 的必要條件。

### Sean Goedecke：Agentic AI Tooling

- 來源：[What have we learned about building agentic AI tools?](https://www.seangoedecke.com/ideas-in-agentic-ai-tooling/)
- 日期：2025-10-19
- 重點：總結 coding agent 工具設計經驗，包括先計畫再行動、工具集要小、支援中途介入、規則檔、slash commands 與一般搜尋。
- 與 Harness 的關係：偏產品與工具設計層面，說明實務上 Agent UX 與 tool surface 如何影響結果。

## 代表性論文

### Agent Loop 與工具使用

| 論文 | 來源 | 貢獻 |
|------|------|------|
| [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) | ICLR 2023 | 提出 reasoning 與 action 交錯的 Agent loop，是許多 Agent 架構的基礎。 |
| [MRKL Systems](https://arxiv.org/abs/2205.00445) | arXiv 2022 | 將 LLM 與外部知識、工具、符號模組結合，對應 tool routing 與 modular harness。 |
| [Toolformer](https://arxiv.org/abs/2302.04761) | NeurIPS 2023 | 研究模型如何學會何時使用工具，例如搜尋、計算器與 API。 |
| [SWE-agent](https://arxiv.org/abs/2405.15793) | arXiv 2024 | 強調 Agent-computer interface 會直接影響自動軟體工程表現。 |

### 規劃、搜尋與自我修正

| 論文 | 來源 | 貢獻 |
|------|------|------|
| [Tree of Thoughts](https://arxiv.org/abs/2305.10601) | NeurIPS 2023 | 讓模型探索多條推理路徑，支援評分、回溯與搜尋。 |
| [LLM+P](https://arxiv.org/abs/2304.11477) | arXiv 2023 | 將自然語言任務轉成 classical planner 可處理的規劃問題。 |
| [Reflexion](https://arxiv.org/abs/2303.11366) | NeurIPS 2023 | 讓 Agent 失敗後透過 verbal feedback 反思並在後續嘗試中改善。 |
| [Tree Search for Language Model Agents](https://arxiv.org/abs/2407.01476) | arXiv 2024 | 探討 Agent 在環境中進行 inference-time tree search。 |

### 記憶與上下文

| 論文 | 來源 | 貢獻 |
|------|------|------|
| [Lost in the Middle](https://arxiv.org/abs/2307.03172) | TACL 2024 | 說明模型在長上下文中容易忽略中間資訊，是 context engineering 的重要依據。 |
| [MemGPT](https://arxiv.org/abs/2310.08560) | arXiv 2023 | 將 LLM 視為作業系統，提出短期與長期記憶管理。 |
| [RULER](https://arxiv.org/abs/2404.06654) | COLM 2024 | 測試長上下文模型的真實可用 context size。 |
| [NeedleBench](https://arxiv.org/abs/2407.11963) | arXiv 2024 | 評估不同資訊密度下的長上下文檢索與推理。 |
| [HippoRAG](https://arxiv.org/abs/2405.14831) | NeurIPS 2024 | 使用 knowledge graph 與 retrieval 建構長期記憶。 |
| [Mem0](https://arxiv.org/abs/2504.19413) | arXiv 2025 | 討論 production-ready Agent 長期記憶，包含抽取、合併、檢索、成本與延遲。 |
| [Zep](https://arxiv.org/abs/2501.13956) | arXiv 2025 | 使用 temporal knowledge graph 管理企業 Agent 記憶。 |

### 多 Agent 與社會化 Agent

| 論文 | 來源 | 貢獻 |
|------|------|------|
| [Generative Agents](https://arxiv.org/abs/2304.03442) | UIST 2023 | 提出 memory stream、reflection 與 planning，對記憶設計有啟發。 |
| [AutoGen](https://arxiv.org/abs/2308.08155) | Microsoft Research 2023 | 使用多 Agent 對話完成工具使用、程式執行與人類介入流程。 |
| [CAMEL](https://arxiv.org/abs/2303.17760) | arXiv 2023 | 探討角色扮演式多 Agent 協作。 |
| [Magentic-One](https://arxiv.org/abs/2411.04468) | Microsoft 2024 | Generalist multi-agent system，包含 orchestrator、specialist agents 與 error recovery。 |

### 評測、驗證與安全

| 論文 / Benchmark | 來源 | 貢獻 |
|------------------|------|------|
| [AgentBench](https://arxiv.org/abs/2308.03688) | ICLR 2024 | 評估 LLM 作為 Agent 在多種互動環境中的能力。 |
| [WebArena](https://arxiv.org/abs/2307.13854) | ICLR 2024 | 提供真實網站操作任務，用於 Web Agent 評測。 |
| [SWE-bench](https://arxiv.org/abs/2310.06770) | ICLR 2024 | 評測模型能否修復真實 GitHub issue 並通過測試。 |
| [GAIA](https://arxiv.org/abs/2311.12983) | ICLR 2024 | 評估一般 AI assistant 的多步驟、工具與推理能力。 |
| [tau-bench](https://arxiv.org/abs/2406.12045) | arXiv 2024 | 評估 tool-agent-user interaction，包含 policy 與資料庫狀態。 |
| [ToolSandbox](https://arxiv.org/abs/2408.04682) | Apple 2024 | 評估 stateful、conversational、interactive tool use。 |
| [AgentDojo](https://arxiv.org/abs/2406.13352) | arXiv 2024 | 評估 Agent 在工具輸出與外部內容中的 prompt injection 風險。 |
| [OSWorld](https://arxiv.org/abs/2404.07972) | arXiv 2024 | 評估 multimodal Agent 在真實作業系統中的任務能力。 |
| [TheAgentCompany](https://arxiv.org/abs/2412.14161) | arXiv 2024 | 用模擬公司環境評測工作型 Agent。 |
| [Constitutional AI](https://arxiv.org/abs/2212.08073) | Anthropic 2022 | 用明確原則、critique 與 revision 約束模型行為。 |

## 工程規格與工具

| 名稱 | 來源 | 用途 |
|------|------|------|
| [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-06-18) | MCP | 定義 Agent host 如何接入 tools、resources、prompts、logging、cancellation 與 trust boundary。 |
| [OpenAI Function Calling Guide](https://platform.openai.com/docs/guides/function-calling) | OpenAI | 說明 function calling schema、tool result loop、strict JSON schema 與工具設計。 |
| [Anthropic Tool Use Docs](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview) | Anthropic | 說明 Claude tool use、client/server tools、tool schema 與工具選擇。 |
| [OpenTelemetry Semantic Conventions for Generative AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/) | OpenTelemetry | 定義 GenAI / Agent traces、spans、metrics 與 exceptions。 |
| [Inspect AI](https://inspect.aisi.org.uk/) | UK AI Security Institute | LLM eval framework，支援 tools、sandbox、approval、logs 與 tracing。 |
| [LangGraph Durable Execution](https://docs.langchain.com/oss/python/langgraph/durable-execution) | LangChain | 說明 checkpoint、resume、replay、idempotent side effects 與長任務耐久執行。 |

## 對 Harness 設計的啟示

### 1. 先設計任務迴圈，不要只寫 prompt

可靠 Agent 應明確定義任務如何開始、如何取得環境回饋、如何判斷完成、失敗後如何重試。`ReAct`、Anthropic 的 workflows、OpenAI 的 Codex 實驗都指向同一件事：Agent 必須活在可觀察、可修正的 loop 裡。

### 2. 上下文要分層，不要一次塞滿

`Lost in the Middle`、`RULER`、`NeedleBench` 都顯示長上下文並不保證有效使用。較好的做法是使用短入口文件、索引、按需載入、workspace search、skills、subagents 與外部 memory。

### 3. 工具要少而清楚

工具描述本身就是 Agent-computer interface。Anthropic 與 Sean Goedecke 都指出工具太多會吃掉 context 並造成選擇錯誤。好的工具要有清楚名稱、參數、邊界、錯誤訊息與範例。

### 4. 驗證要外部化與機械化

Agent 說完成不代表真的完成。Coding agent 需要測試、lint、build、type check、browser automation、screenshot、logs 與 PR review。Research agent 需要 citation、source quality rubric 與 fact checking。

### 5. 多 Agent 適合讀取與探索，不一定適合寫入

Anthropic 的 multi-agent research system 適合 breadth-first research，因為子任務可平行探索。Cognition 則提醒寫入型任務容易因上下文不完整與隱性決策衝突而失敗。

### 6. Production Agent 需要 observability 與 durable execution

長任務可能跑數十分鐘到數小時。系統要支援 checkpoint、resume、trace、tool logs、side-effect idempotency 與錯誤恢復，否則任何中斷都會造成昂貴重跑。

### 7. 安全邊界必須明確

Agent 會讀不可信內容，也會使用有副作用的工具。需要 sandbox、approval gate、tool allowlist、prompt injection 防護、secret handling 與權限隔離。

## 建議閱讀順序

1. [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
2. [ReAct](https://arxiv.org/abs/2210.03629)
3. [Context Engineering for Coding Agents](https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html)
4. [Lost in the Middle](https://arxiv.org/abs/2307.03172)
5. [SWE-agent](https://arxiv.org/abs/2405.15793)
6. [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
7. [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system)
8. [Don’t Build Multi-Agents](https://cognition.ai/blog/dont-build-multi-agents)
9. [AgentDojo](https://arxiv.org/abs/2406.13352)
10. [LangGraph Durable Execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)

## 若要實作一個基本 Harness

可以從以下最小可行版本開始：

1. 明確定義任務輸入、完成條件與停止條件。
2. 提供少量高品質工具，例如 search、read、edit、run tests。
3. 建立短入口規則檔，例如 `AGENTS.md`，只放最重要的工作規則與索引。
4. 將長文件、規格、決策紀錄放入可搜尋的 `docs/` 目錄。
5. 每次修改後強制跑最小驗證，例如 test、lint、build 或 smoke test。
6. 記錄 tool calls、錯誤、重試與最終 artifact。
7. 對危險工具加 approval gate，例如刪檔、網路請求、部署、生產資料存取。
8. 對長任務加入 checkpoint 與可恢復狀態。
9. 定期清理過期文件、重複規則與壞模式。

## 結論

AI Agent Harness 是把 LLM 從「會回答問題的模型」變成「能完成工作的系統」的關鍵。它的核心不是單純提升模型能力，而是設計一個能讓模型可靠運作的環境。

從研究與工程案例來看，最重要的方向包括：清楚的 Agent loop、精簡且可用的工具、分層上下文、長期記憶、外部驗證、明確限制、可觀測性、durable execution 與安全邊界。未來 Agent 的競爭，很可能不只是模型能力競爭，而是 Harness 設計能力的競爭。
