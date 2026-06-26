import { useReactiveStore } from "./lib/reactiveCompat";
import { useChatClient } from "./composables/useChatClient";
import { useConfirmDialog } from "./composables/useConfirmDialog";
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

export default function App() {
  return (
    <AppProviders>
      <OpenSpriteShell />
    </AppProviders>
  );
}

function OpenSpriteShell() {
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
