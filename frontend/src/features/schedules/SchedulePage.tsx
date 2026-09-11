import { useEffect, useMemo, useRef, useState } from "react";
import {
  CloseCircleOutlined,
  EditOutlined,
  MoreOutlined,
  ReloadOutlined,
  PlusOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Dropdown, Input, Modal, Pagination, Select, Switch, Tag, Tooltip } from "antd";

import type { ContextBudget, OutputBudget, OutputContinuation, PersistedModelSelection, ResponseMode } from "../../api/aiSettings";
import { ScheduleApiError, type Schedule, type ScheduleCadence, type ScheduleFields, type ScheduleStatus } from "../../api/schedules";
import type { ModelChoice } from "../ai-settings/modelCatalog";
import { DEFAULT_WORKSPACE_ID } from "../../api/agentChat";
import type { Workspace } from "../../api/workspaces";
import { workspaceName } from "../workspaces/WorkspaceSwitcher";
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
  activeWorkspaceId?: string;
  workspaces?: readonly Workspace[];
  workspaceLoading?: boolean;
  workspaceError?: boolean;
  onWorkspaceRetry?: () => void;
};

type FormState = {
  workspaceId: string;
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

const emptyForm = (timeZone: string, selection: PersistedModelSelection | null, responseMode: ResponseMode, outputContinuation: OutputContinuation, workspaceId: string): FormState => ({
  workspaceId,
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
    workspaceId: schedule.workspaceId,
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

export function SchedulePage({ active, container, defaultTimeZone, modelSelection, modelChoices, responseMode, outputContinuation, onOpenConversation, onOverlayChange, activeWorkspaceId = DEFAULT_WORKSPACE_ID, workspaces = [], workspaceLoading = false, workspaceError = false, onWorkspaceRetry }: Props) {
  const { t, locale } = useI18n();
  const controller = useSchedules(active);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [form, setForm] = useState(() => emptyForm(defaultTimeZone, modelSelection, responseMode, outputContinuation, activeWorkspaceId));
  const [formError, setFormError] = useState<string | null>(null);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [removing, setRemoving] = useState<Schedule | null>(null);
  const [query, setQuery] = useState("");
  const [workspaceFilter, setWorkspaceFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<"all" | ScheduleStatus>("all");
  const [page, setPage] = useState(1);
  const menuOpeners = useRef<Record<string, HTMLElement | null>>({});
  const [mobile, setMobile] = useState(() => window.innerWidth <= 767);
  const openerRef = useRef<HTMLElement | null>(null);
  const historyOpenerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const resize = () => setMobile(window.innerWidth <= 767);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    onOverlayChange?.(editorOpen || historyId !== null || removing !== null);
  }, [editorOpen, historyId, removing, onOverlayChange]);

  useEffect(() => () => onOverlayChange?.(false), [onOverlayChange]);

  const filtered = useMemo(() => {
    const search = query.trim().normalize("NFC").toLowerCase();
    return controller.schedules.filter((item) => item.name.normalize("NFC").toLowerCase().includes(search)
      && (workspaceFilter === "all" || item.workspaceId === workspaceFilter)
      && (statusFilter === "all" || item.status === statusFilter));
  }, [controller.schedules, query, workspaceFilter, statusFilter]);
  const currentPage = Math.min(page, Math.max(1, Math.ceil(filtered.length / 20)));
  const blocked = controller.saving || controller.loading || controller.refreshFailed;

  const modelOptions = modelChoices.map((choice) => ({
    value: `${choice.selection.providerId}:${choice.selection.modelId}`,
    label: choice.label,
  }));
  const workspaceDisplayName = (item: Workspace) => workspaceName(item.kind, item.name, t("workspaces.default"));
  const workspaceReason = (item: Workspace) => item.unavailableReason
    ? t(`workspaces.unavailableReason.${item.unavailableReason}` as never)
    : t("workspaces.unavailable");
  const workspaceLabel = (item: Workspace) => item.availability === "unavailable"
    ? t("schedules.workspaceUnavailableLabel", { name: workspaceDisplayName(item), reason: workspaceReason(item) })
    : workspaceDisplayName(item);
  const workspaceOptions = workspaces.map((item) => ({
    value: item.id,
    label: workspaceLabel(item),
  }));
  const workspaceFallbackLabel = t(workspaceError ? "schedules.workspaceLoadError" : workspaceLoading ? "schedules.workspaceLoading" : "schedules.workspaceMissing");
  if (!workspaceOptions.some((option) => option.value === form.workspaceId)) {
    workspaceOptions.push({ value: form.workspaceId, label: workspaceFallbackLabel });
  }
  if (editing && !modelOptions.some((option) => option.value === form.providerModel)) {
    modelOptions.push({
      value: form.providerModel,
      label: editing.executionProfile.modelId,
    });
  }

  const openEditor = (schedule: Schedule | null, opener: HTMLElement) => {
    openerRef.current = opener;
    setEditing(schedule);
    setForm(schedule ? scheduleForm(schedule) : emptyForm(defaultTimeZone, modelSelection, responseMode, outputContinuation, activeWorkspaceId));
    setFormError(null);
    setEditorOpen(true);
  };

  const closeEditor = () => {
    if (controller.saving) return;
    setEditorOpen(false);
    window.requestAnimationFrame(() => openerRef.current?.focus());
  };

  const save = async () => {
    if (blocked) return;
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
      workspaceId: form.workspaceId,
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

  const displayZone = resolvedTimeZone(defaultTimeZone);
  const formatDate = (value: string | null, timeZone = displayZone) => value ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(value)) : t("schedules.none");
  const cadenceText = (item: Schedule) => item.cadence.type === "once"
    ? t("schedules.cadence.onceAt", { time: formatDate(item.cadence.runAt, item.timeZone) })
    : item.cadence.type === "daily"
      ? t("schedules.cadence.dailyAt", { time: item.cadence.localTime.slice(0, 5) })
      : t("schedules.cadence.weeklyAt", { days: item.cadence.weekdays.map((day) => t(`schedules.weekday.${day}` as never)).join("、"), time: item.cadence.localTime.slice(0, 5) });

  const errorText = controller.error instanceof ScheduleApiError
    ? t(`schedules.error.${controller.error.code}` as never)
    : controller.error ? t("schedules.error.load") : null;

  const editor = <ScheduleEditor container={container} form={form} setForm={setForm} modelOptions={modelOptions} workspaceOptions={workspaceOptions} saving={controller.saving} error={formError} onCancel={closeEditor} onSave={() => void save()} />;

  return <section className="schedules-settings" aria-label={t("settings.category.schedules")}>
    <div className="schedules-toolbar">
      <Tooltip title={t("schedules.refresh")}><Button aria-label={t("schedules.refresh")} icon={<ReloadOutlined />} loading={controller.loading} disabled={controller.saving} onClick={() => void controller.refresh()} /></Tooltip>
      <Button type="primary" icon={<PlusOutlined />} onClick={(event) => openEditor(null, event.currentTarget)} disabled={!modelSelection || workspaceLoading || workspaceError || blocked}>{t("schedules.create")}</Button>
    </div>
    {controller.runtimeStatus && controller.runtimeStatus.continuity !== "linger_enabled" ? <details className="schedules-warning"><summary>{t("schedules.runtimeHint")}</summary><p>{t(controller.runtimeStatus.platform === "linux" ? "schedules.warning.linux" : "schedules.warning.windows")}</p></details> : null}
    {workspaceError ? <div className="schedules-error" role="alert"><span>{t("schedules.workspaceLoadError")}</span>{onWorkspaceRetry ? <Button loading={workspaceLoading} disabled={workspaceLoading} onClick={onWorkspaceRetry}>{t("common.retry")}</Button> : null}</div> : null}
    {errorText ? <div className="schedules-error" role="alert"><div>{errorText}{controller.mutationRefreshFailed ? <p>{t("schedules.savedRefreshFailed")}</p> : controller.refreshFailed && controller.schedules.length > 0 ? <p>{t("schedules.stale")}</p> : null}</div><Button disabled={controller.saving} loading={controller.loading} onClick={() => void controller.refresh()}>{t("common.retry")}</Button></div> : null}
    <div className="schedules-filters">
      <Input aria-label={t("schedules.search")} placeholder={t("schedules.search")} value={query} allowClear={{ clearIcon: <CloseCircleOutlined aria-label={t("schedules.clearSearch")} /> }} onChange={(event) => { setQuery(event.target.value); setPage(1); }} />
      <Select aria-label={t("schedules.filterWorkspace")} getPopupContainer={() => container ?? document.body} value={workspaceFilter} options={[{ value: "all", label: t("schedules.allWorkspaces") }, ...workspaces.map((item) => ({ value: item.id, label: workspaceDisplayName(item) }))]} onChange={(value) => { setWorkspaceFilter(value); setPage(1); }} />
      <Select aria-label={t("schedules.filterStatus")} getPopupContainer={() => container ?? document.body} value={statusFilter} options={[{ value: "all", label: t("schedules.allStatuses") }, ...(["active", "paused", "completed"] as const).map((value) => ({ value, label: t(`schedules.status.${value}`) }))]} onChange={(value: "all" | ScheduleStatus) => { setStatusFilter(value); setPage(1); }} />
    </div>
    <p className="schedules-count">{t("schedules.results", { count: filtered.length, total: controller.schedules.length })}</p>
    <p className="schedules-zone">{t("schedules.displayZone", { zone: displayZone })}</p>
    {controller.loading ? <p className="schedules-state" role="status">{t("schedules.loading")}</p> : null}
    {!controller.loading && !errorText && controller.schedules.length === 0 ? <p className="schedules-state">{t("schedules.emptyTitle")}</p> : null}
    {controller.schedules.length > 0 && filtered.length === 0 ? <p className="schedules-state">{t("schedules.noMatches")}</p> : null}
    <div className="schedule-list">{filtered.slice((currentPage - 1) * 20, currentPage * 20).map((item) => {
      const workspace = workspaces.find((candidate) => candidate.id === item.workspaceId);
      const workspaceMissing = !workspaceLoading && !workspaceError && workspaces.length > 0 && !workspace;
      const workspaceWarning = workspace?.availability === "unavailable"
        ? t("schedules.workspaceUnavailableWarning", { reason: workspaceReason(workspace) })
        : workspaceMissing ? t("schedules.workspaceMissingWarning") : null;
      return <article className="schedule-card" key={item.id}>
        <div className="schedule-card__top">
          <div><h3>{item.name}</h3><p><span>{workspace ? workspaceLabel(workspace) : workspaceFallbackLabel}</span> · {cadenceText(item)} · {item.timeZone}</p></div>
          <div className="schedule-card__actions">
            {item.status === "completed" ? <Tag>{t("schedules.status.completed")}</Tag> : <Tooltip title={t("schedules.pauseHint")}><Switch checked={item.status === "active"} aria-label={t("schedules.toggle", { name: item.name })} disabled={blocked} onChange={(enabled) => void (enabled ? controller.resume(item) : controller.pause(item)).catch(() => undefined)} /></Tooltip>}
            <Tooltip title={t("schedules.edit")}><Button type="text" icon={<EditOutlined />} aria-label={t("schedules.editItem", { name: item.name })} disabled={blocked || workspaceLoading || workspaceError} onClick={(event) => openEditor(item, event.currentTarget)} /></Tooltip>
            <Dropdown trigger={["click"]} getPopupContainer={() => container ?? document.body} menu={{ items: [
              { key: "run", label: t("schedules.runNow"), disabled: blocked },
              { key: "history", label: t("schedules.history") },
              ...(item.conversationId ? [{ key: "conversation", label: t("schedules.openConversation") }] : []),
              { type: "divider" },
              { key: "remove", label: t("common.remove"), danger: true, disabled: blocked },
            ], onClick: ({ key }) => {
              if (key === "run" && !blocked) void controller.runNow(item).catch(() => undefined);
              if (key === "history") { historyOpenerRef.current = menuOpeners.current[item.id]; setHistoryId(item.id); void controller.loadOccurrences(item.id); }
              if (key === "conversation" && item.conversationId) onOpenConversation(item.conversationId);
              if (key === "remove" && !blocked) setRemoving(item);
            } }}><Button type="text" icon={<MoreOutlined />} aria-label={t("schedules.more", { name: item.name })} ref={(node) => { menuOpeners.current[item.id] = node; }} /></Dropdown>
          </div>
        </div>
        {workspaceWarning ? <p className="schedule-card__workspace-warning" role="status"><WarningOutlined aria-hidden="true" />{workspaceWarning}</p> : null}
        <div className="schedule-card__summary"><span>{t("schedules.nextRun")}：{item.status === "paused" ? t("schedules.pausedNext") : item.status === "completed" ? t("schedules.status.completed") : formatDate(item.nextRunAt)}</span><span>{t("schedules.latestRun")}：{item.latestOccurrence ? <Tag color={item.latestOccurrence.status === "failed" ? "error" : item.latestOccurrence.status === "completed" ? "success" : "default"}>{t(`schedules.occurrence.${item.latestOccurrence.status}`)}</Tag> : t("schedules.none")}</span></div>
        <details className="schedule-card__details"><summary>{t("schedules.details")}</summary>
          <p className="schedule-card__prompt">{item.prompt}</p>
          <dl><div><dt>{t("schedules.model")}</dt><dd>{modelChoices.find((choice) => choice.selection.providerId === item.executionProfile.providerId && choice.selection.modelId === item.executionProfile.modelId)?.label ?? item.executionProfile.modelId} · {item.executionProfile.providerId}</dd></div>
          <div><dt>{t("models.responseMode")}</dt><dd>{t(`models.response.${item.executionProfile.responseMode}`)}</dd></div>
          <div><dt>{t("models.contextBudget")}</dt><dd>{item.executionProfile.contextBudget}</dd></div><div><dt>{t("models.outputBudget")}</dt><dd>{item.executionProfile.outputBudget}</dd></div></dl>
        </details>
      </article>;
    })}</div>
    <Pagination current={currentPage} pageSize={20} total={filtered.length} hideOnSinglePage showSizeChanger={false} onChange={setPage} />
    <Modal open={removing !== null} title={t("schedules.deleteConfirm")} getContainer={container ?? false} confirmLoading={controller.saving} okText={t("common.remove")} cancelText={t("common.cancel")} okButtonProps={{ danger: true, disabled: blocked }} onCancel={() => { if (!controller.saving) { const id = removing?.id; setRemoving(null); requestAnimationFrame(() => { if (id) menuOpeners.current[id]?.focus(); }); } }} onOk={() => { if (removing && !blocked) void controller.remove(removing).then(() => setRemoving(null)).catch(() => undefined); }}><p>{removing?.name}</p><p>{t("schedules.deleteDescription")}</p></Modal>
    {mobile ? <Drawer getContainer={container ?? false} rootStyle={container ? { position: "absolute" } : undefined} open={editorOpen} placement="right" size="100vw" title={editing ? t("schedules.editTitle") : t("schedules.createTitle")} onClose={closeEditor} destroyOnHidden>{editor}</Drawer> : <Modal rootClassName="schedule-editor-modal" getContainer={container ?? false} open={editorOpen} title={editing ? t("schedules.editTitle") : t("schedules.createTitle")} footer={null} onCancel={closeEditor} destroyOnHidden>{editor}</Modal>}
    <Drawer getContainer={container ?? false} rootStyle={container ? { position: "absolute" } : undefined} open={historyId !== null} placement="right" size={mobile ? "100vw" : 480} title={t("schedules.historyTitle")} onClose={() => { setHistoryId(null); window.requestAnimationFrame(() => historyOpenerRef.current?.focus()); }}><p className="schedules-zone">{t("schedules.displayZone", { zone: displayZone })}</p><OccurrenceHistory items={historyId ? controller.occurrences[historyId] : undefined} loading={historyId ? controller.historyLoading[historyId] : false} error={historyId ? controller.historyErrors[historyId] : null} onRetry={() => { if (historyId) void controller.loadOccurrences(historyId); }} formatDate={formatDate} /></Drawer>
  </section>;
}

function ScheduleEditor({ container, form, setForm, modelOptions, workspaceOptions, saving, error, onCancel, onSave }: { container: HTMLElement | null; form: FormState; setForm: (next: FormState) => void; modelOptions: { value: string; label: string }[]; workspaceOptions: { value: string; label: string }[]; saving: boolean; error: string | null; onCancel: () => void; onSave: () => void }) {
  const { t } = useI18n();
  const patch = (next: Partial<FormState>) => setForm({ ...form, ...next });
  const popupContainer = (trigger: HTMLElement) => container ?? trigger.parentElement ?? document.body;
  return <form className="schedule-editor" onSubmit={(event) => { event.preventDefault(); onSave(); }}>
    <fieldset disabled={saving} className="schedule-editor-section"><legend>{t("schedules.section.task")}</legend>
    <label>{t("schedules.field.workspace")}<Select disabled={saving} aria-label={t("schedules.field.workspace")} getPopupContainer={popupContainer} value={form.workspaceId} options={workspaceOptions} onChange={(workspaceId) => patch({ workspaceId })} /></label>
    <label>{t("schedules.field.name")}<Input value={form.name} maxLength={120} onChange={(event) => patch({ name: event.target.value })} /></label>
    <label>{t("schedules.field.prompt")}<Input.TextArea value={form.prompt} rows={7} maxLength={32768} showCount onChange={(event) => patch({ prompt: event.target.value })} /></label>
    </fieldset>
    <fieldset disabled={saving} className="schedule-editor-section"><legend>{t("schedules.section.time")}</legend>
    <label>{t("schedules.field.cadence")}<Select disabled={saving} getPopupContainer={popupContainer} value={form.cadenceType} options={["once", "daily", "weekly"].map((value) => ({ value, label: t(`schedules.cadence.${value}` as never) }))} onChange={(cadenceType) => patch({ cadenceType })} /></label>
    {form.cadenceType === "once" ? <label>{t("schedules.field.runAt")}<Input type="datetime-local" value={form.runAt} onChange={(event) => patch({ runAt: event.target.value })} /></label> : <label>{t("schedules.field.localTime")}<Input type="time" value={form.localTime} onChange={(event) => patch({ localTime: event.target.value })} /></label>}
    {form.cadenceType === "weekly" ? <fieldset><legend>{t("schedules.field.weekdays")}</legend><div className="schedule-weekdays">{[1,2,3,4,5,6,7].map((day) => <button type="button" aria-pressed={form.weekdays.includes(day)} className={form.weekdays.includes(day) ? "is-selected" : ""} key={day} onClick={() => patch({ weekdays: form.weekdays.includes(day) ? form.weekdays.filter((item) => item !== day) : [...form.weekdays, day] })}>{t(`schedules.weekday.${day}` as never)}</button>)}</div></fieldset> : null}
    <label>{t("schedules.field.timeZone")}<Input value={form.timeZone} onChange={(event) => patch({ timeZone: event.target.value })} /></label>
    {form.cadenceType === "once" ? <p className="schedules-zone">{t("schedules.onceZone", { zone: Intl.DateTimeFormat().resolvedOptions().timeZone })}</p> : null}
    </fieldset>
    <fieldset disabled={saving} className="schedule-editor-section"><legend>{t("schedules.section.execution")}</legend>
    <label>{t("schedules.field.model")}<Select disabled={saving} getPopupContainer={popupContainer} showSearch value={form.providerModel || undefined} options={modelOptions} onChange={(providerModel) => patch({ providerModel })} /></label>
    <details className="schedule-editor-advanced"><summary>{t("schedules.advanced")}</summary>
    <label>{t("models.responseMode")}<Select disabled={saving} getPopupContainer={popupContainer} value={form.responseMode} options={(["default", "fast", "balanced", "deep"] as const).map((value) => ({ value, label: t(`models.response.${value}`) }))} onChange={(value) => patch({ responseMode: value })} /></label>
    <label>{t("models.contextBudget")}<Select disabled={saving} getPopupContainer={popupContainer} value={form.contextBudget} options={(["auto", "32k", "64k", "128k", "256k", "max"] as const).map((value) => ({ value, label: t(`models.context.${value}`) }))} onChange={(value) => patch({ contextBudget: value })} /></label>
    <label>{t("models.outputBudget")}<Select disabled={saving} getPopupContainer={popupContainer} value={form.outputBudget} options={(["auto", "8k", "16k", "32k", "64k", "max"] as const).map((value) => ({ value, label: t(`models.output.${value}`) }))} onChange={(value) => patch({ outputBudget: value })} /></label>
    <label>{t("models.outputContinuation")}<Select disabled={saving} getPopupContainer={popupContainer} value={form.outputContinuation} options={(["off", "1", "2", "3", "5", "10", "20", "50", "unlimited"] as const).map((value) => ({ value, label: t(value === "off" || value === "unlimited" ? `models.outputContinuation.${value}` : `models.outputContinuation.${({ "1": "one", "2": "two", "3": "three", "5": "five", "10": "ten", "20": "twenty", "50": "fifty" } as const)[value]}`) }))} onChange={(value) => patch({ outputContinuation: value })} /></label>
    </details></fieldset>
    {error ? <p className="schedule-editor__error" role="alert">{error}</p> : null}
    <div className="schedule-editor__actions"><Button disabled={saving} onClick={onCancel}>{t("common.cancel")}</Button><Button type="primary" htmlType="submit" loading={saving} disabled={saving}>{t("schedules.save")}</Button></div>
  </form>;
}

function OccurrenceHistory({ items, loading, error, onRetry, formatDate }: { items: ReturnType<typeof useSchedules>["occurrences"][string] | undefined; loading: boolean | undefined; error: unknown; onRetry: () => void; formatDate: (value: string | null) => string }) {
  const { t } = useI18n();
  return <>
    {loading || (!items && !error) ? <p role="status">{t("schedules.loading")}</p> : null}
    {error ? <div role="alert"><p>{t("schedules.historyError")}</p><Button loading={loading} onClick={onRetry}>{t("common.retry")}</Button></div> : null}
    {!loading && !error && items?.length === 0 ? <p className="schedules-state">{t("schedules.noHistory")}</p> : null}
    <ol className="occurrence-list">{items?.map((item) => <li key={item.id}><div><strong>{t(`schedules.occurrence.${item.status}` as never)}</strong><span>{formatDate(item.scheduledFor)}</span></div><p>{t(item.trigger === "manual" ? "schedules.trigger.manual" : "schedules.trigger.scheduled")}</p><p>{t("schedules.started")}：{formatDate(item.startedAt)}</p><p>{t("schedules.finished")}：{formatDate(item.finishedAt)}</p>{item.errorCode ? <p>{t("schedules.reason", { reason: item.errorCode })}</p> : null}{item.missedCount ? <p>{t("schedules.missedCount", { count: item.missedCount })}</p> : null}</li>)}</ol>
  </>;
}
