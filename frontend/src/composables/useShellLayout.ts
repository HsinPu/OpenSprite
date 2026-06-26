import { type CSSProperties, type PointerEvent as ReactPointerEvent, useState } from "react";

const TRACE_WIDTH_STORAGE_KEY = "opensprite:web:traceInspectorWidth";
const SIDEBAR_WIDTH_STORAGE_KEY = "opensprite:web:sidebarWidth";
const SIDEBAR_WIDTH_DEFAULT = 268;
const SIDEBAR_WIDTH_MIN = 220;
const SIDEBAR_WIDTH_MAX = 440;
const SIDEBAR_COLLAPSED_WIDTH = 52;
const TRACE_WIDTH_MIN = 440;
const TRACE_CHAT_MIN = 520;

type ShellLayoutClient = {
  sidebarCollapsed: { value: boolean };
  traceInspectorCollapsed: { value: boolean };
};

export function useShellLayout(client: ShellLayoutClient) {
  const [sidebarWidth, setSidebarWidth] = useState(readStoredSidebarWidth);
  const [traceInspectorWidth, setTraceInspectorWidth] = useState(readStoredTraceWidth);

  const appShellStyle = {
    "--sidebar-width": sidebarWidth ? `${sidebarWidth}px` : undefined,
    "--trace-sidebar-width": traceInspectorWidth ? `${traceInspectorWidth}px` : undefined,
  } as CSSProperties;

  function currentSidebarGutter() {
    return client.sidebarCollapsed.value ? SIDEBAR_COLLAPSED_WIDTH : sidebarWidth || SIDEBAR_WIDTH_DEFAULT;
  }

  function clampSidebarWidth(width: number) {
    const viewportWidth = window.innerWidth || 0;
    const maxFromViewport = viewportWidth
      ? Math.max(
          SIDEBAR_WIDTH_MIN,
          viewportWidth - TRACE_CHAT_MIN - (client.traceInspectorCollapsed.value ? 0 : TRACE_WIDTH_MIN),
        )
      : SIDEBAR_WIDTH_MAX;
    const maxWidth = Math.min(SIDEBAR_WIDTH_MAX, maxFromViewport);
    return Math.round(Math.min(Math.max(width, SIDEBAR_WIDTH_MIN), maxWidth));
  }

  function clampTraceWidth(width: number) {
    const viewportWidth = window.innerWidth || 0;
    const fallbackMax = Math.max(TRACE_WIDTH_MIN, Math.round(viewportWidth * 0.78));
    const maxWidth = viewportWidth ? Math.max(TRACE_WIDTH_MIN, viewportWidth - currentSidebarGutter() - TRACE_CHAT_MIN) : fallbackMax;
    return Math.round(Math.min(Math.max(width, TRACE_WIDTH_MIN), maxWidth));
  }

  function beginSidebarResize(event: ReactPointerEvent) {
    if (client.sidebarCollapsed.value || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const handlePointerMove = (moveEvent: PointerEvent) => {
      setSidebarWidth(clampSidebarWidth(moveEvent.clientX));
      if (!client.traceInspectorCollapsed.value && traceInspectorWidth) {
        setTraceInspectorWidth(clampTraceWidth(traceInspectorWidth));
      }
    };
    const stopResize = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopResize);
      window.removeEventListener("pointercancel", stopResize);
      try {
        window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, String(sidebarWidth));
        if (traceInspectorWidth) {
          window.localStorage.setItem(TRACE_WIDTH_STORAGE_KEY, String(traceInspectorWidth));
        }
      } catch {
        // Keep resize functional even when storage is unavailable.
      }
    };
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResize, { once: true });
    window.addEventListener("pointercancel", stopResize, { once: true });
  }

  function beginTraceResize(event: ReactPointerEvent) {
    if (client.traceInspectorCollapsed.value || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const handlePointerMove = (moveEvent: PointerEvent) => {
      setTraceInspectorWidth(clampTraceWidth(window.innerWidth - moveEvent.clientX));
    };
    const stopResize = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopResize);
      window.removeEventListener("pointercancel", stopResize);
      try {
        window.localStorage.setItem(TRACE_WIDTH_STORAGE_KEY, String(traceInspectorWidth));
      } catch {
        // Keep resize functional even when storage is unavailable.
      }
    };
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResize, { once: true });
    window.addEventListener("pointercancel", stopResize, { once: true });
  }

  return {
    appShellStyle,
    beginSidebarResize,
    beginTraceResize,
  };
}

function readStoredTraceWidth() {
  try {
    const value = Number.parseInt(window.localStorage.getItem(TRACE_WIDTH_STORAGE_KEY) || "", 10);
    return Number.isFinite(value) ? Math.max(TRACE_WIDTH_MIN, value) : 0;
  } catch {
    return 0;
  }
}

function readStoredSidebarWidth() {
  try {
    const value = Number.parseInt(window.localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY) || "", 10);
    return Number.isFinite(value) ? Math.min(Math.max(value, SIDEBAR_WIDTH_MIN), SIDEBAR_WIDTH_MAX) : SIDEBAR_WIDTH_DEFAULT;
  } catch {
    return SIDEBAR_WIDTH_DEFAULT;
  }
}
