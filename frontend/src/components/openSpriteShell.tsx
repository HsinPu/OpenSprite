import { useReactiveStore } from "../lib/reactiveCompat";
import { useChatClient } from "../composables/useChatClient";
import { useConfirmDialog } from "../composables/useConfirmDialog";
import { useShellLayout } from "../composables/useShellLayout";
import { AuthGate } from "./authGate";
import { ChatPanel } from "./chatPanel";
import { ConfirmDialog } from "./confirmDialog";
import { MobileNavControls } from "./mobileNavControls";
import { SidebarNav } from "./sidebarNav";
import { ToastStack } from "./toastStack";
import { TraceSidebar } from "./traceSidebar";
import { SettingsModal } from "../settings/settingsModal";

export function OpenSpriteShell() {
  const client = useReactiveStore(useChatClient);
  const { appShellStyle, beginSidebarResize, beginTraceResize } = useShellLayout(client);
  const { confirmDialog, closeConfirmDialog, confirmDialogAction, deleteSessions, clearWebSessions } =
    useConfirmDialog(client);

  function viewTraceForRun(runId: string) {
    client.selectRun(runId);
    if (client.traceInspectorCollapsed.value) {
      client.toggleTraceInspectorCollapsed();
    }
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
