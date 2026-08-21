# Installers

這個目錄保留給未來的 Linux 與 Windows 安裝器。

兩個平台必須維持相同行為：安裝依賴、部署前後端、建立背景啟動方式、執行健康檢查，以及預設保留使用者資料的安全解除安裝。本階段不建立任何可執行腳本。

安裝器必須遵守 [`../docs/architecture/local-data-layout.md`](../docs/architecture/local-data-layout.md)：

- Windows 程式安裝於 `%LOCALAPPDATA%\OpenSprite\app`，使用者資料固定在
  `%USERPROFILE%\.opensprite`。
- Linux 程式安裝位置與使用者資料 `~/.opensprite` 分開。
- 一般解除安裝只移除程式、背景啟動與安裝器擁有的 lifecycle 資源；預設保留 `.opensprite`。
- `.opensprite/auth.json` 與 `.opensprite/config/credential.key` 必須一起備份、搬移或刪除；兩者
  同時外流即可解密 Provider API Key，因此安裝器與支援包必須把整個 `.opensprite` 視為敏感資料。
- 只有使用者明確要求且安裝器驗證絕對目標仍是該使用者的 `.opensprite` 時，才可提供資料刪除流程。
- 安裝器不得建立尚未由產品功能使用的 config、database、conversation、log 或 cache 空目錄。
- 背景啟動只能維持一個 OpenSprite backend process；不得以多 worker 或 reloader 同時寫入同一
  `.opensprite/auth.json`。
