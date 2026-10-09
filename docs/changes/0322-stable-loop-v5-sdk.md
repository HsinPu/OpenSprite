# 固定 v5 SDK 資料契約

- 版本：`0.21.37` → `0.21.38`。
- 唯一目標：隔離公開 SDK 與內部儲存／傳輸資料，固定已核准 v5 契約並驗證原有 wheel。
- 分支：`codex/core-runtime-hardening`。
- 日期：2026-10-09（Asia/Taipei）。

## 實作與公開影響

`agent.plugin` 保留原作者匯入路徑、factory、entry point、Host 方法、欄位順序、邏輯型別、預設值與 enum 值。公开 Message／ConversationCompaction／PublicRunError／ModelMessage 與兩個 enum 使用独立 SDK 定義，沒有儲存或供應商傳輸模組依賴。內部資料層可演進，不會把新增的儲存欄位自動暴露给 Loop。

Host 明確複製上下文、摘要、錯誤與 finish reason；完整輸入只轉換一次到傳輸 DTO，receipt 的來源綁定使用該次轉換的同一物件。Executor 在儲存前轉換公開錯誤與 completion reason。來源所有權／防修改核對與草稿私有規則保留。

`contracts/agent-loop-v5.sdk.json` 是此次重構前 v5 契約快照，測試直接比對，不隨實作自動重建期待值。作者仍只使用 `opensprite_backend.agent.plugin`，不能依賴內部 persistence／transport class 身分；新不相容契約必須另行核准新 API。官方 wheel 維持 0.2.0，範例維持 0.5.0。

作者教學及來源 ZIP 同步，ZIP 增加固定 SDK 契約（9 檔、57,758 bytes）。沒有新增執行相容轉接層或 CLI。

## 驗證

- 目前核心 Host／Loop／共享限制聚焦回歸 **88 passed**。
- 公開 SDK／上下文／摘要來源回歸 **28 passed**，包括重構前契約、所有摘要欄位、独立物件、防內部模組依賴、傳輸 DTO、來源 receipt 與公開錯誤回存。
- 未重建的範例 wheel SHA-256：`e75ed2849b131bf3c051885e6d68a290856a168b662d9a7c7df60b01b0c9b4b3`。產品 **0.21.38** 離線隔離安裝後，透過真 Host、SQLite、Native Provider adapter 完成可變 UUID 的 draft／review／final 三步與取消保存。這是協定測試，不是付費模型。
- Docker SDK 重構快照完整後端 **1029 passed**，compileall、lockfile 及 pip check 通過；最後補充的公開錯誤回存已包含於上述 28 項聚焦回歸。最終全套、安裝及實際故障／模型／瀏覽器證據接續最後階段。
