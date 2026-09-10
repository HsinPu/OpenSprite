# Custom Provider 0.21.0 implementation checkpoints

Status: implementation checkpoints retained for traceability. Final delivery and
verification limits are recorded in 0240-release-0.21.0.md; later entries supersede
earlier incomplete-state notes.

## 最新提交與驗證

- `9d0a19d7`：catalog／加密儲存。
- `79ed0d38`：API、協定、Run／排程／子代理、SQLite v16 與後端 0.21.0。
- `57c08204`：前端管理與三語介面。
- 最新完整後端：1074 passed、3 skipped；最後額外調整的內建 metadata 隔離邏輯，
  聊天 17 項測試通過。完整前端 423 項通過，提交前相關 43 項再驗證通過。
- 最終文件與驗證請見 0240。以下是歷史過程，未完成項目可能已被後續段落取代。

## Approved scope

Separate provider identity from protocol adapters. Keep openai, anthropic and
openrouter IDs, credentials and behavior. Add UUID-identified custom OpenAI
Chat Completions providers with managed Base URL, optional Bearer credentials,
model discovery and manual models. Integrate chat, schedules and subagents.
Do not push or update the installed runtime.

## Sequence and acceptance gates

1. Catalog schema, AppPaths mapping, strict IDs, atomic persistence and migration.
2. Protected CRUD, credential transactions, URL policy, model discovery/manual models.
3. Immutable execution resolution and Chat Completions adapter.
4. Conversation/history, schedule and agent ID validation and reference guards.
5. Three-language settings UI, provider editor and model management.
6. Full regression checks, version 0.21.0 and reviewable commits.

## Safety boundaries

- Credentials remain encrypted; no arbitrary headers or TLS bypass.
- No redirects; public endpoints require HTTPS. Local/private HTTP requires explicit acknowledgement.
- Existing IDs survive migration; no silent model fallback.
- Active runs block endpoint/auth mutation; referenced providers cannot be deleted.
- Model list refresh preserves manual metadata and current valid selection.
- Real service compatibility is only claimed for exercised cases.

## Current checkpoint

- Prior 0.20.4 UI changes isolated in commit 5e06c0e6.
- Provider identity now accepts builtin IDs and canonical UUID v4 custom IDs across
  frontend, backend, inference, conversations, schedules and subagents.
- Added the custom catalog, encrypted-credential transaction recovery, model
  discovery/manual creation and Chat Completions endpoint integration.
- Added initial custom-provider settings and model management UI. The builtin
  provider and model workflows remain covered by the existing regression suite.
- Corrected a frontend regression: the custom catalog no longer loads eagerly
  when there are no custom providers, and builtin model metadata remains available
  independently of connection status. Disconnected builtin providers are not made
  selectable merely because their static model metadata exists.
- Verification at this checkpoint: SettingsPage and App suites pass (60 tests),
  frontend typecheck passes, and the complete frontend suite passes (49 files,
  416 tests). Added a focused regression for on-demand custom catalog loading.
- Remaining release gates include complete edit/delete flows and reference guards,
  immutable model capability resolution, strict API/OpenAPI alignment, integration
  and full regression verification, documentation and the 0.21.0 version bump.
- No custom-provider release commit, push or installed-runtime update has occurred.

### Model mutation checkpoint

- Added model removal to the transactional catalog service. It checks the provider
  revision and stable model key, rejects missing models without changing state,
  increments catalog/provider revisions, and preserves encrypted credentials.
- Verified edit keeps the stable model key and removal rejects stale revisions.
- `test_custom_provider_service.py`: 4 passed with warnings treated as errors.
- This is a service primitive, not yet an exposed delete endpoint: application
  reference and active-run guards must be connected before HTTP deletion is enabled.

### Guarded mutation checkpoint (supersedes the preceding endpoint limitation)

- Added Provider and stable-key model PUT/DELETE endpoints behind ProviderMutations.
- Shared Workspace mutation gate serializes Run acceptance, AI settings writes,
  schedule/Agent reference creation and guarded provider changes.
