# System prompt architecture

## Purpose

OpenSprite builds one bounded base system-prompt snapshot when a Run starts.
Settings changed during an active Run take effect only on the next Run.

The initial dynamic surface is intentionally small:

- fixed Role, Task, Constraints and Output sections;
- confirmed interface locale;
- confirmed time-zone setting; and
- current date and time from an injectable clock; and
- the immutable Workspace execution snapshot for this Run.

User messages and conversation history enter the model request as separate
text messages. Credentials, Provider responses and hidden reasoning are not
inserted into this Prompt. The core sends no tool definitions.

Prompt version 2 includes a delimited Workspace section containing ID, name,
revision, availability, managed root and external mounts with their access modes.
Workspace names and roots are JSON-encoded untrusted metadata, not instructions. The fixed text
also states that knowing a path grants no file capability. The text core cannot
read or write Workspace files. The fixed Default Workspace uses the
managed `.opensprite/workspace/default` root.

## Ownership and dependency direction

The top-level `system_prompt.py` feature owns the production renderer, General
Settings fallback and clock conversion. `DynamicSystemPromptProvider` returns
an immutable rendered snapshot without writing files. The product wrapper
supplies its text through the internal `SystemPromptProvider` protocol and
submits a complete receipt only when the admitted Run has `logFullPrompts` enabled.
`runtime.py` composes the renderer and the optional `PromptRecorder`.

```text
General Settings + Workspace snapshot + Clock
                -> DynamicSystemPromptProvider
                -> ProductSystemPromptProvider
                -> RunExecutor -> Loop
                -> normalized ModelRequest
                -> one Provider adapter

Opt-in product wrapper + request observer
                -> bounded PromptRecorder -> filesystem receipts
```

The Agent package does not import AppPaths, General Settings persistence,
FastAPI or the filesystem log writer.

## Failure and bounds

The renderer limits the Prompt to 128 Ki characters; the production receipt
also enforces its 64 KiB UTF-8 content bound. Missing General Settings use the
normal `zh-TW` and `system` defaults. An unavailable or malformed General
Settings store falls back without writing settings: follow the user's language
and use UTC time.

An invalid clock or an oversized rendered Prompt is a preparation failure.
Filesystem receipts are diagnostics, not a precondition for execution. The
recorder uses one lazy daemon worker and admits at most four pending records,
including the record being written; each admitted content body is at most 8 MiB.
The individual System Prompt writer additionally enforces its 64 KiB receipt
bound. A full queue, oversized record, duplicate file, write failure or fsync
failure emits only a sanitized diagnostic and does not stop inference.
A failed new file write removes the partial file when possible.

Run shutdown drains the product recorder for up to two seconds; slow or blocked
filesystem I/O cannot hold inference or process shutdown indefinitely. Optional
recording failures never replace mandatory SQLite step, source, event, summary
or terminal transactions. Those persistence failures still fail closed.

## Full Prompt logs

When full recording is enabled, the product submits one System Prompt receipt:

```text
.opensprite/logs/system-prompts/<UTC-date>/<run-id>.md
```

The receipt contains Prompt version, Run id, UTC creation time, locale and
time-zone sources, fallback status, SHA-256 digest and the complete rendered
Prompt. It is create-only and cannot overwrite an earlier receipt. Linux uses
`0700` directories and `0600` files; Windows relies on the user-profile ACL.

These logs intentionally contain the complete current Prompt, including a
Workspace's canonical root, so the entire
`.opensprite` root remains sensitive. Full Prompt content is not copied into
application logs, the database, HTTP responses or Run events.

The same admitted `logFullPrompts` choice controls the System Prompt receipt
and `.opensprite/logs/prompts` request receipts. Disabled Runs create neither
receipt directory. Existing files are unaffected. Request observers receive
normalized non-secret inputs and may not replace or mutate model requests.
SDK v5 still requires the complete first System Prompt to preserve the pinned
base prefix; moving rendering and recording policy does not change that contract.

Future custom instructions, memory, Workspace-specific instructions or other context must not
enter the rendered Prompt until their trust, size, failure and full-log
exposure policies are explicitly designed and tested.
