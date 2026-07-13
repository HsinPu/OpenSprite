import type { LiveEntryMetadata, LiveEntryMetadataPayload } from "./chatClientSessions";
import { toPayloadSource } from "./payloadBoundary";

export type OutgoingMessageMetadata = {
  overlay_profile_id?: string;
};

export type OutgoingMessageInputPayload = {
  text: string;
  metadata: OutgoingMessageMetadata;
};

export function toLiveEntryMetadata(value: unknown): LiveEntryMetadata {
  const payload = toPayloadSource<LiveEntryMetadataPayload>(value);
  if (!payload) {
    return {};
  }
  const metadata: LiveEntryMetadata = {};
  const senderName = String(payload.sender_name || "").trim();
  const senderId = String(payload.sender_id || "").trim();
  const runId = String(payload.runId || "").trim();
  const legacyRunId = String(payload.run_id || "").trim();
  if (senderName) {
    metadata.sender_name = senderName;
  }
  if (senderId) {
    metadata.sender_id = senderId;
  }
  if (runId) {
    metadata.runId = runId;
  }
  if (legacyRunId) {
    metadata.run_id = legacyRunId;
  }
  return metadata;
}

export function toOutgoingMessageMetadata(value: unknown): OutgoingMessageMetadata {
  const payload = toPayloadSource<OutgoingMessageMetadata>(value);
  if (!payload) {
    return {};
  }
  if (!("overlay_profile_id" in payload)) {
    return {};
  }
  return {
    overlay_profile_id: String(payload.overlay_profile_id ?? "").trim(),
  };
}

export function toOutgoingMessageInputPayload(value: unknown): OutgoingMessageInputPayload | null {
  const payload = toPayloadSource<OutgoingMessageInputPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    text: String(payload.text || "").trim(),
    metadata: toOutgoingMessageMetadata(payload.metadata),
  };
}
