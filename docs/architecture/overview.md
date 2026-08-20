# OpenSprite architecture

## 目標

新架構先建立清楚、淺層且可從根目錄辨識的邊界。前端先完成使用流程，後端再依實際契約補上最小能力。

```text
Frontend -> Contracts <- Backend
                 ^
                 |
             Installers
```

## 邊界

- Frontend 只透過明確契約與未來後端溝通，不讀取 Python implementation。
- Backend 不依賴 frontend source；它只實作已批准的契約與服務能力。
- Contracts 不包含 UI、資料庫或 provider implementation。
- Installers 只處理部署與 lifecycle，不承擔產品行為。
- Scripts 只承擔可重現的 repository 驗證與維護工作。

## 目前階段

Frontend 已有可執行的 fake-data demo。本階段已建立 provider connection HTTP 契約、最小
FastAPI service foundation、作業系統 credential-store boundary、固定的 OpenAI/Anthropic
validation adapters，以及負責 rollback 的 provider connection service。`create_provider_runtime()`
是未來 server launch 可注入 `create_app()` 的 system composition；在 launch wiring 尚未批准前，
未注入 dependency 的 routes 仍以 `credential_store_unavailable` fail closed。`GET /healthz` 只代表
HTTP process liveness，不代表 credential store 或上游 provider 可用。

## Provider connection 邊界

`contracts/provider-connections.openapi.json` 是唯一 authoritative contract。主要 consumer
是 OpenSprite desktop frontend 的模型廠家設定頁；次要 consumer 是本機診斷工具與 contract
tests。Backend 擁有 HTTP provider implementation，未來的 credential-store 與 provider
adapter 只能透過已定義的 `ProviderConnections` seam 接入，不得改寫 consumer-visible schema。

第一版固定支援 `openai` 與 `anthropic`，每個 provider 最多一份 credential：

| Operation | Observable behavior |
| --- | --- |
| `GET /api/providers` | 固定順序回傳兩筆完整 public summary；全部成功或固定錯誤，不做 partial success。 |
| `PUT /api/providers/{provider_id}/connection` | 先在 30 秒 deadline 內驗證候選 key，再原子替換；失敗保留既有 credential 與 summary。 |
| `POST /api/providers/{provider_id}/connection/test` | 不接受 body，只測試已儲存 credential；失敗會更新該連線的最後檢查狀態，但不刪除 credential。 |
| `DELETE /api/providers/{provider_id}/connection` | 刪除 credential 與檢查 metadata；對已斷線的 supported provider 仍回 `204`。 |

`connected` 只表示安全 store 中存在 credential。`status` 表示最後可觀察狀態，因此測試
失敗時允許 `connected=true` 且 status 為失敗原因。`credentialPreview` 是不可解析的顯示提示，
可為 null；`lastCheckedAt` 是 UTC RFC 3339 timestamp 或 null。Raw secret、filesystem path、
credential-store identifier、上游 response body 與 internal config path 永不屬於公開 model。
Internal credential fingerprint 也不屬於公開 model。

同一 provider 的 replace、test、delete 必須序列化；不同 provider 可獨立處理。不提供 ETag、
`If-Match` 或 idempotency key。每次 PUT 都必須重新驗證傳入 credential，即使內容與已儲存值
相同；成功時更新 `lastCheckedAt`，因此不承諾 repeated PUT 有完全相同的 observable result。
DELETE 維持 idempotent；catalog 固定且極小，因此沒有 pagination、filtering 或 sorting query。

## 信任、安全與可用性

- API 是單使用者、低流量、interactive 的 local desktop boundary，沒有已承諾的正式 SLO。
- Transport 必須只綁定 loopback。Provider routes 上線前，runtime/installer 必須拒絕非
  loopback Host 與 cross-origin browser mutation；初版不開 CORS。
- OpenAPI 明確宣告沒有 application-layer authentication；這依賴 loopback 與 same-origin
  deployment control，若未來要放寬 network scope，必須先以 versioned migration 加入 auth。
- `apiKey` 是 write-only secret，長度上限 4096，whitespace-only 無效。Validation error 使用
  固定訊息，不回傳 Pydantic detail 或輸入值。
- Error envelope 固定為 `error.code/message/retryable`。Status mapping、retryability 與公開訊息
  都由 contract 定義；provider response 與 exception detail 不得透出。
