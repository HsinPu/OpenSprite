import { useRef, useState } from "react";

export function PanelResizeHandle({ side, width, maximum, minimum, label, hint, onChange, onReset }: {
  side: "left" | "right"; width: number; maximum: number; minimum: number; label: string; hint: string;
  onChange: (width: number) => void; onReset: () => void;
}) {
  const drag = useRef<{ id: number; x: number; width: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  return <div role="separator" aria-orientation="vertical" aria-label={label}
    aria-valuemin={minimum} aria-valuemax={Math.round(maximum)} aria-valuenow={Math.round(width)}
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
