# 0076 — Live Context manager

## Outcome

- Replaced the live Agent loop's fixed latest-100-message input with the
  token-budget Context manager.
- Added backend capability resolution for direct models and bounded in-memory
  OpenRouter capability caching.
- Added selected-model compaction generation with tools disabled and a 2K
  output limit.
- Added explicit 8K main-response limits to OpenAI, Anthropic and OpenRouter
  native requests.
- Recounted every model round, including in-memory tool calls and results.
- Added safe context metrics and stable `context_limit_exceeded` and
  `context_preparation_failed` Run errors without logging prompt content.

## Behavior

Recent 12 visible Messages and the current user Message are mandatory. Older
history is compacted until the assembled request is below the configured
trigger. Original Messages remain in SQLite. If required context or a tool round
cannot fit, the Run fails before a Provider request instead of truncating data.

## Verification

- Long-history compaction and raw-message retention.
- Required-recent-history overflow without a Provider request.
- Direct and OpenRouter capability resolution and cache behavior.
- Summary model request bounds and no-tool policy.
- Three Provider output-limit request mappings.
- Agent architecture dependency guard over nested Context modules.
