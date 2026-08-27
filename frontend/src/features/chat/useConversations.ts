import { useCallback, useEffect, useState } from "react";

import {
  agentChatErrorText,
  listConversations,
  type ConversationSummary,
} from "../../api/agentChat";

export function useConversations() {
  const [conversations, setConversations] = useState<ReadonlyArray<ConversationSummary>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const page = await listConversations();
      setConversations(page.conversations);
      setError(null);
    } catch (refreshError) {
      setError(agentChatErrorText(refreshError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const recordAcceptedConversation = useCallback((conversationId: string, firstMessage: string) => {
    const now = new Date().toISOString();
    setConversations((current) => current.some((conversation) => conversation.id === conversationId)
      ? current
      : [{
        id: conversationId,
        title: firstMessage.slice(0, 160),
        latestMessagePreview: firstMessage.slice(0, 280),
        createdAt: now,
        updatedAt: now,
      }, ...current]);
    void refresh();
  }, [refresh]);

  return {
    conversations,
    loading,
    error,
    refresh,
    recordAcceptedConversation,
  };
}
