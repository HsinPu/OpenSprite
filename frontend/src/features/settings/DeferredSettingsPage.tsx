import { useEffect, useState, type ComponentProps } from "react";
import { Button, Spin } from "antd";
import { useI18n } from "../../i18n/I18nProvider";

type Page = typeof import("./SettingsPage").SettingsPage;
type Props = ComponentProps<Page>;

export function DeferredSettingsPage(props: Props) {
  const { t } = useI18n();
  const [Page, setPage] = useState<Page | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!props.active || Page) return;
    let cancelled = false;
    setFailed(false);
    void import("./SettingsPage").then(module => {
      if (!cancelled) setPage(() => module.SettingsPage);
    }).catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [props.active, Page, attempt]);
  if (Page) return <Page {...props} />;
  if (!props.active) return null;
  return <div className="settings-page" aria-busy={!failed}>
    {failed ? <div role="alert"><p>{t("settings.loadFailed")}</p><Button onClick={() => setAttempt(value => value + 1)}>{t("common.retry")}</Button></div>
      : <div role="status"><Spin /> {t("settings.loading")}</div>}
    <Button onClick={props.onClose}>{t("settings.close")}</Button>
  </div>;
}
