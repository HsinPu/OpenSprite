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
FastAPI service foundation、跨平台本機加密 credential-store boundary、固定的 OpenAI／Anthropic／OpenRouter
validation adapters、負責 rollback 的 provider connection service，以及安全的本機 system
runtime。匯入或呼叫 `create_system_app()` 本身維持離線；每次 FastAPI lifespan entry 才以
`create_provider_runtime()` 建立並綁定全新的 dependency，teardown 先解除綁定再精確關閉該次
entry 擁有的 HTTP client。startup/close 失敗後維持 fail closed，下一次 entry 重新建立 runtime；
concurrent lifespan entry 在 serving 前直接拒絕。一般 `create_app()` 未注入 dependency 時仍以
`credential_store_unavailable` fail closed，方便 contract test 與明確 composition。`GET /healthz`
只代表 HTTP process liveness，不代表 credential store 或上游 provider 可用。

## Provider connection 邊界

`contracts/provider-connections.openapi.json` 是唯一 authoritative contract。主要 consumer
是 OpenSprite desktop frontend 的模型廠家設定頁；次要 consumer 是本機診斷工具與 contract
tests。Backend 擁有 HTTP provider implementation，未來的 credential-store 與 provider
adapter 只能透過已定義的 `ProviderConnections` seam 接入，不得改寫 consumer-visible schema。

第一版固定支援 `openai`、`anthropic` 與 `openrouter`，每個 provider 最多一份 credential：

| Operation | Observable behavior |
| --- | --- |
| `GET /api/providers` | 依 OpenAI、Anthropic、OpenRouter 固定順序回傳三筆完整 public summary；全部成功或固定錯誤，不做 partial success。 |
| `PUT /api/providers/{provider_id}/connection` | 先在 30 秒 deadline 內驗證候選 key，再原子替換；失敗保留既有 credential 與 summary。 |
| `POST /api/providers/{provider_id}/connection/test` | 不接受 body，只測試已儲存 credential；失敗會更新該連線的最後檢查狀態，但不刪除 credential。 |
| `DELETE /api/providers/{provider_id}/connection` | 刪除 credential 與檢查 metadata；對已斷線的 supported provider 仍回 `204`。 |
| `POST /api/providers/openrouter/models` | 不接受 body，使用已儲存 credential 即時讀取 OpenRouter 可用文字模型；不落盤、不快取。 |

`connected` 只表示安全 store 中存在 credential。`status` 表示最後可觀察狀態，因此測試
失敗時允許 `connected=true` 且 status 為失敗原因。`credentialPreview` 是不可解析的顯示提示，
可為 null；`lastCheckedAt` 是 UTC RFC 3339 timestamp 或 null。Raw secret、filesystem path、
credential-store identifier、上游 response body 與 internal config path 永不屬於公開 model。
Internal credential fingerprint 也不屬於公開 model。

Frontend 消費者只使用相對 `/api` 路徑。Vite dev 與 preview proxy 轉送至
`127.0.0.1:8765` 時保留 browser-facing Host 和 Origin（`changeOrigin: false`），讓本機
runtime 的 exact same-origin mutation policy 繼續生效。前端會嚴格驗證固定 catalog 的順序、
欄位、狀態與 UTC timestamp；無法驗證的回應只顯示固定安全錯誤。API key 只存在連線 modal
的短暫密碼欄位 state，絕不寫入 URL、browser storage 或顯示字串；送出、錯誤、取消或卸載時
都會清除。OpenAI 與 Anthropic 模型選項仍是前端 local catalog；OpenRouter 則在連線後即時
取得模型清單，只在同一次設定視窗工作階段重用記憶體結果。選擇值分開保存 provider id、
執行用 model id 與顯示 label，不將動態清單寫入 browser storage、URL 或 `.opensprite`。

同一 provider 的 replace、test、delete 必須序列化；不同 provider 可獨立處理。不提供 ETag、
`If-Match` 或 idempotency key。每次 PUT 都必須重新驗證傳入 credential，即使內容與已儲存值
相同；成功時更新 `lastCheckedAt`，因此不承諾 repeated PUT 有完全相同的 observable result。
DELETE 維持 idempotent；catalog 固定且極小，因此沒有 pagination、filtering 或 sorting query。

## 信任、安全與可用性

- API 是單使用者、低流量、interactive 的 local desktop boundary，沒有已承諾的正式 SLO。
- System runtime 的 uvicorn 啟動命令只綁定 `127.0.0.1`，並以 `--no-proxy-headers` 禁止
  `X-Forwarded-*` 改寫 request scheme；不建立 trusted proxy。
- Secured runtime 對所有 HTTP request 要求恰好一個 `Host`，canonical hostname 只能是
  `localhost`、`127.0.0.1` 或 `::1`。拒絕 duplicate/combined Host、userinfo、control character、
  非標準 loopback encoding、alias、非 loopback IP、錯誤 bracket 與越界 port。
- `POST`、`PUT`、`PATCH`、`DELETE` 另要求恰好一個 `Origin`，其 canonical scheme、hostname 與
  effective port 必須和 request scheme + Host 相同。拒絕 missing/null/opaque/multiple Origin、
  wildcard、userinfo、path/query/fragment、scheme/host/port mismatch；不開 CORS，也不使用
  `Referer` fallback。
- Vite development proxy 必須使用 `changeOrigin: false`，保留原始 browser-facing Host 與
  Origin；兩者連 port 都必須同源，不為任意 localhost port 放寬 equality。
- OpenAPI 明確宣告沒有 application-layer authentication；這依賴 loopback 與 same-origin
  deployment control，若未來要放寬 network scope，必須先以 versioned migration 加入 auth。
