import { useEffect, useRef, useState } from "react";

export type PanelSide = "left" | "right";
export type PanelWidths = Record<PanelSide, number>;
export const PANEL_STORAGE_KEY = "opensprite.panel-widths.v1";
export const PANEL_LIMITS = { left: { min: 220, max: 600, default: 248 }, right: { min: 260, max: 800, default: 330 } };
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

export function readPanelWidths(): PanelWidths {
  const defaults = { left: 248, right: 330 };
  try {
    const value: unknown = JSON.parse(localStorage.getItem(PANEL_STORAGE_KEY) ?? "null");
    if (!value || typeof value !== "object" || Array.isArray(value)) return defaults;
    const record = value as Record<string, unknown>;
    for (const side of ["left", "right"] as const) {
      const width = record[side];
      if (typeof width === "number" && Number.isFinite(width)) defaults[side] = clamp(width, PANEL_LIMITS[side].min, PANEL_LIMITS[side].max);
    }
  } catch { /* Browser storage is optional for interface preferences. */ }
  return defaults;
}

export function fitPanelWidths(preferred: PanelWidths, viewport: number, leftOpen: boolean, rightOpen: boolean): PanelWidths {
  const left = leftOpen ? clamp(preferred.left, PANEL_LIMITS.left.min, PANEL_LIMITS.left.max) : 0;
  const right = rightOpen ? clamp(preferred.right, PANEL_LIMITS.right.min, PANEL_LIMITS.right.max) : 0;
  const excess = Math.max(0, left + right + 360 - viewport);
  const leftRoom = leftOpen ? left - 220 : 0;
  const rightRoom = rightOpen ? right - 260 : 0;
  const room = leftRoom + rightRoom;
  if (!excess || !room) return { left, right };
  const fraction = Math.min(1, excess / room);
  return { left: left - leftRoom * fraction, right: right - rightRoom * fraction };
}

export function usePanelSizing(leftOpen: boolean, rightOpen: boolean) {
  const [preferred, setPreferred] = useState(readPanelWidths);
  const [viewport, setViewport] = useState(() => window.innerWidth);
  useEffect(() => {
    const resize = () => setViewport(window.innerWidth);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  useEffect(() => {
    try { localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify(preferred)); } catch { /* Keep the in-memory preference. */ }
  }, [preferred]);
  const actual = fitPanelWidths(preferred, viewport, leftOpen, rightOpen);
  const maximum = (side: PanelSide) => Math.max(PANEL_LIMITS[side].min, Math.min(PANEL_LIMITS[side].max, viewport - 360 - actual[side === "left" ? "right" : "left"]));
  const change = (side: PanelSide, width: number) => setPreferred(current => ({ ...current, [side]: clamp(width, PANEL_LIMITS[side].min, maximum(side)) }));
  const reset = (side: PanelSide) => setPreferred(current => ({ ...current, [side]: PANEL_LIMITS[side].default }));
  return { actual, maximum, change, reset };
}

export function PanelResizeHandle({ side, width, maximum, label, hint, onChange, onReset }: {
  side: PanelSide; width: number; maximum: number; label: string; hint: string;
  onChange: (width: number) => void; onReset: () => void;
}) {
  const drag = useRef<{ id: number; x: number; width: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  return <div role="separator" aria-orientation="vertical" aria-label={label}
    aria-valuemin={PANEL_LIMITS[side].min} aria-valuemax={Math.round(maximum)} aria-valuenow={Math.round(width)}
    tabIndex={0} title={`${label} — ${hint}`} className={`panel-resize-handle panel-resize-handle--${side}${dragging ? " is-dragging" : ""}`}
    onDoubleClick={onReset}
    onKeyDown={event => {
      if (event.key === "Home") { event.preventDefault(); onReset(); }
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      onChange(width + (event.key === "ArrowRight" ? 10 : -10) * (side === "left" ? 1 : -1));
    }}
    onPointerDown={event => {
      if (event.button !== 0 || !event.isPrimary) return;
      event.preventDefault(); event.currentTarget.focus();
      event.currentTarget.setPointerCapture(event.pointerId);
      drag.current = { id: event.pointerId, x: event.clientX, width }; setDragging(true);
    }}
    onPointerMove={event => {
      if (drag.current?.id !== event.pointerId) return;
      onChange(drag.current.width + (event.clientX - drag.current.x) * (side === "left" ? 1 : -1));
    }}
    onPointerUp={event => {
      if (drag.current?.id !== event.pointerId) return;
      drag.current = null; setDragging(false);
      event.currentTarget.releasePointerCapture(event.pointerId);
    }}
    onPointerCancel={() => { drag.current = null; setDragging(false); }}
    onLostPointerCapture={() => { drag.current = null; setDragging(false); }}
  />;
}
