# OpenSprite

OpenSprite 是一個本機優先的個人 AI assistant gateway。它提供 Python CLI / service runtime、Web chat 介面、Telegram channel、SQLite storage/search、排程、MCP tools、記憶整理與 trace 檢視能力。

目前 Web UI 已改為 React + Vite + TypeScript + Ant Design，前端原始碼位於 `frontend`。

## 功能

- 本機 gateway：以前景或背景服務方式執行。
- Web chat：瀏覽器聊天、設定、Trace、run history 與測試檢視。
- LLM provider 管理：可在 Web 設定頁連接 provider、選模型與設定 credential。
- Channel：內建 Web channel，並支援 Telegram bot channel。
- 記憶與歷史：SQLite storage/search、recent summary、long-term memory、run traces。
- 工具與排程：MCP servers、內建工具、cron-style scheduled jobs。
- 跨平台安裝：Linux shell installer、Windows PowerShell/CMD installer，也可手動開發安裝。

## 需求

- Python 3.12+
- Git
- Node.js 20.19+ 或 22.12+，含 npm。Web UI build 需要。
- 至少一個 LLM provider API key 或 OAuth provider。
- Telegram bot token 只有在使用 Telegram channel 時需要。

## 快速安裝

### Linux

```bash
curl -fsSL https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/install.sh | bash
```

只安裝不啟動 gateway：

```bash
curl -fsSL https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/install.sh | bash -s -- --no-start
```

安裝位置：

```text
~/.local/share/opensprite/opensprite   # code checkout + .venv
~/.local/bin/opensprite                # command symlink
~/.opensprite                          # config, data, logs, memory
```

### Windows

```powershell
powershell -ExecutionPolicy ByPass -NoProfile -Command "iex (irm https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/install.ps1)"
```

只安裝不啟動 gateway：

```powershell
powershell -ExecutionPolicy ByPass -NoProfile -Command '$script = irm https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/install.ps1; & ([scriptblock]::Create($script)) -NoStart'
```

也可以從 `cmd.exe` 安裝：

```cmd
curl -fsSL https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/install.cmd -o install.cmd && install.cmd && del install.cmd
```

安裝位置：

```text
%LOCALAPPDATA%\OpenSprite\opensprite                 # code checkout + .venv
%LOCALAPPDATA%\Microsoft\WindowsApps\opensprite.cmd # command shim
%USERPROFILE%\.opensprite                            # config, data, logs, memory
```

Windows 若缺少基本工具，可先安裝：

```powershell
winget install Git.Git
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
```

## 手動開發安裝

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

若要測 optional vector search backend：

```bash
python -m pip install -e ".[dev,vector]"
```

## 常用命令

```bash
opensprite --version
opensprite status
opensprite gateway              # foreground gateway
opensprite service start        # background gateway
opensprite service status
opensprite service stop
opensprite update
opensprite update --check
opensprite update --restart
opensprite config validate
opensprite config validate --json
```

`opensprite gateway` 會以前景模式執行。要背景常駐請使用 `opensprite service start`。

Web gateway 啟動後，預設可從本機瀏覽器開啟：

```text
http://127.0.0.1:8765/
```

## 設定

第一次啟動會在 `~/.opensprite` 建立設定與資料檔。主要設定檔包含：

```text
~/.opensprite/opensprite.json
~/.opensprite/llm.providers.json
~/.opensprite/channels.json
~/.opensprite/search.json
~/.opensprite/media.json
~/.opensprite/messages.json
~/.opensprite/mcp_servers.json
```

Channel 設定來源是 `channels.json` 的 `instances`。`web` 是內建 channel；Telegram 需要在設定中加入 bot token。

如果 gateway 需要 proxy，可以在 `~/.opensprite/opensprite.json` 設定：

```json
{
  "network": {
    "http_proxy": "http://proxy-host:port",
    "https_proxy": "http://proxy-host:port",
    "no_proxy": "127.0.0.1,localhost"
  }
}
```

