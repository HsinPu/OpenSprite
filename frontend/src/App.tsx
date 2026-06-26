import { useState } from "react";
import { useReactiveStore } from "./lib/reactiveCompat";
import { useChatClient } from "./composables/useChatClient";
import { useShellLayout } from "./composables/useShellLayout";
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
  const { appShellStyle, beginSidebarResize, beginTraceResize } = useShellLayout(client);
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
