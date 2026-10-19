import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { mkdtemp, mkdir, rm, symlink, writeFile } from 'node:fs/promises';
import { request } from 'node:http';
import os from 'node:os';
import path from 'node:path';
import test, { type TestContext } from 'node:test';
import { cookieName, createHost } from '../apps/host/src/host.js';

async function fixture(t: TestContext) {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'opensprite-host-test-'));
  const webRoot = path.join(directory, 'web');
  await mkdir(path.join(webRoot, 'assets'), { recursive: true });
  await writeFile(path.join(webRoot, 'index.html'), '<!doctype html><title>OpenSprite Harness</title>');
  await writeFile(path.join(webRoot, 'assets', 'app.js'), 'document.title = "OpenSprite Harness";');
  await writeFile(path.join(directory, 'private.js'), 'private-canary');
  const bootstrapToken = randomBytes(32).toString('hex');
  const host = await createHost({ bootstrapToken, webRoot });
  t.after(async () => {
    await host.close();
    await rm(directory, { recursive: true, force: true });
  });
  async function authenticate(): Promise<string> {
    const response = await fetch(`${host.origin}/internal/bootstrap`, {
      method: 'POST', headers: { Authorization: `Bearer ${bootstrapToken}` },
    });
    assert.equal(response.status, 200);
    const { sessionToken } = await response.json() as { sessionToken: string };
    return `${cookieName}=${sessionToken}`;
  }
  return { ...host, webRoot, directory, bootstrapToken, authenticate };
}

test('private host requires authentication and reports only the implemented skeleton capabilities', async (t) => {
  const host = await fixture(t);
  assert.match(host.origin, /^http:\/\/127\.0\.0\.1:\d+$/);
  assert.deepEqual(await (await fetch(`${host.origin}/health`)).json(), { status: 'ready' });
  for (const endpoint of ['/', '/assets/app.js', '/api/v1/status']) {
    assert.equal((await fetch(`${host.origin}${endpoint}`)).status, 403);
  }
  const cookie = await host.authenticate();
  const status = await fetch(`${host.origin}/api/v1/status`, { headers: { Cookie: cookie } });
  assert.deepEqual(await status.json(), {
    product: 'OpenSprite Harness', version: '0.1.0', host: 'ready',
    provider: 'not-configured', storage: 'not-initialized', outbound: 'disabled', telemetry: false,
  });
  const page = await fetch(host.origin, { headers: { Cookie: cookie } });
  assert.equal(page.status, 200);
  assert.match(await page.text(), /OpenSprite Harness/);
  assert.equal(page.headers.get('cache-control'), 'no-store');
  assert.match(page.headers.get('content-security-policy')!, /connect-src 'self'/);
  assert.match(page.headers.get('content-security-policy')!, /frame-ancestors 'none'/);
  assert.equal(page.headers.get('access-control-allow-origin'), null);
  const asset = await fetch(`${host.origin}/assets/app.js`, { headers: { Cookie: cookie } });
  assert.equal(asset.status, 200);
  assert.match(asset.headers.get('content-type')!, /text\/javascript/);
});

test('bootstrap is secret-authenticated and single-use, with non-persistent HttpOnly cookie', async (t) => {
  const host = await fixture(t);
  const exchange = (token: string) => fetch(`${host.origin}/internal/bootstrap`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` },
  });
  assert.equal((await exchange('wrong')).status, 403);
  const response = await exchange(host.bootstrapToken);
  assert.equal(response.status, 200);
  const cookie = response.headers.get('set-cookie')!;
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /SameSite=Strict/);
  assert.match(cookie, /Path=\//);
  assert.doesNotMatch(cookie, /Expires|Max-Age/);
  assert.equal((await exchange(host.bootstrapToken)).status, 403);
  assert.equal((await exchange('wrong')).status, 403);
});

test('host rejects forged authorities, foreign origins, cross-site requests and ambiguous cookies', async (t) => {
  const host = await fixture(t);
  const cookie = await host.authenticate();
  const deniedHeaders: Record<string, string>[] = [
    { Host: 'attacker.invalid' },
    { Host: '127.0.0.1:1' },
    { Origin: 'https://attacker.invalid' },
    { Origin: 'null' },
    { Origin: `${host.origin}.attacker.invalid` },
    { 'Sec-Fetch-Site': 'cross-site' },
    { Cookie: `${cookie}; ${cookie}` },
  ];
  for (const headers of deniedHeaders) {
    // Fetch rewrites forbidden headers such as Host in newer Node releases.
    // Use raw HTTP so these are actual wire-level forgery tests.
    const response = await rawGet(host.origin, '/api/v1/status', cookie, headers);
    assert.equal(response.status, 403, JSON.stringify(headers));
  }
  assert.equal((await fetch(`${host.origin}/api/v1/status`, {
    headers: { Cookie: cookie, Origin: host.origin },
  })).status, 200);
});

function rawGet(origin: string, requestPath: string, cookie: string,
  extraHeaders: Record<string, string> = {}): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const url = new URL(origin);
    const req = request({ hostname: url.hostname, port: url.port, path: requestPath,
      headers: { Cookie: cookie, ...extraHeaders } }, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk: string) => { body += chunk; });
      response.on('end', () => resolve({ status: response.statusCode!, body }));
    });
    req.on('error', reject);
    req.end();
  });
}

test('static resources cannot escape the web root or expose arbitrary files', async (t) => {
  const host = await fixture(t);
  const cookie = await host.authenticate();
  for (const requestPath of [
    '/assets/../../private.js', '/assets/%2e%2e/%2e%2e/private.js',
    '/assets/..%2f..%2fprivate.js', '/assets/%5c..%5c..%5cprivate.js',
    '/assets/%00.js', '/assets/%ZZ.js', '/package.json', '/missing',
  ]) {
    const response = await rawGet(host.origin, requestPath, cookie);
    assert.notEqual(response.status, 200, requestPath);
    assert.doesNotMatch(response.body, /private-canary/);
    assert.doesNotMatch(response.body, /stack|ENOENT|private\.js|webRoot/);
  }
});

test('static resources reject symlinks resolving outside the packaged root', async (t) => {
  const host = await fixture(t);
  try {
    await symlink(host.directory, path.join(host.webRoot, 'assets', 'escape'),
      process.platform === 'win32' ? 'junction' : 'dir');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'EPERM') {
      t.skip('Creating a symlink requires privileges on this machine');
      return;
    }
    throw error;
  }
  const response = await rawGet(host.origin, '/assets/escape/private.js', await host.authenticate());
  assert.equal(response.status, 404);
  assert.doesNotMatch(response.body, /private-canary/);
});

test('each host instance has an independent authentication secret', async (t) => {
  const first = await fixture(t);
  const second = await fixture(t);
  const cookie = await first.authenticate();
  assert.equal((await fetch(`${second.origin}/api/v1/status`, { headers: { Cookie: cookie } })).status, 403);
});
