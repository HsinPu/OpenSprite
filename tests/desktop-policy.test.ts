import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hostEnvironment, isHostOrigin, isOwnedOrigin, resolveDataRoot } from '../apps/desktop/src/policy.js';
import { isHostStatus } from '../packages/contracts/src/host-status.js';

test('desktop trusts the exact owned authority, not another localhost port or credentials', () => {
  assert.equal(isHostOrigin('http://127.0.0.1:32100'), true);
  for (const origin of ['http://localhost:32100', 'https://api.deepseek.com', 'http://127.0.0.1:32100/path', 'http://user@127.0.0.1:32100']) {
    assert.equal(isHostOrigin(origin), false);
  }
  assert.equal(isOwnedOrigin('http://127.0.0.1:32100/api/v1/status', 'http://127.0.0.1:32100'), true);
  assert.equal(isOwnedOrigin('http://127.0.0.1:32101/', 'http://127.0.0.1:32100'), false);
  assert.equal(isOwnedOrigin('http://secret@127.0.0.1:32100/', 'http://127.0.0.1:32100'), false);
});

test('Host environment does not inherit secrets, proxies, Node hooks or arbitrary PATH', () => {
  assert.deepEqual(hostEnvironment({ SystemRoot: 'C:/Windows', TEMP: 'C:/temp', API_KEY: 'canary',
    HTTPS_PROXY: 'http://proxy', NODE_OPTIONS: '--import evil', PATH: 'untrusted' }),
  { SystemRoot: 'C:/Windows', TEMP: 'C:/temp' });
});

test('data overrides must be absolute and status must not claim implemented capabilities', () => {
  assert.throws(() => resolveDataRoot(process.cwd(), 'relative'));
  assert.equal(isHostStatus({ product: 'OpenSprite Harness', version: '0.1.0', host: 'ready',
    provider: 'not-configured', storage: 'not-initialized', outbound: 'disabled', telemetry: false }), true);
  assert.equal(isHostStatus({ product: 'OpenSprite Harness', telemetry: true }), false);
});
