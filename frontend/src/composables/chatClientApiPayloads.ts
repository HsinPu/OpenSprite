import { coerceStringList } from "./chatClientCoercion";
import { toPayloadSource } from "./payloadBoundary";

export type SettingsErrorPayload = {
  status?: unknown;
  message?: unknown;
};

export type CommandCatalogPayload = { commands?: unknown };

export type CommandCatalogItemPayload = {
  name: string;
  command: string;
  usage: string;
  description: string;
  category: string;
  subcommands: string[];
};

export function toSettingsErrorPayload(value: unknown): SettingsErrorPayload | null {
  const payload = toPayloadSource<SettingsErrorPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    status: payload.status,
    message: payload.message,
  };
}

export function toCommandCatalogPayload(value: unknown): CommandCatalogPayload | null {
  const payload = toPayloadSource<CommandCatalogPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    commands: payload.commands,
  };
}

export function toCommandCatalogItemPayload(value: unknown): CommandCatalogItemPayload | null {
  const payload = toPayloadSource<CommandCatalogItemPayload>(value);
  if (!payload) {
    return null;
  }
  const name = String(payload.name || "").trim();
  const command = String(payload.command || (name ? `/${name}` : "")).trim();
  return {
    name,
    command,
    usage: String(payload.usage || command).trim() || command,
    description: String(payload.description || "").trim(),
    category: String(payload.category || "").trim(),
    subcommands: coerceStringList(payload.subcommands),
  };
}
