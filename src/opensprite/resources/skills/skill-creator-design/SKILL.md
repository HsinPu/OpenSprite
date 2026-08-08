---
name: skill-creator-design
description: Skill design guide for creating reusable skills with clear metadata, lean instructions, progressive disclosure, and the right mix of scripts, references, and assets. Use when creating a new skill or refining an existing one that extends agent capabilities.
source: HsinPu/Autoverse-Ai-Agent-Skills
license: Apache-2.0
---

# Skill 建立者（Skill Creator）

Skill 是**模組化套件**（modular package），透過提供**專業知識**（specialized knowledge）、**工作流程**（workflows）與**工具**（tools）來擴充 agent 的能力。

## 核心原則（Core Principles）

### 簡潔為上（Concise is Key）
Context window 是一種公共財。Skill 與 agent 所需的一切共用同一個 context window：system prompt、對話紀錄、其他 Skill 的 metadata，以及使用者實際的請求。

**預設前提：agent 已經很聰明。** 只加入 agent 尚未具備的內容。對每一段資訊自問：「agent 真的需要這段說明嗎？」以及「這段文字值得它消耗的 token 嗎？」

寧可多用**簡潔範例**（concise examples），少用**冗長說明**（verbose explanations）。

### 設定適當的自由度（Set Appropriate Degrees of Freedom）

依照任務的**脆弱度**（fragility）與**可變性**（variability），決定要給的**具體程度**（level of specificity）：

**高自由度（high freedom，文字化指示）**：適用於多種做法都成立、決策依情境而定，或由啟發式引導做法時。

**中自由度（medium freedom，pseudocode 或帶參數的 scripts）**：適用於已有偏好的模式、允許一定變化，或行為會受設定影響時。

**低自由度（low freedom，具體 scripts、少參數）**：適用於操作容易出錯、一致性很重要，或必須依特定順序執行時。

可把 agent 想成在探路：狹橋懸崖需要明確護欄（low freedom），開闊原野則可多條路線（high freedom）。

### 漸進式揭露設計原則（Progressive Disclosure Design Principle）

Skill 以**三層載入機制**（three-level loading system）有效管理 **context**：

1. **Metadata（name + description）**：始終在 context 中（約 ~100 字）
2. **SKILL.md body**：skill 觸發時才載入（<5k 字）
3. **Bundled resources**：由 agent 依需要載入（數量不限，因 scripts 可不讀入 context window 直接執行）

#### 漸進式揭露實作模式（Progressive Disclosure Patterns）

**SKILL.md** body 只保留必要內容，控制在 500 行以內，以減少 **context 膨脹**（context bloat）。接近此上限時請將內容拆成獨立檔案。拆出到其他檔案時，務必在 SKILL.md 中**引用**（reference）並清楚說明「何時該讀」，讓 skill 的讀者知道這些檔案存在以及使用時機。

**核心原則（Key principle）：** 當 skill 支援多種變體、框架或選項時，SKILL.md 只保留核心 workflow 與選擇指引；把各變體專屬的細節（patterns、examples、configuration）移到獨立的 reference 檔案。

**Pattern 1：高層指引＋參考連結（High-level guide with references）**

```markdown
# PDF Processing

## Quick start

Extract text with pdfplumber:
[code example]

## Advanced features

- **Form filling**: See [FORMS.md](FORMS.md) for complete guide
- **API reference**: See [REFERENCE.md](REFERENCE.md) for all methods
- **Examples**: See [EXAMPLES.md](EXAMPLES.md) for common patterns
```

agent 只在需要時才載入 FORMS.md、REFERENCE.md 或 EXAMPLES.md。

**Pattern 2：依領域／變體組織（Domain-specific organization）**

若 Skill 涵蓋多個**領域**（domains），依領域分檔以避免載入不相關的 **context**：

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── reference/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    ├── product.md (API usage, features)
    └── marketing.md (campaigns, attribution)
