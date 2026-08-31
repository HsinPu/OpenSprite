# Historical context boundary

## Objective

Prevent instructions from earlier conversation turns from being mistaken for
the current request after context selection or compaction.

## Changes

- Keep raw conversation Messages unchanged in SQLite.
- Mark summaries and every non-current Message as quoted historical data when
  assembling a model request.
- Preserve the active Run's user Message as the only unmarked actionable user
  instruction.
- Add a System Prompt policy that explicitly separates quoted history from the
  current request.
- Apply the same boundary on initial requests, provider context retries, and
  output-continuation retries.

## Compatibility and safety

This changes only the provider-facing assembled transcript. Conversation APIs,
stored text, compaction records, run events and prompt-log contents continue to
use their existing contracts. The boundary reduces accidental instruction
following from historical test prompts without deleting or rewriting history.

## Public impact

There is no HTTP, database or frontend payload change. The model-facing
transcript now contains explicit historical-data markers and a context policy;
the persisted conversation remains byte-for-byte unchanged.

## Verification

- Context assembly tests verify historical markers, summary markers and
  preservation of the current user Message.
- Agent-loop tests verify the dynamic System Prompt remains present and the
  existing compaction/continuation paths still pass.
- Targeted verification:

  ```text
  backend/.venv/Scripts/python.exe -m pytest -W error --basetemp .pytest-historical tests/test_context_assembly.py tests/test_agent_loop.py tests/test_conversation_compactor.py
  ```

## Remaining work

No additional context hierarchy, retrieval layer or background compaction is
introduced by this change.
