import { isHostStatus, type HostStatus } from '../../../packages/contracts/src/host-status.js';

export type { HostStatus } from '../../../packages/contracts/src/host-status.js';

export async function fetchHostStatus(signal: AbortSignal): Promise<HostStatus> {
  const response = await fetch('/api/v1/status', {
    credentials: 'same-origin',
    cache: 'no-store',
    redirect: 'error',
    signal,
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error('Host status request failed.');
  const value: unknown = await response.json();
  if (!isHostStatus(value)) throw new Error('Host returned an unsupported status.');
  return value;
}
