import type { ContextUsage, RunEvent } from "../../api/agentChat";
import { useI18n } from "../../i18n/I18nProvider";
import { formatTokenLimit } from "../ai-settings/contextBudget";

type ContextUsageIndicatorProps = {
  usage: ContextUsage | null;
  fallbackLimitTokens: number | null;
  compacting?: boolean;
};

const isInteger = (value: unknown): value is number => typeof value === "number" && Number.isInteger(value);

export function contextUsageFromEvents(events: ReadonlyArray<RunEvent>): ContextUsage | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event?.type !== "model.started") continue;
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
    ) continue;
    return {
      providerId,
      modelId,
      contextTokens,
      contextLimitTokens,
      inputBudgetTokens,
    };
  }
  return null;
}

export function ContextUsageIndicator({ usage, fallbackLimitTokens, compacting = false }: ContextUsageIndicatorProps) {
  const { t } = useI18n();
  const used = usage ? formatTokenLimit(usage.contextTokens) : "—";
  const limitTokens = usage?.contextLimitTokens ?? fallbackLimitTokens;
  const limit = limitTokens === null ? "—" : formatTokenLimit(limitTokens);
  const ratio = usage ? usage.contextTokens / usage.inputBudgetTokens : 0;
  const tone = usage === null
    ? "is-unavailable"
    : ratio >= 0.9
      ? "is-danger"
      : ratio >= 0.75
        ? "is-warning"
        : "is-ok";
  const label = t("chat.contextUsageLabel", { used, limit });

  return (
    <span
      className={`chat-workspace__context-usage ${tone}${compacting ? " is-compacting" : ""}`}
      data-testid="context-usage"
      aria-label={label}
      title={label}
    >
      <span className="chat-workspace__context-usage-value">{t("chat.contextUsage", { used, limit })}</span>
      {compacting ? <span className="chat-workspace__context-usage-status">{t("chat.contextUsageCompacting")}</span> : null}
    </span>
  );
}
