import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PrivacySettings } from "../src/features/settings/PrivacySettings";
import { I18nProvider } from "../src/i18n/I18nProvider";

afterEach(() => vi.unstubAllGlobals());

describe("PrivacySettings", () => {
  it("changes the password with the exact secret fields and clears the form", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: "authenticated",
      expiresAt: new Date(Date.now() + 60_000).toISOString(),
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><PrivacySettings /></I18nProvider>);

    fireEvent.change(screen.getByLabelText("目前密碼"), { target: { value: "current password value" } });
    fireEvent.change(screen.getByLabelText("新密碼"), { target: { value: "replacement password value" } });
    fireEvent.change(screen.getByLabelText("確認新密碼"), { target: { value: "replacement password value" } });
    fireEvent.click(screen.getByRole("button", { name: "修改密碼" }));

    await screen.findByText("密碼已更新，其他 Session 已登出。");
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/password", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ currentPassword: "current password value", newPassword: "replacement password value" }),
    }));
    await waitFor(() => expect((screen.getByLabelText("目前密碼") as HTMLInputElement).value).toBe(""));
  });

  it("calls the all-session revocation endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><PrivacySettings /></I18nProvider>);
    fireEvent.click(screen.getByRole("button", { name: "登出所有 Session" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout-all", { method: "POST", credentials: "same-origin" }));
  });
});
