import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  AgentChatApiError,
  DEFAULT_WORKSPACE_ID,
  agentChatErrorText,
  cancelRun,
  getRun,
  listConversationMessages,
  openRunEventStream,
  startRun,
  type ChatMessage,
  type RunError,
  type RunEvent,
  type RunEventStream,
  type RunEventStreamHandlers,
  type RunSnapshot,
} from "../../api/agentChat";
import type { ResponseDelivery } from "../../api/aiSettings";
import { useI18n } from "../../i18n/I18nProvider";
import { appendEventPreservingContextUsage } from "./contextUsage";


export type DisplayMessage = Pick<ChatMessage, "id" | "role" | "content" | "createdAt"> & {
  runId: string | null;
  delivery: "persisted" | "sending" | "failed";
};

type UseConversationRunOptions = {
  conversationId: string | null;
  workspaceId?: string;
  onConversationAccepted: (conversationId: string, firstMessage: string) => void;
  onConversationUpdated: () => void;
  responseDelivery: ResponseDelivery;
  requestIdFactory?: () => string;
  eventStreamFactory?: (runId: string, handlers: RunEventStreamHandlers) => RunEventStream;
};

const terminalTypes = new Set(["run.completed", "run.failed", "run.cancelled", "run.interrupted"]);
const activeStatuses = new Set(["queued", "running", "cancelling"]);

const persistedMessages = (messages: ChatMessage[]): DisplayMessage[] => messages.map((message) => ({
  id: message.id,
  role: message.role,
  content: message.content,
  createdAt: message.createdAt,
  runId: message.runId,
  delivery: "persisted",
}));

function applyTerminalEvent(current: RunSnapshot | null, event: RunEvent): RunSnapshot | null {
  if (!current || current.id !== event.runId) return current;
  const finishedAt = event.createdAt;
  switch (event.type) {
    case "run.completed":
      return {
        ...current,
        status: "completed",
        assistantMessageId: event.data.assistantMessageId as string,
        completionReason: event.data.completionReason as RunSnapshot["completionReason"],
        startedAt: current.startedAt ?? finishedAt,
        finishedAt,
        error: null,
      };
    case "run.failed":
      return {
        ...current,
        status: "failed",
        assistantMessageId: null,
        completionReason: null,
        startedAt: current.startedAt ?? finishedAt,
        finishedAt,
        error: event.data.error as RunError,
      };
    case "run.cancelled":
      return { ...current, status: "cancelled", assistantMessageId: null, completionReason: null, finishedAt, error: null };
    case "run.interrupted":
      return { ...current, status: "interrupted", assistantMessageId: null, completionReason: null, finishedAt, error: event.data.error as RunError };
    default:
      return current;
  }
}

function defaultRequestId(): string {
  if (typeof globalThis.crypto?.randomUUID !== "function") throw new Error("randomUUID unavailable");
  return globalThis.crypto.randomUUID();
}

