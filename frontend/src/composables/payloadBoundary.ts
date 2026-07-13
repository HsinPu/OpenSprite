type PayloadSource<Payload extends object> = {
  [Key in keyof Payload]?: unknown;
};

export function toPayloadSource<Payload extends object>(value: unknown): PayloadSource<Payload> | null;
export function toPayloadSource(value: unknown): object | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
}

export function toPayloadList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}
