# 乾淨 Agent 核心（0.21.33）

## 目前範圍

核心保留「接受文字任務 → 固定執行設定 → 模型推論 → 保存文字與事件 → 完成／失敗／取消」。
聊天、Provider、加密憑證、工作區中繼資料、上下文預算／摘要、輸出續寫、語意事件與診斷仍是正式流程。
Tools／核准、Skills、自訂 Agent／Subagent／delegation、MCP 與排程已從程式組裝、Python 套件、HTTP 契約、前端及專用相依套件移除。
沒有隱藏總開關、相容端點或內建自動回復這些功能的機制。

## 可替換的部分

執行插件仍以受信任 Python wheel 的 entry point 發現。
`opensprite_backend.agent_loops.v3` 提供單一 Agent Loop factory；同一插件實例負責 execute 與兩個恢復判斷。
factory 的 `api_version` 必須為整數 `3`，每次 `create()` 回傳新實例。
Driver 只依序 await `checkpoint()`、`next_turn()`、`finish(turn)`，原樣回傳 Host 發出的結果。
Host 管理 Provider、transcript、事件、取消、預算、恢復與唯一終止交易。
模型訊息只有 system/user/assistant 文字；不接受 tool role、action definitions 或 tool finish reason。

首個文字片段立即保存並發布；後續快速片段以 4,096 字或 100 ms 的條件批次保存。
時間條件在每次收到片段時判斷，不建立額外計時執行緒；完成或取消前仍會排空已收到的片段。
短回覆不必等模型結束才出現在介面，快速串流仍避免逐片段 SQLite 交易。

API v1／v2 不提供自動相容轉接；外部插件須合併方法並重新建置。API v2 歷史執行紀錄仍可讀，舊 wheel 快取保留為需要更新。
舊安裝套件只讀 metadata 並標示不相容，選取時不載入；舊匯入快取仍可查看／移除，不能下載部署包。
後續任何擴充都需要新的明確需求、權威契約與驗證，這一版不預先建立萬用插件生命週期。

## 資料界線與升級

`.opensprite` 是唯一產品資料根目錄，完整備份仍包含 `auth.json` 與 `config/credential.key`。
此變更清除產品實作，不刪除使用者資料。
新 SQLite v21 只建立 conversations/messages/runs/run_events/conversation_compactions 五張表，不包含排程或子代理欄位。
SQLite v20 的核心結構經確認後可升至 v21；舊額外表與事件原始列保留，沒有 DROP 或重寫歷史交易。
歷史事件讀取跳過已移除事件、API v1 執行紀錄和舊 context receipts；model.started 投影移除 toolNames。
游標仍使用原始 sequence，跳過資料時繼續掃描，避免空頁導致歷史中斷。
早於 v20 的資料須先用 0.21.30 升級；無法驗證結構時拒絕啟動。

AI 設定讀取舊版時忽略 retired Provider tool policies，不改寫檔案；下次保存使用 schema v11。
Provider catalog 舊工具欄位僅在讀取投影中去除；新保存不包含這些欄位。
舊 MCP 密文只作磁碟格式驗證及原值保留；公開 credential operations 拒絕其 ID，不解密、不啟用。
工作區路徑只是模型中繼資料，沒有隱含的檔案／命令存取能力。

## 驗證要求

既有聊天／接受／冪等／取消／摘要／輸出續寫與 hostile Driver 測試維持。
新增三種原生 Provider 的文字串流及 action 回應拒絕、retired routes 404、套件不可匯入、fresh schema、v20 真實 schema fixture 保存、AI 設定與密文保留測試。
範例單元測試與實際 wheel 安裝測試分開，後者透過真實 AgentLoop、SQLite 與 Provider adapter 使用每次不同的輸入，確認動態輸出與 API v3 執行紀錄。
最後在獨立 Docker 資料根目錄驗證真 HTTP 任務、部署內容及桌面／平板／手機介面；正式服務不在此分支階段更新。
