# OpenSprite

OpenSprite 正在從乾淨的 repository 基礎重新設計。目前已建立可啟動的 React 前端與 Python 本機服務，提供真實的 Provider 連線、AI 設定、Conversation、Run、SSE 串流與 bounded Agent loop。

目前產品版本為 `0.21.18`。

## Windows 安裝與更新

### 一行指令下載原始碼並安裝

新版腳本推送到 GitHub `main` 後，可在任意目錄開啟 PowerShell，貼上：

```powershell
& ([scriptblock]::Create((Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/HsinPu/OpenSprite/main/installers/windows/bootstrap.ps1').Content)) -FromSource -InstallPrerequisites
```

不需要事先 clone 或發布 Release。腳本會透過 winget 補齊 Git、Node.js／npm、uv，
再把官方 repository 的 `main` 淺層 clone 到暫存目錄，執行安裝、檢查啟動並開啟瀏覽器。
更新也使用同一條指令；個人資料與既有存取模式保留，完成後清理下載暫存。
此指令同意安裝缺少的工具及套件條款；Windows 可能顯示權限提示。
沒有 winget 或既有 Node.js 過舊時會提示手動處理。
安裝期間會暫時允許目前 PowerShell 程序執行下載的安裝腳本，成功或失敗後都還原；不永久修改使用者或整台電腦的執行原則，組織的群組原則仍優先。
此入口執行官方 `main` 最新原始碼，請只在信任此來源時使用；正式版本入口見下方。

### 從本機原始碼安裝（目前可用）

安裝器會檢查 Node.js 20.19+（20.x）或 22.12+、npm 與 uv；缺少時可同意透過 winget 安裝。沒有 winget 時請手動安裝並重新開啟 PowerShell。
在下載或 clone 的 OpenSprite 專案根目錄執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\installers\windows\install.ps1
```

若要自動補齊必要工具，並在缺少 Git 時一併安裝：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\installers\windows\install.ps1 -InstallPrerequisites -InstallGit
```

`-InstallPrerequisites` 代表同意安裝缺少的套件及其授權條款；Git 為選用。既有 Node.js 版本過舊時仍需手動升級。自動化環境可加 `-NonInteractive`，未提供安裝同意時會直接回報缺少工具。

更新時，先取得新版原始碼，再執行同一條指令。安裝完成後會啟動程式並開啟瀏覽器；之後可透過 `http://localhost:8765/` 使用。

### 從 GitHub 一鍵下載安裝（需先發布 Release）

**此入口需要含安裝資產的正式 Release；只有原始碼 commit／push 還不夠，尚未發布時請使用上方本機安裝方式。**

正式 Release 發布後，可在 PowerShell 執行：

```powershell
& ([scriptblock]::Create((Invoke-WebRequest -UseBasicParsing 'https://github.com/HsinPu/OpenSprite/releases/latest/download/OpenSprite-install.ps1').Content))
```

