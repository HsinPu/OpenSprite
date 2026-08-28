# 0058 System prompt provider boundary

## Objective

Replace the Agent Loop's direct dependency on one module constant with an
injectable system-prompt boundary while preserving current behavior.

## Changes

- Added the narrow asynchronous `SystemPromptProvider` contract.
- Added a static provider that preserves the existing minimal prompt for
  isolated Agent compositions.
- Made the Agent Loop build one prompt snapshot before the first model round
  and reuse that exact content for all later tool rounds in the same Run.
- Added regression coverage for one provider call per Run and stable prompt
  content across model rounds.

## Public impact

Provider payloads, HTTP contracts, persisted data, frontend behavior, and the
rendered system prompt remain unchanged in this refactor slice.

## Verification

- Agent Loop tests.
- Agent architecture guards.
- Native inference adapter tests.