```

使用者問銷售指標時，agent 只會讀 sales.md。

同理，支援多種 **framework** 或**變體**（variants）的 skill 可依變體分檔：

```
cloud-deploy/
├── SKILL.md (workflow + provider selection)
└── references/
    ├── aws.md (AWS deployment patterns)
    ├── gcp.md (GCP deployment patterns)
    └── azure.md (Azure deployment patterns)
```

使用者選擇 AWS 時，agent 只會讀 aws.md。

**Pattern 3：條件式細節（Conditional details）**

主體放**基本內容**（basic content），**進階內容**（advanced content）用連結帶出：

```markdown
# DOCX Processing

## Creating documents

Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents

For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

agent 僅在使用者需要該功能時才讀 REDLINING.md 或 OOXML.md。

**重要準則（Important guidelines）：**

- **避免深層巢狀引用（Avoid deeply nested references）**：reference 只做一層，從 SKILL.md 直接連結；所有 reference 檔都應由 SKILL.md 直接連結。
- **長 reference 要有結構（Structure longer reference files）**：超過 100 行的檔案，在開頭放**目錄**（table of contents），讓 agent 在**預覽**（preview）時能掌握**完整範圍**（full scope）。

### Skill 的結構（Anatomy of a Skill）

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/      - Executable code
    ├── references/   - Documentation
    └── assets/       - Templates, images