這條指令會直接執行 GitHub 上的安裝腳本，僅在信任 `HsinPu/OpenSprite` 來源時使用。
也可以先下載 Release 的 `OpenSprite-install.ps1`，檢查內容後執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\OpenSprite-install.ps1
```

- 不需要 Git；會下載正式版安裝包、檢查 SHA-256，並在本機建置安裝。
- 缺少必要工具時會先詢問，取得同意後才透過 winget 安裝；沒有 winget 時需手動安裝工具。
- 更新使用相同指令；下載的腳本可加上 `-Version X.Y.Z` 指定版本。
- 成功後清理下載暫存與安裝中的建置依賴；不移除 Node.js、uv 或共用快取。Windows 鎖定的暫存／備份目錄會保留並提示。
- 程式安裝於 `%LOCALAPPDATA%\OpenSprite\app`；個人資料保存於 `%USERPROFILE%\.opensprite`，更新不清除對話、設定、金鑰或既有存取模式。

完整參數、解除安裝、失敗處理及 Release 發布流程見 [Windows 安裝說明](installers/windows/README.md)。

## 近期調整

`0.21.13` 整理排程設定頁，加入名稱搜尋、工作區與狀態篩選、精簡清單及分頁，集中操作並將表單分區；明確標示時區，補齊紀錄載入與重試狀態，保留既有排程執行規則。

`0.21.4` 移除聊天頂部重複的「＋ 新對話」快捷按鈕；保留側欄新對話、面板收合與工作區／對話標題。

`0.21.3` 支援左右側面板獨立拖曳寬度並記住偏好，左側最大 600px、右側最大 800px；保留聊天區最小空間，支援鍵盤及雙擊重設。側欄新對話與工作區選單統一為 44px 高。

`0.21.2` 整理主聊天版面：移除橫跨側欄的頂部工具列，側欄從頂端開始，聊天區以小型「工作區 / 對話」顯示位置。左右面板可完全收合，聊天與輸入框隨可用空間置中；保留原有配色、模型設定與資料，窄畫面使用覆蓋式面板。

聊天使用的模型統一於「設定 → AI 模型」選擇；修改後供新的執行使用，既有執行及排程保存的模型設定不會被改寫。聊天輸入框不再提供模型選單。

## 自訂 OpenAI-compatible 供應商

`0.21.0` 保留 OpenAI、Anthropic、OpenRouter，另可在「設定 → AI 模型」新增多個自訂供應商。
自訂項目使用 OpenAI-compatible **Chat Completions** 協定，不會把內建 OpenAI 的 Responses API 改成另一種協定。

1. 新增自訂供應商，填寫顯示名稱與 API Base URL，例如 `https://example.com/v1`；不要填完整的 `/chat/completions` 路徑。
2. 選擇無認證或 Bearer API Key。編輯時金鑰留白代表保留既有金鑰；改成無認證會移除該供應商的金鑰。
3. 重新取得模型清單，或手動新增模型 ID、顯示名稱、Context／輸出上限及工具呼叫能力。
4. 在模型選擇區選取這個供應商及模型。排程保存自己的模型選擇；Agent 定義可使用自訂供應商 ID，或省略以繼承父任務。

模型探索使用 `<Base URL>/models`，推論使用 `<Base URL>/chat/completions`。
有些服務不提供模型探索，可改用手動模型。探索成功不代表該模型一定支援工具、所有參數或推論；
請依服務能力設定模型上限與工具能力。自訂相容端點不自動套用 OpenRouter 專屬參數。

公開端點必須使用 HTTPS。只有明確允許時才接受本機／私人網路 HTTP；HTTP 不會加密金鑰與對話內容。
不支援任意自訂 Header、關閉 TLS 驗證或自動跟隨重新導向。Base URL 指向的服務會收到實際送出的對話內容。

執行中會固定 Provider 端點與模型能力快照，因此不能同時修改該供應商或模型。
刪除被 AI 設定、排程或 Agent 定義引用的項目之前，必須先調整引用；不會自動換成其他供應商。
刪除登記不刪除歷史對話與 Run。更多細節見 [自訂 Provider 架構](docs/architecture/custom-providers.md)。

Skills 工具列的「批次操作」選單提供全部啟用、全部停用與移除全部，僅作用於目前全域或所選工作區的專用 Skills，不修改繼承的全域項目或總開關。啟用時略過無效項目；移除需輸入確認文字，檔案只移至封存位置。工作區全部停用仍遮蔽同名全域版本，移除登記後才恢復繼承。

### 匯入 Skill ZIP

在「設定 → Skills」選擇全域或工作區，再按「匯入 → 匯入 ZIP」。一次匯入一個 Skill，
支援 ZIP 根層的 `SKILL.md`，或 `code-review/SKILL.md` 這種單一外層目錄。
Ant 視窗先在瀏覽器預覽名稱、說明、檔案與內容，按「確認匯入」才上傳。
儲存目錄名稱預設採外層資料夾名稱，無外層時採 ZIP 檔名（不含副檔名），可在預覽修改。
顯示名稱採 front matter 的 `name`。同名不覆蓋；匯入成功後預設啟用，不必再編輯或確認版本。

最多 200 個檔案、合計 10 MiB、單一附屬檔案 5 MiB、深度 8 層；`SKILL.md`
仍限 UTF-8 與 64 KiB。ZIP 本身最多 12 MiB，支援 stored／deflate；拒絕加密、損壞、
連結、路徑跳脫、跨平台名稱衝突、巢狀 Skills、版本庫與依賴目錄。
空目錄不匯入。遠端部署會上傳檔案副本，不是掛載來源路徑。

