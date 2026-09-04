import type { ContextUsage, RunEvent } from "../../api/agentChat";

const MAX_VISIBLE_EVENTS = 500;
const isInteger = (value: unknown): value is number => typeof value === "number" && Number.isInteger(value);

export function contextUsageFromEvent(event: RunEvent): ContextUsage | null {
  if (event.type !== "model.started") return null;
  const { providerId, modelId, contextTokens, contextLimitTokens, inputBudgetTokens } = event.data;
  if (
    (providerId !== "openai" && providerId !== "anthropic" && providerId !== "openrouter")
    || typeof modelId !== "string"
    || !modelId
    || !isInteger(contextTokens)
    || !isInteger(contextLimitTokens)
    || !isInteger(inputBudgetTokens)
    || contextTokens < 1
    || contextLimitTokens < 1
    || inputBudgetTokens < 1
    || contextTokens > inputBudgetTokens
    || inputBudgetTokens > contextLimitTokens
  ) return null;
  return {
    providerId,
    modelId,
    contextTokens,
    contextLimitTokens,
    inputBudgetTokens,
  };
}

export function contextUsageFromEvents(events: ReadonlyArray<RunEvent>): ContextUsage | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const usage = events[index] ? contextUsageFromEvent(events[index]) : null;
    if (usage !== null) return usage;
  }
  return null;
}

export function appendEventPreservingContextUsage(
  events: ReadonlyArray<RunEvent>,
  event: RunEvent,
): RunEvent[] {
  const next = [...events, event];
  if (next.length <= MAX_VISIBLE_EVENTS) return next;
  const runStarted = next.find((candidate) => candidate.type === "run.started");
  const latestContextEvent = [...next].reverse().find((candidate) => contextUsageFromEvent(candidate) !== null);
  const pinned = [runStarted, latestContextEvent].filter(
    (candidate, index, values): candidate is RunEvent => candidate !== undefined
      && values.findIndex((value) => value?.sequence === candidate.sequence) === index,
  );
  const pinnedSequences = new Set(pinned.map((candidate) => candidate.sequence));
  const recent = next
    .filter((candidate) => !pinnedSequences.has(candidate.sequence))
    .slice(-(MAX_VISIBLE_EVENTS - pinned.length));
  return [...pinned, ...recent].sort((left, right) => left.sequence - right.sequence);
}
