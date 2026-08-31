import { useCallback, useEffect, useRef, useState } from "react";
import { getAppInfo, type AppInfo } from "../../api/appInfo";

export function useAppInfo() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const generationRef = useRef(0);
  const reload = useCallback(async () => {
    const generation = ++generationRef.current;
    setLoading(true); setError(false);
    try { const next = await getAppInfo(); if (generationRef.current === generation) setInfo(next); }
    catch { if (generationRef.current === generation) setError(true); }
    finally { if (generationRef.current === generation) setLoading(false); }
  }, []);
  useEffect(() => { void reload(); return () => { generationRef.current += 1; }; }, [reload]);
  return { info, loading, error, reload };
}
