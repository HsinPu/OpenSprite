import { useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarOutlined,
  EditOutlined,
  HistoryOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Input, Modal, Popconfirm, Select, Tag } from "antd";

import type { ContextBudget, OutputBudget, OutputContinuation, PersistedModelSelection, ResponseMode } from "../../api/aiSettings";
import { ScheduleApiError, type Schedule, type ScheduleCadence, type ScheduleFields } from "../../api/schedules";
import type { ModelChoice } from "../ai-settings/modelCatalog";
import { useI18n } from "../../i18n/I18nProvider";
import { useSchedules } from "./useSchedules";
import "./schedules.css";


type Props = {
  active: boolean;
  container: HTMLElement | null;
  defaultTimeZone: string;
  modelSelection: PersistedModelSelection | null;
  modelChoices: readonly ModelChoice[];
  responseMode: ResponseMode;
  outputContinuation: OutputContinuation;
  onOpenConversation: (conversationId: string) => void;
  onOverlayChange?: (open: boolean) => void;
};

type FormState = {
  name: string;
  prompt: string;
  timeZone: string;
  cadenceType: ScheduleCadence["type"];
  runAt: string;
  localTime: string;
  weekdays: number[];
  providerModel: string;
  responseMode: ResponseMode;
  contextBudget: ContextBudget;
  outputBudget: OutputBudget;
  outputContinuation: OutputContinuation;
};

const localDateTime = (value: string) => {
  const date = new Date(value);
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
};

const resolvedTimeZone = (value: string) => value === "system"
  ? Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
  : value;

const emptyForm = (timeZone: string, selection: PersistedModelSelection | null, responseMode: ResponseMode, outputContinuation: OutputContinuation): FormState => ({
  name: "",
  prompt: "",
  timeZone: resolvedTimeZone(timeZone),
  cadenceType: "daily",
  runAt: localDateTime(new Date(Date.now() + 3_600_000).toISOString()),
  localTime: "09:00",
  weekdays: [1],
  providerModel: selection ? `${selection.providerId}:${selection.modelId}` : "",
  responseMode,
  contextBudget: selection?.contextBudget ?? "auto",
  outputBudget: selection?.outputBudget ?? "auto",
  outputContinuation,
});

function scheduleForm(schedule: Schedule): FormState {
  return {
    name: schedule.name,
    prompt: schedule.prompt,
    timeZone: schedule.timeZone,
    cadenceType: schedule.cadence.type,
    runAt: schedule.cadence.type === "once" ? localDateTime(schedule.cadence.runAt) : localDateTime(new Date(Date.now() + 3_600_000).toISOString()),
    localTime: schedule.cadence.type === "once" ? "09:00" : schedule.cadence.localTime.slice(0, 5),
    weekdays: schedule.cadence.type === "weekly" ? schedule.cadence.weekdays : [1],
    providerModel: `${schedule.executionProfile.providerId}:${schedule.executionProfile.modelId}`,
    responseMode: schedule.executionProfile.responseMode,
    contextBudget: schedule.executionProfile.contextBudget,
    outputBudget: schedule.executionProfile.outputBudget,
    outputContinuation: schedule.executionProfile.outputContinuation,
  };
}

