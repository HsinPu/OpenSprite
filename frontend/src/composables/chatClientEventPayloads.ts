import { toPayloadSource } from "./payloadBoundary";
import {
  normalizeRunTimelinePayload,
  type RunTimelinePayload,
} from "./chatClientRunHelpers";

export type RunEventPayloadInput = {
  message?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  args_preview?: unknown;
  argsPreview?: unknown;
  action?: unknown;
  path?: unknown;
  ok?: unknown;
  result_preview?: unknown;
  resultPreview?: unknown;
  diff_preview?: unknown;
  diffPreview?: unknown;
  input_delta?: unknown;
  inputDelta?: unknown;
  content_delta?: unknown;
  contentDelta?: unknown;
  command?: unknown;
  process_session_id?: unknown;
  processSessionId?: unknown;
  exit_code?: unknown;
  exitCode?: unknown;
  had_tool_error?: unknown;
  hadToolError?: unknown;
  status?: unknown;
  error?: unknown;
};

export type RunPartDeltaPayload = {
  part_id?: unknown;
  partId?: unknown;
  part_type?: unknown;
  partType?: unknown;
  content_delta?: unknown;
  delta?: unknown;
  text?: unknown;
  content?: unknown;
  state?: unknown;
  status?: unknown;
  kind?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  metadata?: unknown;
};

export type LiveRunEventPayloadSource =
  RunTimelinePayload
  & RunPartDeltaPayload;

export function toRunEventPayloadInput(value: unknown): RunEventPayloadInput {
  const payload = toPayloadSource<RunEventPayloadInput>(value);
  if (!payload) {
    return {};
  }
  return {
    message: payload.message,
    tool_name: payload.tool_name,
    toolName: payload.toolName,
    args_preview: payload.args_preview,
    argsPreview: payload.argsPreview,
    action: payload.action,
    path: payload.path,
    ok: payload.ok,
    result_preview: payload.result_preview,
    resultPreview: payload.resultPreview,
    diff_preview: payload.diff_preview,
    diffPreview: payload.diffPreview,
    input_delta: payload.input_delta,
    inputDelta: payload.inputDelta,
    content_delta: payload.content_delta,
    contentDelta: payload.contentDelta,
    command: payload.command,
    process_session_id: payload.process_session_id,
    processSessionId: payload.processSessionId,
    exit_code: payload.exit_code,
    exitCode: payload.exitCode,
    had_tool_error: payload.had_tool_error,
    hadToolError: payload.hadToolError,
    status: payload.status,
    error: payload.error,
  };
}

export function toRunPartDeltaPayload(value: unknown): RunPartDeltaPayload {
  const payload = toPayloadSource<RunPartDeltaPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    part_id: payload.part_id,
    partId: payload.partId,
    part_type: payload.part_type,
    partType: payload.partType,
    content_delta: payload.content_delta,
    delta: payload.delta,
    text: payload.text,
    content: payload.content,
    state: payload.state,
    status: payload.status,
    kind: payload.kind,
    tool_name: payload.tool_name,
    toolName: payload.toolName,
    metadata: payload.metadata,
  };
}

export function toLiveRunEventPayloadSource(value: unknown): LiveRunEventPayloadSource {
  return {
    ...normalizeRunTimelinePayload(value),
    ...toRunPartDeltaPayload(value),
  };
}
