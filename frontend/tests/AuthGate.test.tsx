import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthGate } from "../src/features/auth/AuthGate";
import { notifyAuthenticationRequired } from "../src/api/http";
import { I18nProvider } from "../src/i18n/I18nProvider";

const response = (body: unknown, status = 200, headers?: HeadersInit) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
const authenticated = () => ({ state: "authenticated", expiresAt: new Date(Date.now() + 60_000).toISOString() });

function ProtectedApp() {
  useEffect(() => { void fetch("/api/conversations"); }, []);
  return <p>SENSITIVE APP</p>;
}

beforeEach(() => { Object.defineProperty(navigator, "languages", { configurable: true, value: ["zh-TW"] }); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); window.history.replaceState(null, "", "#new-chat"); });

describe("AuthGate", () => {
  it("mounts the application directly in trusted local mode", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === "/api/auth/status") return Promise.resolve(response({ state: "trusted_local" }));
      if (path === "/api/conversations") return Promise.resolve(response({ conversations: [], nextCursor: null }));
      throw new Error(`unexpected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><AuthGate><ProtectedApp /></AuthGate></I18nProvider>);
    expect(await screen.findByText("SENSITIVE APP")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "登入 OpenSprite" })).toBeNull();
  });

  it("does not mount protected application before authentication", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === "/api/auth/status") return Promise.resolve(response({ state: "unauthenticated" }));
      if (path === "/api/app-info") return Promise.resolve(response({ version: "0.9.0", revision: "development", buildType: "development", dirty: true, installedAt: null }));
      throw new Error(`unexpected protected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><AuthGate><ProtectedApp /></AuthGate></I18nProvider>);
    expect(await screen.findByRole("heading", { name: "登入 OpenSprite" })).toBeTruthy();
    expect(screen.queryByText("SENSITIVE APP")).toBeNull();
    expect(fetchMock.mock.calls.every(([path]) => path !== "/api/conversations")).toBe(true);
  });

  it("consumes the bootstrap fragment and mounts only after setup succeeds", async () => {
    window.history.replaceState(null, "", "#setup=abcdefghijklmnopqrstuvwxyzABCDEFGH12345678");
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === "/api/auth/status") return Promise.resolve(response({ state: "setup_required" }));
      if (path === "/api/app-info") return Promise.resolve(response({ version: "0.9.0", revision: "development", buildType: "development", dirty: true, installedAt: null }));
      if (path === "/api/auth/setup") return Promise.resolve(response(authenticated()));
      if (path === "/api/conversations") return Promise.resolve(response({ conversations: [], nextCursor: null }));
      throw new Error(`unexpected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><AuthGate><ProtectedApp /></AuthGate></I18nProvider>);
    expect(await screen.findByRole("heading", { name: "設定本機存取密碼" })).toBeTruthy();
    expect(window.location.hash).toBe("#new-chat");
    fireEvent.change(screen.getByLabelText("新密碼"), { target: { value: "這是一組足夠長的本機密碼 12345" } });
    fireEvent.change(screen.getByLabelText("確認新密碼"), { target: { value: "這是一組足夠長的本機密碼 12345" } });
    fireEvent.click(screen.getByRole("button", { name: "設定並登入" }));
    expect(await screen.findByText("SENSITIVE APP")).toBeTruthy();
    const setupCall = fetchMock.mock.calls.find(([path]) => path === "/api/auth/setup");
    expect(JSON.parse(setupCall?.[1]?.body as string)).toEqual({ bootstrapToken: "abcdefghijklmnopqrstuvwxyzABCDEFGH12345678", password: "這是一組足夠長的本機密碼 12345" });
  });

  it("returns to login and unmounts sensitive state when authentication expires", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === "/api/auth/status") return Promise.resolve(response(authenticated()));
      if (path === "/api/conversations") return Promise.resolve(response({ conversations: [], nextCursor: null }));
      if (path === "/api/app-info") return Promise.resolve(response({ version: "0.9.0", revision: "development", buildType: "development", dirty: true, installedAt: null }));
      throw new Error(`unexpected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><AuthGate><ProtectedApp /></AuthGate></I18nProvider>);
    expect(await screen.findByText("SENSITIVE APP")).toBeTruthy();
    act(() => notifyAuthenticationRequired());
    await waitFor(() => expect(screen.queryByText("SENSITIVE APP")).toBeNull());
    expect(screen.getByRole("heading", { name: "登入 OpenSprite" })).toBeTruthy();
  });

  it("unmounts the application when the reported session deadline passes", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === "/api/auth/status") return Promise.resolve(response({ state: "authenticated", expiresAt: new Date(Date.now() + 50).toISOString() }));
      if (path === "/api/conversations") return Promise.resolve(response({ conversations: [], nextCursor: null }));
      if (path === "/api/app-info") return Promise.resolve(response({ version: "0.9.0", revision: "development", buildType: "development", dirty: true, installedAt: null }));
      throw new Error(`unexpected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><AuthGate><ProtectedApp /></AuthGate></I18nProvider>);
    expect(await screen.findByText("SENSITIVE APP")).toBeTruthy();
    await waitFor(() => expect(screen.queryByText("SENSITIVE APP")).toBeNull());
    expect(screen.getByRole("heading", { name: "登入 OpenSprite" })).toBeTruthy();
  });

  it("shows the server retry delay after throttling", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === "/api/auth/status") return Promise.resolve(response({ state: "unauthenticated" }));
      if (path === "/api/app-info") return Promise.resolve(response({ version: "0.9.0", revision: "development", buildType: "development", dirty: true, installedAt: null }));
      if (path === "/api/auth/login") return Promise.resolve(response({ error: { code: "rate_limited", message: "Too many authentication attempts.", retryable: true } }, 429, { "Retry-After": "2" }));
      throw new Error(`unexpected request: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<I18nProvider><AuthGate><ProtectedApp /></AuthGate></I18nProvider>);
    fireEvent.change(await screen.findByLabelText("密碼"), { target: { value: "123456789012345" } });
    fireEvent.click(screen.getByRole("button", { name: /登\s*入/ }));
    expect(await screen.findByText("請等待 2 秒後再試。")).toBeTruthy();
  });
});