`references`、`scripts`、`assets` 可保存，但目前只有 `SKILL.md` 會載入 Context；
不會執行附屬腳本，也不支援 GitHub 匯入。單一 `SKILL.md` 匯入仍保留；資料夾選取入口已移除。

## Agents：全域與工作區子代理

在「設定 → Agents」管理可委派的角色。全域定義放在 `.opensprite/agents/*.toml`，
工作區定義放在 `.opensprite/workspace/<工作區目錄>/agents/*.toml`。支援新增、TOML 匯入、
重新掃描、啟用／停用與封存移除；工作區同名版本優先，停用或無效時不回退全域版本。

```toml
name = "reviewer"
description = "適合獨立檢查指定內容，回報問題與證據。"
developer_instructions = "檢查被委派的範圍，區分確認問題與不確定處，不宣稱未執行的驗證。"
```

可選擇同時設定 `provider_id` 與 `model`；省略時繼承父任務的模型。這是 OpenSprite 的
定義格式，不接受任意 Codex 設定、腳本或權限設定。

模型先探索角色，再決定是否委派。子代理有獨立 Context，使用同一工作區快照與可用 Skills，
不直接讀取父對話，也不能再建立子代理或要求人工工具核准。每輪最多建立 6 個，
每個父任務同時最多 2 個，全域同時最多 4 個；10 分鐘期限包含排隊。
父任務結束前會收妥子任務，服務重啟後未完成項目標示中斷，不自動重試。

「本次執行」的 Subagents 區塊可查看狀態、分頁報告及取消子任務。子任務不會新增側邊欄對話。
啟用角色不保證模型每次都會委派，仍取決於任務與模型能力。
詳見 [Agents 架構](docs/architecture/custom-agents.md)。

## Skills：全域與工作區指引

在「設定 → Skills」管理文字型指引。全域 Skills 位於
`.opensprite/skills/<名稱>/SKILL.md`；工作區 Skills 位於
`.opensprite/workspace/<工作區目錄>/skills/<名稱>/SKILL.md`。
檔案必須包含 YAML 的 `name`、`description` 與非空 Markdown 正文，最大 64 KiB。

```markdown
---
name: review
description: 在需要程式碼審查時使用
---
先檢查正確性與回歸風險，再列出有證據支持的問題。
```

- 新增及匯入成功後預設啟用，清單提供啟用／停用與移除，不再要求確認版本。
- 總開關預設開啟。重新掃描發現的合法新 Skill 預設啟用；已登記項目的開關保持不變，格式錯誤的新項目保持停用。
- 工作區自動繼承全域 Skills；以 `name` 的 NFC 正規化、不分大小寫比對，工作區同名版本優先。工作區版本停用、遺失或無效時不回退全域；移除登記後才恢復繼承。
- `0.17.0` 升級會清除舊「此工作區停用」覆寫，恢復自動繼承，保留各 Skill 本身開關。工作區頁的全域清單為唯讀，不再提供手動覆寫選單。
- 模型起初只收到已生效 Skill 的簡介，需要時才透過 `load_skill` 載入全文。
- Skills 統一在設定頁管理，由 AI 依需求自動選用；模型須支援工具呼叫。輸入框不提供手動選擇。
- 「允許 AI 使用工具」關閉不會禁止文字 Skill；Skills 也不能啟用工具、執行腳本或繞過核准。
- 已啟用檔案的合法外部修改會由下一次 Run 使用，不再詢問；格式錯誤、遺失或路徑不安全仍禁止載入。已開始的 Run 使用固定快照。
- 刪除會封存到 `.opensprite/archive/skills`，不立即永久刪除。工作區移除保留實體檔案，但撤銷啟用登記。
- 「本次執行」顯示真正載入的 Skills，而不是整份可用清單。

本版不讀取參照檔、不執行 Skill scripts、不掃描外部掛載，也不下載遠端 Skills。
完整 Prompt log 若啟用可能包含指引全文；一般事件與 Log 不保存全文或絕對路徑。
詳見 [Skills 架構](docs/architecture/skills.md)。

Windows 與 Linux 都從 repository root 使用各自的 installer。安裝後透過
`http://localhost:8765/` 使用；backend 固定只監聽 loopback，不直接提供公網模式。

## 目前狀態

