import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  WorkspaceApiError,
  addWorkspaceMount,
  createWorkspace,
  deleteWorkspaceMount,
  deleteWorkspace,
  importWorkspace,
  listWorkspaceImportCandidates,
  listWorkspaces,
  setActiveWorkspace,
  updateWorkspaceMount,
  updateWorkspace,
  type Workspace,
  type WorkspaceCatalog,
  type WorkspaceImportCandidate,
  type WorkspaceMountAccess,
} from "../../api/workspaces";

export type WorkspaceController = {
  catalog: WorkspaceCatalog | null;
  activeWorkspace: Workspace | null;
  loaded: boolean;
  loading: boolean;
  saving: boolean;
  error: WorkspaceApiError | null;
  importCandidates: readonly WorkspaceImportCandidate[];
  importCandidatesLoading: boolean;
  importCandidatesNextCursor: string | null;
  reload: () => Promise<WorkspaceCatalog | null>;
  loadImportCandidates: (reset?: boolean) => Promise<void>;
  create: (name: string) => Promise<WorkspaceCatalog>;
  importExisting: (directoryName: string) => Promise<WorkspaceCatalog>;
  update: (item: Workspace, name: string) => Promise<Workspace>;
  activate: (workspaceId: string) => Promise<WorkspaceCatalog>;
  remove: (item: Workspace) => Promise<void>;
  addMount: (item: Workspace, alias: string, rootPath: string, accessMode: WorkspaceMountAccess) => Promise<Workspace>;
  updateMount: (item: Workspace, mountId: string, alias: string, rootPath: string, accessMode: WorkspaceMountAccess, enabled: boolean) => Promise<Workspace>;
  removeMount: (item: Workspace, mountId: string) => Promise<Workspace>;
};

export function useWorkspaces(): WorkspaceController {
  const [catalog, setCatalog] = useState<WorkspaceCatalog | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<WorkspaceApiError | null>(null);
  const [importCandidates, setImportCandidates] = useState<readonly WorkspaceImportCandidate[]>([]);
  const [importCandidatesLoading, setImportCandidatesLoading] = useState(false);
  const [importCandidatesNextCursor, setImportCandidatesNextCursor] = useState<string | null>(null);
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

  const loadImportCandidates = useCallback(async (reset = true): Promise<void> => {
    if (importCandidatesLoading) return;
    setImportCandidatesLoading(true);
    try {
      const page = await listWorkspaceImportCandidates(reset ? undefined : importCandidatesNextCursor ?? undefined);
      if (mounted.current) {
        setImportCandidates((current) => reset ? page.candidates : [...current, ...page.candidates]);
        setImportCandidatesNextCursor(page.nextCursor);
        setError(null);
      }
    } catch (caught) {
      const nextError = caught instanceof WorkspaceApiError ? caught : new WorkspaceApiError("network_error");
      if (mounted.current) setError(nextError);
    } finally {
      if (mounted.current) setImportCandidatesLoading(false);
    }
  }, [importCandidatesLoading, importCandidatesNextCursor]);

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
  const create = useCallback((name: string) => mutate((current) => createWorkspace(name, current.revision), (result) => result as WorkspaceCatalog), [mutate]);
  const importExisting = useCallback((directoryName: string) => mutate((current) => importWorkspace(directoryName, current.revision), (result) => result as WorkspaceCatalog), [mutate]);
  const update = useCallback((item: Workspace, name: string) => mutate(() => updateWorkspace(item, name)), [mutate]);
  const activate = useCallback((workspaceId: string) => mutate((current) => setActiveWorkspace(workspaceId, current.revision), (result) => result as WorkspaceCatalog), [mutate]);
  const remove = useCallback((item: Workspace) => mutate(() => deleteWorkspace(item)), [mutate]);
  const addMount = useCallback((item: Workspace, alias: string, rootPath: string, accessMode: WorkspaceMountAccess) => mutate(() => addWorkspaceMount(item, alias, rootPath, accessMode)), [mutate]);
  const updateMount = useCallback((item: Workspace, mountId: string, alias: string, rootPath: string, accessMode: WorkspaceMountAccess, enabled: boolean) => mutate(() => updateWorkspaceMount(item, mountId, alias, rootPath, accessMode, enabled)), [mutate]);
  const removeMount = useCallback((item: Workspace, mountId: string) => mutate(() => deleteWorkspaceMount(item, mountId)), [mutate]);

  return {
    catalog,
    activeWorkspace,
    loaded,
    loading,
    saving,
    error,
    importCandidates,
    importCandidatesLoading,
    importCandidatesNextCursor,
    reload,
    loadImportCandidates,
    create,
    importExisting,
    update,
    activate,
    remove,
    addMount,
    updateMount,
    removeMount,
  };
}
