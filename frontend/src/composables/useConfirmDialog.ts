import { useState } from "react";

type AnyRecord = Record<string, any>;

function closedConfirmDialog() {
  return {
    open: false,
    eyebrow: "",
    title: "",
    message: "",
    detail: "",
    cancelLabel: "",
    confirmLabel: "",
    busy: false,
    action: null,
  };
}

export function useConfirmDialog(client: AnyRecord) {
  const copy = client.copy.value;
  const [confirmDialog, setConfirmDialog] = useState<AnyRecord>(closedConfirmDialog);

  function closeConfirmDialog() {
    setConfirmDialog(closedConfirmDialog());
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

  return {
    confirmDialog,
    closeConfirmDialog,
    confirmDialogAction,
    deleteSessions,
    clearWebSessions,
  };
}
