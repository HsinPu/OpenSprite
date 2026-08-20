# 0001 - Project foundation

## Objective

從空白 `main` 建立前端優先、前後端分離且沒有應用程式碼的 repository foundation。

## Changes

- 建立 frontend、backend、contracts、installers、docs、scripts 頂層邊界。
- 加入 React、TypeScript、Vite、Ant Design 的前端依賴與設定。
- 建立 repository `AGENTS.md`、架構說明與修改紀錄規則。
- 排除本機工具狀態、依賴、build、cache、secret 與 editor 產物。

## Public impact

沒有 runtime、HTTP、WebSocket、CLI 或 installer 公開介面。Frontend 仍不可啟動或 build。

## Verification

- `npm install --package-lock-only --ignore-scripts` 成功產生 lockfile。
- `npm ci --ignore-scripts` 成功安裝 89 個 packages，audit 為 0 vulnerabilities。
- 實際版本符合規劃：React 19.2.8、React DOM 19.2.8、Ant Design 6.6.1、Vite 8.2.2、TypeScript 7.0.2。
- Frontend 與 Backend runtime source count 為 0；沒有 `.py`、`.tsx`、應用入口或 installer scripts。
- 預定骨架內沒有未追蹤目的的空目錄，舊 root `src/tests/.venv/.pytest_cache` 均不存在。
- `git diff --check` 通過，CodeGraph 已同步且狀態為最新。

## Remaining work

- 建立最小 React 應用入口與視覺基礎。
- 根據前端需求設計 contracts。
- 等待明確授權後才建立 backend。
- 實作 Linux 與 Windows installers。
