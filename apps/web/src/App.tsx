import { useEffect, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  ConfigProvider,
  Input,
  Skeleton,
  Tag,
  Typography,
} from 'antd';
import {
  ArrowUpOutlined,
  DesktopOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { fetchHostStatus, type HostStatus } from './host-status.js';

type Connection =
  | { state: 'loading' }
  | { state: 'ready'; status: HostStatus }
  | { state: 'error' };

const theme = {
  token: {
    colorPrimary: '#2563eb',
    colorBgLayout: '#f8f9fb',
    colorText: '#1f2328',
    colorTextSecondary: '#667085',
    colorBorder: '#dfe3e8',
    colorBorderSecondary: '#eceff3',
    borderRadius: 6,
    fontSize: 14,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", sans-serif',
    controlHeight: 32,
    motion: false,
  },
};

export function App() {
  const [connection, setConnection] = useState<Connection>({ state: 'loading' });
  const [request, setRequest] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setConnection({ state: 'loading' });
    const timeout = window.setTimeout(() => controller.abort(), 10_000);

    void fetchHostStatus(controller.signal)
      .then((status) => {
        if (active) setConnection({ state: 'ready', status });
      })
      .catch(() => {
        if (active) setConnection({ state: 'error' });
      })
      .finally(() => window.clearTimeout(timeout));

    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [request]);

  const reload = () => setRequest((previous) => previous + 1);

  return (
    <ConfigProvider theme={theme}>
      <div className="app-shell">
        <aside className="sidebar" aria-label="工作台導覽">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">OS</span>
            <div className="brand-name">OpenSprite<span>Harness</span></div>
          </div>
          <div className="sidebar-section-label">本機工作台</div>
          <div className="current-view" aria-current="page">
            <DesktopOutlined aria-hidden="true" />
            <span>桌面概覽</span>
          </div>
          <div className="sidebar-footer">
            <span>第一階段 · 桌面骨架</span>
            <span>{connection.state === 'ready' ? `v${connection.status.version}` : '本機執行'}</span>
          </div>
        </aside>

        <main className="workspace">
          <header className="page-header">
            <div>
              <h1>OpenSprite Harness</h1>
              <p>你的本機 AI Agent 工作台</p>
            </div>
            <Tag icon={<DesktopOutlined aria-hidden="true" />} className="desktop-tag">桌面版</Tag>
          </header>

          <div className="page-content">
            <section className="intro" aria-labelledby="intro-title">
              <div className="section-eyebrow">桌面環境</div>
              <h2 id="intro-title">{connection.state === 'ready' ? '桌面骨架已就緒' : connection.state === 'error' ? '本機連線需要重試' : '正在確認本機環境'}</h2>
              <p>此階段提供獨立視窗與本機 Host。模型連線、工作區與對話功能將在後續階段提供。</p>
            </section>

            <section className="status-section" aria-labelledby="status-title" aria-busy={connection.state === 'loading'}>
              <div className="section-heading">
                <h2 id="status-title">系統狀態</h2>
                <Button
                  icon={<ReloadOutlined aria-hidden="true" />}
                  onClick={reload}
                  loading={connection.state === 'loading'}
                  disabled={connection.state === 'loading'}
                >重新整理狀態</Button>
              </div>
              <div aria-live="polite" className="status-content">
                {connection.state === 'loading' && (
                  <div className="status-loading" role="status" aria-label="正在載入系統狀態">
                    <Skeleton active={false} title={false} paragraph={{ rows: 4 }} />
                  </div>
                )}
                {connection.state === 'error' && (
                  <Alert
                    type="error"
                    showIcon
                    title="無法連線本機 Host"
                    description="狀態讀取失敗或回應格式不符。請重新連線；若持續失敗，請關閉並重新啟動 OpenSprite Harness。"
                    action={<Button onClick={reload}>重新連線</Button>}
                  />
                )}
                {connection.state === 'ready' && (
                  <dl className="status-list">
                    <div className="status-row">
                      <dt>本機 Host</dt>
                      <dd><Badge status="success" text="Host 已連線" /></dd>
                      <dd className="status-detail">私有本機程序</dd>
                    </div>
                    <div className="status-row">
                      <dt>模型供應商</dt>
                      <dd>未設定</dd>
                      <dd className="status-detail">尚未開放模型連線</dd>
                    </div>
                    <div className="status-row">
                      <dt>使用者資料</dt>
                      <dd>尚未初始化</dd>
                      <dd className="status-detail">尚未建立會話或憑證資料</dd>
                    </div>
                    <div className="status-row">
                      <dt>產品外部連線</dt>
                      <dd>已停用</dd>
                      <dd className="status-detail">沒有模型或遙測目的地</dd>
                    </div>
                    <div className="status-row">
                      <dt>遙測與會話上傳</dt>
                      <dd>已停用</dd>
                      <dd className="status-detail">本階段不含上傳機制</dd>
                    </div>
                  </dl>
                )}
              </div>
            </section>

            <section className="privacy-note" aria-label="資料傳送政策">
              <SafetyCertificateOutlined aria-hidden="true" />
              <div>
                <h2>由你決定資料去向</h2>
                <p>不帶入 DeepSeek 或參考專案服務的遙測、回饋、會話上傳與背景補送機制。</p>
              </div>
            </section>

            <section className="composer-section" aria-labelledby="composer-title">
              <div className="section-heading">
                <h2 id="composer-title">對話</h2>
                <Typography.Text type="secondary">後續階段提供</Typography.Text>
              </div>
              <label className="composer-label" htmlFor="message">訊息</label>
              <Input.TextArea
                id="message"
                disabled
                rows={3}
                placeholder="模型連線與 Agent Runtime 完成後，即可開始對話。"
                aria-describedby="composer-help"
              />
              <div className="composer-footer">
                <p id="composer-help">目前僅提供桌面骨架，尚不支援傳送訊息或執行工具。</p>
                <Button type="primary" icon={<ArrowUpOutlined aria-hidden="true" />} disabled>傳送</Button>
              </div>
            </section>
          </div>
        </main>
      </div>
    </ConfigProvider>
  );
}
