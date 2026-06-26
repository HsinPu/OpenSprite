import { Alert, Modal, Typography } from "antd";

type ConfirmDialogState = {
  open?: boolean;
  eyebrow?: string;
  title?: string;
  message?: string;
  detail?: string;
  cancelLabel?: string;
  confirmLabel?: string;
  busy?: boolean;
};

type ConfirmDialogProps = {
  dialog: ConfirmDialogState;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
};

export function ConfirmDialog({ dialog, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <Modal
      open={Boolean(dialog.open)}
      title={dialog.title}
      okText={dialog.confirmLabel}
      cancelText={dialog.cancelLabel}
      okButtonProps={{ danger: true, loading: dialog.busy }}
      cancelButtonProps={{ disabled: dialog.busy }}
      onOk={onConfirm}
      onCancel={dialog.busy ? undefined : onCancel}
    >
      <Typography.Text type="secondary">{dialog.eyebrow}</Typography.Text>
      <Typography.Paragraph>{dialog.message}</Typography.Paragraph>
      {dialog.detail ? <Alert type="warning" showIcon message={dialog.detail} /> : null}
    </Modal>
  );
}
