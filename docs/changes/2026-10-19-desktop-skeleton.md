---
title: 階段 1 首個 slice：桌面骨架 v0.1.0
documentType: implementation-change
createdDate: "2026-10-19"
status: verified-pending-commit
---

# 階段 1 首個 slice：桌面骨架 v0.1.0

## 目標與版本

使用者要求開始第一階段，先交付點 OpenSprite Harness 圖示就能開啟獨立視窗的桌面骨架；確認測試後 commit／push。GitHub 儲存庫名稱保留 OpenSprite。

產品版本由「只有規劃、無可執行版本」進入 **0.1.0**；架構、資料政策與路線圖由 **v0.3 → v0.4**。這是階段 1 的首個 slice，完整階段 1 與可執行對話的 Harness 均尚未全部完成。

## 實作範圍

- Electron 44.9.0 main／preload／renderer 與受管理 utility process Host，隨包攜帶內嵌 Node.js／Chromium。
- React／React DOM 19.3.1、TypeScript 7.0.2、Fastify 5.12.7、Vite 8.3.4、Ant Design 6.6.6、Icons 6.3.4。
- npm workspace、`package-lock.json`、build／typecheck／test／desktop／package scripts；electron-builder 26.15.3。
- Windows 目前使用者的 NSIS 安裝精靈、自有圖示、桌面／開始功能表捷徑與 `release/win-unpacked/`。目前是未簽署開發測試版，不是已簽正式發行版。
- 獨立視窗、single instance 喚回、Host 啟動／關閉與失敗顯示；沒有開瀏覽器、開機自啟或預設托盤常駐流程。
- React 以私有 `/api/v1/status` 顯示 Host、provider、storage、outbound、telemetry 狀態；載入／錯誤／重試與 disabled composer 清楚說明目前能力。

目前沒有模型 adapter、Session／Run、SQLite、SSE、Outbound Broker、CredentialStore 或檔案／shell／MCP 工具。狀態 `storage: not-initialized` 指應用資料未建立；Electron desktop profile／session/cache／本機 crash dump 仍位於 `.opensprite/desktop/`。

## 本機認證與資料傳送限制

1. Host 綁 `127.0.0.1` 隨機 port，驗證 Host／Origin；一次性 bootstrap token 經 private IPC，交換 instance-bound session cookie（`HttpOnly`、`SameSite=Strict`），使用獨立記憶體 Chromium session。
2. renderer 關閉 Node integration，啟用 context isolation、sandbox、CSP 與自身 origin 請求限制。preload 只提供版本／平台，IPC 驗證 sender、主 frame 與 origin。
3. 導航、新視窗、下載與 Chromium 權限請求預設拒絕；release 不自動開 DevTools 或建立 remote-debugging 入口。
4. main bootstrap 使用顯式 `node:http` agent，設定 `proxyEnv: {}` 並限制逾時／回應大小；Chromium 為 direct proxy，Host 使用環境允許清單，不繼承代理、供應商金鑰或 `NODE_OPTIONS`。
5. 不包含 DeepSeek adapter、原產品套件、遙測、回饋／Session uploader、背景補送、crash-report sender 或更新器。

這些是目前自有程式與桌面邊界的實作，**不構成 OS／容器對全部程序的零網路強制保證**。未來模型、broker、工具與 relay 必須各自補資料流、允許清單、測試及隔離證據。

## 驗證命令與覆蓋

以下為儲存庫根目錄的重現命令；本次結果記錄於下節，命令與測試檔存在本身不代表通過。`npm ci` 是後續依鎖檔重現的入口，本次實際以 `npm install --no-audit --no-fund` 安裝並產生鎖檔，沒有執行 `npm ci`。

```powershell
npm ci
npm run typecheck
npm test
npm run test:desktop
npm run package:win
npm run dist:win
git diff --check
```

- 單元／整合：Host 認證、一次性交換、Host／Origin 拒絕、狀態 contracts、靜態資源／CSP，以及 desktop origin／環境政策與 bootstrap 連線。
- Electron 實測：真正視窗、preload 隔離、Host 狀態、外部 fetch 拒絕、重複啟動與關閉／Host 生命週期；測試使用隔離資料根。
- UI 實測：載入／失敗／重試、停用對話、裝飾性圖示的 accessible name；預設 1180 寬度與 900×680 的視窗不出現水平溢出。手機樣式已實作，但沒有手機尺寸實測。
- 靜態複查：navigation、新視窗、下載／權限請求與非主 frame IPC 的拒絕邊界；本次沒有逐項動態對抗測試，不列為 E2E 已測情境。
- 打包：`win-unpacked` 與 NSIS 產物；後續以實際啟動結果記錄已驗範圍，不以產物存在代替乾淨帳號安裝測試。

### 實際執行結果

2026-10-19 在目前 Windows 使用者環境完成：

| 驗證 | 結果 |
|---|---|
| 依賴安裝與鎖檔 | `npm install --no-audit --no-fund` 完成；`npm ci` 未執行 |
| 單元／整合測試 | 11／11 通過 |
| 正式依賴已知漏洞檢查 | `npm audit --omit=dev`：0 個已通報漏洞；不等於完整供應鏈安全保證 |
| TypeScript typecheck／build | 通過 |
| Electron E2E：開發 build | 3／3 通過 |
| Electron E2E：`release/win-unpacked` | 3／3 通過 |
| Electron E2E：NSIS 安裝後程式 | 3／3 通過 |
| Windows 打包 | `win-unpacked` 與 NSIS 安裝包均成功產生 |
| 目前使用者實際安裝 | 成功安裝至 `C:\Users\win10\AppData\Local\Programs\OpenSprite Harness` |
| 桌面／開始功能表捷徑 | `.lnk` 均存在；實際由桌面捷徑啟動獨立視窗，正常關閉 |
| 安裝包簽章 | `Get-AuthenticodeSignature` 回報 `NotSigned`，明確標示為開發測試版 |
| 文件 | 5 份文件的本機 Markdown 連結均存在；`git diff --check` 通過 |

安裝包：`release/OpenSprite-Harness-0.1.0-Setup.exe`。

SHA-256：

```text
AA2E01905006A1611C4C12D3D16DC1954A97267B500F231E6EDA91DEDC98EBA0
```

上述安裝／捷徑／E2E 均在目前使用者環境完成，**不是乾淨 VM 或新測試帳號**；不據此宣稱乾淨帳號、升級或解除安裝生命週期已完整驗收。此紀錄於提交前完成，commit／push 結果以實際 Git 狀態為準。

## 使用方式

一般使用者雙擊 `release/OpenSprite-Harness-0.1.0-Setup.exe` 安裝，再點桌面上的 **OpenSprite Harness**。無需另外安裝 Node.js、npm 或使用瀏覽器／終端。完整 `release/win-unpacked/` 中的 `OpenSprite Harness.exe` 亦為直接啟動入口。

開發者使用 `npm start`，會先建置再啟動 Electron。首次 `npm ci` 與打包工具下載可能需要網路，與產品執行期限制分開。

## 尚未驗收的後續範圍

- 模型推論、Session／Run、SQLite、事件／恢復、SSE、Outbound Broker 與受控工具。
- 乾淨 Windows 測試帳號的完整安裝、重裝／升級與解除安裝資料保留流程；本次已驗目前使用者實際安裝，尚未驗此完整門檻。
- Linux 安裝與生命週期、簽署發行、OS／容器隔離及全程序網路觀測。

沒有以這個 slice 宣稱完整階段 1、安全驗收矩陣或第一個可用 Harness 已完成。
