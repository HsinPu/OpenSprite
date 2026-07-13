import { useState } from "react";
import type { ChatSession } from "./chatClientSessions";

type ValueRef<T> = { value: T };
type ConfirmDialogAction = () => void | Promise<void>;

interface ConfirmDialogState {
  open: boolean;
  eyebrow: string;
  title: string;
  message: string;
  detail: string;
  cancelLabel: string;
  confirmLabel: string;
  busy: boolean;
  action: ConfirmDialogAction | null;
}

interface ConfirmDialogCopy {
  sidebar: {
    deleteChat: string;
    confirmDeleteTitle: string;
    confirmDeleteChat: (title: string) => string;
    confirmDeleteChats: (count: number) => string;
    confirmDeleteDetail: string;
    cancelDelete: string;
    confirmDeleteAction: string;
  };
  settings: {
    general: {
      clearWebChats: {
        action: string;
        confirmTitle: string;
        confirm: string;
        confirmDescription: (count: number) => string;
        confirmAction: string;
      };
    };
  };
}

type ConfirmDialogClient = {
  copy: ValueRef<ConfirmDialogCopy>;
  webSessionCount: ValueRef<number>;
  getSessionTitle: (session: ChatSession | null | undefined) => string;
  deleteSessions: (sessions: ChatSession[]) => void | Promise<void>;
  clearWebSessions: () => void | Promise<void>;
};

function closedConfirmDialog(): ConfirmDialogState {
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

export function useConfirmDialog(client: ConfirmDialogClient) {
  const copy = client.copy.value;
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>(closedConfirmDialog);

  function closeConfirmDialog() {
    setConfirmDialog(closedConfirmDialog());
  }

  async function confirmDialogAction() {
    const action = confirmDialog.action;
    if (!action || confirmDialog.busy) {
      return;
    }
    setConfirmDialog((dialog) => ({ ...dialog, busy: true }));
    try {
      await action();
    } finally {
      closeConfirmDialog();
    }
  }

  function deleteSessions(sessions: ChatSession[]) {
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
