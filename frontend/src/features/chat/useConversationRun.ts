import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  AgentChatApiError,
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


export type DisplayMessage = Pick<ChatMessage, "id" | "role" | "content" | "createdAt"> & {
  runId: string | null;
  delivery: "persisted" | "sending" | "failed";
};

type UseConversationRunOptions = {
  conversationId: string | null;
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
  onConversationAccepted,
  onConversationUpdated,
  responseDelivery,
  requestIdFactory = defaultRequestId,
  eventStreamFactory = openRunEventStream,
}: UseConversationRunOptions) {
  const { t } = useI18n();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [activeRun, setActiveRun] = useState<RunSnapshot | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [streamedText, setStreamedText] = useState("");
  const [loading, setLoading] = useState(conversationId !== null);
  const [loadingOlderMessages, setLoadingOlderMessages] = useState(false);
  const [nextBeforeSequence, setNextBeforeSequence] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const generationRef = useRef(0);
  const streamRef = useRef<RunEventStream | null>(null);
  const activeRunRef = useRef<RunSnapshot | null>(null);
  const resolvedConversationRef = useRef<string | null>(conversationId);
  const seenEventSequencesRef = useRef(new Set<number>());
  const finishingRunsRef = useRef(new Set<string>());
  const responseDeliveryRef = useRef(responseDelivery);

  useEffect(() => {
    responseDeliveryRef.current = responseDelivery;
  }, [responseDelivery]);

  useEffect(() => {
    activeRunRef.current = activeRun;
  }, [activeRun]);

  const closeStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
  }, []);

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
      setError(run.error ? agentChatErrorText(new AgentChatApiError(run.error.code), t) : null);
      onConversationUpdated();
      closeStream();
    } catch (nextError) {
      if (generationRef.current === generation) setError(agentChatErrorText(nextError, t));
    } finally {
      finishingRunsRef.current.delete(runId);
    }
  }, [closeStream, commitRun, onConversationUpdated, t]);

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
          setEvents((current) => [...current, event].slice(-500));
          if (event.type === "assistant.delta") {
            const text = String(event.data.text);
            if (!receivedDelta) bufferedText = "";
            receivedDelta = true;
            bufferedText += text;
            if (delivery === "stream") setStreamedText(bufferedText);
          }
          if (event.type === "run.started") {
            updateRun((current) => current ? { ...current, status: "running", startedAt: current.startedAt ?? event.createdAt } : current);
          }
          if (terminalTypes.has(event.type)) {
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
  }, [closeStream, eventStreamFactory, refreshTerminal, t, updateRun]);

  useEffect(() => {
    const generation = generationRef.current + 1;
    generationRef.current = generation;
    closeStream();
    resolvedConversationRef.current = conversationId;
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
    const message = content.trim();
    if (!message || (activeRunRef.current && activeStatuses.has(activeRunRef.current.status))) return false;
    const generation = generationRef.current;
    let clientRequestId: string;
    try {
      clientRequestId = requestIdFactory();
    } catch (nextError) {
      setError(agentChatErrorText(nextError, t));
      return false;
    }
    setError(null);
    setEvents([]);
    setStreamedText("");
    setMessages((current) => [...current, {
      id: clientRequestId,
      role: "user",
      content: message,
      createdAt: new Date().toISOString(),
      runId: null,
      delivery: "sending",
    }]);
    try {
      const accepted = await startRun({
        conversationId: resolvedConversationRef.current,
        clientRequestId,
        message,
      });
      if (generationRef.current !== generation) return false;
      resolvedConversationRef.current = accepted.conversationId;
      onConversationAccepted(accepted.conversationId, message);
      const [page, run] = await Promise.all([
        listConversationMessages(accepted.conversationId),
        getRun(accepted.runId),
      ]);
      if (generationRef.current !== generation) return false;
      setMessages(persistedMessages(page.messages));
      setNextBeforeSequence(page.nextBeforeSequence);
      commitRun(run);
      setStreamedText(responseDeliveryRef.current === "stream" ? run.partialText : "");
      watchRun(run.id, generation, run.partialText, responseDeliveryRef.current);
      return true;
    } catch (nextError) {
      if (generationRef.current === generation) {
        setMessages((current) => current.map((item) => item.id === clientRequestId ? { ...item, delivery: "failed" } : item));
        setError(agentChatErrorText(nextError, t));
      }
      return false;
    }
  }, [commitRun, onConversationAccepted, requestIdFactory, t, watchRun]);

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
    send,
    cancel,
    loadOlderMessages,
  };
}
