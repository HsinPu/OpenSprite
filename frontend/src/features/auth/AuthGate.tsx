import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Button, Input, Select, Spin } from "antd";

import { AuthenticationApiError, getAuthStatus, login, logout, setupAccess, type AuthStatus } from "../../api/authentication";
import { AUTHENTICATION_REFRESHED_EVENT, AUTHENTICATION_REQUIRED_EVENT } from "../../api/http";
import { getAppInfo } from "../../api/appInfo";
import { isLocale, localeLabels, supportedLocales, type Locale } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import "./auth.css";

type AuthContextValue = { signOut: () => Promise<void>; requireLogin: () => void };
const AuthContext = createContext<AuthContextValue | null>(null);
const unavailableAuthContext: AuthContextValue = {
  signOut: async () => undefined,
  requireLogin: () => undefined,
};

export function useAuthentication(): AuthContextValue {
  return useContext(AuthContext) ?? unavailableAuthContext;
}

function browserLocale(): Locale {
  for (const language of navigator.languages ?? [navigator.language]) {
    const normalized = language.toLowerCase();
    if (normalized.startsWith("zh")) return "zh-TW";
    if (normalized.startsWith("ja")) return "ja";
    if (normalized.startsWith("en")) return "en";
  }
  return "zh-TW";
}

function readBootstrapToken(): string | null {
  const match = /^#setup=([A-Za-z0-9_-]{32,128})$/.exec(window.location.hash);
  if (!match) return null;
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#new-chat`);
  return match[1];
}

function messageFor(code: AuthenticationApiError["code"], t: ReturnType<typeof useI18n>["t"]): string {
  if (code === "invalid_credentials") return t("auth.error.invalidCredentials");
  if (code === "rate_limited") return t("auth.error.rateLimited");
  if (code === "setup_unavailable" || code === "setup_required") return t("auth.error.setupUnavailable");
  if (code === "invalid_request") return t("auth.error.invalidPassword");
  if (code === "network_error") return t("auth.error.network");
  return t("auth.error.unavailable");
}

