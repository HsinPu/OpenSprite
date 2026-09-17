import { useEffect, useState } from "react";
import { getResponseModeResolution, type ReasoningResolution, type ResponseMode } from "../../api/responseModes";
import type { ProviderId } from "../../api/providerConnections";
import type { Translator } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";

export function responseModeResolutionText(value: ReasoningResolution, t: Translator): string {
  if (value.requested === "default") return t("models.response.defaultDescription");
  if (value.status === "unknown") return t("models.response.unknown");
  if (value.status === "provider_default") return t("models.response.providerDefault");
  const effective = value.effective === null ? "" : t(`models.response.${value.effective}`);
  return value.status === "exact" ? t("models.response.exact", { effective })
    : t("models.response.fallback", { requested: t(`models.response.${value.requested}`), effective });
}

export function ResponseModeHint({ id, providerId, modelId, mode, enabled = true }: {
  id?: string; providerId?: ProviderId; modelId?: string; mode: ResponseMode; enabled?: boolean;
}) {
  const { t } = useI18n();
  const key = JSON.stringify([providerId, modelId, mode]);
  const [result, setResult] = useState<{ key: string; value: ReasoningResolution | null } | null>(null);
  useEffect(() => {
    if (mode === "default" || !enabled || !providerId || !modelId) return;
    const controller = new AbortController();
    void getResponseModeResolution(providerId, modelId, mode, controller.signal).then(
      (value) => { if (!controller.signal.aborted) setResult({ key, value }); },
      () => { if (!controller.signal.aborted) setResult({ key, value: null }); },
    );
    return () => controller.abort();
  }, [enabled, key, providerId, modelId, mode]);
  const text = mode === "default" ? t("models.response.defaultDescription")
    : !providerId || !modelId ? t("models.response.selectModel")
    : result?.key !== key ? t("models.response.loading")
    : result.value === null ? t("models.response.unavailable")
    : responseModeResolutionText(result.value, t);
  return <p id={id} className="settings-helper-text response-mode-hint" role="status" aria-live="polite">{text}</p>;
}
