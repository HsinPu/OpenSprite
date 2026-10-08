# OpenSprite

OpenSprite 正在從乾淨的 repository 基礎重新設計。目前已建立可啟動的 React 前端與 Python 本機服務，提供真實的 Provider 連線、AI 設定、Conversation、Run、SSE 串流與 bounded Agent loop。

目前產品版本為 `0.21.31`。

## Docker 部署

安裝 Docker Engine／Docker Desktop（Linux containers）與 Docker Compose v2，在 repository 根目錄執行：

```bash
docker compose up -d --build --wait
```

開啟 [http://localhost:8765/](http://localhost:8765/)。更新原始碼後再次執行相同指令。
首次啟動使用「信任本機」存取模式，預設只綁定主機 `127.0.0.1`。
此部署供本機使用；遠端主機請用 SSH tunnel 轉送到本機 localhost，現有 Host／Origin 保護不支援直接用網域或 LAN IP 存取。
例如 `ssh -L 8765:127.0.0.1:8765 user@server`，再開啟 localhost 網址。
不要直接公開容器的連接埠。自訂主機連接埠可設定 `OPENSPRITE_PORT`，例如 PowerShell：

```powershell
$env:OPENSPRITE_PORT = '18765'
docker compose up -d --build --wait
```

映像包含建置完成的前端及鎖定版本的 Python 相依套件，沿用既有同源服務。
容器以 UID/GID `10001` 執行，僅一個 Uvicorn worker，不使用 reload。
`opensprite-data` named volume 掛載到容器使用者的 `/home/opensprite/.opensprite`，所有設定、加密憑證、資料庫及工作區都位於其中。
它與主機桌面安裝的 `.opensprite` 分開；不要讓多個容器或桌面服務同時寫入相同資料。
容器中的 `localhost` 與檔案路徑都是容器環境；原生主機資料夾選擇器不可用。需連線主機 Provider 時，在 Docker Desktop 可使用 `host.docker.internal`，並確認該 Provider 的監聽及防火牆設定。
正式映像提供 Python runtime 與文字 Agent 核心。

停止並保留資料：`docker compose down`。查看狀態與日誌：`docker compose ps`、`docker compose logs --tail 100`。
**不要使用 `docker compose down -v`**，它會永久刪除資料 volume。
備份時先停止容器，備份整個 volume；還原時保留 UID/GID 與權限，並一起處理 `auth.json` 和 `config/credential.key`。
整份 volume 含敏感資料，備份也須保護。

### 安裝執行插件

在「設定 → 執行方式」匯入已審查的純 Python wheel，下載部署包，在 Docker 主機依包內 README 建置並重新啟動既有 Compose project，再回頁面核對安裝狀態，選取 Loop／策略並套用至新任務。匯入只做靜態檢查與快取，不會在後端程序安裝或執行套件。

此 repository 的 Compose 明確使用 `opensprite:local` 作為部署包的預設基底。若使用其他映像標籤，啟動服務前設定 `OPENSPRITE_DEPLOYMENT_BASE_IMAGE` 為已建置、可用的實際映像；直接 `docker run` 也需傳入此環境變數。未設定合法基底时，匯入與清單仍可用，但部署包下載會停用。請沿用既有 project 名稱與資料 volume。

插件是受信任 Python 程式碼，靜態檢查與安裝內容核對不提供安全沙箱。作者介面、測試、套件格式、Docker／本機安裝與回復方法見 [執行插件作者指南](docs/architecture/execution-plugin-authoring.md)；可建置範例位於 [examples/execution-plugin](examples/execution-plugin/README.md)，頁面也提供完整專案 ZIP。

### Docker 驗證

```powershell
docker build --target frontend-test -t opensprite:frontend-test .
docker build --target backend-test -t opensprite:backend-test .
./scripts/test-docker.ps1
```

測試 target 執行現有前後端檢查，不會進入正式 runtime 映像。
smoke test 使用獨立 Compose project／volume 及預設連接埠 `18765`，驗證健康檢查、前端資產、API、Origin 保護、非 root 帳號及重建後的資料保留。
完成後停止測試容器並保留測試資料 volume，終端機會列出名稱；正式部署與其他服務不受影響。

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
此入口執行官方 `main` 最新原始碼，請只在信任此來源時使用。
安裝完成後可透過 `http://localhost:8765/` 使用。

完整參數與失敗處理見 [Windows 安裝說明](installers/windows/README.md)。

## 解除安裝（Uninstall）

安裝時已附帶解除安裝腳本，不需要重新下載或 clone 專案。請使用原本安裝 OpenSprite 的帳號執行。
預設只停止 OpenSprite、移除自動啟動設定與程式檔案，保留個人資料；Git、Node.js 與 uv 不會一起移除。

### Windows

在任意目錄開啟 PowerShell，貼上：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\OpenSprite\app\installers\windows\uninstall.ps1"
```

依畫面提示確認後，移除 `%LOCALAPPDATA%\OpenSprite\app` 與目前帳號的自動啟動項目。
對話、設定及供應商金鑰等資料保留在 `%USERPROFILE%\.opensprite`，重新安裝後可繼續使用。

若要在解除安裝時**一併永久刪除所有個人資料**，請改用以下指令並確認提示；刪除後無法復原：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\OpenSprite\app\installers\windows\uninstall.ps1" -RemoveUserData
```

### Linux

在終端機執行，**不要使用 `sudo`**：

```bash
bash "${XDG_DATA_HOME:-$HOME/.local/share}/opensprite/app/installers/linux/uninstall.sh"
```

解除安裝會停止並移除目前帳號的 `opensprite.service`，刪除程式目錄，保留 `~/.opensprite`。
若安裝時設定過 `XDG_DATA_HOME` 或 `XDG_CONFIG_HOME`，解除安裝時請使用相同設定。

若要在解除安裝時**一併永久刪除所有個人資料**，請改用以下指令，並在提示時輸入 `DELETE`；刪除後無法復原：

```bash
bash "${XDG_DATA_HOME:-$HOME/.local/share}/opensprite/app/installers/linux/uninstall.sh" --remove-user-data
```

更多平台說明見 [Windows 安裝說明](installers/windows/README.md)及 [Linux 安裝說明](installers/linux/README.md)。

### 安裝與解除安裝完成摘要

安裝完成時，終端機會列出程式、個人資料及自動啟動設定的實際位置。
Windows 一行安裝也會顯示已清理的下載暫存路徑；無法清理時會顯示保留位置。

| 項目 | Windows | Linux |
| --- | --- | --- |
| 程式、前端及 Python 執行環境 | `%LOCALAPPDATA%\OpenSprite\app` | `${XDG_DATA_HOME:-$HOME/.local/share}/opensprite/app` |
| 個人資料根目錄 | `%USERPROFILE%\.opensprite` | `~/.opensprite` |
| 自動啟動設定 | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 的 `OpenSprite` 項目 | `${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/opensprite.service` |

個人資料都放在 `.opensprite` 之下，各項用途如下；只有實際使用功能時才會建立對應檔案或目錄：

| 相對位置 | 內容 |
| --- | --- |
| `config/` | AI、供應商、工作區等設定、本機存取設定與加密金鑰 |
| `auth.json` ＋ `config/credential.key` | 加密的供應商憑證及解密金鑰；備份、搬移或刪除時必須一起處理 |
| `data/opensprite.db` | 對話、執行、語意事件與摘要 |
| `workspace/` | OpenSprite 管理的工作區及其檔案 |
| `logs/`、`state/`、`cache/` | 日誌、執行狀態及快取 |

解除安裝最後會依實際狀態列出程式、自動啟動設定及個人資料的位置：

- `Removed`：本次已刪除。
- `Retained`：仍保留，例如預設保留個人資料，或未確認移除。
- `Already absent`：執行前就不存在，沒有算成本次刪除。

預設解除安裝會移除程式與自動啟動設定，保留整個 `.opensprite`。
選擇刪除個人資料並確認後，上表中的設定、憑證、對話、受管理工作區檔案與日誌等都會一起移除。
若途中失敗，摘要會顯示目前仍存在的項目並提示未完成；仍存在的目錄可能已有部分內容被刪除。
Windows 的 `-WhatIf` 會標示僅預覽。

Git、Node.js、uv、工具共用快取、另外下載或 clone 的原始碼，以及外部掛載的工作區資料夾，都不會由解除安裝器移除。

## 乾淨 Agent 核心

`0.21.31` 保留聊天、Provider、加密憑證、工作區中繼資料、上下文管理、取消、歷史診斷，以及可替換的 Agent Loop／執行策略。
Tools、工具核准、Skills、Subagents、自訂 Agent 定義、MCP 和排程的執行模組、路由、前端與專用相依套件已移除。文字核心不會讀寫工作區檔案或呼叫外部工具。

執行插件使用 **Host API v2**，只有 `checkpoint`、`next_turn`、`finish`。
舊 API v1 插件顯示不相容，不會載入或部署；作者須更新 entry point 群組、factory 及行為後重新建置 wheel。
完整邊界與資料處理見 [乾淨核心設計](docs/architecture/clean-agent-core.md)及 [插件作者指南](docs/architecture/execution-plugin-authoring.md)。

此版可讀取 `0.21.30` 的 SQLite v20 資料並升至 v21。既有舊表、檔案與加密資料保留，不執行已移除的功能；歷史介面只呈現目前支持的核心事件。早於 v20 的資料須先使用 `0.21.30` 完成升級。不要以舊版程式直接讀取新版資料；回復時使用升級前完整備份。

## 自訂 OpenAI-compatible 供應商

在「設定 → AI 模型」新增供應商，填寫 Base URL、認證模式與金鑰；金鑰只以 AES-256-GCM 密文保存。
Base URL 例如 `https://example.com/v1`，不含 `/chat/completions`。
探索使用 `<Base URL>/models`，文字推論使用 `<Base URL>/chat/completions`；不支援探索的服務可手動新增模型 ID、名稱及 Context／輸出上限。
內建 OpenAI 使用 Responses API，Anthropic 使用 Messages API，OpenRouter 使用 Chat Completions。

公開端點須使用 HTTPS；本機／私人網路 HTTP 需明確允許。禁止任意 Header、TLS bypass 或自動跟隨重新導向。
執行中的 Provider 與模型能力固定為接受任務時的快照，使用期間不可修改；刪除被 AI 模型設定引用的項目前須先更換選擇。
探索成功不代表推論一定相容。詳細設計見 [自訂 Provider](docs/architecture/custom-providers.md)。

## 工作區

Workspace 是對話的執行範圍。Windows 使用 `%USERPROFILE%\.opensprite\workspace`，Linux 使用 `~/.opensprite/workspace`；固定的預設工作區位於 `workspace/default`。
設定可建立 managed root、明確匯入既有第一層目錄，或管理最多 20 個外部掛載與權限。
移除工作區只移除登記，保留檔案；有對話或活躍執行時拒絕移除。

Conversation 依工作區分頁，每個 Run 保留一次不可變的 Workspace 快照。SQLite 保存 ID、revision、名稱及路徑 hash，不保存完整路徑。
System Prompt 將路徑當成不可信的中繼資料；核心不據此取得檔案存取能力。
掛載仍拒絕系統根目錄、家目錄、`.opensprite`、安裝目錄與 symlink／reparse 路徑。完整規則見 [工作區設計](docs/architecture/workspaces.md)。

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
- 重設存取只替換登入 policy、密碼/bootstrap 與記憶體 Session，不刪除 Conversation、SQLite、AI 設定、Provider 金鑰或 Log。
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
