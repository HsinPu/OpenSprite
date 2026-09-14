import { useEffect, useState } from "react";
import { Alert, Button, Checkbox, Collapse, Modal, Select, Space, Typography } from "antd";
import { getAiSettings, putProviderToolPolicy, aiSettingsErrorText, type NativeProviderId, type ProviderToolPolicy } from "../../api/aiSettings";
import { useI18n } from "../../i18n/I18nProvider";

export function NativeProviderTools({ provider, name, container, onOverlayChange }: { provider: NativeProviderId; name: string; container?: HTMLElement | null; onOverlayChange?: (open: boolean) => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  useEffect(() => { onOverlayChange?.(open); }, [open, onOverlayChange]);
  useEffect(() => () => { onOverlayChange?.(false); }, [onOverlayChange]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [policy, setPolicy] = useState<ProviderToolPolicy>({ toolsEnabled: true, transport: "stream", disabledModels: [] });
  const load = async () => {
    setOpen(true); setBusy(true); setLoaded(false); setError(null);
    try { const settings = await getAiSettings(); setPolicy(settings.providerToolPolicies?.[provider] ?? { toolsEnabled: true, transport: "stream", disabledModels: [] }); setLoaded(true); }
    catch (e) { setError(aiSettingsErrorText(e, t)); }
    finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true); setError(null);
    try { await putProviderToolPolicy(provider, policy); setOpen(false); }
    catch (e) { setError(aiSettingsErrorText(e, t)); }
    finally { setBusy(false); }
  };
  return <>
    <Button type="text" onClick={() => void load()}>{t("models.tools.title")}</Button>
    <Modal title={`${name} · ${t("models.tools.title")}`} getContainer={container ?? false} open={open} onCancel={() => { if (!busy) setOpen(false); }} onOk={() => void save()} confirmLoading={busy} okButtonProps={{ disabled: !loaded }} okText={t("common.save")} cancelText={t("common.cancel")}>
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
        {error ? <Alert type="error" title={error} action={!loaded ? <Button onClick={() => void load()}>{t("common.retry")}</Button> : undefined} /> : null}
        <Checkbox disabled={busy || !loaded} checked={policy.toolsEnabled} onChange={e => setPolicy({ ...policy, toolsEnabled: e.target.checked })}>{t("models.custom.toolsEnabled")}</Checkbox>
        <Typography.Text type="secondary">{t("models.custom.toolsEnabledHelp")}</Typography.Text>
        <label htmlFor={`transport-${provider}`}>{t("models.tools.transport")}</label>
        <Select id={`transport-${provider}`} style={{ width: "100%" }} disabled={busy || !loaded || !policy.toolsEnabled} value={policy.transport} onChange={transport => setPolicy({ ...policy, transport })} options={[{ value: "stream", label: t("diagnostics.transport.streaming") }, { value: "non_streaming", label: t("diagnostics.transport.non_streaming") }]} />
        <Typography.Text type="secondary">{t("models.tools.transportHelp")}</Typography.Text>
        <Collapse ghost items={[{ key: "models", label: t("models.custom.advancedTools"), children: <><label htmlFor={`disabled-${provider}`}>{t("models.tools.disabledModels")}</label><Select id={`disabled-${provider}`} mode="tags" style={{ width: "100%" }} disabled={busy || !loaded} value={policy.disabledModels} onChange={disabledModels => setPolicy({ ...policy, disabledModels })} /><Typography.Text type="secondary">{t("models.tools.disabledModelsHelp")}</Typography.Text></> }]} />
      </Space>
    </Modal>
  </>;
}
