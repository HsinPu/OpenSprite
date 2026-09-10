import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, renderHook, act } from "@testing-library/react";
import { fitPanelWidths, readPanelWidths, PANEL_STORAGE_KEY, PanelResizeHandle, usePanelSizing } from "../src/app/panelSizing";

afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); });

test("supports larger panels and still reserves chat space", () => {
  expect(fitPanelWidths({ left: 600, right: 800 }, 1920, true, true)).toEqual({ left: 600, right: 800 });
  const fitted = fitPanelWidths({ left: 600, right: 800 }, 960, true, true);
  expect(fitted.left + fitted.right).toBeCloseTo(600);
  localStorage.setItem(PANEL_STORAGE_KEY, '{"left":600,"right":800}');
  expect(readPanelWidths()).toEqual({ left: 600, right: 800 });
});

test("fits both panels while reserving chat space", () => {
  const widths = fitPanelWidths({ left: 420, right: 520 }, 960, true, true);
  expect(widths.left + widths.right).toBeCloseTo(600);
  expect(widths.left).toBeGreaterThanOrEqual(220);
  expect(widths.right).toBeGreaterThanOrEqual(260);
  expect(fitPanelWidths({ left: 420, right: 520 }, 1440, false, false)).toEqual({ left: 0, right: 0 });
});

test("validates persisted widths and tolerates invalid storage", () => {
  localStorage.setItem(PANEL_STORAGE_KEY, '{"left":9999,"right":20}');
  expect(readPanelWidths()).toEqual({ left: 600, right: 260 });
  localStorage.setItem(PANEL_STORAGE_KEY, 'invalid');
  expect(readPanelWidths()).toEqual({ left: 248, right: 330 });
});

test("viewport constraints do not overwrite preferred widths", () => {
  vi.spyOn(window, "innerWidth", "get").mockReturnValue(1440);
  const { result } = renderHook(() => usePanelSizing(true, true));
  act(() => { result.current.change("left", 400); result.current.change("right", 500); });
  vi.spyOn(window, "innerWidth", "get").mockReturnValue(960);
  act(() => { window.dispatchEvent(new Event("resize")); });
  expect(result.current.actual.left + result.current.actual.right).toBeCloseTo(600);
  expect(JSON.parse(localStorage.getItem(PANEL_STORAGE_KEY)!)).toEqual({ left: 400, right: 500 });
  vi.spyOn(window, "innerWidth", "get").mockReturnValue(1440);
  act(() => { window.dispatchEvent(new Event("resize")); });
  expect(result.current.actual).toEqual({ left: 400, right: 500 });
});

test("right separator supports mirrored keyboard direction and reset", () => {
  const change = vi.fn(); const reset = vi.fn();
  const { getByRole } = render(<PanelResizeHandle side="right" width={330} maximum={520} label="Resize" hint="Help" onChange={change} onReset={reset} />);
  const handle = getByRole("separator");
  fireEvent.keyDown(handle, { key: "ArrowLeft" }); expect(change).toHaveBeenLastCalledWith(340);
  fireEvent.keyDown(handle, { key: "ArrowRight" }); expect(change).toHaveBeenLastCalledWith(320);
  fireEvent.keyDown(handle, { key: "Home" }); fireEvent.doubleClick(handle);
  expect(reset).toHaveBeenCalledTimes(2);
});
