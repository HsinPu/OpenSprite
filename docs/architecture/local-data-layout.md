# OpenSprite local data layout

OpenSprite uses one user-data root on every supported desktop platform:

```text
Windows: %USERPROFILE%\.opensprite
Linux:   ~/.opensprite
```

This is a durable product invariant: every future conversation, database,
uploaded attachment, generated output, memory document, runtime state, log, and
cache entry and encrypted provider credential must remain below this root.
Features may not introduce their own application-data root or persist an
absolute user-profile path in the database.

Program files are separate from user data. The Windows installer owns
`%LOCALAPPDATA%\OpenSprite\app`; the future Linux installer owns its documented
application installation directory. Uninstallers preserve `.opensprite` unless
the user explicitly requests verified user-data deletion.

## Authoritative layout

```text
.opensprite/
├─ auth.json
├─ config/
│  ├─ settings.json
│  ├─ general.json
│  ├─ conversation.json
│  └─ credential.key
├─ data/
│  └─ opensprite.db
├─ state/
│  ├─ providers.json
│  └─ provider-transaction.json  # exists only during an in-flight mutation
├─ conversations/
│  └─ <backend-generated-id>/
│     ├─ uploads/
│     ├─ outputs/
│     └─ memory/
├─ logs/
│  └─ system-prompts/
│     └─ <UTC-date>/
│        └─ <run-id>.md
└─ cache/
```

`AppPaths` is the sole backend owner of this mapping. Constructing the mapping,
importing the backend, starting the system app, and reading absent state do not
create the root or any child directory. A persistence owner creates only the
parent directory needed for an actual write.

`auth.json`, `config/credential.key`, `config/settings.json`, `config/general.json`,
`config/conversation.json`,
`state/providers.json`, the transient `state/provider-transaction.json`, and
`data/opensprite.db` are implemented today. Each Run also writes one complete,
create-only System Prompt receipt below `logs/system-prompts/<UTC-date>` before
its first Provider request.
`auth.json` contains only
AES-256-GCM ciphertext; `credential.key` is a random per-install 256-bit key.
Both are sensitive and must be backed up, moved, or deleted together. An
isolated `auth.json` cannot be decrypted, but a copy of the complete
`.opensprite` root can be. Linux uses owner-only directory and file modes;
Windows relies on the user-profile ACL. Files are created only after a provider
key validates, AI settings are successfully saved, or general settings are
successfully saved.

`config/settings.json` is a strict schema-v8, non-secret file containing one
nullable `model` (`providerId`, `modelId`, `contextBudget`, and `outputBudget`)
plus `responseMode`, strict `outputContinuation` policy, strict
`responseDelivery` preference and the opt-in `logFullPrompts` boolean. The
continuation policy is `off`, `1`, `2`, `3`, `5`, or `unlimited`, with `2` as
the default. The response delivery is `stream` or `complete`, with `stream` as
the default. The response mode is `default`, `fast`, `balanced`, or `deep`.
`default` means future inference omits
the Provider reasoning-strength parameter. It never contains a display label, API key, or
provider model catalog. Schema-v6 booleans are converted in memory to `2` or
`off` without rewriting until the next successful PUT. Schema-v7 settings are
read with `responseDelivery: stream` without rewriting. Reads of a missing file
are side-effect free and return `model: null`, `responseMode: default`,
`outputContinuation: 2`, and `responseDelivery: stream`. `stream` is the
default browser presentation and `complete` buffers streamed deltas until the
Run is terminal; Provider requests and SSE remain streaming in either mode.
Every successful change replaces the full settings
document atomically; clearing the model preserves the other selected settings.
`state/providers.json` remains strict non-secret metadata. Other
paths are not created in advance.

Provider connect and disconnect update encrypted credentials and non-secret
metadata in separate files. Before either mutation begins, the backend writes a
strict non-secret recovery journal containing only the before/after
fingerprints, masked preview, status, and timestamps. Normal completion removes
the journal. If the process stops between the two atomic replacements, startup
uses the credential fingerprint to finish or roll back the metadata side and
then removes the journal. The journal never contains an API key or ciphertext.

`config/general.json` is a separate strict schema-v1, non-secret file containing
only `locale` and `timeZone`. A missing file returns `zh-TW` and `system`
without creating a directory. Every successful change replaces both values
atomically.

`config/conversation.json` is an independent strict schema-v3, non-secret file
containing `startupView` (`new` or `recent`), `sendBehavior` (`enter` or
`modifier-enter`), boolean `autoScroll`, and boolean
`executionPanelDefaultExpanded`. A missing file returns `new`, `enter`, `true`
and `false` without creating a directory. Current schema-v2 is read as a
collapsed execution-panel preference without rewriting the file; the next
successful PUT writes canonical v3. Schema-v1 is rejected. It does not alter
`config/general.json`.

`data/opensprite.db` is created only when the first user message and Run are
successfully accepted. It owns Conversation, visible Message, Run, append-only
conversation compaction, and safe semantic Run-event tables described by
`agent-chat.md`. SQLite schema v8 snapshots each Run's requested output budget,
strict output-continuation policy and full-Prompt logging preference
and stores the resolved maximum in its `model.started` event. Empty reads,
backend import, and service startup do not create `data/` or the database.
Conversation and Run identifiers are backend-generated UUIDs rather than values
derived from a channel, title, or user text. Database file references are stored
relative to the data root; the database must not persist the absolute user
profile path. Upload, output, memory, other logs, and cache directories remain
unimplemented and are not created in advance. The System Prompt log directory
is created only when the first Run reaches Prompt construction.

Runtime startup creates `logs/backend/<local-date>/backend.log`. The centralized
handler rotates at 10 MiB with two same-day backups, retains 14 days, redacts
credential-like text and records safe traceback diagnostics. System Prompt logs
remain isolated under `logs/system-prompts` and are never mixed into runtime logs.
Opt-in full model-request receipts use `logs/prompts/<local-date>/<run-id>/` and
are controlled by the AI setting `logFullPrompts`; they are plaintext diagnostic
records and may contain user-provided sensitive content, so the directory and
files use the same local protection. Automatic retention or cleanup for these
receipts is not implemented yet; they must be treated as sensitive until a
separate retention policy is approved and delivered.

This rebuild is new-install-only. It does not scan, migrate, import, or fall back
to any earlier application-data location.
