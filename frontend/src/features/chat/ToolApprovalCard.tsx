import { Button } from "antd";
import { useEffect, useMemo, useState } from "react";

import type { RunEvent } from "../../api/agentChat";
import { getToolApproval, putToolApproval, toolApprovalErrorText, type ToolApprovalDetail, type ToolApprovalDecision } from "../../api/toolApprovals";
import { useI18n } from "../../i18n/I18nProvider";


export function pendingToolApprovalId(events: RunEvent[]): string | null {
  const decided = new Set(events.filter((event) => event.type === "tool.approval_decided").map((event) => String(event.data.approvalId ?? "")));
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event?.type === "tool.approval_requested") {
      const id = String(event.data.approvalId ?? "");
      if (id && !decided.has(id)) return id;
    }
  }
  return null;
}

export function ToolApprovalCard({ events }: { events: RunEvent[] }) {
  const { t } = useI18n();
  const approvalId = useMemo(() => pendingToolApprovalId(events), [events]);
  const [detail, setDetail] = useState<ToolApprovalDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [locallyDecided, setLocallyDecided] = useState<string | null>(null);

  useEffect(() => {
    if (approvalId === null || approvalId === locallyDecided) { setDetail(null); return; }
    let active = true;
    setError(null);
    void getToolApproval(approvalId).then((next) => { if (active) setDetail(next); }).catch((nextError: unknown) => { if (active) setError(toolApprovalErrorText(nextError, t)); });
    return () => { active = false; };
  }, [approvalId, locallyDecided, t]);

  if (approvalId === null || approvalId === locallyDecided) return null;
  const decide = async (decision: ToolApprovalDecision) => {
    setDeciding(true);
    setError(null);
    try {
      await putToolApproval(approvalId, decision);
      setLocallyDecided(approvalId);
      setDetail(null);
    } catch (nextError) {
      setError(toolApprovalErrorText(nextError, t));
    } finally { setDeciding(false); }
  };
  return <section className="execution-approval" aria-labelledby="execution-approval-title">
    <h3 id="execution-approval-title">{t("approval.title")}</h3>
    {!detail && !error ? <p role="status">{t("approval.loading")}</p> : null}
    {detail ? <><p>{t("approval.description", { tool: detail.toolName })}</p><strong>{t("approval.arguments")}</strong><pre>{JSON.stringify(detail.arguments, null, 2)}</pre><p className="execution-approval__warning">{t("approval.warning")}</p><div className="execution-approval__actions"><Button danger disabled={deciding} onClick={() => void decide("deny")}>{t("approval.deny")}</Button><Button type="primary" loading={deciding} onClick={() => void decide("allow_once")}>{t("approval.allowOnce")}</Button></div></> : null}
    {error ? <p role="alert">{error}</p> : null}
  </section>;
}
