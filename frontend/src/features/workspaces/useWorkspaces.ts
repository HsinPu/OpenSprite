import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  WorkspaceApiError,
  createWorkspace,
  deleteWorkspace,
  listWorkspaces,
  setActiveWorkspace,
  updateWorkspace,
  type Workspace,
  type WorkspaceCatalog,
} from "../../api/workspaces";

export type WorkspaceController = {
  catalog: WorkspaceCatalog | null;
  activeWorkspace: Workspace | null;
  loaded: boolean;
  loading: boolean;
  saving: boolean;
  error: WorkspaceApiError | null;
  reload: () => Promise<WorkspaceCatalog | null>;
  create: (name: string, rootPath: string) => Promise<WorkspaceCatalog>;
  update: (item: Workspace, name: string, rootPath: string) => Promise<Workspace>;
  activate: (workspaceId: string) => Promise<WorkspaceCatalog>;
  remove: (item: Workspace) => Promise<void>;
};

export function useWorkspaces(): WorkspaceController {
  const [catalog, setCatalog] = useState<WorkspaceCatalog | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<WorkspaceApiError | null>(null);
  const mounted = useRef(true);

  useEffect(() => () => { mounted.current = false; }, []);

  const reload = useCallback(async (): Promise<WorkspaceCatalog | null> => {
    if (mounted.current) setLoading(true);
    try {
      const next = await listWorkspaces();
      if (mounted.current) {
        setCatalog(next);
        setError(null);
      }
      return next;
    } catch (caught) {
      const nextError = caught instanceof WorkspaceApiError ? caught : new WorkspaceApiError("network_error");
      if (mounted.current) setError(nextError);
      return null;
    } finally {
      if (mounted.current) {
        setLoaded(true);
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => { void reload(); }, [reload]);

  const mutate = useCallback(async <T,>(operation: (current: WorkspaceCatalog) => Promise<T>, apply?: (result: T) => WorkspaceCatalog | null): Promise<T> => {
    if (catalog === null) throw error ?? new WorkspaceApiError("workspace_store_unavailable");
    setSaving(true);
    try {
      const result = await operation(catalog);
      const immediate = apply?.(result) ?? null;
      if (mounted.current && immediate) setCatalog(immediate);
      if (!immediate) await reload();
      if (mounted.current) setError(null);
      return result;
    } catch (caught) {
      const nextError = caught instanceof WorkspaceApiError ? caught : new WorkspaceApiError("network_error");
      if (mounted.current) setError(nextError);
      throw nextError;
    } finally {
      if (mounted.current) setSaving(false);
    }
  }, [catalog, error, reload]);

  const activeWorkspace = useMemo(() => catalog?.workspaces.find((item) => item.id === catalog.activeWorkspaceId) ?? null, [catalog]);
  const create = useCallback((name: string, rootPath: string) => mutate((current) => createWorkspace(name, rootPath, current.revision), (result) => result as WorkspaceCatalog), [mutate]);
  const update = useCallback((item: Workspace, name: string, rootPath: string) => mutate(() => updateWorkspace(item, name, rootPath)), [mutate]);
  const activate = useCallback((workspaceId: string) => mutate((current) => setActiveWorkspace(workspaceId, current.revision), (result) => result as WorkspaceCatalog), [mutate]);
  const remove = useCallback((item: Workspace) => mutate(() => deleteWorkspace(item)), [mutate]);

  return {
    catalog,
    activeWorkspace,
    loaded,
    loading,
    saving,
    error,
    reload,
    create,
    update,
    activate,
    remove,
  };
}