export function SchedulePage({ active, container, defaultTimeZone, modelSelection, modelChoices, responseMode, outputContinuation, onOpenConversation, onOverlayChange }: Props) {
  const { t, locale } = useI18n();
  const controller = useSchedules(active);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [form, setForm] = useState(() => emptyForm(defaultTimeZone, modelSelection, responseMode, outputContinuation));
  const [formError, setFormError] = useState<string | null>(null);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [mobile, setMobile] = useState(() => window.innerWidth <= 767);
  const openerRef = useRef<HTMLElement | null>(null);
  const historyOpenerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const resize = () => setMobile(window.innerWidth <= 767);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    onOverlayChange?.(editorOpen || historyId !== null);
  }, [editorOpen, historyId, onOverlayChange]);

  useEffect(() => () => onOverlayChange?.(false), [onOverlayChange]);

  const grouped = useMemo(() => ({
    active: controller.schedules.filter((item) => item.status === "active"),
    paused: controller.schedules.filter((item) => item.status === "paused"),
    completed: controller.schedules.filter((item) => item.status === "completed"),
  }), [controller.schedules]);

  const modelOptions = modelChoices.map((choice) => ({
    value: `${choice.selection.providerId}:${choice.selection.modelId}`,
    label: choice.label,
  }));
  if (editing && !modelOptions.some((option) => option.value === form.providerModel)) {
    modelOptions.push({
      value: form.providerModel,
      label: editing.executionProfile.modelId,
    });
  }

  const openEditor = (schedule: Schedule | null, opener: HTMLElement) => {
    openerRef.current = opener;
    setEditing(schedule);
    setForm(schedule ? scheduleForm(schedule) : emptyForm(defaultTimeZone, modelSelection, responseMode, outputContinuation));
    setFormError(null);
    setEditorOpen(true);
  };

  const closeEditor = () => {
    setEditorOpen(false);
    window.requestAnimationFrame(() => openerRef.current?.focus());
  };

  const save = async () => {
    const choice = modelChoices.find((item) => `${item.selection.providerId}:${item.selection.modelId}` === form.providerModel);
    const onceTime = form.cadenceType === "once" ? new Date(form.runAt) : null;
    if (!form.name.trim() || !form.prompt.trim() || !form.timeZone.trim() || !choice || (onceTime && Number.isNaN(onceTime.getTime())) || (form.cadenceType === "weekly" && form.weekdays.length === 0)) {
      setFormError(t("schedules.error.invalid"));
      return;
    }
    const cadence: ScheduleCadence = form.cadenceType === "once"
      ? { type: "once", runAt: onceTime!.toISOString() }
      : form.cadenceType === "daily"
        ? { type: "daily", localTime: form.localTime }
        : { type: "weekly", localTime: form.localTime, weekdays: [...form.weekdays].sort() };
    const fields: ScheduleFields = {
      name: form.name,
      prompt: form.prompt,
      timeZone: form.timeZone,
      cadence,
      executionProfile: {
        providerId: choice.selection.providerId,
        modelId: choice.selection.modelId,
        responseMode: form.responseMode,
        contextBudget: form.contextBudget,
        outputBudget: form.outputBudget,
        outputContinuation: form.outputContinuation,
      },
    };
    try {
      if (editing) await controller.update(editing, fields);
      else await controller.create(fields);
      closeEditor();
    } catch (error) {
      setFormError(t(error instanceof ScheduleApiError && error.code === "revision_conflict" ? "schedules.error.conflict" : "schedules.error.save"));
    }
  };

  const formatDate = (value: string | null) => value ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: resolvedTimeZone(defaultTimeZone) }).format(new Date(value)) : t("schedules.none");
  const cadenceText = (item: Schedule) => item.cadence.type === "once"
    ? t("schedules.cadence.onceAt", { time: formatDate(item.cadence.runAt) })
    : item.cadence.type === "daily"
      ? t("schedules.cadence.dailyAt", { time: item.cadence.localTime.slice(0, 5) })
      : t("schedules.cadence.weeklyAt", { days: item.cadence.weekdays.map((day) => t(`schedules.weekday.${day}` as never)).join("、"), time: item.cadence.localTime.slice(0, 5) });

  const errorText = controller.error instanceof ScheduleApiError
    ? t(`schedules.error.${controller.error.code}` as never)
    : controller.error ? t("schedules.error.load") : null;

  const editor = <ScheduleEditor container={container} form={form} setForm={setForm} modelOptions={modelOptions} saving={controller.saving} error={formError} onCancel={closeEditor} onSave={() => void save()} />;

  return <section className="schedules-settings" aria-label={t("settings.category.schedules")}>
    <div className="schedules-toolbar">
      <Button type="primary" icon={<PlusOutlined />} onClick={(event) => openEditor(null, event.currentTarget)} disabled={!modelSelection}>{t("schedules.create")}</Button>
    </div>
    {controller.runtimeStatus?.continuity !== "linger_enabled" ? <div className="schedules-warning" role="status">{t(controller.runtimeStatus?.platform === "linux" ? "schedules.warning.linux" : "schedules.warning.windows")}</div> : null}
    {errorText ? <div className="schedules-error" role="alert"><span>{errorText}</span><Button onClick={() => void controller.refresh()}>{t("common.retry")}</Button></div> : null}
    {controller.loading ? <p className="schedules-state" role="status">{t("schedules.loading")}</p> : null}
    {!controller.loading && controller.schedules.length === 0 ? <div className="schedules-empty"><CalendarOutlined /><h2>{t("schedules.emptyTitle")}</h2><p>{t("schedules.emptyDescription")}</p></div> : null}
    {(["active", "paused", "completed"] as const).map((status) => grouped[status].length ? <section className="schedule-group" key={status}><h2>{t(`schedules.group.${status}` as never)} <span>{grouped[status].length}</span></h2><div className="schedule-grid">{grouped[status].map((item) => <article className="schedule-card" key={item.id}>
      <div className="schedule-card__top"><div><h3>{item.name}</h3><p>{cadenceText(item)}</p></div><Tag color={item.status === "active" ? "green" : item.status === "paused" ? "gold" : "default"}>{t(`schedules.status.${item.status}` as never)}</Tag></div>
      <p className="schedule-card__prompt">{item.prompt}</p>
      <dl><div><dt>{t("schedules.nextRun")}</dt><dd>{formatDate(item.nextRunAt)}</dd></div><div><dt>{t("schedules.model")}</dt><dd>{modelChoices.find((choice) => choice.selection.modelId === item.executionProfile.modelId)?.label ?? item.executionProfile.modelId}</dd></div><div><dt>{t("schedules.latestRun")}</dt><dd>{item.latestOccurrence ? t(`schedules.occurrence.${item.latestOccurrence.status}` as never) : t("schedules.none")}</dd></div></dl>
      <div className="schedule-card__actions">
        <Button icon={<PlayCircleOutlined />} onClick={() => void controller.runNow(item).catch(() => undefined)} disabled={controller.saving}>{t("schedules.runNow")}</Button>
        {item.status === "active" ? <Button icon={<PauseCircleOutlined />} onClick={() => void controller.pause(item).catch(() => undefined)} disabled={controller.saving}>{t("schedules.pause")}</Button> : item.status === "paused" ? <Button icon={<PlayCircleOutlined />} onClick={() => void controller.resume(item).catch(() => undefined)} disabled={controller.saving}>{t("schedules.resume")}</Button> : null}
        <Button icon={<EditOutlined />} onClick={(event) => openEditor(item, event.currentTarget)}>{t("schedules.edit")}</Button>
        <Button icon={<HistoryOutlined />} onClick={(event) => { historyOpenerRef.current = event.currentTarget; setHistoryId(item.id); void controller.loadOccurrences(item.id); }}>{t("schedules.history")}</Button>
        {item.conversationId ? <Button onClick={() => onOpenConversation(item.conversationId!)}>{t("schedules.openConversation")}</Button> : null}
        <Popconfirm getPopupContainer={() => container ?? document.body} title={t("schedules.deleteConfirm")} description={t("schedules.deleteDescription")} okText={t("common.remove")} cancelText={t("common.cancel")} onConfirm={() => controller.remove(item).catch(() => undefined)}><Button danger>{t("common.remove")}</Button></Popconfirm>
      </div>
    </article>)}</div></section> : null)}
    {mobile ? <Drawer getContainer={container ?? false} rootStyle={container ? { position: "absolute" } : undefined} open={editorOpen} placement="right" size="100vw" title={editing ? t("schedules.editTitle") : t("schedules.createTitle")} onClose={closeEditor} destroyOnHidden>{editor}</Drawer> : <Modal rootClassName="schedule-editor-modal" getContainer={container ?? false} open={editorOpen} title={editing ? t("schedules.editTitle") : t("schedules.createTitle")} footer={null} onCancel={closeEditor} destroyOnHidden>{editor}</Modal>}
    <Drawer getContainer={container ?? false} rootStyle={container ? { position: "absolute" } : undefined} open={historyId !== null} placement="right" size={mobile ? "100vw" : 480} title={t("schedules.historyTitle")} onClose={() => { setHistoryId(null); window.requestAnimationFrame(() => historyOpenerRef.current?.focus()); }}><OccurrenceHistory items={historyId ? controller.occurrences[historyId] ?? [] : []} formatDate={formatDate} /></Drawer>
  </section>;
}

