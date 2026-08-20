import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { App } from "../src/app/App";

beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value(this: HTMLDialogElement) { this.open = true; },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value(this: HTMLDialogElement) {
      this.open = false;
      this.dispatchEvent(new Event("close"));
    },
  });
});

describe("settings dialog focus restoration", () => {
  it.each([[1440], [390]])("returns focus to the actual settings opener at %ipx after close", async (width) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    render(<App />);
    const opener = screen.getByRole("button", { name: "設定" });
    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "關閉設定" }));

    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it.each([[1440], [390]])("returns focus to the opener after native-dialog Escape at %ipx", async (width) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    const { container } = render(<App />);
    const opener = screen.getByRole("button", { name: "設定" });
    fireEvent.click(opener);
    const dialog = container.querySelector("dialog")!;
    const cancel = new Event("cancel", { cancelable: true });
    dialog.dispatchEvent(cancel);
    if (!cancel.defaultPrevented) dialog.close();

    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});
