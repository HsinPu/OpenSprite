# OpenSprite

OpenSprite 正在從乾淨的 repository 基礎重新設計。目前已建立可啟動的 React 前端與 Python 本機服務，提供真實的 Provider 連線、AI 設定、Conversation、Run、SSE 串流與 bounded Agent loop。

Windows 與 Linux 都從 repository root 使用各自的 installer。安裝後透過
`http://localhost:8765/` 使用；backend 固定只監聽 loopback，不直接提供公網模式。

## 目前狀態

- 前端：React、TypeScript、Vite、Ant Design，透過同源 `/api` 與本機服務溝通。
- 對話：Conversation、Message、Run 與安全語意事件保存於 `.opensprite/data/opensprite.db`，前端以 HTTP 與 SSE 消費。
- AI：固定支援 OpenAI、Anthropic、OpenRouter；模型、Context／輸出上限、推理模式、續接次數、回覆顯示方式與 Prompt log 偏好保存於 `.opensprite/config/settings.json`。
- 金鑰：只以 AES-256-GCM ciphertext 保存於 `.opensprite/auth.json`，每次安裝使用獨立的 `config/credential.key`。
- Agent：所有使用者訊息進入同一個 Token-budgeted Agent loop；舊對話只做可重建摘要，原始訊息不刪除。執行事件與 Context 用量可由前端即時／歷史查看；production Tool Registry 目前包含安全的唯讀計算器。
- CLI：不在新版本範圍內。
- API：Provider、AI settings 與 Agent chat HTTP/SSE 契約已實作；未使用 WebSocket。
- 存取：支援本機免密碼的 `trusted_local` 與需要 Argon2id 密碼、記憶體 Session 的 `password_required`。
- 安裝器：Windows 與 Linux current-user installer 均已實作；Linux 實機 systemd 隔離測試仍待真實 Linux 主機執行。

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
