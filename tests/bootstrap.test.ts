import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { authenticateHost } from '../apps/desktop/src/bootstrap.js';

test('bootstrap connects directly even when a child starts with environment proxy enabled', async () => {
  let proxyCalls = 0;
  const token = 'a'.repeat(64);
  const host = createServer((req, res) => {
    assert.equal(req.method, 'POST');
    assert.equal(req.url, '/internal/bootstrap');
    assert.equal(req.headers.authorization, 'Bearer canary');
    res.end(JSON.stringify({ sessionToken: token }));
  });
  const proxy = createServer((_req, res) => { proxyCalls++; res.writeHead(502).end(); });
  await Promise.all([new Promise<void>(resolve => host.listen(0, '127.0.0.1', resolve)),
    new Promise<void>(resolve => proxy.listen(0, '127.0.0.1', resolve))]);
  try {
    const address = host.address();
    const proxyAddress = proxy.address();
    assert.ok(address && typeof address === 'object' && proxyAddress && typeof proxyAddress === 'object');
    const origin = `http://127.0.0.1:${address.port}`;
    const child = spawn(process.execPath, ['--import', 'tsx', '--input-type=module', '-e',
      `import { authenticateHost } from './apps/desktop/src/bootstrap.ts';
       const token = await authenticateHost(${JSON.stringify(origin)}, 'canary');
       if (token !== '${token}') process.exitCode = 1;`], {
      env: { ...process.env, NODE_USE_ENV_PROXY: '1', HTTP_PROXY: `http://127.0.0.1:${proxyAddress.port}`,
        http_proxy: `http://127.0.0.1:${proxyAddress.port}`, NO_PROXY: '', no_proxy: '' },
      stdio: 'pipe', windowsHide: true,
    });
    let diagnostics = '';
    child.stderr.on('data', chunk => { diagnostics += String(chunk); });
    const code = await new Promise<number | null>((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', resolve);
    });
    assert.equal(code, 0, diagnostics);
    assert.equal(proxyCalls, 0);
  } finally {
    await Promise.all([new Promise<void>(resolve => host.close(() => resolve())),
      new Promise<void>(resolve => proxy.close(() => resolve()))]);
  }
});

test('bootstrap rejects non-owned origins, redirects, malformed and oversized receipts', async () => {
  await assert.rejects(authenticateHost('https://example.invalid', 'canary'), /Invalid Host origin/);
  let mode = 'redirect';
  let redirected = false;
  const host = createServer((req, res) => {
    if (req.url !== '/internal/bootstrap') redirected = true;
    if (mode === 'redirect') res.writeHead(302, { location: '/other' }).end();
    else if (mode === 'oversized') res.end('x'.repeat(2048));
    else res.end(JSON.stringify({ sessionToken: 'invalid' }));
  });
  await new Promise<void>(resolve => host.listen(0, '127.0.0.1', resolve));
  try {
    const address = host.address();
    assert.ok(address && typeof address === 'object');
    const origin = `http://127.0.0.1:${address.port}`;
    await assert.rejects(authenticateHost(origin, 'canary'), /Host authentication failed/);
    assert.equal(redirected, false);
    mode = 'malformed';
    await assert.rejects(authenticateHost(origin, 'canary'), /Invalid Host authentication/);
    mode = 'oversized';
    await assert.rejects(authenticateHost(origin, 'canary'), /Invalid Host authentication/);
  } finally { await new Promise<void>(resolve => host.close(() => resolve())); }
});
