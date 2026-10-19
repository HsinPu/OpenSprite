export const PRODUCT_NAME = 'OpenSprite Harness' as const;
export const PRODUCT_VERSION = '0.1.0' as const;

export interface HostStatus {
  product: typeof PRODUCT_NAME;
  version: typeof PRODUCT_VERSION;
  host: 'ready';
  provider: 'not-configured';
  storage: 'not-initialized';
  outbound: 'disabled';
  telemetry: false;
}

export function isHostStatus(value: unknown): value is HostStatus {
  if (typeof value !== 'object' || value === null) return false;
  const status = value as Record<string, unknown>;
  return status.product === PRODUCT_NAME && status.version === PRODUCT_VERSION
    && status.host === 'ready' && status.provider === 'not-configured'
    && status.storage === 'not-initialized' && status.outbound === 'disabled'
    && status.telemetry === false;
}
