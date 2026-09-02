import { useCallback, useState } from "react";

import { localPathErrorText, pickLocalPath, type LocalPathKind } from "../../api/localPaths";
import { useI18n } from "../../i18n/I18nProvider";


export function useLocalPathPicker() {
  const { t } = useI18n();
  const [picking, setPicking] = useState<LocalPathKind | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pick = useCallback(async (kind: LocalPathKind): Promise<string | null> => {
    if (picking !== null) return null;
    setPicking(kind);
    setError(null);
    try {
      return await pickLocalPath(kind);
    } catch (nextError) {
      setError(localPathErrorText(nextError, t));
      return null;
    } finally {
      setPicking(null);
    }
  }, [picking, t]);

  return { pick, picking, error };
}
