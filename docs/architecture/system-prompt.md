# System prompt architecture

## Purpose

OpenSprite builds one bounded system-prompt snapshot when a Run starts. The
same snapshot is sent in every model round of that Run, including rounds after
tool results. Settings changed during an active Run take effect only on the
next Run.

The initial dynamic surface is intentionally small:

- fixed Role, Task, Constraints and Output sections;
- confirmed interface locale;
- confirmed time-zone setting; and
- current date and time from an injectable clock.

Tool definitions remain in the Provider's structured tool field. User
messages, conversation history, credentials, Provider responses, hidden
reasoning, memory, workspace paths, Skills, subagents and MCP catalogs are not
inserted into this Prompt.

## Ownership and dependency direction

`agent/prompt.py` owns the narrow `SystemPromptProvider` protocol. `AgentLoop`
depends only on that protocol and requests one Prompt before its first model
request. The top-level `system_prompt.py` feature owns the production renderer,
General Settings fallback, clock conversion and full-log writer. `runtime.py`
composes the production provider.

```text
General Settings + Clock + AppPaths
                -> DynamicSystemPromptProvider
                -> SystemPromptProvider protocol
                -> AgentLoop
                -> normalized ModelRequest
                -> one Provider adapter
```

The Agent package does not import AppPaths, General Settings persistence,
FastAPI or the filesystem log writer.

## Failure and bounds

The rendered Prompt is limited to 16 KiB. Missing General Settings use the
normal `zh-TW` and `system` defaults. An unavailable or malformed General
Settings store falls back without writing settings: follow the user's language
and use UTC time.

Production requires a complete Prompt log before a Provider request may start.
An invalid Run id, invalid clock, oversized Prompt, duplicate log path, write
failure or fsync failure stops the Run with the existing safe internal error;
the model is not called. A failed new file write removes the partial file when
possible.

## Full Prompt logs

Each production Run writes exactly one local receipt:

```text
.opensprite/logs/system-prompts/<UTC-date>/<run-id>.md
```

The receipt contains Prompt version, Run id, UTC creation time, locale and
time-zone sources, fallback status, SHA-256 digest and the complete rendered
Prompt. It is create-only and cannot overwrite an earlier receipt. Linux uses
`0700` directories and `0600` files; Windows relies on the user-profile ACL.

These logs intentionally contain the complete current Prompt, so the entire
`.opensprite` root remains sensitive. Full Prompt content is not copied into
application logs, the database, HTTP responses or Run events.

Future custom instructions, memory, workspace rules or other context must not
enter the rendered Prompt until their trust, size, failure and full-log
exposure policies are explicitly designed and tested.
