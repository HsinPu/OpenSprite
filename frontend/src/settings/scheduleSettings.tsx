import { ArrowLeftOutlined, CloseOutlined, PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Form, Input, InputNumber, List, Select, Space, Switch, Tag } from "antd";
import { scheduleTimezoneOptions } from "./scheduleNetworkHelpers";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type AnyRecord = Record<string, any>;
type ValueRef<T> = { value: T };

type ScheduleSettingsClient = {
  copy: ValueRef<AnyRecord>;
  settingsState: AnyRecord;
  saveScheduleSettings: () => void;
  beginCronJobCreate: () => void;
  beginCronJobEdit: (job: AnyRecord) => void;
  runCronJobAction: (job: AnyRecord, action: string) => void;
  cancelCronJobEdit: () => void;
  saveCronJob: () => void;
};

export function ScheduleSettings({ client }: { client: ScheduleSettingsClient }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const scheduleCopy = copy.settings.schedule || {};
  const timezones = scheduleTimezoneOptions(state);
  const form = state.cronJobForm;

  return (
    <section className="settings-page">
      <SettingsStatus message={state.scheduleLoading ? scheduleCopy.loading || "Loading schedule settings..." : ""} />
      <SettingsStatus message={state.scheduleNotice} />
      <SettingsStatus message={state.scheduleError} type="error" />

      <SettingsSectionTitle>{scheduleCopy.defaultsTitle || "Schedule defaults"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={scheduleCopy.defaultTimezone?.title || "Default timezone"} description={scheduleCopy.defaultTimezone?.description || ""} className="settings-row--field">
          <Select
            value={state.scheduleForm.defaultTimezone}
            aria-label={scheduleCopy.defaultTimezone?.title || "Default timezone"}
            disabled={state.scheduleLoading}
            options={timezones.map((timezone) => ({ value: timezone, label: timezone }))}
            onChange={(value) => (state.scheduleForm.defaultTimezone = value)}
          />
        </SettingsRow>
        <SettingsRow title={scheduleCopy.currentTitle || "Currently active"} description={state.schedule.default_timezone || "UTC"}>
          <Button icon={<SaveOutlined />} loading={state.scheduleLoading} disabled={state.scheduleLoading} onClick={client.saveScheduleSettings}>
            {scheduleCopy.save || "Save"}
          </Button>
        </SettingsRow>
      </SettingsCard>

      <div className="schedule-list-screen__header">
        <SettingsSectionTitle>{scheduleCopy.manageTitle || "Manage schedules"}</SettingsSectionTitle>
        <Button type="primary" icon={<PlusOutlined />} onClick={client.beginCronJobCreate}>
          {scheduleCopy.openAdd || "Create schedule"}
        </Button>
      </div>
      <SettingsStatus message={state.cronJobsError} type="error" />

      <SettingsSectionTitle>{scheduleCopy.jobsTitle || "Schedules"}</SettingsSectionTitle>
      <SettingsStatus message={state.cronJobsLoading ? scheduleCopy.jobsLoading || "Loading schedules..." : ""} />
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list schedule-job-list"
          dataSource={state.cronJobs || []}
          locale={{
            emptyText: (
              <div className="provider-row provider-row--empty">
                <div>
                  <strong>{scheduleCopy.noJobsTitle || "No schedules yet"}</strong>
                  <span>{scheduleCopy.noJobsDescription || ""}</span>
                </div>
              </div>
            ),
          }}
          renderItem={(job: AnyRecord) => (
            <List.Item key={job.id} className="schedule-job-row">
              <div className="schedule-job-row__main">
                <div className="provider-row__title">
                  <strong>{job.name || job.id}</strong>
                  <Tag className="provider-row__badge">{job.enabled ? scheduleCopy.enabled || "Enabled" : scheduleCopy.paused || "Paused"}</Tag>
                </div>
                <span>{job.schedule?.display || job.cron_expr || job.every_seconds || ""}</span>
                {job.session_id ? <span>{typeof scheduleCopy.sessionLabel === "function" ? scheduleCopy.sessionLabel(job.session_id) : job.session_id}</span> : null}
                {job.state?.next_run_display ? <span>{typeof scheduleCopy.nextRun === "function" ? scheduleCopy.nextRun(job.state.next_run_display) : job.state.next_run_display}</span> : null}
                <p>{job.payload?.message || job.message || ""}</p>
              </div>
              <Space className="schedule-job-row__actions" wrap>
                <Button onClick={() => client.beginCronJobEdit(job)}>{scheduleCopy.edit || "Edit"}</Button>
                <Button disabled={state.cronJobsLoading} onClick={() => client.runCronJobAction(job, job.enabled ? "pause" : "enable")}>
                  {job.enabled ? scheduleCopy.pause || "Pause" : scheduleCopy.enable || "Enable"}
                </Button>
                <Button disabled={state.cronJobsLoading} onClick={() => client.runCronJobAction(job, "run")}>{scheduleCopy.runNow || "Run now"}</Button>
                <Button danger disabled={state.cronJobsLoading} onClick={() => client.runCronJobAction(job, "remove")}>{scheduleCopy.remove || "Remove"}</Button>
              </Space>
            </List.Item>
          )}
        />
      </SettingsCard>

      <SettingsSectionTitle>{scheduleCopy.usageTitle || "Usage"}</SettingsSectionTitle>
      <SettingsCard>
        <SettingsRow title={scheduleCopy.usageCron?.title || "Create scheduled jobs"} description={scheduleCopy.usageCron?.description || ""} />
        <SettingsRow title={scheduleCopy.usageExisting?.title || "Existing jobs"} description={scheduleCopy.usageExisting?.description || ""} />
      </SettingsCard>

      {form.showEditor ? (
        <div className="provider-connect-dialog" role="dialog" aria-modal="true">
          <header className="provider-connect-dialog__top">
            <Button type="text" aria-label={scheduleCopy.backToList || "Back"} icon={<ArrowLeftOutlined />} onClick={client.cancelCronJobEdit} />
            <Button type="text" aria-label={copy.settings.closeAria || "Close"} icon={<CloseOutlined />} onClick={client.cancelCronJobEdit} />
          </header>
          <Form className="provider-connect-dialog__body" layout="vertical" onFinish={() => client.saveCronJob()}>
            <div className="provider-connect-dialog__title">
              <span className="provider-row__mark" aria-hidden="true">SC</span>
              <h3>{form.jobId ? scheduleCopy.editJobTitle || "Edit schedule" : scheduleCopy.newJobTitle || "Create schedule"}</h3>
            </div>
            <p>{scheduleCopy.newJobDescription || ""}</p>
            <Form.Item className="provider-connect-field" label={scheduleCopy.jobName || "Name"}>
              <Input value={form.name} autoComplete="off" onChange={(event) => (form.name = event.target.value)} />
            </Form.Item>
            <Form.Item className="provider-connect-field" label={scheduleCopy.jobType || "Type"}>
              <Select
                value={form.mode}
                options={[
                  { value: "cron", label: scheduleCopy.jobTypes?.cron || "Cron expression" },
                  { value: "every", label: scheduleCopy.jobTypes?.every || "Fixed interval" },
                  { value: "at", label: scheduleCopy.jobTypes?.at || "Run once" },
                ]}
                onChange={(value) => (form.mode = value)}
              />
            </Form.Item>
            {form.mode === "every" ? (
              <Form.Item className="provider-connect-field" label={scheduleCopy.everySeconds || "Interval seconds"}>
                <InputNumber className="settings-control" value={Number(form.everySeconds || 3600)} min={1} step={1} onChange={(value) => (form.everySeconds = String(value || 3600))} />
              </Form.Item>
            ) : null}
            {form.mode === "cron" ? (
              <>
                <Form.Item className="provider-connect-field" label={scheduleCopy.cronExpression || "Cron expression"}>
                  <Input value={form.cronExpr} spellCheck={false} autoComplete="off" onChange={(event) => (form.cronExpr = event.target.value)} />
                </Form.Item>
                <Form.Item className="provider-connect-field" label={scheduleCopy.timezone || "Timezone"}>
                  <Select value={form.timezone} options={timezones.map((timezone) => ({ value: timezone, label: timezone }))} onChange={(value) => (form.timezone = value)} />
                </Form.Item>
              </>
            ) : null}
            {form.mode === "at" ? (
              <Form.Item className="provider-connect-field" label={scheduleCopy.runAt || "Run at"}>
                <Input value={form.at} type="datetime-local" onChange={(event) => (form.at = event.target.value)} />
              </Form.Item>
            ) : null}
            <Form.Item className="provider-connect-field" label={scheduleCopy.message || "Message"}>
              <Input.TextArea value={form.message} rows={3} spellCheck={false} onChange={(event) => (form.message = event.target.value)} />
            </Form.Item>
            <SettingsRow title={scheduleCopy.deliver?.title || "Send back to chat"} description={scheduleCopy.deliver?.description || ""} className="schedule-editor__deliver">
              <Switch aria-label={scheduleCopy.deliver?.title || "Deliver"} checked={Boolean(form.deliver)} onChange={(checked) => (form.deliver = checked)} />
            </SettingsRow>
            <Button className="provider-connect-dialog__submit" type="primary" htmlType="submit" loading={state.cronJobsLoading} disabled={state.cronJobsLoading}>
              {form.jobId ? scheduleCopy.updateJob || "Update schedule" : scheduleCopy.createJob || "Create schedule"}
            </Button>
          </Form>
        </div>
      ) : null}
    </section>
  );
}
