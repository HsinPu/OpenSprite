import { Alert } from "antd";
import { noticeTone } from "./displayHelpers";
import type { ToastNotice } from "../composables/useChatClient";

type ValueRef<T> = { value: T };

type ToastClient = {
  toasts: ValueRef<ToastNotice[]>;
  dismissToast: (id: string) => void;
};

export function ToastStack({ client }: { client: ToastClient }) {
  const toasts = client.toasts.value || [];
  if (!toasts.length) {
    return null;
  }
  return (
    <div className="toast-stack">
      {toasts.map((toast: ToastNotice) => (
        <Alert
          key={toast.id}
          type={noticeTone(toast.tone)}
          message={toast.text}
          closable
          onClose={() => client.dismissToast(toast.id)}
        />
      ))}
    </div>
  );
}
