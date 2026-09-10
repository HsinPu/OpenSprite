import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UserMenu } from "../src/app/UserMenu";

describe("UserMenu", () => {
  it("opens settings and about from a single user entry", async () => {
    const open = vi.fn();
    render(<UserMenu onSettings={open} />);
    const trigger = screen.getByRole("button", { name: "使用者" });
    fireEvent.click(trigger);
    fireEvent.click(await screen.findByRole("menuitem", { name: /設定/ }));
    expect(open).toHaveBeenCalledWith("general", trigger);
    fireEvent.click(trigger);
    fireEvent.click(await screen.findByRole("menuitem", { name: /關於/ }));
    expect(open).toHaveBeenCalledWith("about", trigger);
    expect(screen.queryByRole("menuitem", { name: /登出/ })).toBeNull();
  });
  it("offers logout only when provided and restores focus on Escape", async () => {
    const logout = vi.fn();
    render(<UserMenu onSettings={vi.fn()} onLogout={logout} />);
    const trigger = screen.getByRole("button", { name: "使用者" });
    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu");
    fireEvent.keyDown(menu, { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(trigger));
    fireEvent.click(trigger);
    fireEvent.click(await screen.findByRole("menuitem", { name: /登出/ }));
    expect(logout).toHaveBeenCalledOnce();
  });
});