- 不提供 plaintext credential fallback。Credential store 不可用時必須回 `503`，不能降級儲存。
- Credential store 固定使用 service namespace `OpenSprite`，並以
  `provider.openai.api-key`、`provider.anthropic.api-key` 作為不可由 caller 指定的 credential
  name。Windows 僅接受 keyring 的 `WinVaultKeyring`（Windows Credential Manager），Linux 僅
  接受 `SecretService.Keyring`（Secret Service）。keyring 25.7.0 已依 platform 宣告 Windows 的
  `pywin32-ctypes` 與 Linux 的 `SecretStorage`/`jeepney`；不另設 file fallback。
- Backend preflight 只檢查 platform、backend identity 與 backend priority，不以測試寫入探測
  可用性。Fake-backed unit tests 驗證 adapter selection policy，但不構成 Windows 或 Linux OS
  integration 成功證明；installer/runtime 階段仍須在各目標 OS 做 read-only preflight 與人工驗證。
- PUT 與 test 的 provider deadline 是 30 秒；client retry 必須 bounded backoff。Draft v1
  不加 application rate limit，上游 rate limit 以固定 `provider_rate_limited` 錯誤呈現。
- OpenAI 只以 `GET https://api.openai.com/v1/models` 驗證 Bearer credential；Anthropic 只以
  `GET https://api.anthropic.com/v1/models?limit=1` 驗證 `x-api-key`，並固定送出
  `anthropic-version: 2023-06-01`。HTTP client 使用預設 TLS 驗證、禁止 redirect、固定 30 秒
  timeout；成功 body 上限 1 MiB，且必須是含 `data` list 的 JSON object，但 model list 不落盤。
- Provider metadata 使用 `platformdirs` 決定本機 application-data 位置並以 atomic replace 寫入
  strict schema-v2 JSON；保存 provider id、status、display-only preview、UTC last-check time 與
  internal full SHA-256 credential fingerprint。GET 以完整 fingerprint 綁定 metadata 與 secure-store
  credential，不以 preview 判斷 identity；fingerprint 永不進入 public model。schema v1 直接拒絕，
  不做 migration、legacy lookup 或 plaintext fallback。
- 同 provider 的 PUT/test/DELETE 由 process-local async lock 序列化；此設計假設單一 desktop
  backend process 擁有 runtime。secret/state partial failure 會嘗試還原並重讀前一 snapshot；無法
  證明 rollback 時永不回 success，只回固定 `credential_store_unavailable`。
- POST test 是 state-only transaction：只讀 secure-store credential，永不呼叫 credential
  set/delete；metadata 寫入失敗時只還原 prior state，再重讀 credential 證明未變。

## 相容與演進

這是 new-install-only 的 draft v1，沒有舊 client 或資料 migration。第一個 consumer 發布後，
預設只允許 additive evolution。刪除或重新命名 operation/field、改變 nullability、縮窄 enum、
更換 identifier、加入更嚴格 validation、改變 auth/idempotency/concurrency/error semantics，均視為
breaking change，必須建立明確的新版本與 consumer migration。固定 catalog 不建立額外的 URL
version compatibility layer；真正需要 breaking change 時才設計新 boundary。

本契約不定義 event、webhook 或 WebSocket，因此沒有 delivery、ordering、duplicate、retry、
signature 或 replay 保證。未來若加入，必須以獨立 message contract 明確定義。

## 決策與後續 handoff

已拒絕：plaintext fallback、先存後驗證、test request 攜帶 secret、動態 provider registry、
過早加入 pagination/version alias，以及從 archived implementation 整批搬移。

本切片已決定最小 validation request、per-provider serialization、non-secret metadata 與 runtime
composition。尚未決定且不屬於本切片：server launch wiring、runtime Host/Origin enforcement 以及
packaging/installer binding。其中 loopback binding、Host validation 與 same-origin mutation
enforcement 仍是 provider routes 上線前的 release-blocking requirement。Frontend implementer
只消費 contract 中的 public model，不推測 store 或 provider internals。

## 長期限制

- 不建立應用程式 CLI。
- 不恢復關鍵字任務分類或舊 Task lifecycle。
- 不用相容 alias、停用開關或死碼保留舊架構。
- 不在需求出現前預建抽象層、registry 或跨功能 shared service。
- 舊版存檔只能作為行為參考，所有新程式必須依目前需求重新建立。
