import type { FormEvent } from "react";
import { Alert, Button, Form, Input, Space, Typography } from "antd";

type AnyRecord = Record<string, any>;

type AuthGateClient = {
  copy: { value: AnyRecord };
  state: {
    authRequired?: boolean;
    authError?: string;
  };
  settingsForm: {
    accessToken: string;
  };
  submitAccessToken: (event: FormEvent<HTMLFormElement>) => void;
  openSettings: (section: string) => void;
};

export function AuthGate({ client }: { client: AuthGateClient }) {
  const copy = client.copy.value;
  if (!client.state.authRequired) {
    return null;
  }
  return (
    <section className="auth-gate" aria-labelledby="authGateTitle">
      <form className="auth-gate__card" onSubmit={client.submitAccessToken}>
        <span className="auth-gate__mark" aria-hidden="true">OS</span>
        <Typography.Title id="authGateTitle">{copy.auth.title}</Typography.Title>
        <Typography.Paragraph>{copy.auth.description}</Typography.Paragraph>
        <Form layout="vertical">
          <Form.Item label={copy.auth.tokenLabel}>
            <Input.Password
              value={client.settingsForm.accessToken}
              autoFocus
              onChange={(event) => {
                client.settingsForm.accessToken = event.target.value;
              }}
            />
          </Form.Item>
        </Form>
        {client.state.authError ? <Alert type="error" message={client.state.authError} /> : null}
        <Space>
          <Button type="primary" htmlType="submit">{copy.auth.submit}</Button>
          <Button onClick={() => client.openSettings("general")}>{copy.auth.settings}</Button>
        </Space>
      </form>
    </section>
  );
}
