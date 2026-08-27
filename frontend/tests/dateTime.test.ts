import { describe, expect, it } from "vitest";

import { formatTime, isTodayInTimeZone } from "../src/features/general-settings/dateTime";

describe("localized date and time", () => {
  it("uses the selected time zone for Today boundaries", () => {
    const now = new Date("2026-08-20T16:30:00Z");
    const timestamp = "2026-08-20T15:30:00Z";

    expect(isTodayInTimeZone(timestamp, "UTC", now)).toBe(true);
    expect(isTodayInTimeZone(timestamp, "Asia/Taipei", now)).toBe(false);
  });

  it("formats execution time with locale defaults and the requested time zone", () => {
    const timestamp = "2026-08-20T16:00:00Z";
    const expected = new Intl.DateTimeFormat("en", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZone: "Asia/Taipei",
    }).format(new Date(timestamp));

    expect(formatTime(timestamp, "en", "Asia/Taipei")).toBe(expected);
    expect(formatTime(null, "en", "UTC")).toBe("—");
  });
});
