import { useCallback, useLayoutEffect, useRef } from "react";

type UseConversationAutoScrollOptions = {
  enabled: boolean;
  conversationId: string | null;
  loading: boolean;
  messageCount: number;
  streamedText: string;
  showLiveAssistant: boolean;
};

const BOTTOM_THRESHOLD_PX = 96;

export function useConversationAutoScroll({
  enabled,
  conversationId,
  loading,
  messageCount,
  streamedText,
  showLiveAssistant,
}: UseConversationAutoScrollOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const followOutputRef = useRef(enabled);
  const positionedConversationRef = useRef(false);
  const conversationGenerationRef = useRef(0);
  const frameRef = useRef<number | null>(null);

  const cancelScheduledScroll = useCallback(() => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
  }, []);

  const scheduleBottom = useCallback(() => {
    if (frameRef.current !== null) return;
    let completedSynchronously = false;
    const frame = requestAnimationFrame(() => {
      completedSynchronously = true;
      frameRef.current = null;
      const container = containerRef.current;
      if (container) container.scrollTop = container.scrollHeight;
    });
    if (!completedSynchronously) frameRef.current = frame;
  }, []);

  useLayoutEffect(() => {
    conversationGenerationRef.current += 1;
    positionedConversationRef.current = false;
    followOutputRef.current = enabled;
    cancelScheduledScroll();
  }, [cancelScheduledScroll, conversationId]);

  useLayoutEffect(() => {
    if (!enabled) {
      followOutputRef.current = false;
      cancelScheduledScroll();
    }
  }, [cancelScheduledScroll, enabled]);

  useLayoutEffect(() => {
    if (loading) return;
    if (!positionedConversationRef.current) {
      positionedConversationRef.current = true;
      scheduleBottom();
      return;
    }
    if (enabled && followOutputRef.current) scheduleBottom();
  }, [enabled, loading, messageCount, scheduleBottom, showLiveAssistant, streamedText]);

  useLayoutEffect(() => () => cancelScheduledScroll(), [cancelScheduledScroll]);

  const onScroll = useCallback(() => {
    const container = containerRef.current;
    if (!enabled || !container) {
      followOutputRef.current = false;
      return;
    }
    const distanceFromBottom = container.scrollHeight - container.clientHeight - container.scrollTop;
    followOutputRef.current = distanceFromBottom <= BOTTOM_THRESHOLD_PX;
  }, [enabled]);

  const followLatest = useCallback(() => {
    if (!enabled) return;
    followOutputRef.current = true;
    scheduleBottom();
  }, [enabled, scheduleBottom]);

  const preservePositionWhilePrepending = useCallback(async (load: () => Promise<void>): Promise<void> => {
    const container = containerRef.current;
    if (!container) {
      await load();
      return;
    }
    const generation = conversationGenerationRef.current;
    const previousHeight = container.scrollHeight;
    const previousTop = container.scrollTop;
    followOutputRef.current = false;
    cancelScheduledScroll();
    try {
      await load();
    } finally {
      requestAnimationFrame(() => {
        if (conversationGenerationRef.current !== generation || containerRef.current !== container) return;
        container.scrollTop = previousTop + (container.scrollHeight - previousHeight);
      });
    }
  }, [cancelScheduledScroll]);

  return {
    containerRef,
    onScroll,
    followLatest,
    preservePositionWhilePrepending,
  };
}
