import { useEffect, useState } from "react";
import { Alert, Badge, Button, Collapse, Empty, Skeleton, Typography } from "antd";
import { AgentChatApiError, agentChatErrorText, listRunSteps, type RunStep } from "../../api/agentChat";
import { useI18n } from "../../i18n/I18nProvider";
import "./RunSteps.css";

export function RunSteps({ runId, revision }: { runId: string; revision: string }) {
  const { t } = useI18n();
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let disposed = false;
    setLoading(true); setError(null);
    void (async () => {
      try {
        let cursor = 0;
        const items: RunStep[] = [];
        for (let page = 0; page < 21; page += 1) {
          const result = await listRunSteps(runId, cursor);
          if (disposed) return;
          items.push(...result.steps);
          if (result.nextAfterSequence === null) { setSteps(items); return; }
          cursor = result.nextAfterSequence;
        }
        throw new Error("step bound exceeded");
      } catch (failure) { if (!disposed) setError(agentChatErrorText(failure, t)); }
      finally { if (!disposed) setLoading(false); }
    })();
    return () => { disposed = true; };
  }, [runId, revision, retry, t]);
  return <section className="run-steps" aria-label={t("diagnostics.steps")}>
    <Typography.Text strong>{t("diagnostics.steps")}</Typography.Text>
    <Typography.Text type="secondary">{t("diagnostics.draftNote")}</Typography.Text>
    {error ? <Alert type="error" title={error} action={<Button size="small" onClick={() => setRetry(value => value + 1)}>{t("diagnostics.retry")}</Button>} /> : null}
    {loading && steps.length === 0 ? <Skeleton active paragraph={{ rows: 2 }} /> : steps.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("diagnostics.empty")} /> :
      <Collapse ghost size="small" items={steps.map(step => ({ key: step.id,
        label: <div className="run-steps__label"><span>{step.sequence}. {step.label} <Typography.Text type="secondary">{t(step.channel === "draft" ? "diagnostics.draft" : "diagnostics.answer")}</Typography.Text></span>
          <Badge status={step.status === "completed" ? "success" : step.status === "failed" || step.status === "interrupted" ? "error" : step.status === "running" ? "processing" : "default"}
            text={t(`execution.status.${step.status}`)} /></div>,
        children: <div className="run-steps__detail">
          {step.retryOf ? <Typography.Text type="secondary">{t("diagnostics.retrySource")}: {steps.find(item => item.id === step.retryOf)?.label ?? step.retryOf}</Typography.Text> : null}
          {step.errorCode ? <Typography.Text type="danger">{agentChatErrorText(new AgentChatApiError(step.errorCode), t)}</Typography.Text> : null}
          <pre className="run-steps__text">{step.text || "—"}</pre>
          <Typography.Text type="secondary">{t("diagnostics.inputTokens")}: {step.inputTokens ?? "—"} · {t("diagnostics.outputTokens")}: {step.outputTokens ?? "—"}</Typography.Text>
        </div>,
      }))} />}
  </section>;
}
