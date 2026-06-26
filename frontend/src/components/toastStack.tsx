import { Alert } from "antd";
import { noticeTone } from "./displayHelpers";

type AnyRecord = Record<string, any>;

type ToastClient = {
  toasts: { value?: AnyRecord[] };
  dismissToast: (id: any) => void;
};

export function ToastStack({ client }: { client: ToastClient }) {
  const toasts = client.toasts.value || [];
  if (!toasts.length) {
    return null;
  }
  return (
    <div className="toast-stack">
      {toasts.map((toast: AnyRecord) => (
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