- RunManager tracks providers retained by each parent Agent snapshot, including
  possible child providers, and releases them when the task ends. Task registration
  now remains within the acceptance gate to avoid a child-reference gap.
- SQLite usage excludes historical runs but includes all saved schedules; deleting
  referenced providers/models fails without deleting history or credentials.
- Registered Agent references include disabled definitions. Unreadable definitions
  fail the reference check closed rather than guessing that deletion is safe.
- Custom schedule and Agent writes validate provider/model existence. Endpoint and
  model mutations reject live Run use. Cancelling a mutation request waits for its
  background write before releasing the gate.
- Verification: 30 provider/Run/chat tests, 36 AI-settings/runtime tests, 28
  runtime/schedule/Agent tests, and 7 route/usage tests passed in focused runs.
  These sets overlap; they are not a claimed aggregate count or full regression.
- Still required: UI edit/delete, complete race/cancellation tests, immutable model
  capabilities, strict full contracts, refresh-removal reference policy and final
  release gates. Version remains 0.20.4; no feature commit/push/install yet.

### Frontend mutation checkpoint

- Connected Provider edit/remove and stable-key model edit/remove to guarded APIs.
- Provider edit omits an empty API Key, preserving encrypted credentials without
  reading them back. Model edits retain the separate display name and stable key.
- Added removal confirmation, three-language action/credential guidance, and
  outer-settings overlay ownership while the provider editor is open.
- API, hook and SettingsPage focused suites passed (37 tests before the additional
  mutation adapter test); mutation API suite then passed 4 tests and typecheck passed.
- Still incomplete: localized error states, full component/browser verification,
  immutable capability snapshots, discovery reference safety, contract documents,
  complete backend/frontend gates and release/commits. No installed app changes.

### Discovery and capability snapshot checkpoint

- Discovery captures endpoint and credential together under the shared gate before
  network I/O. Its commit checks revision, live parent/child use and references to
  any removed discovered model. Rejected refreshes preserve the previous catalog.
- ProviderEndpointSnapshot now retains immutable model capabilities. Custom Run
  Context preparation, Skill/Agent tool capability decisions and child execution
  use those retained capabilities rather than rereading the mutable catalog.
- Focused evidence: 11 discovery/service tests, 25 chat/service/manager tests and
  43 service/Agent-loop tests passed (overlapping suites, not aggregate coverage).
- Final integration/browser/contract and release verification remain outstanding.

### Full regression and version checkpoint

- Full backend run exposed a misplaced Provider uniqueness validator in the MCP
  create schema. Moved it to ProviderListResponse; MCP creation no longer accesses
  a nonexistent providers field.
- Agent mutation summaries now omit detail-only developerInstructions along with
  content, matching their strict response contract. The focused MCP/Agent suites
  passed 22 tests after the corrections.
- Product source, existing current-version assertions and lockfile updated to
  0.21.0. Historical single-step v14-to-v15 migration retains its original expected
  version; full migration now expects v16 (3 schema tests passed).
- Frontend production build, Python compileall, uv lock --check --offline and
  uv pip check passed. Full backend verification is still being completed.
- This is not a release completion record. No feature commit, push or local
  installation update has been performed.

- Latest full backend run: 1053 passed, 3 skipped, 13 failed. All remaining
  failures were migration version expectations (two child-schema assertions were
  already corrected while that run was in progress). Updated only final-version
  expectations, preserving data/history assertions; the affected migration suites
  then passed all 46 tests. A final full rerun remains required.

## Contract and request-boundary checkpoint

- Full backend rerun passed: 1066 passed, 3 skipped. Subsequent request-boundary
  changes passed all 8 custom-provider route tests; contract tests passed 2 tests.
- Full frontend suite passed: 49 files, 418 tests. JSDOM pseudo-element warnings
  remain test-environment limitations, not browser verification.
