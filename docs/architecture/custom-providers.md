# 自訂 Provider 與協定分離

## 身分與協定

`0.21.0` 將 Provider 身分與推論協定分開。內建 `openai`、`anthropic`、`openrouter`
保持既有 ID、金鑰及原生 Adapter；自訂 Provider 使用 canonical UUIDv4，協定為
`openai_chat_completions`。顯示名稱不是路由鍵，同一協定可以有多個端點及獨立金鑰。

`provider_identity.py` 定義共用身分驗證。聊天、AI 設定、排程及 Agent 定義接受相同 ID；
內建連線測試端點仍只接受內建三個 ID。自訂資源契約位於
`contracts/custom-providers.openapi.json`。

## 保存與恢復

- `config/providers.json`：strict schema v1，自訂 Provider、模型及 revision，不包含金鑰。
- `auth.json`：沿用 AES-256-GCM，金鑰項目為 `provider:<UUID>:bearer`。
- `state/provider-catalog-transaction.json`：跨 catalog／金鑰更新的暫時交易紀錄。
  候選金鑰只暫存為加密 credential entry，交易紀錄不含原始金鑰。
- 所有位置由 `AppPaths` 推導。缺少 catalog 時回傳空清單，首次寫入才建立。
- SQLite v15 → v16 放寬 Provider ID 約束；不改寫既有內建 ID、對話或排程選擇。

`ProviderCatalogTransaction` 以 roll-forward 恢復中斷的 catalog／credential 更新；
`CustomProviderService` 擁有 catalog revision、Provider revision、穩定模型 key 及去重規則。
不透過 HTTP 回傳明文金鑰。備份仍須一起保存 `auth.json` 與 `config/credential.key`。

## 變更與參照邊界

`ProviderMutations` 使用共用 Workspace mutation gate，協調執行接受、設定、排程與 Agent 引用。
RunManager 記錄父任務及其可用子代理快照保留的 Provider，活躍執行期間拒絕修改。
刪除 Provider、移除模型或修改模型 ID 時，檢查 AI 設定、所有已保存排程及已登記 Agent 定義。
無法可靠讀取引用時拒絕變更，不猜測資料已不再使用；歷史 Run 不阻擋刪除，也不被刪除。

模型探索先取得端點、金鑰及 revision，再於鎖外執行網路請求；提交時重新檢查 revision、
活躍使用與被移除模型的引用。手動模型資料不被探索覆蓋。

## 執行快照

接受 Run 時解析 `ProviderEndpointSnapshot`，包含端點、協定、認證模式、revision 與模型能力 tuple。
同一快照傳入 RunManager、Agent loop、Context 準備、摘要壓縮及輸出續接。
子代理使用父任務接受時保留的端點快照；排程依自己的 Provider／模型設定建立新 Run。
未知或不可用模型不會靜默回退至內建服務。

`NativeModelGateway` 依快照的協定選擇 Adapter，而不是用顯示名稱推測。
通用 Chat Completions Adapter 不附加 OpenRouter 專屬擴充；內建 OpenRouter 保留原本行為。
金鑰由 credential store 取得，不放進一般事件或快照的公開資料。

## HTTP 與清單

自訂 API 受現有登入／trusted-local middleware 保護。JSON mutation 拒絕未知與重複欄位，
使用有界串流讀取（64 KiB）；所有變更帶 expected revision。
Provider catalog 與模型 GET 使用 revision-bound cursor，預設 50、每頁最多 100；
未知／重複 query 拒絕，跨頁版本變動回 `revision_conflict`。
前端完成所有頁面驗證後才替換清單。新增、編輯、刪除與探索模型回應仍回傳完整結果。

公開 Base URL 必須 HTTPS；本機／私人 IP 的 HTTP 需要明確允許。
禁止 URL 內嵌帳密、query、fragment、重新導向與任意 Header／TLS bypass。
`/models` 不提供推論能力保證；手動模型能力由使用者依上游服務設定。

## 驗證界線

回歸測試涵蓋資料、交易、身分、CRUD、參照、快照及契約；測試伺服器或 MockTransport
只證明所覆蓋的協定資料形狀。未對特定真實服務驗證時，不宣稱該服務完全相容。
本功能不新增工具權限、不改變排程／子代理人工核准限制，也不自動部署本機安裝。
