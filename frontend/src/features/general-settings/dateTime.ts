import type { TimeZoneSetting } from "../../api/generalSettings";

function timeZoneOption(timeZone: TimeZoneSetting): string | undefined {
  return timeZone === "system" ? undefined : timeZone;
}

function dateKey(value: Date, timeZone: TimeZoneSetting): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: timeZoneOption(timeZone),
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function isTodayInTimeZone(timestamp: string, timeZone: TimeZoneSetting, now: Date = new Date()): boolean {
  const value = new Date(timestamp);
  return !Number.isNaN(value.getTime()) && dateKey(value, timeZone) === dateKey(now, timeZone);
}

export function formatTime(timestamp: string | null, locale: string, timeZone: TimeZoneSetting): string {
  if (!timestamp) return "—";
  return new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: timeZoneOption(timeZone),
  }).format(new Date(timestamp));
}
