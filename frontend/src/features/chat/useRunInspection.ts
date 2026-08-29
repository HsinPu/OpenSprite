import { useCallback, useEffect, useRef, useState } from "react";

import {
  AgentChatApiError,
  agentChatErrorText,
  getRun,
  openRunEventStream,
  type RunEvent,
  type RunEventStream,
  type RunEventStreamHandlers,
  type RunSnapshot,
} from "../../api/agentChat";
import { useI18n } from "../../i18n/I18nProvider";

type UseRunInspectionOptions = {
  conversationId: string | null;
  getRunRequest?: (runId: string) => Promise<RunSnapshot>;
  eventStreamFactory?: (runId: string, handlers: RunEventStreamHandlers) => RunEventStream;
};

const terminalEventTypes = new Set<RunEvent["type"]>([
  "run.completed",
  "run.failed",
  "run.cancelled",
  "run.interrupted",
]);

export function useRunInspection({
  conversationId,
  getRunRequest = getRun,
  eventStreamFactory = openRunEventStream,
}: UseRunInspectionOptions) {
  const { t } = useI18n();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunSnapshot | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generationRef = useRef(0);
  const streamRef = useRef<RunEventStream | null>(null);
  const seenSequencesRef = useRef(new Set<number>());

  const closeStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
  }, []);

  const returnToLatest = useCallback(() => {
    generationRef.current += 1;
    closeStream();
    seenSequencesRef.current = new Set();
    setSelectedRunId(null);
    setRun(null);
    setEvents([]);
    setLoading(false);
    setError(null);
  }, [closeStream]);

  useEffect(() => {
    returnToLatest();
  }, [conversationId, returnToLatest]);

  useEffect(() => () => {
    generationRef.current += 1;
    closeStream();
  }, [closeStream]);

  const inspectRun = useCallback(async (runId: string): Promise<void> => {
    const generation = generationRef.current + 1;
    generationRef.current = generation;
    closeStream();
    seenSequencesRef.current = new Set();
    setSelectedRunId(runId);
    setRun(null);
    setEvents([]);
    setLoading(true);
    setError(null);

    try {
      const snapshot = await getRunRequest(runId);
      if (generationRef.current !== generation) return;
      if (conversationId === null || snapshot.conversationId !== conversationId) {
        throw new AgentChatApiError("malformed_response");
      }
      setRun(snapshot);
      setLoading(false);

      let terminalReceived = false;
      const stream = eventStreamFactory(runId, {
        onEvent: (event) => {
          if (generationRef.current !== generation || seenSequencesRef.current.has(event.sequence)) return;
          seenSequencesRef.current.add(event.sequence);
          setEvents((current) => [...current, event].slice(-500));
          if (terminalEventTypes.has(event.type)) {
            terminalReceived = true;
            closeStream();
          }
        },
        onError: (streamError) => {
          if (generationRef.current !== generation) return;
          closeStream();
          setError(agentChatErrorText(streamError, t));
        },
      });
      if (generationRef.current !== generation || terminalReceived) stream.close();
      else streamRef.current = stream;
    } catch (nextError) {
      if (generationRef.current !== generation) return;
      setLoading(false);
      setError(agentChatErrorText(nextError, t));
    }
  }, [closeStream, conversationId, eventStreamFactory, getRunRequest, t]);

  const retry = useCallback(async (): Promise<void> => {
    if (selectedRunId !== null) await inspectRun(selectedRunId);
  }, [inspectRun, selectedRunId]);

  return {
    selectedRunId,
    run,
    events,
    loading,
    error,
    inspectRun,
    retry,
    returnToLatest,
  };
}
