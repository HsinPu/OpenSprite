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
  const reloadInFlight = useRef<Promise<WorkspaceCatalog | null> | null>(null);
  const reloadGeneration = useRef(0);

  const loadCatalog = useCallback((force: boolean): Promise<WorkspaceCatalog | null> => {
    if (!force && reloadInFlight.current) return reloadInFlight.current;
    const generation = reloadGeneration.current + 1;
    reloadGeneration.current = generation;
    let request!: Promise<WorkspaceCatalog | null>;
    request = (async () => {
      if (mounted.current && reloadGeneration.current === generation) {
        setLoading(true);
        setError(null);
      }
      try {
        const next = await listWorkspaces();
        if (mounted.current && reloadGeneration.current === generation) setCatalog(next);
        return next;
      } catch (caught) {
        const nextError = caught instanceof WorkspaceApiError ? caught : new WorkspaceApiError("network_error");
        if (mounted.current && reloadGeneration.current === generation) setError(nextError);
        return null;
      } finally {
        if (reloadInFlight.current === request) reloadInFlight.current = null;
        if (mounted.current && reloadGeneration.current === generation) {
          setLoaded(true);
          setLoading(false);
        }
      }
    })();
    reloadInFlight.current = request;
    return request;
  }, []);

  const reload = useCallback(() => loadCatalog(false), [loadCatalog]);

  useEffect(() => {
    mounted.current = true;
    void reload();
    return () => { mounted.current = false; };
  }, [reload]);

  const mutate = useCallback(async <T,>(operation: (current: WorkspaceCatalog) => Promise<T>, apply?: (result: T) => WorkspaceCatalog | null): Promise<T> => {
    if (catalog === null) throw error ?? new WorkspaceApiError("workspace_store_unavailable");
    setSaving(true);
    try {
      const result = await operation(catalog);
      const immediate = apply?.(result) ?? null;
      let refreshSucceeded = true;
      if (immediate) {
        reloadGeneration.current += 1;
        reloadInFlight.current = null;
        if (mounted.current) {
          setCatalog(immediate);
          setLoaded(true);
          setLoading(false);
        }
      } else {
        refreshSucceeded = await loadCatalog(true) !== null;
      }
      if (mounted.current && refreshSucceeded) setError(null);
      return result;
    } catch (caught) {
      const nextError = caught instanceof WorkspaceApiError ? caught : new WorkspaceApiError("network_error");
      if (mounted.current) setError(nextError);
      throw nextError;
    } finally {
      if (mounted.current) setSaving(false);
    }
  }, [catalog, error, loadCatalog]);

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