- Chat, AI settings, schedules and Provider catalog contracts now accept canonical
  custom UUIDv4 identities. Built-in connection path parameters remain restricted
  to the original three providers. Catalog responses allow appended custom rows.
- All custom Provider JSON mutations now share a bounded streaming body reader;
  regression coverage proves oversized streams stop before consuming their tail.
- git diff --check passed (line-ending conversion warnings only).
- Remaining delivery work includes browser verification, controlled inference
  integration, pagination and final architecture/release documentation review.
  Feature commits have not been created; no push or installed-app update occurred.

## Provider catalog pagination

- Catalog GET now accepts strict limit/cursor query parameters (default 50,
  maximum 100 per page), returns nextCursor, and rejects stale revision cursors.
- Frontend aggregates revision-consistent pages before replacing its catalog and
  rejects duplicate identities, non-progressing cursors and mixed revisions.
- OpenAPI documents the page contract. Route/contract tests: 11 passed; frontend
  adapter tests: 5 passed; TypeScript typecheck passed.
- Model-list pagination, browser/inference integration and final delivery audit
  remain outstanding. This checkpoint does not claim release completion.

## Model pagination checkpoint

- Model-list GET now uses strict revision-bound cursor pages, with a default of
  50 and maximum of 100 records per request. Mutation responses keep their
  complete resulting list contract.
- Frontend model loading aggregates pages, rejects mixed revisions and duplicate
  identities, and validates cursor progress. OpenAPI separates ModelPage from
  ModelList. Frontend adapter tests passed 6 tests.
- Backend route tests cover page boundaries, stale cursors and duplicate/unknown
  query parameters; no installed runtime or remote provider was changed.

## 文件與真實 HTTP 驗證

- README 補上自訂供應商操作、Base URL、金鑰保留／移除、模型探索與手動模型、
  HTTP 風險及引用阻擋說明。新增 custom-providers 架構文件，同步 Agent chat、
  overview 與 local-data-layout，區分舊內建連線與新自訂 catalog。
- 使用隨機 loopback port 的 ThreadingHTTPServer，讓 NativeModelGateway 經由真正
  HTTP 傳輸驗證 Bearer Header、請求路徑／JSON 及 SSE 解碼；未使用真實金鑰或連外。
  自訂推論測試 2 項通過。這不構成第三方服務全面相容證據。
- Windows installer isolation test passed，隔離安裝產物版本為 0.21.0；
  已安裝使用者 runtime 未更新。Production build 仍有既有大型 chunk 警告。
- 尚需前端實際畫面檢查、最後安全／需求審核及可審查提交。

## 前端錯誤與表單收尾

- 自訂 Provider 錯誤改用繁中／英文／日文復原提示，區分欄位、revision、
  執行中、引用限制、模型探索與連線問題；未知錯誤不直接顯示原始內容。
- Provider 與模型欄位補上唯一 ID 與 label 關聯，移除模型後清除殘留顯示名稱。
- 錯誤文案與 SettingsPage 測試合計 34 項通過；typecheck、diff check 通過。
- 這些是元件測試，不取代桌面與 390px 真實瀏覽器驗證。

## 隔離瀏覽器驗證

- 新增 tests/browser/providers.html 與 providers.tsx，使用前端模擬 API，
  不連接已安裝 runtime、不保存真實金鑰或修改使用者 Provider。
- 真實內嵌瀏覽器驗證新增視窗與欄位標籤。發現認證 Select 在目前縮放下浮層
  持續錯位，改成 Ant Radio.Group，直接顯示兩個選項。
- 已實際切換無認證、填寫測試名稱／URL，提交模擬 409 後保留輸入並顯示本地化提示。
- 實際 CSS viewport 寬度 390，document scrollWidth 同為 390；模型管理展開後仍無水平溢出。
  viewport override 已重設，測試 tab 已關閉。
- 本次驗證是元件隔離頁，不宣稱完整 Settings overlay 或真實 Provider CRUD 已端到端驗證。