- 前端：React、TypeScript、Vite、Ant Design，透過同源 `/api` 與本機服務溝通。
- 對話：Conversation、Message、Run 與安全語意事件保存於 `.opensprite/data/opensprite.db`，前端以 HTTP 與 SSE 消費。
- 工作區：OpenSprite 在使用者目錄建立 managed root，並可掛載最多 20 個具唯讀／可讀寫權限的外部目錄；Conversation 與 Schedule 明確歸屬 Workspace，每次 Run 固定使用開始時的 Workspace 快照。
- AI：內建 OpenAI、Anthropic、OpenRouter，並支援自訂 OpenAI-compatible Chat Completions 供應商；模型與執行偏好保存於 `.opensprite/config/settings.json`。
- 金鑰：只以 AES-256-GCM ciphertext 保存於 `.opensprite/auth.json`，每次安裝使用獨立的 `config/credential.key`。
- Agent：所有使用者訊息進入同一個 Token-budgeted Agent loop；舊對話只做可重建摘要，原始訊息不刪除。執行事件與 Context 用量可由前端即時／歷史查看；production Tool Registry 目前包含安全的唯讀計算器。
- 排程：支援單次、每日與每週自動執行；每個排程使用專屬對話與固定模型設定，執行紀錄保存在 SQLite，backend 重啟後可恢復。
- CLI：不在新版本範圍內。
- API：Provider、AI settings、Workspace、Agent chat HTTP/SSE 與受保護的排程 CRUD／執行紀錄契約已實作；未使用 WebSocket。
- 存取：支援本機免密碼的 `trusted_local` 與需要 Argon2id 密碼、記憶體 Session 的 `password_required`。
- 安裝器：Windows 與 Linux current-user installer 均已實作；Linux 已在 WSL 2＋Ubuntu 24.04 驗證隔離安裝、systemd 啟動、更新、解除安裝及重裝保留資料，詳見 [驗證紀錄](docs/changes/0299-linux-systemd-wsl-verification.md)。Linux 目前仍需先備妥 Node.js／npm、uv、Python 與原始碼。

## 工作區

Workspace 是網頁聊天、排程以及後續 Skills／外部 Channel Adapter 共用的執行範圍。Windows 使用 `%USERPROFILE%\.opensprite\workspace`，Linux 使用 `~/.opensprite/workspace`；固定的「預設工作區」位於 `workspace/default`。建立 `test` 會建立 `workspace/test`，也能明確加入容器內既有的第一層目錄。

- Workspace catalog 與目前選擇保存在 `.opensprite/config/workspaces.json`；managed root 路徑由使用者家目錄推導，不使用瀏覽器儲存。
- 外部目錄以預設唯讀的 mount 掛入 Workspace，可明確提升為可讀寫；重疊、系統敏感與 reparse/symlink 路徑會被拒絕。
- SQLite 只保存 Workspace ID、revision、名稱、root hash 與 mount-manifest hash，不保存完整絕對路徑。
- Conversation 清單依目前 Workspace 隔離；一般 Conversation 可在沒有執行中 Run 時安全移動。
- Schedule 保存自己的 Workspace，不會隨 Sidebar 目前選擇改變。
- managed root 或 mount 失效時仍可文字聊天；未來需要檔案路徑的工具必須拒絕執行。
- `0.12.1` 只建立目錄權限架構，尚未提供檔案、Git、Terminal 或檔案樹工具。模型知道 Workspace 路徑不代表取得檔案能力。

Managed root 僅允許 `.opensprite/workspace` 的合法第一層子目錄。外部掛載仍拒絕磁碟根目錄、家目錄、`.opensprite` 及其子目錄、OpenSprite 安裝目錄，以及 symlink／junction／reparse-point。完整設計見 [`docs/architecture/workspaces.md`](docs/architecture/workspaces.md)。

升級至 0.12.1 時，已登記的舊工作區與 default 會複製到新位置，核對內容後才切換；原始目錄保留。目的地衝突、權限不足或來源檔案變動會阻止切換，設定頁顯示搬遷未完成；排除問題後重新整理重試。未登記的舊目錄及外部掛載不會自動搬動。請勿直接降版讀取新版 catalog。失敗的暫存副本位於 `.opensprite/cache/workspace-relocation`，不會自動刪除。

