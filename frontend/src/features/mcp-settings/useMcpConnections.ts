import { useCallback, useEffect, useRef, useState } from "react";

import {
  createMcpServer,
  deleteMcpServer,
  listMcpServers,
  listMcpTools,
  mcpErrorText,
  startMcpServer,
  stopMcpServer,
  testMcpServer,
  updateMcpServer,
  type McpServerDraft,
  type McpServerSummary,
  type McpToolSummary,
} from "../../api/mcpConnections";
import { useI18n } from "../../i18n/I18nProvider";


export type McpConnectionsController = {
  servers: McpServerSummary[];
  tools: Readonly<Record<string, McpToolSummary[]>>;
  loaded: boolean;
  error: string | null;
  busyServerId: string | null;
  reload: () => Promise<void>;
  create: (draft: McpServerDraft) => Promise<string | null>;
  update: (id: string, draft: McpServerDraft) => Promise<string | null>;
  remove: (id: string) => Promise<string | null>;
  test: (id: string) => Promise<string | null>;
  start: (id: string) => Promise<string | null>;
  stop: (id: string) => Promise<string | null>;
  loadTools: (id: string) => Promise<string | null>;
};

export function useMcpConnections(): McpConnectionsController {
  const { t } = useI18n();
  const [servers, setServers] = useState<McpServerSummary[]>([]);
  const [tools, setTools] = useState<Record<string, McpToolSummary[]>>({});
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyServerId, setBusyServerId] = useState<string | null>(null);
  const generationRef = useRef(0);

  const reload = useCallback(async () => {
    const generation = generationRef.current + 1;
    generationRef.current = generation;
    setError(null);
    try {
      const result = await listMcpServers();
      if (generationRef.current !== generation) return;
      setServers(result);
      const connected = result.filter((server) => server.status === "connected");
      const discovered = await Promise.all(connected.map(async (server) => [server.id, await listMcpTools(server.id)] as const));
      if (generationRef.current !== generation) return;
      setTools(Object.fromEntries(discovered));
      setLoaded(true);
    } catch (nextError) {
      if (generationRef.current !== generation) return;
      setError(mcpErrorText(nextError, t));
      setLoaded(false);
    }
  }, [t]);
  useEffect(() => { void reload(); }, [reload]);

  const operation = useCallback(async (id: string, action: () => Promise<McpServerSummary | void>): Promise<string | null> => {
    if (busyServerId !== null) return t("error.mcp.busy");
    setBusyServerId(id);
    setError(null);
    try {
      const result = await action();
      if (result) setServers((current) => current.map((item) => item.id === result.id ? result : item));
      else setServers((current) => current.filter((item) => item.id !== id));
      return null;
    } catch (nextError) {
      const message = mcpErrorText(nextError, t);
      setError(message);
      return message;
    } finally {
      setBusyServerId(null);
    }
  }, [busyServerId, t]);

  const create = useCallback(async (draft: McpServerDraft) => {
    if (busyServerId !== null) return t("error.mcp.busy");
    setBusyServerId("new");
    try {
      const created = await createMcpServer(draft);
      setServers((current) => [...current, created]);
      return null;
    } catch (nextError) {
      const message = mcpErrorText(nextError, t);
      setError(message);
      return message;
    } finally { setBusyServerId(null); }
  }, [busyServerId, t]);

  const loadTools = useCallback(async (id: string) => {
    try {
      const result = await listMcpTools(id);
      setTools((current) => ({ ...current, [id]: result }));
      return null;
    } catch (nextError) {
      const message = mcpErrorText(nextError, t);
      setError(message);
      return message;
    }
  }, [t]);

  return {
    servers, tools, loaded, error, busyServerId, reload, create,
    update: (id, draft) => operation(id, () => updateMcpServer(id, draft)),
    remove: (id) => operation(id, () => deleteMcpServer(id)),
    test: (id) => operation(id, () => testMcpServer(id)),
    start: async (id) => { const result = await operation(id, () => startMcpServer(id)); if (result === null) await loadTools(id); return result; },
    stop: async (id) => { const result = await operation(id, () => stopMcpServer(id)); if (result === null) setTools((current) => { const next = { ...current }; delete next[id]; return next; }); return result; },
    loadTools,
  };
}
