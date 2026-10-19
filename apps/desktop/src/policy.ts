import { isAbsolute, join, resolve } from 'node:path';

export function resolveDataRoot(home: string, override?: string): string {
  if (override !== undefined && !isAbsolute(override)) throw new Error('Data directory must be absolute.');
  return resolve(override ?? join(home, '.opensprite'));
}

export function isOwnedOrigin(url: string, origin: string): boolean {
  try {
    const target = new URL(url);
    return target.origin === origin && target.username === '' && target.password === '';
  } catch { return false; }
}

export function isHostOrigin(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  try {
    const url = new URL(value);
    return url.protocol === 'http:' && url.hostname === '127.0.0.1'
      && url.port !== '' && url.pathname === '/' && url.search === '' && url.hash === ''
      && url.username === '' && url.password === '' && url.origin === value;
  } catch { return false; }
}

export function hostEnvironment(env: NodeJS.ProcessEnv): NodeJS.ProcessEnv {
  const allowed = ['SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'HOME', 'USERPROFILE'];
  return Object.fromEntries(allowed.flatMap(key => env[key] === undefined ? [] : [[key, env[key]]]));
}
