import React, { CSSProperties, useEffect, useState } from "react";
import { useReactiveStore } from "./lib/reactiveCompat";
import { useChatClient } from "./composables/useChatClient";
import { AuthGate } from "./components/authGate";
import { ChatPanel } from "./components/chatPanel";
import { ConfirmDialog } from "./components/confirmDialog";
import { MobileNavControls } from "./components/mobileNavControls";
import { SidebarNav } from "./components/sidebarNav";
import { ToastStack } from "./components/toastStack";
import { TraceSidebar } from "./components/traceSidebar";
import { AppProviders } from "./providers/appProviders";
import { SettingsModal } from "./settings/settingsModal";

type AnyRecord = Record<string, any>;
type Client = ReturnType<typeof useChatClient>;

const TRACE_WIDTH_STORAGE_KEY = "opensprite:web:traceInspectorWidth";
const SIDEBAR_WIDTH_STORAGE_KEY = "opensprite:web:sidebarWidth";
const SIDEBAR_WIDTH_DEFAULT = 268;
const SIDEBAR_WIDTH_MIN = 220;
const SIDEBAR_WIDTH_MAX = 440;
const SIDEBAR_COLLAPSED_WIDTH = 52;
const TRACE_WIDTH_MIN = 440;
const TRACE_CHAT_MIN = 520;

export default function App() {
  return (
    <AppProviders>
      <OpenSpriteShell />
    </AppProviders>
  );
}

function OpenSpriteShell() {
  const client = useReactiveStore(useChatClient);
  const copy = client.copy.value;
  const [sidebarWidth, setSidebarWidth] = useState(readStoredSidebarWidth);
  const [traceInspectorWidth, setTraceInspectorWidth] = useState(readStoredTraceWidth);
  const [confirmDialog, setConfirmDialog] = useState<AnyRecord>({
    open: false,
    eyebrow: "",
    title: "",
    message: "",
    detail: "",
    cancelLabel: "",
    confirmLabel: "",
    busy: false,
    action: null,
  });

  const appShellStyle = {
    "--sidebar-width": sidebarWidth ? `${sidebarWidth}px` : undefined,
    "--trace-sidebar-width": traceInspectorWidth ? `${traceInspectorWidth}px` : undefined,
  } as CSSProperties;

  function viewTraceForRun(runId: string) {
    client.selectRun(runId);
    if (client.traceInspectorCollapsed.value) {
      client.toggleTraceInspectorCollapsed();
    }
  }

  function closeConfirmDialog() {
    setConfirmDialog({
      open: false,
      eyebrow: "",
      title: "",
      message: "",
      detail: "",
      cancelLabel: "",
      confirmLabel: "",
      busy: false,
      action: null,
    });
  }

  async function confirmDialogAction() {
    if (typeof confirmDialog.action !== "function" || confirmDialog.busy) {
      return;
    }
    setConfirmDialog((dialog) => ({ ...dialog, busy: true }));
    try {
      await confirmDialog.action();
    } finally {
      closeConfirmDialog();
    }
  }

  function deleteSessions(sessions: AnyRecord[]) {
    const targets = Array.isArray(sessions) ? sessions.filter(Boolean) : [];
    if (!targets.length) {
      return;
    }
    setConfirmDialog({
      open: true,
      eyebrow: copy.sidebar.deleteChat,
      title: copy.sidebar.confirmDeleteTitle,
      message:
        targets.length === 1
          ? copy.sidebar.confirmDeleteChat(client.getSessionTitle(targets[0]))
          : copy.sidebar.confirmDeleteChats(targets.length),
      detail: copy.sidebar.confirmDeleteDetail,
      cancelLabel: copy.sidebar.cancelDelete,
      confirmLabel: copy.sidebar.confirmDeleteAction,
      busy: false,
      action: () => client.deleteSessions(targets),
    });
  }

  function clearWebSessions() {
    setConfirmDialog({
      open: true,
      eyebrow: copy.settings.general.clearWebChats.action,
      title: copy.settings.general.clearWebChats.confirmTitle,
      message: copy.settings.general.clearWebChats.confirm,
      detail: copy.settings.general.clearWebChats.confirmDescription(client.webSessionCount.value || 0),
      cancelLabel: copy.sidebar.cancelDelete,
      confirmLabel: copy.settings.general.clearWebChats.confirmAction,
      busy: false,
      action: () => client.clearWebSessions(),
    });
  }

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

  function beginSidebarResize(event: React.PointerEvent) {
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

  function beginTraceResize(event: React.PointerEvent) {
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

  return (
    <>
      <div
        className={[
          "app-shell",
          client.sidebarCollapsed.value ? "app-shell--sidebar-collapsed" : "",
          client.traceInspectorCollapsed.value ? "app-shell--trace-collapsed" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={appShellStyle}
      >
        <MobileNavControls client={client} />

        <SidebarNav
          client={client}
          beginSidebarResize={beginSidebarResize}
          deleteSessions={deleteSessions}
        />

        <ChatPanel client={client} viewTraceForRun={viewTraceForRun} />

        <TraceSidebar client={client} beginTraceResize={beginTraceResize} />
      </div>

      <AuthGate client={client} />
      <SettingsModal client={client} clearWebSessions={clearWebSessions} />
      <ConfirmDialog dialog={confirmDialog} onConfirm={confirmDialogAction} onCancel={closeConfirmDialog} />
      <ToastStack client={client} />
    </>
  );
}

function copyText(value: any, fallback: string) {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (value && typeof value === "object") {
    if (typeof value.title === "string" && value.title.trim()) {
      return value.title;
    }
    if (typeof value.label === "string" && value.label.trim()) {
      return value.label;
    }
    if (typeof value.action === "string" && value.action.trim()) {
      return value.action;
    }
  }
  return fallback;
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
