# Agent workbench redesign

## Objective

在獨立分支重新整理 Agent 工作臺的布局、排版與色彩，保留既有功能。
產品版本：`0.21.23` → `0.21.24`。

## Changes

- 以冷灰表面、石墨色文字與青綠主色統一 Ant Design 主題及既有 CSS tokens，縮小控制項與圓角。
- 左側分開工作區資源與對話紀錄，AI 模型、Agents、Skills 快捷入口連到既有設定頁。
- 新對話區呈現工作目標說明及實際工作區／模型資訊；輸入區增加標頭與依現有傳送設定顯示的鍵盤提示。
- 桌面執行面板按鈕增加文字標籤，保留可調寬度、收合與手機抽屜。
- 調整對話泡泡、回應區、執行資訊與設定頁間距；一般設定模組採用平面分隔結構。
- 三種語言同步更新工作臺文案；HTTP 契約、Provider 憑證、對話執行、工具核准及持久化邏輯沿用原實作。

## Verification

- 使用獨立 Compose project `opensprite-workbench`、映像 `opensprite:workbench-preview` 與專屬資料卷，預覽網址為 `http://localhost:18766/`。
- Production build 與 TypeScript 編譯通過。
- `docker build --target frontend-test -t opensprite:workbench-frontend-test .` 通過：65 個測試檔案、565 項測試及 `npm run typecheck`。
- 後端建置環境中 `uv lock --check --offline`、`uv pip check` 通過。
- Chrome 實際檢查 1440 × 900 桌面、768 × 1024 平板與 390 × 844 手機；手機及平板沒有水平溢出。
- 檢查模型／Agents 資源入口、返回對話、手機導覽、執行抽屜與桌面面板開關；草稿在開關面板、設定及尺寸變化後保留。
- 首次完整測試指出新增標籤誤用設定模型，已改用既有 `displayedModelName`，保留目前 Run 模型顯示契約；完整重跑通過。
- 左側 resize separator 以 ArrowRight 從 248 調整為 258，Home 還原為 248。
- `/healthz` 回應正常，`/api/app-info` 確認版本 `0.21.24`；Chrome 沒有應用程式 error（擴充套件另有 warning）。
- 預覽未設定 Provider 憑證，沒有向外部模型送出訊息；執行與工具行為由既有前端回歸測試驗證。
- Vite 保留既有 chunk-size 提示；測試環境保留 React act 與 jsdom pseudo-element 提示，未放寬斷言。
