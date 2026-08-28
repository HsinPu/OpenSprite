# 0059 Dynamic system prompt and full logs

## Objective

Build one small trusted system-prompt snapshot per Run and persist the complete
rendered Prompt locally before any Provider request.

## Changes

- Added a production Prompt provider using confirmed locale, time zone and an
  injectable current-time source.
- Kept the Prompt to Role, Task, Constraints and Output sections with a 16 KiB
  bound and a neutral UTC fallback when General Settings are unavailable.
- Added create-only full Prompt receipts under
  `.opensprite/logs/system-prompts/<UTC-date>/<run-id>.md` with version, source,
  fallback and SHA-256 metadata.
- Added owner-only POSIX permissions, file and directory fsync, duplicate-path
  rejection, UUID path validation and partial-file cleanup.
- Composed the dynamic provider only in the production runtime; isolated Agent
  tests may still inject the static provider explicitly or by default.

## Public impact

Provider, Agent Chat, General Settings and frontend HTTP contracts are
unchanged. The new local log contains the complete trusted System Prompt but no
user message, conversation history, credential, Provider response or hidden
reasoning.

## Verification

- Dynamic locale/time rendering and General Settings fallback tests.
- Complete-log content, create-only behavior, fsync failure cleanup, invalid
  Run id and POSIX permission tests.
- Agent proof that Prompt/log failure prevents every model request.
- AppPaths, runtime composition, Agent Loop and inference adapter tests.