```

#### SKILL.md（必填，required）

每份 SKILL.md 包含**兩部分**（two parts）：

- **Frontmatter**（YAML）：**必填欄位**（required）為 `name`、`description`；**選填**（optional）可加 `license`、`metadata`、`compatibility`。其中 `name` 與 `description` 會被 agent 用來判斷何時**觸發**（trigger）此 skill，因此 `description` 必須寫得**清楚、完整、且足夠詳細**，先直接說明這個 skill 本身提供什麼能力、負責什麼工作或 workflow，再補充適用情境、常見觸發語句或任務類型；不要只寫過短或籠統的一句話。整個 frontmatter **必須使用英文**，讓 agent 在跨專案與跨語系情境下更穩定判斷與比對 metadata。`compatibility` 用於標註**環境需求**（environment requirements），多數 skill 不必填。
- **Body**（Markdown）：使用此 skill 的**指示與指引**（instructions and guidance）。只有在 skill 觸發後才會載入（若有的話）。

#### Bundled Resources（選填，optional）

##### Scripts（`scripts/`）

**可執行程式碼**（Executable code，如 Python/Bash），用於需要**確定性、可重現**（deterministic, reproducible）的任務，或常被反覆改寫的程式。

- **何時納入（When to include）**：同一段程式被反覆改寫，或需要 **deterministic** 可靠性時。
- **範例（Example）**：PDF 旋轉任務用 `scripts/rotate_pdf.py`。
- **優點（Benefits）**：省 **token**、結果確定、可不載入 **context** 直接**執行**（execute）。
- **注意（Note）**：agent 仍可能需讀取 script 以進行 **patch** 或依**環境**（environment）調整。

##### References（`references/`）

**文件與參考資料**（Documentation and reference material），依需要載入 **context**，供 agent **推理與決策**（reasoning and decision-making）時參考。

- **何時納入（When to include）**：agent 工作時需要查閱的文件。
- **範例（Examples）**：`references/finance.md` 財務 **schema**、`references/mnda.md` 公司 NDA 範本、`references/policies.md` 公司政策、`references/api_docs.md` **API** 規格。
- **適用情境（Use cases）**：資料庫 **schema**、**API** 文件、**領域知識**（domain knowledge）、公司政策、詳細**流程指引**（workflow guides）。
- **優點（Benefits）**：SKILL.md 保持**精簡**（lean），僅在 agent 判斷需要時才載入。
- **建議（Best practice）**：若檔案很大（>10k 字），在 SKILL.md 中提供 **grep** 搜尋模式。
- **避免重複（Avoid duplication）**：同一資訊只放在 SKILL.md 或 **references** 其一。詳細內容優先放 references，除非是 skill **核心**（core）；SKILL.md 只保留必要**流程與指引**（procedural instructions and workflow guidance），把詳細參考、schema、範例移到 references，才不會佔滿 **context window**。

##### Assets（`assets/`）

不打算載入 **context**，而是用在 agent 產出的**輸出**（output）裡使用的檔案。

- **何時納入（When to include）**：skill 需要會在**最終輸出**（final output）中用到的檔案時。
- **範例（Examples）**：`assets/logo.png` 品牌素材、`assets/slides.pptx` 簡報範本、`assets/frontend-template/` HTML/React **boilerplate**、`assets/font.ttf` 字型。
- **適用情境（Use cases）**：**範本**（templates）、圖片、圖示、**boilerplate** 程式碼、字型、會被**複製或修改**（copied or modified）的範例文件。
- **優點（Benefits）**：把**輸出資源**（output resources）與文件分開，agent 可直接使用檔案而無須載入 **context**。

#### 不要納入的內容（What to Not Include in a Skill）

Skill 只應包含 AI **agent** 執行**當下任務**（task at hand）所需的資訊，不要放進多餘的 **auxiliary context**，例如：**開發過程**（creation process）說明、**setup／testing** 流程、**user-facing** 文件等。多建額外文件只會增加**雜訊與混淆**（clutter and confusion）。

只保留**直接支援此 skill 功能**（directly support its functionality）的**必要檔案**（essential files）。請勿建立**多餘的文件或輔助檔**（extraneous documentation or auxiliary files），例如：

- README.md
- INSTALLATION_GUIDE.md
- QUICK_REFERENCE.md
- CHANGELOG.md
- 其他類似檔案（etc.）

## Skill 建立流程（Skill Creation Process）

### Step 1：用具體範例理解 Skill（Understanding the Skill with Concrete Examples）

**何時可跳過（When to skip）**：僅在 skill 的 **usage patterns**（使用模式）已非常明確時；即使優化既有 skill，此步驟仍有價值。

**目標（Goal）**：掌握「此 skill 會如何被使用」的 **concrete examples**（具體範例）。範例可來自使用者提供，或你產出後經 **user feedback**（使用者回饋）確認。

**可問的題目（Questions to ask）**—以 **image-editor** skill 為例：

- **Functionality**（功能範圍）：應支援哪些？編輯、旋轉，還有其他嗎？
- 能否舉幾個此 skill 實際會被怎麼用的例子？
- 例如「把紅眼去掉」「旋轉這張圖」—還有你預期會用到的情境嗎？
- **Trigger**（觸發）：使用者說什麼話時應觸發此 skill？

**注意（Note）**：一次不要問太多，先問最關鍵的，再視需要 **follow up**（追問）。

**完成條件（Completion criteria）**：能明確說出此 skill 應支援的 **functionality** 與典型 **trigger** 語句時，即可進入 Step 2。

### Step 2：規劃可重複使用的 Skill 內容（Planning the Reusable Skill Contents）

**目標（Goal）**：把 Step 1 的 **concrete examples**（具體範例）轉成要放進 skill 的**資源清單**（resource list）—**scripts**、**references**、**assets**。

**分析方法（Analysis）**—對每個範例做兩件事：

1. 思考「**從零開始執行這個範例**」（execute from scratch）會怎麼做。
2. 找出若**反覆執行**（repeatedly execute）這類 **workflow**（工作流程）時，哪些 **scripts / references / assets** 能**重複用、值得納入**（reusable, worth including）。

**範例（Examples）**—依資源類型：

| **情境**（Scenario） | **重複發生的成本**（Recurring cost） | **建議納入**（Include） |
|------|----------------|----------|
| `pdf-editor`：旋轉 PDF | 每次重寫同一段程式 | `scripts/rotate_pdf.py` |
| `frontend-webapp-builder`：做 todo app / dashboard | 每次都要相同 **boilerplate** HTML/React | `assets/hello-world/` 範本 |
| `big-query`：查「今天多少使用者登入」 | 每次重查表 **schema** 與關聯 | `references/schema.md` |

**完成條件（Completion criteria）**：對每個 concrete example 做完分析，並列出一份要納入的 **scripts / references / assets** 清單後，即可進入 Step 3。

### Step 3：初始化 Skill（Initializing the Skill）

**若 skill 已存在（When skill already exists）**：改為檢查 **目錄結構**（directory structure）與**必備檔案**（required files）是否正確（含 SKILL.md 與 **frontmatter**）；若只是編輯既有內容或做 **iteration**（迭代），確認結構無誤後即可進行下一步。

**目標（Goal）**：建立 skill 目錄結構與必備檔案。

**建立位置（Location）**：在**當前工作目錄**（current working directory）底下建立。

**目錄結構（Directory structure）**：

```
skill-name/
├── SKILL.md          ← 必填（required）
└── [選填 optional] Bundled resources
    ├── scripts/      ← Executable code（可執行程式碼）
    ├── references/   ← Documentation（參考文件）
    └── assets/       ← Templates, images（範本、圖片等）
