import { app, BrowserWindow, ipcMain, session, utilityProcess } from 'electron';
import type { UtilityProcess } from 'electron';
import { randomBytes, randomUUID } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PRODUCT_NAME, PRODUCT_VERSION } from '../../../packages/contracts/src/host-status.js';
import { hostEnvironment, isHostOrigin, isOwnedOrigin, resolveDataRoot } from './policy.js';
import { authenticateHost } from './bootstrap.js';

app.setName(PRODUCT_NAME);
const dataRoot = resolveDataRoot(app.getPath('home'), process.env.OPENSPRITE_DATA_DIR);
const desktopRoot = join(dataRoot, 'desktop');
for (const directory of ['profile', 'session', 'crashes']) mkdirSync(join(desktopRoot, directory), { recursive: true });
app.setPath('userData', join(desktopRoot, 'profile'));
app.setPath('sessionData', join(desktopRoot, 'session'));
app.setPath('crashDumps', join(desktopRoot, 'crashes'));
for (const flag of ['disable-background-networking', 'disable-component-update', 'disable-domain-reliability', 'no-pings']) {
  app.commandLine.appendSwitch(flag);
}
app.commandLine.appendSwitch('disable-features', 'MediaRouter,OptimizationHints,AutofillServerCommunication');

let window: BrowserWindow | undefined;
let host: UtilityProcess | undefined;
let origin: string | undefined;
let stopping = false;
let allowClose = false;
let hostExited = false;

function localPage(message: string): string {
  return 'data:text/html;charset=utf-8,' + encodeURIComponent(`<!doctype html><html lang="zh-Hant"><head>
    <meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
    <title>${PRODUCT_NAME}</title><style>body{font:14px system-ui;color:#1f2328;background:#f8f9fb;margin:48px}h1{font-size:24px}p{color:#667085}</style>
    </head><body><h1>${PRODUCT_NAME}</h1><p>${message}</p></body></html>`);
}

function failStartup(): void {
  if (!stopping && window && !window.isDestroyed()) {
    origin = undefined;
    void window.loadURL(localPage('本機 Host 無法啟動或已停止。請關閉視窗後重新啟動；不會自動重送工作。')).catch(() => undefined);
  }
}

async function stop(): Promise<void> {
  if (stopping) return;
  stopping = true;
  if (host && !hostExited) {
    const ownedHost = host;
    await new Promise<void>(resolve => {
      const timeout = setTimeout(() => { ownedHost.kill(); resolve(); }, 4000);
      ownedHost.once('exit', () => { clearTimeout(timeout); resolve(); });
      ownedHost.postMessage({ type: 'shutdown' });
    });
  }
  allowClose = true;
  // Let the cancelled before-quit/close event unwind before requesting the final quit.
  setImmediate(() => app.quit());
}

async function start(): Promise<void> {
  const partition = session.fromPartition(`opensprite-${randomUUID()}`, { cache: false });
  await partition.setProxy({ mode: 'direct' });
  partition.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  partition.setPermissionCheckHandler(() => false);
  partition.on('will-download', event => event.preventDefault());
  partition.webRequest.onBeforeRequest((details, callback) => {
    const allowed = (origin !== undefined && isOwnedOrigin(details.url, origin))
      || details.url.startsWith('data:text/html;charset=utf-8,') || details.url === 'about:blank';
    callback({ cancel: !allowed });
  });
  const currentWindow = new BrowserWindow({
    title: PRODUCT_NAME, width: 1180, height: 780, minWidth: 880, minHeight: 640,
    backgroundColor: '#f8f9fb', autoHideMenuBar: true,
    icon: join(app.getAppPath(), 'apps/desktop/packaging/icon.ico'),
    webPreferences: {
      session: partition, preload: fileURLToPath(new URL('./preload.cjs', import.meta.url)),
      nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true,
      devTools: !app.isPackaged,
    },
  });
  window = currentWindow;
  currentWindow.removeMenu();
  currentWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  currentWindow.webContents.on('will-navigate', (event, url) => {
    if (!origin || !isOwnedOrigin(url, origin)) event.preventDefault();
  });
  currentWindow.on('close', event => {
    if (!allowClose) { event.preventDefault(); void stop(); }
  });
  await currentWindow.loadURL(localPage('正在啟動本機 Host…'));
  if (stopping || currentWindow.isDestroyed()) return;

  const bootstrapToken = randomBytes(32).toString('hex');
  const ownedHost = utilityProcess.fork(join(app.getAppPath(), 'dist/apps/host/src/utility.js'), [], {
    serviceName: 'OpenSprite Host', stdio: 'pipe', env: hostEnvironment(process.env),
  });
  host = ownedHost;
  ownedHost.stdout?.resume();
  ownedHost.stderr?.resume();
  ownedHost.on('exit', () => { hostExited = true; failStartup(); });
  const readyOrigin = await new Promise<string>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Host startup timed out.')), 20000);
    ownedHost.once('exit', () => { clearTimeout(timeout); reject(new Error('Host exited.')); });
    ownedHost.on('message', (message: unknown) => {
      if (typeof message !== 'object' || message === null) return;
      const result = message as Record<string, unknown>;
      if (result.type === 'ready' && isHostOrigin(result.origin)) { clearTimeout(timeout); resolve(result.origin); }
      if (result.type === 'fatal') { clearTimeout(timeout); reject(new Error('Host startup failed.')); }
    });
    ownedHost.postMessage({ type: 'start', bootstrapToken, webRoot: join(app.getAppPath(), 'dist/renderer') });
  });
  if (stopping || currentWindow.isDestroyed()) return;
  origin = readyOrigin;
  const sessionToken = await authenticateHost(origin, bootstrapToken);
  if (stopping || currentWindow.isDestroyed()) return;
  await partition.cookies.set({ url: origin, name: 'opensprite_session', value: sessionToken,
    httpOnly: true, sameSite: 'strict', path: '/' });
  if (stopping || currentWindow.isDestroyed()) return;
  await currentWindow.loadURL(origin);
}

ipcMain.handle('opensprite:app-info', event => {
  if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame
    || !origin || !isOwnedOrigin(event.senderFrame.url, origin)) throw new Error('Unauthorized desktop request.');
  return { version: PRODUCT_VERSION, platform: process.platform };
});

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => { if (window?.isMinimized()) window.restore(); window?.show(); window?.focus(); });
  app.on('before-quit', event => { if (!allowClose) { event.preventDefault(); void stop(); } });
  app.on('window-all-closed', () => { void stop(); });
  app.whenReady().then(start).catch(() => {
    origin = undefined;
    if (host && !hostExited) host.kill();
    failStartup();
  });
}
