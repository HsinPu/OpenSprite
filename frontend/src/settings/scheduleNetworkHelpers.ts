import type { NetworkForm } from "../composables/networkDefaults";
import type { ScheduleForm, ScheduleState } from "../composables/scheduleDefaults";

type ScheduleTimezoneState = {
  schedule: ScheduleState;
  scheduleForm: ScheduleForm;
};

type NetworkSummaryCopy = {
  settings: {
    network?: {
      noProxyConfigured?: string;
      proxyConfigured?: (active: number) => string;
    };
  };
};

type NetworkSummaryState = {
  networkForm?: Partial<NetworkForm>;
};

export function scheduleTimezoneOptions(state: ScheduleTimezoneState): string[] {
  const configured = Array.isArray(state.schedule.common_timezones) ? state.schedule.common_timezones : [];
  const options = configured.map((timezone) => String(timezone || "").trim()).filter(Boolean);
  const current = String(state.scheduleForm.defaultTimezone || state.schedule.default_timezone || "UTC").trim() || "UTC";
  const uniqueOptions: string[] = Array.from(new Set<string>(options.length ? options : ["UTC"]));
  if (!uniqueOptions.includes(current)) {
    uniqueOptions.unshift(current);
  }
  return uniqueOptions;
}

export function networkSummary(copy: NetworkSummaryCopy, state: NetworkSummaryState): string {
  const form = state.networkForm || {};
  const active = [form.httpProxy, form.httpsProxy].map((value) => String(value || "").trim()).filter(Boolean).length;
  if (!active) {
    return copy.settings.network?.noProxyConfigured || "No proxy configured";
  }
  return typeof copy.settings.network?.proxyConfigured === "function"
    ? copy.settings.network.proxyConfigured(active)
    : `${active} proxy setting${active === 1 ? "" : "s"} configured`;
}