function ScheduleEditor({ container, form, setForm, modelOptions, saving, error, onCancel, onSave }: { container: HTMLElement | null; form: FormState; setForm: (next: FormState) => void; modelOptions: { value: string; label: string }[]; saving: boolean; error: string | null; onCancel: () => void; onSave: () => void }) {
  const { t } = useI18n();
  const patch = (next: Partial<FormState>) => setForm({ ...form, ...next });
  const popupContainer = (trigger: HTMLElement) => container ?? trigger.parentElement ?? document.body;
  return <form className="schedule-editor" onSubmit={(event) => { event.preventDefault(); onSave(); }}>
    <label>{t("schedules.field.name")}<Input value={form.name} maxLength={120} onChange={(event) => patch({ name: event.target.value })} /></label>
    <label>{t("schedules.field.prompt")}<Input.TextArea value={form.prompt} rows={7} maxLength={32768} showCount onChange={(event) => patch({ prompt: event.target.value })} /></label>
    <label>{t("schedules.field.cadence")}<Select getPopupContainer={popupContainer} value={form.cadenceType} options={["once", "daily", "weekly"].map((value) => ({ value, label: t(`schedules.cadence.${value}` as never) }))} onChange={(cadenceType) => patch({ cadenceType })} /></label>
    {form.cadenceType === "once" ? <label>{t("schedules.field.runAt")}<Input type="datetime-local" value={form.runAt} onChange={(event) => patch({ runAt: event.target.value })} /></label> : <label>{t("schedules.field.localTime")}<Input type="time" value={form.localTime} onChange={(event) => patch({ localTime: event.target.value })} /></label>}
    {form.cadenceType === "weekly" ? <fieldset><legend>{t("schedules.field.weekdays")}</legend><div className="schedule-weekdays">{[1,2,3,4,5,6,7].map((day) => <button type="button" aria-pressed={form.weekdays.includes(day)} className={form.weekdays.includes(day) ? "is-selected" : ""} key={day} onClick={() => patch({ weekdays: form.weekdays.includes(day) ? form.weekdays.filter((item) => item !== day) : [...form.weekdays, day] })}>{t(`schedules.weekday.${day}` as never)}</button>)}</div></fieldset> : null}
    <label>{t("schedules.field.timeZone")}<Input value={form.timeZone} onChange={(event) => patch({ timeZone: event.target.value })} /></label>
    <label>{t("schedules.field.model")}<Select getPopupContainer={popupContainer} showSearch value={form.providerModel || undefined} options={modelOptions} onChange={(providerModel) => patch({ providerModel })} /></label>
    <label>{t("models.responseMode")}<Select getPopupContainer={popupContainer} value={form.responseMode} options={(["default", "fast", "balanced", "deep"] as const).map((value) => ({ value, label: t(`models.response.${value}`) }))} onChange={(value) => patch({ responseMode: value })} /></label>
    <label>{t("models.contextBudget")}<Select getPopupContainer={popupContainer} value={form.contextBudget} options={(["auto", "32k", "64k", "128k", "256k", "max"] as const).map((value) => ({ value, label: t(`models.context.${value}`) }))} onChange={(value) => patch({ contextBudget: value })} /></label>
    <label>{t("models.outputBudget")}<Select getPopupContainer={popupContainer} value={form.outputBudget} options={(["auto", "8k", "16k", "32k", "64k", "max"] as const).map((value) => ({ value, label: t(`models.output.${value}`) }))} onChange={(value) => patch({ outputBudget: value })} /></label>
    <label>{t("models.outputContinuation")}<Select getPopupContainer={popupContainer} value={form.outputContinuation} options={(["off", "1", "2", "3", "5", "10", "20", "50", "unlimited"] as const).map((value) => ({ value, label: t(value === "off" || value === "unlimited" ? `models.outputContinuation.${value}` : `models.outputContinuation.${({ "1": "one", "2": "two", "3": "three", "5": "five", "10": "ten", "20": "twenty", "50": "fifty" } as const)[value]}`) }))} onChange={(value) => patch({ outputContinuation: value })} /></label>
    {error ? <p className="schedule-editor__error" role="alert">{error}</p> : null}
    <div className="schedule-editor__actions"><Button onClick={onCancel}>{t("common.cancel")}</Button><Button type="primary" htmlType="submit" loading={saving}>{t("schedules.save")}</Button></div>
  </form>;
}

function OccurrenceHistory({ items, formatDate }: { items: ReturnType<typeof useSchedules>["occurrences"][string]; formatDate: (value: string | null) => string }) {
  const { t } = useI18n();
  if (items.length === 0) return <p className="schedules-state">{t("schedules.noHistory")}</p>;
  return <ol className="occurrence-list">{items.map((item) => <li key={item.id}><div><strong>{t(`schedules.occurrence.${item.status}` as never)}</strong><span>{formatDate(item.scheduledFor)}</span></div>{item.errorCode ? <p>{t("schedules.reason", { reason: item.errorCode })}</p> : null}{item.missedCount ? <p>{t("schedules.missedCount", { count: item.missedCount })}</p> : null}</li>)}</ol>;
}
