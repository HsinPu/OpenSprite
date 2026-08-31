import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AboutSettings } from "../src/features/settings/AboutSettings";

describe("about settings", () => {
  it("shows the running product version and revision", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      version: "0.1.0",
      revision: "84142959",
      buildType: "installed",
      dirty: false,
      installedAt: "2026-08-31T01:02:03Z",
    }))));

    render(<AboutSettings />);

    expect(await screen.findByText("0.1.0")).toBeTruthy();
    expect(screen.getByText("84142959")).toBeTruthy();
    expect(screen.getByText("已安裝版本")).toBeTruthy();
  });
});
