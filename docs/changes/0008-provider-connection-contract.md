# 0008 - Provider connection contract foundation

## Objective

建立第一份明確的 provider connection HTTP contract 與最小 Python/FastAPI backend
foundation，先固定 frontend/backend 邊界，不加入 provider network 或 credential persistence。

## Changes

- 新增 authoritative OpenAPI 3.1 JSON contract，涵蓋 `/healthz`、固定兩筆 provider catalog、
  validate-then-save replacement、stored-credential test 與 idempotent disconnect。
- 定義所有 public provider 欄位的 presence、nullability、status state、固定 error envelope、HTTP
  status mapping、retryability、30 秒 provider deadline、per-provider concurrency 與無 partial
  success 語意。
- 建立 Python 3.12+ `src` package、FastAPI typed app factory、Pydantic boundary models 與
  `ProviderConnections` dependency seam。
- Parent dependency sync 建立 `backend/uv.lock` 與 `backend/.venv`；lockfile 固定本切片實際解析的
  backend 與 test dependency graph。
- 預設 provider dependency fail closed；沒有 provider adapter、network call、credential store、
  plaintext fallback、database、application CLI 或 compatibility layer。
- Runtime 不公開 `/openapi.json`、`/docs` 或 `/redoc`；repository 內的 static JSON 持續是唯一
  public contract。
- 新增 stdlib contract checks 與安裝 dependencies 後可執行的 FastAPI provider-conformance tests。
- 更新 architecture，記錄 consumers、ownership、trust boundary、secret sensitivity、traffic、
  availability、security、compatibility、rejected alternatives 與後續 handoff。

## Public impact

新增 draft v1 local HTTP boundary。Frontend 尚未接線，沒有既有 consumer 需要 migration。
公開 request/response/error schema 從此以
`contracts/provider-connections.openapi.json` 為準；raw credential 與 internal metadata 不公開。

## Verification

- `ConvertFrom-Json` / stdlib-equivalent parse of the OpenAPI JSON contract。
- Parent 在第一輪 repair 後執行
  `backend/.venv/Scripts/python.exe -m pytest backend/tests -q -W error`：`13 passed`。
- Independent-review repair 後以相同 warning-as-error command 重驗：`27 passed`。
- `git diff --check`。

## Remaining work

- 選擇並實作各 OS secure credential store；不得加入 plaintext fallback。
- 實作 OpenAI/Anthropic validation adapter、30 秒 deadline 與 per-provider serialization。
- 在 provider routes operational 前加入 loopback binding、Host validation 與 same-origin mutation
  enforcement；這三項都是 release-blocking requirement。
- 由 frontend 依 authoritative contract 取代目前 fake provider state。
