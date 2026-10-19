import { createHost, type RunningHost } from './host.js';

// Keep this transport narrow and avoid importing Electron's main-process runtime into Host.
interface ParentPort {
  on(event: 'message', listener: (event: { data: unknown }) => void): void;
  postMessage(message: unknown): void;
}

const parentPort = (process as NodeJS.Process & { parentPort?: ParentPort }).parentPort;
let host: RunningHost | undefined;
let starting: Promise<RunningHost> | undefined;
let stopping = false;

async function stop(code: number): Promise<never> {
  stopping = true;
  try {
    await starting?.catch(() => undefined);
    await host?.close();
  } finally {
    process.exit(code);
  }
}

function fatal(): void {
  if (stopping) return;
  parentPort?.postMessage({ type: 'fatal', message: 'Local host could not start' });
  void stop(1);
}

if (!parentPort) {
  process.exit(1);
} else {
  process.on('uncaughtException', fatal);
  process.on('unhandledRejection', fatal);
  parentPort.on('message', ({ data }) => {
    if (typeof data !== 'object' || data === null) return fatal();
    const message = data as Record<string, unknown>;
    if (message.type === 'shutdown') {
      void stop(0);
      return;
    }
    if (message.type !== 'start' || starting || stopping
      || typeof message.bootstrapToken !== 'string' || typeof message.webRoot !== 'string') {
      return fatal();
    }
    starting = createHost({ bootstrapToken: message.bootstrapToken, webRoot: message.webRoot });
    void starting.then((running) => {
      host = running;
      if (!stopping) parentPort.postMessage({ type: 'ready', origin: running.origin });
    }).catch(fatal);
  });
}