function AuthPage({ status, bootstrapToken, onAuthenticated }: { status: Exclude<AuthStatus, { state: "authenticated" }>; bootstrapToken: string | null; onAuthenticated: (status: AuthStatus) => void }) {
  const { locale, setLocale, t } = useI18n();
  const setup = status.state === "setup_required";
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryUntil, setRetryUntil] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => { void getAppInfo().then((info) => setVersion(info.version)).catch(() => undefined); }, []);
  useEffect(() => {
    if (retryUntil <= Date.now()) { setRemaining(0); return; }
    const update = () => setRemaining(Math.max(0, Math.ceil((retryUntil - Date.now()) / 1000)));
    update();
    const id = window.setInterval(update, 250);
    return () => window.clearInterval(id);
  }, [retryUntil]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || remaining > 0) return;
    const length = Array.from(password.normalize("NFC")).length;
    if (length < 15 || length > 128 || (setup && password !== confirmation)) {
      setError(setup && password !== confirmation ? t("auth.error.passwordMismatch") : t("auth.error.invalidPassword"));
      return;
    }
    if (setup && !bootstrapToken) { setError(t("auth.error.setupUnavailable")); return; }
    setBusy(true); setError(null);
    try {
      const next = setup ? await setupAccess(bootstrapToken!, password) : await login(password);
      setPassword(""); setConfirmation(""); onAuthenticated(next);
    } catch (requestError) {
      const authError = requestError instanceof AuthenticationApiError ? requestError : new AuthenticationApiError("internal_error");
      setError(messageFor(authError.code, t));
      if (authError.retryAfterSeconds) setRetryUntil(Date.now() + authError.retryAfterSeconds * 1000);
      setPassword(""); setConfirmation("");
    } finally { setBusy(false); }
  };

  return <main className="auth-shell">
    <section className="auth-card" aria-labelledby="auth-title">
      <div className="auth-card__brand"><span className="auth-card__mark" aria-hidden="true"><span /></span><strong>OpenSprite</strong></div>
      <Select aria-label={t("auth.language")} className="auth-language" value={locale} options={supportedLocales.map((value) => ({ value, label: localeLabels[value] }))} onChange={(value) => { if (isLocale(value)) setLocale(value); }} />
      <div className="auth-card__heading"><h1 id="auth-title">{t(setup ? "auth.setupTitle" : "auth.loginTitle")}</h1><p>{t(setup ? "auth.setupDescription" : "auth.loginDescription")}</p></div>
      <form onSubmit={submit}>
        <label htmlFor="auth-password">{t(setup ? "auth.newPassword" : "auth.password")}</label>
        <Input.Password id="auth-password" autoFocus autoComplete={setup ? "new-password" : "current-password"} value={password} disabled={busy || remaining > 0} onChange={(event) => setPassword(event.target.value)} aria-describedby={setup ? "auth-password-help" : undefined} />
        {setup ? <><p id="auth-password-help" className="auth-help">{t("auth.passwordHelp")}</p><label htmlFor="auth-confirmation">{t("auth.confirmPassword")}</label><Input.Password id="auth-confirmation" autoComplete="new-password" value={confirmation} disabled={busy} onChange={(event) => setConfirmation(event.target.value)} /></> : null}
        {error ? <p className="auth-error" role="alert">{error}</p> : null}
        {remaining > 0 ? <p className="auth-countdown" role="status" aria-live="polite">{t("auth.retryCountdown", { seconds: remaining })}</p> : null}
        <Button type="primary" htmlType="submit" block loading={busy} disabled={remaining > 0}>{t(setup ? "auth.setupAction" : "auth.loginAction")}</Button>
      </form>
      {version ? <p className="auth-version">OpenSprite v{version}</p> : null}
    </section>
  </main>;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const { setLocale, t } = useI18n();
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const bootstrapToken = useRef<string | null>(null);

  useEffect(() => {
    if (window.location.hostname === "127.0.0.1") {
      const url = new URL(window.location.href); url.hostname = "localhost"; window.location.replace(url.href); return;
    }
    setLocale(browserLocale());
    const token = readBootstrapToken();
    if (token) bootstrapToken.current = token;
    void getAuthStatus().then(setStatus).catch(() => setLoadError(true));
  }, [setLocale]);

  const requireLogin = useCallback(() => { setStatus({ state: "unauthenticated" }); }, []);
  useEffect(() => {
    window.addEventListener(AUTHENTICATION_REQUIRED_EVENT, requireLogin);
    return () => window.removeEventListener(AUTHENTICATION_REQUIRED_EVENT, requireLogin);
  }, [requireLogin]);
  useEffect(() => {
    if (status?.state !== "authenticated") return;
    const refresh = () => setStatus({ state: "authenticated", expiresAt: new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString() });
    window.addEventListener(AUTHENTICATION_REFRESHED_EVENT, refresh);
    const delay = Math.max(0, Date.parse(status.expiresAt) - Date.now());
    const timer = window.setTimeout(requireLogin, delay);
    return () => {
      window.removeEventListener(AUTHENTICATION_REFRESHED_EVENT, refresh);
      window.clearTimeout(timer);
    };
  }, [requireLogin, status]);
  const signOut = useCallback(async () => { try { await logout(); } finally { requireLogin(); } }, [requireLogin]);
  const context = useMemo(() => ({ signOut, requireLogin }), [signOut, requireLogin]);

  if (window.location.hostname === "127.0.0.1") return null;
  if (loadError) return <main className="auth-shell"><section className="auth-card"><p role="alert">{t("auth.error.unavailable")}</p><Button onClick={() => window.location.reload()}>{t("common.retry")}</Button></section></main>;
  if (!status) return <main className="auth-shell" aria-label={t("auth.loading")}><Spin size="large" /></main>;
  if (status.state !== "authenticated") return <AuthPage status={status} bootstrapToken={bootstrapToken.current} onAuthenticated={setStatus} />;
  return <AuthContext.Provider value={context}>{children}</AuthContext.Provider>;
}