修改設定後重新啟動 gateway：

```bash
opensprite service restart
```

## Credential Vault

OpenSprite 會把 LLM provider API key 存在本機 credential vault，而不是直接提交到 repository。Credential 狀態可透過 Web 設定頁或 CLI 查詢：

```bash
opensprite auth status
opensprite auth credentials list openrouter
```

Web UI 的 Provider 設定頁可連接 provider、管理 credential、選擇 text/media model。Runtime trace 和 tool result 只應顯示 redacted preview，不應輸出完整 secret。

## 搜尋與排程

檢查聊天歷史搜尋狀態：

```bash
opensprite search status
```

Cron jobs 需要 gateway 執行時才會觸發。CLI 可檢視或移除 session 綁定的 job：

```bash
opensprite cron list --session telegram:<chat_id>
opensprite cron remove --session telegram:<chat_id> --job-id <job_id>
```

Web UI 的排程設定頁也可以建立、暫停、啟用、立即執行或移除排程。

## Web UI 開發

前端在 `frontend`，使用 React + Vite + TypeScript + Ant Design。

```bash
cd frontend
npm ci
npm run dev
```

Vite dev server 綁定 `127.0.0.1`，並將 `/api`、`/ws`、`/healthz` proxy 到 gateway `127.0.0.1:8765`。通常需要先啟動 gateway：

```bash
opensprite gateway
```

前端驗證：

```bash
cd frontend
npm run test:smoke
npm run build
```

`npm run test:smoke` 是零依賴 UI contract 檢查，不等同完整瀏覽器或 component 測試。

## 專案結構

```text
src/opensprite/
  cli/              # Typer CLI
  agent/            # Agent loop and direct tool execution
  channels/         # Web and Telegram channel wiring
  config/           # Config schema and templates
  context/          # Memory, history, and prompt context assembly
  cron/             # Scheduled jobs
  llms/             # LLM providers
  media/            # Media routing
  search/           # SQLite search and embeddings
  storage/          # Storage backends
  tools/            # Built-in tools and MCP integration
  runtime.py        # Gateway wiring

frontend/
  src/App.tsx       # React + Ant Design shell
  src/composables/  # Shared Web client state and normalization helpers
  scripts/smoke.mjs # UI contract smoke checks
```

## 測試

Python baseline：

```bash
python -m pytest
```

Focused test example：

```bash
python -m pytest tests/channels/test_web.py::test_web_adapter_roundtrip
```

Frontend baseline：

```bash
cd frontend
npm run test:smoke
npm run build
```

目前沒有 repo-configured lint/typecheck/pre-commit/CI workflow；Python 基線是 `python -m pytest`，前端基線是 smoke + build。

## 更新

```bash
opensprite update
```

更新流程會：

- `git fetch origin`
- fast-forward 到 `origin/main`
- 視需要更新 Python package/dependencies
- build Web frontend
- 保留 `~/.opensprite` 使用者資料

如果本機 checkout 有未提交變更，`opensprite update` 會停止，避免覆蓋工作區。

重新啟動背景 gateway：

```bash
opensprite update --restart
```

## 解除安裝

Linux 解除 command 與 code，保留 `~/.opensprite`：

```bash
curl -fsSL https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/uninstall.sh | bash
```

Linux 完整移除 code、config、data、logs、memory：

```bash
curl -fsSL https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/uninstall.sh | bash -s -- --full --yes
```

Windows 解除 command 與 code，保留 `%USERPROFILE%\.opensprite`：

```powershell
powershell -ExecutionPolicy ByPass -NoProfile -Command "iex (irm https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/uninstall.ps1)"
```

Windows 完整移除 code、config、data、logs、memory：

```powershell
powershell -ExecutionPolicy ByPass -NoProfile -Command '$script = irm https://raw.githubusercontent.com/HsinPu/OpenSprite/main/scripts/uninstall.ps1; & ([scriptblock]::Create($script)) -Full -Yes'
```

## License

MIT