- `apiKey` 是 write-only secret，長度上限 4096，whitespace-only 無效。Validation error 使用
  固定訊息，不回傳 Pydantic detail 或輸入值。
- Error envelope 固定為 `error.code/message/retryable`。Status mapping、retryability 與公開訊息
  都由 contract 定義；provider response 與 exception detail 不得透出。
- Credential store 的唯一預設實作是 AES-256-GCM encrypted JSON。`auth.json` 與
  `config/credential.key` 都位於 `.opensprite`；每次安裝產生獨有 256-bit key，每次 secret
  寫入產生新的 12-byte nonce，並以 version、provider id 與完整 fingerprint 作為 AAD。
  Provider 清單只比較 ciphertext entry 的 fingerprint 與 metadata，不解密 API Key；test、模型
  discovery、credential replace/rollback 與未來模型執行才短暫解密。Python 無法保證 immutable
  string 的安全抹除，因此 plaintext 不快取、不記錄、不回傳且盡量縮短生命週期。
- Encrypted store 只接受 strict schema version 1 與固定三個 provider；JSON 損壞、duplicate key、
  未知欄位、ciphertext/tag/AAD 竄改、key 遺失或 I/O 失敗一律回 `503`，不得自動生成新 key
  覆蓋既有 ciphertext。Linux 使用 `0700`/`0600`，Windows 依賴使用者 Profile ACL。
- Encrypted store 的單一同步鎖只保護同一 runtime instance 內的跨 provider read-modify-write；
  deployment 必須維持一個 desktop backend process，不得使用多 Uvicorn worker、reloader 或讓
  多個 backend 共用同一 `.opensprite`。若未來批准 multi-process，必須先加入跨程序檔案鎖或
  transactional store 與對應回歸測試。
- PUT 與 test 的 provider deadline 是 30 秒；client retry 必須 bounded backoff。Draft v1
  不加 application rate limit，上游 rate limit 以固定 `provider_rate_limited` 錯誤呈現。
- OpenAI 只以 `GET https://api.openai.com/v1/models` 驗證 Bearer credential；Anthropic 只以
  `GET https://api.anthropic.com/v1/models?limit=1` 驗證 `x-api-key`，並固定送出
  `anthropic-version: 2023-06-01`；OpenRouter 只以
  `GET https://openrouter.ai/api/v1/key` 驗證 Bearer credential，不送出 attribution headers。
  HTTP client 使用預設 TLS 驗證、禁止 redirect、固定 30 秒 timeout；成功 body 上限 1 MiB。
  OpenAI／Anthropic 必須回傳含 `data` list 的 JSON object，OpenRouter 必須回傳含 `data` object
  的 JSON object；所有上游內容均不落盤。
- OpenRouter 模型清單只透過 bodyless `POST /api/providers/openrouter/models` 觸發，並與該
  provider 的 PUT/test/DELETE 共用 process-local lock。Backend 使用已儲存 Bearer credential
  呼叫 `GET https://openrouter.ai/api/v1/models/user`，成功 body 上限 4 MiB，只保留同時支援
  text input/output 的有效項目，依 id 去重、依 name 再 id 排序，最多回傳 1000 筆。請求不改寫
  credential、metadata 或其他 `.opensprite` 路徑；上游回應與模型清單均不落盤。
- 本機資料位置由 [`local-data-layout.md`](local-data-layout.md) 的 `AppPaths` 單一管理；建立路徑
  mapping、匯入 backend、啟動 system app 與讀取不存在的狀態都不建立任何目錄。Provider metadata
  只在實際寫入時建立 `%USERPROFILE%\.opensprite\state\providers.json`（Linux 為
  `~/.opensprite/state/providers.json`），並以 atomic replace 寫入 strict schema-v2 JSON；保存
  provider id、status、display-only preview、UTC last-check time 與
  internal full SHA-256 credential fingerprint。GET 以完整 fingerprint 綁定 metadata 與 secure-store
  credential，不以 preview 判斷 identity；fingerprint 永不進入 public model。schema v1 直接拒絕，
  不做 migration、legacy lookup 或 plaintext fallback。
- 同 provider 的 PUT/test/DELETE 由 process-local async lock 序列化；此設計假設單一 desktop
  backend process 擁有 runtime。secret/state partial failure 會嘗試還原並重讀前一 snapshot；無法
  證明 rollback 時永不回 success，只回固定 `credential_store_unavailable`。
- System app 在 lifespan 外、startup failure 與 teardown 開始後都綁定
  `UnavailableProviderConnections`。每個 lifespan entry 各自建立/關閉 runtime；close 失敗先解除
  綁定再向上傳遞，且不阻止後續 fresh entry。non-blocking lifecycle guard 拒絕 concurrent entry，
  避免 closed client 被重新提供服務。
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

已拒絕：固定全域加密金鑰、plaintext fallback、先存後驗證、test request 攜帶 secret、動態 provider registry、
過早加入 pagination/version alias，以及從 archived implementation 整批搬移。

本切片已決定最小 validation request、per-provider serialization、non-secret metadata、runtime
composition、loopback Host validation 與 same-origin mutation enforcement。System app 透過
documented uvicorn factory command 啟動，不建立 project CLI。尚未決定且不屬於本切片的是
packaging/installer lifecycle。Frontend implementer 只消費 contract 中的 public model；Vite
proxy 必須保留同源 Host/Origin，不推測 store 或 provider internals。

## 長期限制

- 不建立應用程式 CLI。
- 不恢復關鍵字任務分類或舊 Task lifecycle。
- 不用相容 alias、停用開關或死碼保留舊架構。
- 不在需求出現前預建抽象層、registry 或跨功能 shared service。
- 舊版存檔只能作為行為參考，所有新程式必須依目前需求重新建立。
