# 六個回應模式與模型支援等級

產品版本由 `0.21.17` 提升至 `0.21.18`；已同步後端套件、uv 鎖檔與 README。

## 使用者行為

- 預設模型與排程改用 `low`、`medium`、`high`、`xhigh`、`max`、`ultra` 六個值，新安裝預設為 `medium`。
- 繁體中文顯示「低、中、高、極高、最高、極致」；英文顯示「Low、Medium、High、Extra High、Max、Ultra」。同步補齊既有日文介面字串。
- 支援所選等級時直接使用；不支援時採用該模型的**最高支援等級**，並顯示原選擇與實際等級。這不是取最近的等級。
- 無等級控制的模型使用自身預設；能力未知時明確顯示未知並省略推理等級參數。保留使用者偏好，切換模型後重新判定。
- `ultra` 是產品偏好，沒有對應原生等級時套用最高支援等級；不會因此建立額外 Agent。GPT-5.6 選擇 `ultra` 時實際使用 `max`。
- 設定頁沿用 Ant Design Radio；一般桌面六欄、窄容器三欄、最窄容器兩欄。儲存沿用既有序列佇列，避免停用 Radio 導致方向鍵焦點遺失。

## 能力來源與執行

`response_modes.py` 統一偏好值、舊值轉換及決策。直接供應商沿用既有模型能力目錄；OpenRouter 從模型目錄的 `reasoning.supported_efforts` 取得能力，不以模型名稱猜測。自訂供應商未宣告此能力時視為未知。

新增唯讀 `GET /api/settings/ai/response-mode`，設定與排程使用同一個後端判定邏輯。讀取預覽不寫入偏好、不執行推論；前端取消過期請求，避免切換模型後顯示舊提示。

首次模型請求前，Run 分別保存所選模式和不可變的 `reasoningResolution`。工具回合與續接沿用該決策；子任務依自己的模型重新判定，再於該子任務內固定。OpenAI、Anthropic 與 OpenRouter adapter 使用固定後的實際參數。完整 Prompt 日誌與 request receipt 雜湊同步納入實際等級，執行詳情可顯示保存的判定。

能力依據（實作時核對官方文件）：

- [OpenAI GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) 與 [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)：`low / medium / high / xhigh / max`。
- [Anthropic effort](https://platform.claude.com/docs/en/build-with-claude/effort)：Sonnet 4.6 的 `low / medium / high / max`；Haiku 4.5 不送 effort。
- [OpenRouter reasoning](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)：區分可用清單、`null`、缺少 effort 控制與無法辨識的能力資料。

## 資料升級與契約

- AI 設定格式 `9 → 10`。舊 `default / balanced → medium`、`fast → low`、`deep → high`；讀取時轉換，不因讀取改寫檔案，之後儲存寫入第 10 版並保留供應商工具政策。
- SQLite 格式 `18 → 19`。交易內更新 Run 與排程的模式限制，保留索引並檢查外鍵；新增可空的實際等級欄位，排程舊偏好依同一規則升級。失敗回滾表格與版本。
- 歷史 Run 的模式、事件與紀錄不改寫；舊紀錄沒有實際等級時不補造資料。新設定與排程寫入只接受六個新值，歷史 API 仍可讀取舊值。
- 更新 AI settings、agent chat 與 schedules 契約和對應前端驗證。

## 驗證

- `npm ci --ignore-scripts` 通過；完整前端測試 **564 項通過（65 個檔案）**。
- 手機排版與鍵盤焦點修正後，相關前端測試 **49 項通過**；TypeScript 與正式建置通過。
- 完整後端 `pytest -W error`：**1,180 項通過、3 項跳過**。
- 補充無 effort 參數與子任務測試後，相關後端測試 **59 項通過**，涵蓋六個值、三種 adapter、最高等級回退、未知能力、唯讀預覽、舊設定、真實第 18 版表格升級、歷史事件保留、決策持久化及升級失敗回滾。
- `compileall`、`uv lock --check --offline`、`uv pip check` 與 `git diff --check` 通過；版本三處一致。
- 使用隔離暫存 `.opensprite`、模擬供應商連線與正式前端建置，實際檢查 1280×720 桌面、768×1024 平板、390×844 與 320×740 手機畫面。
- 瀏覽器確認繁中／英文、六個選項逐一儲存、重新載入保留、最高等級回退、無等級控制提示、連續方向鍵焦點，以及排程的相同六個選項。最終瀏覽器主控台沒有錯誤。

未使用真實 API 金鑰或執行付費模型請求；供應商參數以攔截的 HTTP payload 驗證。本次沒有修改安裝器，也未重新安裝現有產品或變更使用者資料。建置仍有既有大型 bundle 提醒。