export function useConversationRun({
  conversationId,
  workspaceId = DEFAULT_WORKSPACE_ID,
  onConversationAccepted,
  onConversationUpdated,
  responseDelivery,
  requestIdFactory = defaultRequestId,
  eventStreamFactory = openRunEventStream,
}: UseConversationRunOptions) {
  const { t: translate } = useI18n();
  const updatedCallbackRef = useRef(onConversationUpdated);
  updatedCallbackRef.current = onConversationUpdated;
  const translatorRef = useRef(translate);
  translatorRef.current = translate;
  const t = useCallback((...args: Parameters<typeof translate>) => translatorRef.current(...args), []);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [activeRun, setActiveRun] = useState<RunSnapshot | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [streamedText, setStreamedText] = useState("");
  const [loading, setLoading] = useState(conversationId !== null);
  const [loadingOlderMessages, setLoadingOlderMessages] = useState(false);
  const [nextBeforeSequence, setNextBeforeSequence] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isRecovering, setIsRecovering] = useState(false);
  const recoveryBusyRef = useRef(false);
  const recoveryAttemptsRef = useRef(0);
  const [recoveryEpoch, setRecoveryEpoch] = useState(0);
  const terminalHydrationPendingRef = useRef(false);
  const acceptedRunRef = useRef<{ runId: string; conversationId: string } | null>(null);
  const sendingRef = useRef(false);
  const pendingRequestRef = useRef<{ conversationId: string | null; workspaceId: string; message: string; clientRequestId: string } | null>(null);
  const generationRef = useRef(0);
  const streamRef = useRef<RunEventStream | null>(null);
  const activeRunRef = useRef<RunSnapshot | null>(null);
  const resolvedConversationRef = useRef<string | null>(conversationId);
  const seenEventSequencesRef = useRef(new Set<number>());
  const finishingRunsRef = useRef(new Set<string>());
  const responseDeliveryRef = useRef(responseDelivery);
  const renderFrameRef = useRef<number | null>(null);
  const pendingEventsRef = useRef<RunEvent[]>([]);
  const pendingStreamedTextRef = useRef<string | null>(null);

  useEffect(() => {
    responseDeliveryRef.current = responseDelivery;
  }, [responseDelivery]);

  useEffect(() => {
    activeRunRef.current = activeRun;
  }, [activeRun]);

  const discardScheduledRender = useCallback(() => {
    const frame = renderFrameRef.current;
    if (frame !== null) {
      if (typeof window.cancelAnimationFrame === "function") window.cancelAnimationFrame(frame);
      else window.clearTimeout(frame);
      renderFrameRef.current = null;
    }
    pendingEventsRef.current = [];
    pendingStreamedTextRef.current = null;
  }, []);

  const flushScheduledRender = useCallback(() => {
    const frame = renderFrameRef.current;
    if (frame !== null) {
      if (typeof window.cancelAnimationFrame === "function") window.cancelAnimationFrame(frame);
      else window.clearTimeout(frame);
      renderFrameRef.current = null;
    }
    const pendingEvents = pendingEventsRef.current;
    pendingEventsRef.current = [];
    if (pendingEvents.length > 0) {
      setEvents((current) => pendingEvents.reduce(
        (next, event) => appendEventPreservingContextUsage(next, event),
        current,
      ));
    }
    const pendingText = pendingStreamedTextRef.current;
    pendingStreamedTextRef.current = null;
    if (pendingText !== null) setStreamedText(pendingText);
  }, []);

  const scheduleRender = useCallback(() => {
    if (renderFrameRef.current !== null) return;
    const flush = () => {
      renderFrameRef.current = null;
      const pendingEvents = pendingEventsRef.current;
      pendingEventsRef.current = [];
      if (pendingEvents.length > 0) {
        setEvents((current) => pendingEvents.reduce(
          (next, event) => appendEventPreservingContextUsage(next, event),
          current,
        ));
      }
      const pendingText = pendingStreamedTextRef.current;
      pendingStreamedTextRef.current = null;
      if (pendingText !== null) setStreamedText(pendingText);
    };
    if (typeof window.requestAnimationFrame === "function") renderFrameRef.current = window.requestAnimationFrame(flush);
    else renderFrameRef.current = window.setTimeout(flush, 16);
  }, []);

  const closeStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
    discardScheduledRender();
  }, [discardScheduledRender]);

  const commitRun = useCallback((run: RunSnapshot | null) => {
    activeRunRef.current = run;
    setActiveRun(run);
  }, []);

  const updateRun = useCallback((updater: (current: RunSnapshot | null) => RunSnapshot | null) => {
    setActiveRun((current) => {
      const next = updater(current);
      activeRunRef.current = next;
      return next;
    });
  }, []);

  const refreshTerminal = useCallback(async (runId: string, eventConversationId: string, generation: number) => {
    if (finishingRunsRef.current.has(runId)) return;
    finishingRunsRef.current.add(runId);
    terminalHydrationPendingRef.current = true;
    try {
      const [run, page] = await Promise.all([
        getRun(runId),
        listConversationMessages(eventConversationId),
      ]);
      if (generationRef.current !== generation || resolvedConversationRef.current !== eventConversationId) return;
      commitRun(run);
      setMessages(persistedMessages(page.messages));
      setNextBeforeSequence(page.nextBeforeSequence);
      setStreamedText((current) => run.partialText || current);
      terminalHydrationPendingRef.current = false;
      setError(run.error ? agentChatErrorText(new AgentChatApiError(run.error.code), t) : null);
      updatedCallbackRef.current();
      closeStream();
    } catch (nextError) {
      if (generationRef.current === generation) setError(agentChatErrorText(nextError, t));
    } finally {
      finishingRunsRef.current.delete(runId);
    }
  }, [closeStream, commitRun, t]);

  const watchRun = useCallback((runId: string, generation: number, initialText = "", delivery: ResponseDelivery = responseDeliveryRef.current) => {
    closeStream();
    seenEventSequencesRef.current = new Set();
    setEvents([]);
    setStreamedText(delivery === "stream" ? initialText : "");
    let bufferedText = initialText;
    let receivedDelta = false;
    try {
      streamRef.current = eventStreamFactory(runId, {
        onEvent: (event) => {
          if (generationRef.current !== generation || seenEventSequencesRef.current.has(event.sequence)) return;
          seenEventSequencesRef.current.add(event.sequence);
          setError(null);
          if (event.type === "assistant.delta") {
            const text = String(event.data.text);
            if (!receivedDelta) bufferedText = "";
            receivedDelta = true;
            bufferedText += text;
            pendingEventsRef.current.push(event);
            if (delivery === "stream") pendingStreamedTextRef.current = bufferedText;
            scheduleRender();
          } else {
            flushScheduledRender();
            setEvents((current) => appendEventPreservingContextUsage(current, event));
          }
          if (event.type === "run.started") {
            updateRun((current) => current ? { ...current, status: "running", startedAt: current.startedAt ?? event.createdAt } : current);
          }
          if (terminalTypes.has(event.type)) {
            flushScheduledRender();
            if (delivery === "complete") setStreamedText(bufferedText);
            closeStream();
            updateRun((current) => applyTerminalEvent(current, event));
            void refreshTerminal(runId, event.conversationId, generation);
          }
        },
        onError: (streamError) => {
          if (delivery === "complete" && bufferedText) setStreamedText(bufferedText);
          if (generationRef.current === generation) setError(agentChatErrorText(streamError, t));
        },
      });
    } catch (streamError) {
      if (delivery === "complete" && bufferedText) setStreamedText(bufferedText);
      if (generationRef.current === generation) setError(agentChatErrorText(streamError, t));
    }
  }, [closeStream, eventStreamFactory, flushScheduledRender, refreshTerminal, scheduleRender, t, updateRun]);

  const reloadAcceptedRun = useCallback(async () => {
    if (recoveryBusyRef.current || sendingRef.current || pendingRequestRef.current) return;
    const targetConversation = acceptedRunRef.current?.conversationId ?? resolvedConversationRef.current;
    if (!targetConversation) return;
    const targetRun = acceptedRunRef.current?.runId ?? activeRunRef.current?.id;
    const generation = generationRef.current;
    recoveryBusyRef.current = true;
    setIsRecovering(true);
    try {
      const page = await listConversationMessages(targetConversation);
      const runId = targetRun ?? page.messages.at(-1)?.runId;
      const recovered = runId ? await getRun(runId) : null;
      if (generationRef.current !== generation) return;
      setMessages(persistedMessages(page.messages));
      setNextBeforeSequence(page.nextBeforeSequence);
      commitRun(recovered);
      terminalHydrationPendingRef.current = false;
      setError(recovered?.error ? agentChatErrorText(new AgentChatApiError(recovered.error.code), t) : null);
      if (recovered && activeStatuses.has(recovered.status)) watchRun(recovered.id, generation, recovered.partialText, responseDeliveryRef.current);
      else closeStream();
    } catch (nextError) {
      if (generationRef.current === generation) setError(agentChatErrorText(nextError, t));
    } finally {
      if (generationRef.current === generation) {
        recoveryBusyRef.current = false;
        setIsRecovering(false);
        setRecoveryEpoch((current) => current + 1);
      }
    }
  }, [closeStream, commitRun, t, watchRun]);

  useEffect(() => {
    if (!error || isRecovering || isSending || recoveryAttemptsRef.current >= 3 || !acceptedRunRef.current) return;
    if (!terminalHydrationPendingRef.current && activeRunRef.current?.id === acceptedRunRef.current.runId && !activeStatuses.has(activeRunRef.current.status)) return;
    const timer = window.setTimeout(() => {
      recoveryAttemptsRef.current += 1;
      void reloadAcceptedRun();
    }, 1000 * (2 ** recoveryAttemptsRef.current));
    return () => window.clearTimeout(timer);
  }, [error, isRecovering, isSending, reloadAcceptedRun, recoveryEpoch]);

  useEffect(() => {
    const generation = generationRef.current + 1;
    generationRef.current = generation;
    closeStream();
    resolvedConversationRef.current = conversationId;
    if (acceptedRunRef.current?.conversationId !== conversationId) acceptedRunRef.current = null;
    recoveryBusyRef.current = false;
    recoveryAttemptsRef.current = 0;
    terminalHydrationPendingRef.current = false;
    setIsRecovering(false);
    sendingRef.current = false;
    setIsSending(false);
    pendingRequestRef.current = null;
    finishingRunsRef.current.clear();
    seenEventSequencesRef.current = new Set();
    setEvents([]);
    setStreamedText("");
    setNextBeforeSequence(null);
    setLoadingOlderMessages(false);
    setError(null);
    if (conversationId === null) {
      setMessages([]);
      commitRun(null);
      setLoading(false);
      return () => { if (generationRef.current === generation) generationRef.current += 1; };
    }
    setLoading(true);
    void listConversationMessages(conversationId)
      .then(async (page) => {
        if (generationRef.current !== generation) return;
        setMessages(persistedMessages(page.messages));
        setNextBeforeSequence(page.nextBeforeSequence);
        const latest = page.messages.at(-1);
        if (!latest) {
          commitRun(null);
          return;
        }
        const run = await getRun(latest.runId);
        if (generationRef.current !== generation) return;
        commitRun(run);
        acceptedRunRef.current = { runId: run.id, conversationId: run.conversationId };
        setStreamedText(responseDeliveryRef.current === "stream" ? run.partialText : "");
        watchRun(run.id, generation, run.partialText, responseDeliveryRef.current);
      })
      .catch((nextError: unknown) => {
        if (generationRef.current === generation) setError(agentChatErrorText(nextError, t));
      })
      .finally(() => {
        if (generationRef.current === generation) setLoading(false);
      });
    return () => {
      if (generationRef.current === generation) generationRef.current += 1;
      closeStream();
    };
  }, [closeStream, commitRun, conversationId, t, watchRun]);

  const send = useCallback(async (content: string): Promise<boolean> => {
    const submittedMessage = content.trim();
    const previous = pendingRequestRef.current;
    const message = previous?.message ?? submittedMessage;
    if (!message || sendingRef.current || recoveryBusyRef.current
      || (acceptedRunRef.current && acceptedRunRef.current.runId !== activeRunRef.current?.id)
      || (activeRunRef.current && activeStatuses.has(activeRunRef.current.status))) return false;
    const generation = generationRef.current;
    let clientRequestId: string;
    try {
      clientRequestId = previous?.clientRequestId ?? requestIdFactory();
    } catch (nextError) {
      setError(agentChatErrorText(nextError, t));
      return false;
    }
    sendingRef.current = true;
    setIsSending(true);
    const request = previous ?? { conversationId: resolvedConversationRef.current, workspaceId, clientRequestId, message };
    pendingRequestRef.current = request;
    setError(null);
    setEvents([]);
    setStreamedText("");
    setMessages((current) => [...current.filter((item) => item.id !== clientRequestId), {
      id: clientRequestId,
      role: "user",
      content: message,
      createdAt: new Date().toISOString(),
      runId: null,
      delivery: "sending",
    }]);
    let wasAccepted = false;
    try {
      const accepted = await startRun(request);
      wasAccepted = true;
      if (generationRef.current !== generation) return submittedMessage === message;
      pendingRequestRef.current = null;
      acceptedRunRef.current = { runId: accepted.runId, conversationId: accepted.conversationId };
      recoveryAttemptsRef.current = 0;
      resolvedConversationRef.current = accepted.conversationId;
      onConversationAccepted(accepted.conversationId, message);
      const [page, run] = await Promise.all([
        listConversationMessages(accepted.conversationId),
        getRun(accepted.runId),
      ]);
      if (generationRef.current !== generation) return submittedMessage === message;
      setMessages(persistedMessages(page.messages));
      setNextBeforeSequence(page.nextBeforeSequence);
      commitRun(run);
      setStreamedText(responseDeliveryRef.current === "stream" ? run.partialText : "");
      watchRun(run.id, generation, run.partialText, responseDeliveryRef.current);
      return submittedMessage === message;
    } catch (nextError) {
      if (generationRef.current === generation) {
        if (!wasAccepted && !previous && nextError instanceof AgentChatApiError
          && ["invalid_request", "idempotency_conflict", "workspace_not_found", "run_busy", "model_not_selected", "provider_not_connected", "workspace_mismatch"].includes(nextError.code)) {
          pendingRequestRef.current = null;
        }
        if (!wasAccepted) setMessages((current) => current.map((item) => item.id === clientRequestId ? { ...item, delivery: "failed" } : item));
        setError(agentChatErrorText(nextError, t));
      }
      return wasAccepted && submittedMessage === message;
    } finally {
      if (generationRef.current === generation) {
        sendingRef.current = false;
        setIsSending(false);
      }
    }
  }, [commitRun, onConversationAccepted, requestIdFactory, t, watchRun, workspaceId]);

  const recoverConnection = useCallback(async (): Promise<void> => {
    if (sendingRef.current || recoveryBusyRef.current) return;
    if (pendingRequestRef.current) {
      await send("");
      return;
    }
    await reloadAcceptedRun();
  }, [send, reloadAcceptedRun]);

  const cancel = useCallback(async (): Promise<void> => {
    const run = activeRunRef.current;
    if (!run || !activeStatuses.has(run.status)) return;
    const generation = generationRef.current;
    try {
      const result = await cancelRun(run.id);
      if (generationRef.current !== generation) return;
      updateRun((current) => current && current.id === run.id ? { ...current, status: result.status } : current);
    } catch (nextError) {
      if (
        generationRef.current === generation
        && activeRunRef.current?.id === run.id
      ) {
        setError(agentChatErrorText(nextError, t));
      }
    }
  }, [t, updateRun]);

  const loadOlderMessages = useCallback(async (): Promise<void> => {
    const beforeSequence = nextBeforeSequence;
    const targetConversation = resolvedConversationRef.current;
    const generation = generationRef.current;
    if (
      beforeSequence === null
      || targetConversation === null
      || loadingOlderMessages
    ) {
      return;
    }
    setLoadingOlderMessages(true);
    try {
      const page = await listConversationMessages(targetConversation, {
        beforeSequence,
      });
      if (
        generationRef.current !== generation
        || resolvedConversationRef.current !== targetConversation
      ) {
        return;
      }
      setMessages((current) => {
        const known = new Set(current.map((message) => message.id));
        return [
          ...persistedMessages(page.messages).filter((message) => !known.has(message.id)),
          ...current,
        ];
      });
      setNextBeforeSequence(page.nextBeforeSequence);
      setError(null);
    } catch (nextError) {
      if (generationRef.current === generation) {
        setError(agentChatErrorText(nextError, t));
      }
    } finally {
      if (generationRef.current === generation) setLoadingOlderMessages(false);
    }
  }, [loadingOlderMessages, nextBeforeSequence, t]);

  const isRunning = useMemo(() => activeRun !== null && activeStatuses.has(activeRun.status), [activeRun]);

  return {
    messages,
    activeRun,
    events,
    streamedText,
    loading,
    loadingOlderMessages,
    hasOlderMessages: nextBeforeSequence !== null,
    error,
    isRunning,
    isSending: isSending || Boolean(acceptedRunRef.current && acceptedRunRef.current.runId !== activeRun?.id),
    isRecovering,
    hasPendingSubmission: Boolean(pendingRequestRef.current),
    canRecover: Boolean(pendingRequestRef.current || acceptedRunRef.current || resolvedConversationRef.current),
    recoverConnection,
    send,
    cancel,
    loadOlderMessages,
  };
}
