import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';
import { readFile, realpath, stat } from 'node:fs/promises';
import path from 'node:path';
import Fastify, { type FastifyReply, type FastifyRequest } from 'fastify';
import { PRODUCT_NAME, PRODUCT_VERSION, type HostStatus } from '../../../packages/contracts/src/host-status.js';

export const cookieName = 'opensprite_session';

export interface HostOptions {
  /** Exchanged once by Electron main over its private bootstrap connection. */
  bootstrapToken: string;
  webRoot: string;
}

export interface RunningHost {
  origin: string;
  close(): Promise<void>;
}

const csp = [
  "default-src 'none'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-ancestors 'none'",
].join('; ');

const contentTypes: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

function digest(value: string): Buffer {
  return createHash('sha256').update(value).digest();
}

function matches(value: string, expectedDigest: Buffer): boolean {
  return timingSafeEqual(digest(value), expectedDigest);
}

function authenticated(request: FastifyRequest, sessionDigest: Buffer): boolean {
  const cookies = (request.headers.cookie ?? '').split(';');
  const sessionCookies = cookies
    .map((entry) => entry.trim())
    .filter((entry) => entry.startsWith(`${cookieName}=`));
  // Duplicate credentials are ambiguous; never let cookie ordering pick one.
  return sessionCookies.length === 1
    && matches(sessionCookies[0]!.slice(cookieName.length + 1), sessionDigest);
}

function deny(reply: FastifyReply, status = 403): FastifyReply {
  return reply.code(status).send({ error: status === 404 ? 'Not found' : 'Access denied' });
}

/** Private, authenticated loopback host. This stage has no outbound clients or persistence. */
export async function createHost(options: HostOptions): Promise<RunningHost> {
  if (typeof options.bootstrapToken !== 'string'
    || options.bootstrapToken.length < 32 || options.bootstrapToken.length > 256
    || !path.isAbsolute(options.webRoot)) {
    throw new Error('Invalid host configuration');
  }
  const root = await realpath(options.webRoot);
  if (!(await stat(root)).isDirectory() || !(await stat(path.join(root, 'index.html'))).isFile()) {
    throw new Error('Desktop resources are unavailable');
  }

  const bootstrapDigest = digest(options.bootstrapToken);
  const sessionToken = randomBytes(32).toString('hex');
  const sessionDigest = digest(sessionToken);
  let bootstrapUsed = false;
  let origin = '';
  let authority = '';
  const app = Fastify({ logger: false, bodyLimit: 1024, exposeHeadRoutes: false });

  app.addHook('onRequest', async (request, reply) => {
    reply.headers({
      'Content-Security-Policy': csp,
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'no-referrer',
      'Cache-Control': 'no-store',
      'Cross-Origin-Resource-Policy': 'same-origin',
      'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), usb=()',
    });
    if (request.raw.socket.remoteAddress !== '127.0.0.1'
      || !authority || request.headers.host !== authority
      || (request.headers.origin !== undefined && request.headers.origin !== origin)
      || request.headers['sec-fetch-site'] === 'cross-site') {
      return deny(reply);
    }
  });

  app.setErrorHandler((_error, _request, reply) => {
    // Fastify errors can include paths, malformed payloads, or parser details.
    // Do not return these or enable request/body logging in the private host.
    void reply.code(400).send({ error: 'Request rejected' });
  });
  app.setNotFoundHandler((_request, reply) => deny(reply, 404));

  app.get('/health', async () => ({ status: 'ready' }));

  app.post('/internal/bootstrap', async (request, reply) => {
    const authorization = request.headers.authorization;
    if (bootstrapUsed || typeof authorization !== 'string'
      || !authorization.startsWith('Bearer ')
      || !matches(authorization.slice(7), bootstrapDigest)) {
      return deny(reply);
    }
    bootstrapUsed = true;
    reply.header('Set-Cookie', `${cookieName}=${sessionToken}; HttpOnly; SameSite=Strict; Path=/`);
    // Only main receives this response, then installs it into an ephemeral Electron session.
    return { sessionToken };
  });

  app.get('/api/v1/status', async (request, reply) => {
    if (!authenticated(request, sessionDigest)) return deny(reply);
    return {
      product: PRODUCT_NAME,
      version: PRODUCT_VERSION,
      host: 'ready',
      provider: 'not-configured',
      storage: 'not-initialized',
      outbound: 'disabled',
      telemetry: false,
    } satisfies HostStatus;
  });

  app.get('/*', async (request, reply) => {
    if (!authenticated(request, sessionDigest)) return deny(reply);
    let pathname: string;
    try {
      pathname = decodeURIComponent(request.raw.url!.split('?')[0]!);
    } catch {
      return deny(reply, 404);
    }
    if (pathname.includes('\\') || pathname.includes('\0')
      || pathname.split('/').some((segment) => segment === '..' || segment === '.')
      || (pathname !== '/' && pathname !== '/index.html' && !pathname.startsWith('/assets/'))) {
      return deny(reply, 404);
    }
    const relative = pathname === '/' ? 'index.html' : pathname.slice(1);
    try {
      const file = await realpath(path.resolve(root, relative));
      const withinRoot = path.relative(root, file);
      if (!withinRoot || withinRoot.startsWith(`..${path.sep}`)
        || withinRoot === '..' || path.isAbsolute(withinRoot)) return deny(reply, 404);
      const info = await stat(file);
      const contentType = contentTypes[path.extname(file).toLowerCase()];
      if (!info.isFile() || !contentType || info.size > 8 * 1024 * 1024) return deny(reply, 404);
      return reply.type(contentType).send(await readFile(file));
    } catch {
      return deny(reply, 404);
    }
  });

  try {
    origin = await app.listen({ host: '127.0.0.1', port: 0 });
    authority = new URL(origin).host;
    return { origin, close: () => app.close() };
  } catch (error) {
    await app.close();
    throw error;
  }
}