```

**必備檔案（Required file）**：

- **SKILL.md**：須含 YAML **frontmatter**，至少包含 `name`、`description`；內文為 **Markdown** 指示。其餘資源目錄（**scripts / references / assets**）依 Step 2 規劃按需建立。

**完成條件（Completion criteria）**：目錄與 SKILL.md 已建立，即可進入 Step 4。

### Step 4：實作（Implementation）

**目標（Goal）**：依 Step 2 的**資源清單**（resource list）產出內容並完成 SKILL.md，使 skill 可被**觸發**（trigger）與使用。

**建議順序（Recommended order）**：

1. **從可重複使用的資源開始（Start with reusable skill contents）**  
   先建立 **scripts/**、**references/**、**assets/**（依 Step 2 規劃）。可能需要**使用者提供資料**（user input），例如 `brand-guidelines` 需提供品牌素材或範本→`assets/`、文件→`references/`。

2. **撰寫 SKILL.md**  
   Frontmatter（`name`、`description`）＋ Body（使用此 skill 與 **bundled resources** 的指示）；必要時以「漸進式揭露」連結 **references**。撰寫要點見下方▼。

3. **驗證（Verify）**  
   **Scripts** 須**實際執行**（run）測試，確認無 bug、輸出符合預期。多個類似 script 時可只測**代表性樣本**（representative sample）。

4. **清理（Cleanup）**  
   刪除用不到的**範例檔與目錄**（example files and directories）；初始化範例多數 skill 不需全留。

**完成條件（Completion criteria）**：資源檔與 SKILL.md 就緒、scripts 測試通過、範例已清理，即可進入 Step 5。

---

#### 撰寫 SKILL.md 要點（Update SKILL.md）

**撰寫原則（Writing guidelines）**：一律使用**祈使句／不定詞**（imperative/infinitive）。

**Frontmatter**：YAML 中至少填 `name`、`description`。

- **`name`**：skill 名稱。
- **`description`**：skill 的**主要觸發依據**（primary triggering mechanism），供 agent 判斷何時使用。
  - 須包含：**做什麼**＋**何時／在什麼情境用**（triggers/contexts）。「何時使用」只寫在 description，不要寫在 body（body 觸發後才載入，寫在 body 對觸發判斷無幫助）。
  - 要寫得**詳細且可判斷**，至少讓 agent 看完後知道：這個 skill 解決什麼問題、典型在哪些任務中該觸發、處理哪些代表性工作，必要時可補充技術範圍、平台、框架、輸入輸出或限制。
  - 要先**直接描述這個 skill 本身**是做什麼的，不要只列「何時用」。
  - frontmatter **必須使用英文**；`name` 使用英文識別詞，`description` 與其他自由文字欄位也使用英文。
  - 不要只寫成過短、抽象、難以觸發的句子，例如 `Help with logging`、`Skill for coding`、`Use for docs`。
  - 優先使用 1-3 句完整英文描述；若技能範圍較廣，可用第二句補充具體觸發條件、常見任務或代表性例子。
  - description 應盡量包含使用者或任務中可能出現的關鍵詞，讓 agent 更容易在正確時機載入 skill。
  - 範例（`docx`）：*"Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when the agent needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"*
  - 範例（`logging-patterns`）：*"Write clean, consistent log statements with stable message patterns, sensible log levels, and low-noise context fields. Use when adding, refactoring, or reviewing application logs so messages stay readable, searchable, and easy to correlate."*
**Body**：撰寫使用此 skill 及其 **bundled resources** 的**指示**（instructions）。

### Step 5：迭代（Iteration）

**目標（Goal）**：在**真實任務**（real tasks）上使用此 skill，根據實際表現持續改進。

**做法（What to do）**：用此 skill 處理**真實需求**（real requests），觀察**困難點**（pain points）與**誤觸發／未觸發**（false trigger / missed trigger）等情況，回頭調整 **SKILL.md**（description、body）、**scripts**、**references** 或 **assets**。必要時回到 Step 1～4 補齊範例、資源或描述。

**完成條件（Completion criteria）**：**迭代**（iteration）可持續進行；當 skill 在**目標情境**（target context）下**穩定觸發**（triggers reliably）、**行為符合預期**（behaves as expected）時，即視為此輪建立完成。

---

## 檢查清單（Skill Review Checklist）

建立或審查 Skill 時，逐項確認以下條件：

### Frontmatter

- [ ] `name` 已填寫且與**資料夾名稱一致**（lowercase, hyphen-separated）
- [ ] `description` 包含「**做什麼**」與「**何時／什麼情境使用**」（triggers/contexts）
- [ ] `description` 不是過短的泛稱，而是有足夠細節讓 agent 可直接判斷是否該觸發
- [ ] `description` 有直接說明這個 skill 本身是做什麼的，不只是列使用時機
- [ ] frontmatter 使用英文撰寫（至少 `name`、`description` 與其他自由文字欄位）
- [ ] 觸發條件**只寫在 description**，不重複寫在 body（body 觸發後才載入，對觸發判斷無幫助）

### SKILL.md Body

- [ ] Body 控制在 **500 行以內**，避免 context 膨脹
- [ ] 使用**祈使句／不定詞**語氣（imperative/infinitive）
- [ ] 只保留 agent 執行任務**直接需要的指示**，不放開發過程說明、setup 流程、user-facing 文件

### Progressive Disclosure（漸進式揭露）

- [ ] 細節內容拆到 **reference/** 檔案，SKILL.md 只做**精簡入口**
- [ ] 每個 reference 連結**說明「何時該讀」**，讓 agent 知道載入時機
- [ ] Reference 只做**一層**，從 SKILL.md 直接連結（避免深層巢狀）
- [ ] 超過 100 行的 reference 檔案**開頭有目錄**（Table of Contents）

### 目錄結構

- [ ] 不包含多餘文件（不要 README.md、CHANGELOG.md、INSTALLATION_GUIDE.md 等）
- [ ] Scripts（若有）已**實際執行測試**，確認無 bug、輸出符合預期
- [ ] 範例檔與目錄已**清理**，只保留必要資源

### 品質

- [ ] 問過自己：「agent **真的需要**這段說明嗎？這段文字**值得它消耗的 token** 嗎？」
- [ ] 寧可多用**簡潔範例**，少用**冗長說明**
- [ ] 同一資訊**不重複**出現在 SKILL.md 與 reference 中
