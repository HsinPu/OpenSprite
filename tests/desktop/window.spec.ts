import { test, expect, _electron } from '@playwright/test';
import type { ElectronApplication } from '@playwright/test';
import { createRequire } from 'node:module';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

declare global {
  interface Window {
    openspriteDesktop: { getAppInfo(): Promise<{ version: string; platform: string }> };
  }
}

const require = createRequire(import.meta.url);
const executablePath = process.env.OPENSPRITE_TEST_EXECUTABLE ?? require('electron') as string;
const args = process.env.OPENSPRITE_TEST_EXECUTABLE ? [] : [process.cwd()];

async function launch(directory: string): Promise<ElectronApplication> {
  const env: Record<string, string> = Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
  env.OPENSPRITE_DATA_DIR = directory;
  delete env.ELECTRON_RUN_AS_NODE;
  return _electron.launch({ executablePath, args, env });
}

test('desktop opens a real independent window, authenticates Host and recovers status errors', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'opensprite-desktop-'));
  const desktop = await launch(directory);
  try {
    const page = await desktop.firstWindow();
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await expect(page.getByRole('heading', { name: 'OpenSprite Harness', exact: true })).toBeVisible();
    await expect(page.getByText('Host 已連線', { exact: true })).toBeVisible();
    expect(new URL(page.url()).hostname).toBe('127.0.0.1');
    await expect(page.getByRole('button', { name: '傳送', exact: true })).toBeDisabled();
    const boundary = await page.evaluate(() => ({
      hasNode: 'require' in window || 'process' in window,
      bridge: Object.keys(window.openspriteDesktop),
    }));
    expect(boundary).toEqual({ hasNode: false, bridge: ['getAppInfo'] });
    expect(await page.evaluate(() => window.openspriteDesktop.getAppInfo()))
      .toMatchObject({ version: '0.1.0' });
    expect(await page.evaluate(async () => {
      try { await fetch('https://example.invalid/opensprite-egress-test'); return false; } catch { return true; }
    })).toBe(true);
    await page.route('**/api/v1/status', route => route.fulfill({ status: 503, body: '{}' }));
    await page.getByRole('button', { name: '重新整理狀態' }).click();
    await expect(page.getByText('無法連線本機 Host', { exact: true })).toBeVisible();
    await page.unroute('**/api/v1/status');
    await page.getByRole('button', { name: '重新連線', exact: true }).click();
    await expect(page.getByText('Host 已連線', { exact: true })).toBeVisible();
    await page.setViewportSize({ width: 900, height: 680 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: 'test-results/desktop.png', fullPage: true });
    expect(errors).toEqual([]);
    const hostUrl = page.url();
    const exited = new Promise<void>(resolve => desktop.process().once('exit', () => resolve()));
    await page.close();
    await exited;
    await expect.poll(async () => {
      try { await fetch(hostUrl, { signal: AbortSignal.timeout(1000) }); return false; } catch { return true; }
    }).toBe(true);
  } finally {
    await desktop.close().catch(() => undefined);
    await rm(directory, { recursive: true, force: true, maxRetries: 5 });
  }
});

test('second icon launch reuses the same window and Host', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'opensprite-single-'));
  const desktop = await launch(directory);
  try {
    const page = await desktop.firstWindow();
    await expect(page.getByText('Host 已連線', { exact: true })).toBeVisible();
    const previousUrl = page.url();
    const env: Record<string, string> = Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
    env.OPENSPRITE_DATA_DIR = directory;
    delete env.ELECTRON_RUN_AS_NODE;
    const second = spawn(executablePath, args, { env, stdio: 'ignore', windowsHide: true });
    await new Promise<void>((resolve, reject) => {
      second.once('error', reject);
      second.once('exit', () => resolve());
    });
    expect(desktop.windows()).toHaveLength(1);
    expect(page.url()).toBe(previousUrl);
    await expect(page.getByText('Host 已連線', { exact: true })).toBeVisible();
  } finally {
    await desktop.close();
    await rm(directory, { recursive: true, force: true, maxRetries: 5 });
  }
});

test('Host crash is visible and does not silently restart or resend', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'opensprite-crash-'));
  const desktop = await launch(directory);
  try {
    const page = await desktop.firstWindow();
    await expect(page.getByText('Host 已連線', { exact: true })).toBeVisible();
    const hostPid = await test.step('locate the owned Host utility process', () => desktop.evaluate(({ app }) => {
      const metric = app.getAppMetrics().find(value => value.name === 'OpenSprite Host');
      if (!metric) throw new Error('Owned Host not found.');
      return metric.pid;
    }));
    await test.step('terminate Host and observe the failure window', async () => {
      process.kill(hostPid);
      await expect(page.getByText('本機 Host 無法啟動或已停止。請關閉視窗後重新啟動；不會自動重送工作。', { exact: true })).toBeVisible();
    });
  } finally {
    await desktop.close();
    await rm(directory, { recursive: true, force: true, maxRetries: 5 });
  }
});