## 存取與登入

存取模式保存於 `.opensprite/config/access-policy.json`。模式是整個安裝層級的設定，不能依單次請求自動判斷，因為本機瀏覽器與 SSH Tunnel 抵達 backend 時都可能呈現為 `localhost`。

### 本機信任模式

`trusted_local` 適合使用者直接操作的 Windows 或 Ubuntu Desktop：

- 開啟 OpenSprite 後直接進入，不顯示登入頁。
- 不建立登入 Session Cookie，也不需要首次設定密碼。
- Backend 仍只綁定 `127.0.0.1`，Host、Origin、CSP 與 no-store 防護仍會執行。
- 任何能以相同作業系統帳號執行程式的人，都可能存取 OpenSprite 的本機資料與 API。

Windows 新安裝預設使用本機信任模式，也可以明確指定：

```powershell
./installers/windows/install.ps1 -AccessMode TrustedLocal
```

Ubuntu Desktop 使用：

```bash
./installers/linux/install.sh --access-mode trusted_local
```

### 密碼保護模式

`password_required` 適合遠端 Linux、共用電腦，或希望本機仍要求密碼的情境：

- 密碼經 Unicode NFC 正規化，必須為 15–128 個字元。
- 密碼只以 Argon2id hash 保存於 `.opensprite/config/access.json`。
- 一次性設定網址有效 30 分鐘，成功設定後立即失效。
- Session Token 只保存在 Secure、HttpOnly、SameSite=Strict Cookie；後端只保存 Token hash。
- Session 閒置 12 小時、登出、修改密碼或 backend 重啟後失效。

Windows 安裝或切換為密碼保護：

```powershell
./installers/windows/install.ps1 -AccessMode Password
```

Installer 啟動服務後會自動開啟包含 `#setup=` 一次性 Token 的設定頁。若設定網址遺失或過期，可重新產生：

```powershell
./installers/windows/install.ps1 -AccessMode Password -ResetLocalAccess
```

遠端 Linux 安裝使用：

```bash
./installers/linux/install.sh --access-mode password_required
```

Linux installer 只將一次性設定網址顯示到目前的互動式 `/dev/tty`，不寫入檔案、stdout、stderr、systemd journal 或 process arguments。在自己的電腦建立 SSH Tunnel：

```bash
ssh -N -L 8765:127.0.0.1:8765 user@server
```

再把 Linux 終端顯示的完整網址貼到自己電腦的瀏覽器：

```text
http://localhost:8765/#setup=<一次性Token>
```

Linux 重新產生設定網址：

```bash
./installers/linux/install.sh --access-mode password_required --reset-local-access
```

### 更新、切換與資料保留

- 既有安裝更新時會保留已選擇的模式，不會自動降低密碼保護。
- 從密碼模式切換到本機信任會保留既有 `access.json`，方便日後重新啟用原密碼，但會移除未使用的 bootstrap。
- 從本機信任切回密碼模式時，已有 `access.json` 就沿用原密碼；沒有時才產生一次性設定網址。
- 重設存取只替換登入 policy、密碼/bootstrap 與記憶體 Session，不刪除 Conversation、SQLite、AI/MCP 設定、Provider 金鑰或 Log。
- 這套登入不防範相同 OS 帳號下的惡意程式、Administrator/root，也不加密既有 SQLite、Log 或整個 `.opensprite`。

詳細設計見 [`docs/architecture/local-authentication.md`](docs/architecture/local-authentication.md)、[`docs/architecture/linux-installation.md`](docs/architecture/linux-installation.md) 與各平台 installer README。

## 資料夾

- `frontend/`：瀏覽器介面與前端測試。
- `backend/`：Python FastAPI 本機服務、Agent、Provider、加密憑證與 SQLite persistence。
- `contracts/`：authoritative OpenAPI HTTP/SSE 契約。
- `installers/`：Windows 與 Linux 安裝、啟動、存取模式、重設與解除安裝流程。
- `docs/`：架構與逐步修改紀錄。
- `scripts/`：未來的驗證及維護自動化。

完整架構原則見 `docs/architecture/overview.md`。每次修改的證據見 `docs/changes/`。

舊版完整程式保存在 `codex/archive-main-before-refactor-20260820`，只能唯讀參考，不直接搬回新架構。
