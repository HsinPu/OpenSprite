import { useCallback, useEffect, useRef, useState } from "react";

import {
  agentChatErrorText,
  listConversations,
  UNASSIGNED_WORKSPACE_ID,
  type ConversationSummary,
} from "../../api/agentChat";
import { useI18n } from "../../i18n/I18nProvider";

export function useConversations(workspaceId = UNASSIGNED_WORKSPACE_ID, enabled = true) {
  const { t } = useI18n();
  const [conversations, setConversations] = useState<ReadonlyArray<ConversationSummary>>([]);
  const [loading, setLoading] = useState(enabled);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadedWorkspaceId, setLoadedWorkspaceId] = useState<string | null>(null);
  const requestGenerationRef = useRef(0);
  const loadingMoreRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    const generation = requestGenerationRef.current + 1;
    requestGenerationRef.current = generation;
    loadingMoreRef.current = false;
    setLoadingMore(false);
    setLoading(true);
    try {
      const page = await listConversations({ workspaceId });
      if (requestGenerationRef.current !== generation) return;
      setConversations(page.conversations);
      setNextCursor(page.nextCursor);
      setError(null);
    } catch (refreshError) {
      if (requestGenerationRef.current === generation) {
        setError(agentChatErrorText(refreshError, t));
      }
    } finally {
      if (requestGenerationRef.current === generation) {
        setLoadedWorkspaceId(workspaceId);
        setLoading(false);
      }
    }
  }, [enabled, t, workspaceId]);

  const loadMore = useCallback(async () => {
    const cursor = nextCursor;
    if (!enabled || cursor === null || loadingMoreRef.current) return;
    const generation = requestGenerationRef.current;
    loadingMoreRef.current = true;
    setLoadingMore(true);
    try {
      const page = await listConversations({ workspaceId, before: cursor });
      if (requestGenerationRef.current !== generation) return;
      setConversations((current) => {
        const known = new Set(current.map((conversation) => conversation.id));
        return [
          ...current,
          ...page.conversations.filter((conversation) => !known.has(conversation.id)),
        ];
      });
      setNextCursor(page.nextCursor);
      setError(null);
    } catch (loadError) {
      if (requestGenerationRef.current === generation) {
        setError(agentChatErrorText(loadError, t));
      }
    } finally {
      loadingMoreRef.current = false;
      if (requestGenerationRef.current === generation) setLoadingMore(false);
    }
  }, [enabled, nextCursor, t, workspaceId]);

  useEffect(() => {
    if (!enabled) {
      requestGenerationRef.current += 1;
      setConversations([]);
      setLoadedWorkspaceId(null);
      setNextCursor(null);
      setError(null);
      setLoading(false);
      return;
    }
    void refresh();
  }, [enabled, refresh]);

  const recordAcceptedConversation = useCallback((conversationId: string, firstMessage: string) => {
    const now = new Date().toISOString();
    setConversations((current) => current.some((conversation) => conversation.id === conversationId)
      ? current
      : [{
        id: conversationId,
        workspaceId,
        revision: 1,
        workspaceManagedBySchedule: false,
        title: firstMessage.slice(0, 160),
        latestMessagePreview: firstMessage.slice(0, 280),
        createdAt: now,
        updatedAt: now,
      }, ...current]);
    void refresh();
  }, [refresh, workspaceId]);

  return {
    conversations,
    loading,
    error,
    hasMore: nextCursor !== null,
    loadingMore,
    loadedWorkspaceId,
    refresh,
    loadMore,
    recordAcceptedConversation,
  };
}
