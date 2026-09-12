import type { ContextUsage } from "../../api/agentChat";
import { Button, Popover, Progress, theme } from "antd";
import { useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { formatTokenLimit } from "../ai-settings/contextBudget";

export { contextUsageFromEvent, contextUsageFromEvents, appendEventPreservingContextUsage } from "./contextUsage";

type ContextUsageIndicatorProps = {
  usage: ContextUsage | null;
  fallbackLimitTokens: number | null;
  compacting?: boolean;
};

export function ContextUsageIndicator({ usage, fallbackLimitTokens, compacting = false }: ContextUsageIndicatorProps) {
  const { t } = useI18n();
  const { token } = theme.useToken();
  const [open, setOpen] = useState(false);
  const limitTokens = usage?.contextLimitTokens ?? fallbackLimitTokens;
  const validLimit = limitTokens !== null && Number.isFinite(limitTokens) && limitTokens > 0;
  const known = usage !== null && Number.isFinite(usage.contextTokens) && usage.contextTokens >= 0 && validLimit;
  const used = known ? formatTokenLimit(usage.contextTokens) : "—";
  const limit = validLimit ? formatTokenLimit(limitTokens) : "—";
  const percent = known ? Math.round(usage.contextTokens / limitTokens * 100) : null;
  const label = `${t("chat.contextWindow")}: ${percent === null ? t("chat.contextUnknown") : t("chat.contextPercent", { percent })}. ${t("chat.contextUsageLabel", { used, limit })}${compacting ? `. ${t("chat.contextUsageCompacting")}` : ""}`;

  return (
    <Popover open={open} onOpenChange={setOpen} trigger={["hover", "focus"]} placement="top" content={
      <div className="context-usage-detail">
        <div>{t("chat.contextWindow")}</div>
        <strong>{percent === null ? t("chat.contextUnknown") : t("chat.contextPercent", { percent })}</strong>
        <div>{used} / {limit} tokens</div>
        {known ? <div>{t("chat.contextEstimate")}</div> : null}
        {compacting ? <div>{t("chat.contextUsageCompacting")}</div> : null}
      </div>
    }>
      <Button type="text" className="chat-workspace__context-usage" data-testid="context-usage" aria-label={label} aria-expanded={open}
        onClick={() => setOpen(true)}
        onKeyDown={(event) => { if (event.key === "Escape") { setOpen(false); event.stopPropagation(); } }}>
        <span aria-hidden="true"><Progress type="circle" size={18} strokeWidth={12} percent={Math.min(100, percent ?? 0)} showInfo={false} strokeColor={token.colorTextSecondary} /></span>
      </Button>
    </Popover>
  );
}
