import { Alert, Button, Form, Select, Space, Tag } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  executionSettingsErrorText, getExecutionSettings, putExecutionSettings,
  type ExecutionPlugin, type ExecutionSelection, type ExecutionSettings as ExecutionSettingsData,
} from "../../api/executionSettings";
import type { MessageKey } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import { SaveStatus, SettingsCard } from "./SettingsPrimitives";
import "./ExecutionSettings.css";

const statusKeys: Record<ExecutionPlugin["status"], MessageKey> = {
  available: "execution.status.available", incompatible: "execution.status.incompatible", unavailable: "execution.status.unavailable",
};
const sameSelection = (left: ExecutionSelection, right: ExecutionSelection) => left.loopId === right.loopId && left.policyId === right.policyId;

export function ExecutionSettings({ active }: { active: boolean }) {
  const { t } = useI18n();
  const [form] = Form.useForm<ExecutionSelection>();
  const root = useRef<HTMLDivElement | null>(null);
  const requestVersion = useRef(0);
  const [data, setData] = useState<ExecutionSettingsData | null>(null);
  const [draft, setDraft] = useState<ExecutionSelection | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  const reload = useCallback(async () => {
    const request = ++requestVersion.current;
    setLoading(true);
    setSaving(false);
    setError(null);
    setSaved(false);
    try {
      const next = await getExecutionSettings();
      if (request !== requestVersion.current) return;
      setData(next);
      setDraft(next.selection);
      form.setFieldsValue(next.selection);
    } catch (failure) {
      if (request === requestVersion.current) setError(failure);
    } finally {
      if (request === requestVersion.current) setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    if (active) void reload();
    return () => { requestVersion.current += 1; };
  }, [active, reload]);

  const save = async (selection: ExecutionSelection) => {
    if (saving || loading || !data) return;
    const request = ++requestVersion.current;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const next = await putExecutionSettings(selection);
      if (request !== requestVersion.current) return;
      setData(next);
      setDraft(next.selection);
      form.setFieldsValue(next.selection);
      setSaved(true);
    } catch (failure) {
      if (request === requestVersion.current) setError(failure);
    } finally {
      if (request === requestVersion.current) setSaving(false);
    }
  };

  const selectedPlugin = (kind: ExecutionPlugin["kind"], id: string | undefined) => data?.plugins.find((item) => item.kind === kind && item.id === id);
  const selectionAvailable = draft !== null
    && selectedPlugin("loop", draft.loopId)?.status === "available"
    && selectedPlugin("policy", draft.policyId)?.status === "available";
  const pluginName = (plugin: ExecutionPlugin) => plugin.id === "standard"
    ? t(plugin.kind === "loop" ? "execution.standardLoopName" : "execution.standardPolicyName")
    : plugin.kind === "policy" && plugin.id === "no_recovery" ? t("execution.noRecoveryName") : plugin.name;
  const options = (kind: ExecutionPlugin["kind"], current: string | undefined) => {
    const items = (data?.plugins ?? []).filter((item) => item.kind === kind).map((item) => ({
      value: item.id,
      label: item.status === "available" ? pluginName(item) : `${pluginName(item)} (${t(statusKeys[item.status])})`,
      disabled: item.status !== "available",
    }));
    if (current && !items.some((item) => item.value === current)) {
      items.push({ value: current, label: `${current} (${t("execution.status.unavailable")})`, disabled: true });
    }
    return items;
  };
  const details = (kind: ExecutionPlugin["kind"], id: string | undefined) => {
    const plugin = selectedPlugin(kind, id);
    if (!plugin) return id ? <p className="settings-helper-text">{t("execution.missingPlugin")}</p> : null;
    const builtinKey: MessageKey | null = plugin.id === "standard"
      ? (kind === "loop" ? "execution.standardLoopDescription" : "execution.standardPolicyDescription")
      : kind === "policy" && plugin.id === "no_recovery" ? "execution.noRecoveryDescription" : null;
    return <div className="execution-settings__details">
      <p className="settings-helper-text">{builtinKey ? t(builtinKey) : plugin.description}</p>
      <Space className="execution-settings__metadata" size={8} wrap><span>{t("execution.version", { version: plugin.version })}</span><span>{t("execution.apiVersion", { version: plugin.apiVersion })}</span><Tag>{t(statusKeys[plugin.status])}</Tag></Space>
    </div>;
  };

  return <div ref={root} className="execution-settings settings-form-stack">
    <div className="settings-intro"><h2>{t("settings.category.execution")}</h2><p>{t("execution.intro")}</p></div>
    <SettingsCard icon="rocket" title={t("execution.selectionTitle")}>
      {loading ? <p className="settings-helper-text" role="status">{t("execution.loading")}</p> : null}
      {error !== null ? <Alert className="execution-settings__error" type="error" showIcon title={executionSettingsErrorText(error, t)} action={<Button disabled={loading || saving} onClick={() => void reload()}>{t("general.reload")}</Button>} /> : null}
      <Form form={form} layout="vertical" disabled={loading || saving || !data} onFinish={(value) => void save(value)} onValuesChange={(_, value: ExecutionSelection) => { setDraft(value); setSaved(false); }}>
        <Form.Item name="loopId" label={t("execution.loop")} extra={details("loop", draft?.loopId)}>
          <Select aria-label={t("execution.loop")} options={options("loop", draft?.loopId)} getPopupContainer={() => root.current ?? document.body} />
        </Form.Item>
        <Form.Item name="policyId" label={t("execution.policy")} extra={details("policy", draft?.policyId)}>
          <Select aria-label={t("execution.policy")} options={options("policy", draft?.policyId)} getPopupContainer={() => root.current ?? document.body} />
        </Form.Item>
        <p className="settings-helper-text execution-settings__scope">{t("execution.scope")}</p>
        <Space size={12} wrap>
          <Button type="primary" htmlType="submit" aria-label={t("execution.save")} aria-busy={saving} loading={saving} disabled={!selectionAvailable || loading || !data || !draft || sameSelection(data.selection, draft)}>{t("execution.save")}</Button>
          {saved ? <SaveStatus saved /> : null}
        </Space>
      </Form>
    </SettingsCard>
  </div>;
}
