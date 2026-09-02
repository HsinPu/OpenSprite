import { Switch } from "antd";

import type { MessageKey } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import type { ToolEffect, ToolSource } from "../../api/toolSettings";
import type { ToolSettingsController } from "../tool-settings/useToolSettings";
import { FutureSettingRow, SettingsCard } from "./SettingsPrimitives";


const sourceKeys: Record<ToolSource, MessageKey> = {
  builtin: "tools.source.builtin",
  mcp: "tools.source.mcp",
  external: "tools.source.external",
};
const effectKeys: Record<ToolEffect, MessageKey> = {
  read_only: "tools.effect.readOnly",
  local_write: "tools.effect.localWrite",
  external_write: "tools.effect.externalWrite",
  destructive: "tools.effect.destructive",
  sensitive: "tools.effect.sensitive",
};

function toolName(id: string, t: ReturnType<typeof useI18n>["t"]): string {
  return id === "calculator" ? t("tool.calculator") : id;
}

function toolDescription(id: string, t: ReturnType<typeof useI18n>["t"]): string {
  return id === "calculator" ? t("tools.calculatorDescription") : t("tools.unknownDescription");
}

export function ToolsSettings({ controller }: { controller: ToolSettingsController }) {
  const { t } = useI18n();
  const controlsDisabled = !controller.loaded || controller.saving;
  return (
    <div className="settings-form-stack">
      <SettingsCard icon="connections" title={t("tools.usageTitle")}>
        <div className="settings-toggle-row">
          <span>
            <span className="settings-control-label">{t("tools.globalEnabled")}</span>
            <span className="settings-control-description">{t("tools.globalEnabledDescription")}</span>
          </span>
          <Switch aria-label={t("tools.globalEnabled")} checked={controller.settings.enabled} disabled={controlsDisabled} onChange={(enabled) => void controller.saveEnabled(enabled)} />
        </div>
        {controller.error ? <div className="settings-model-load-error" role="alert"><p>{controller.error}</p><button type="button" className="settings-secondary-button settings-model-retry" onClick={() => void controller.reload()}>{t("common.retry")}</button></div> : null}
      </SettingsCard>

      <SettingsCard icon="connections" title={t("tools.availableTitle")}>
        <p className="settings-card-description">{t("tools.availableDescription")}</p>
        {!controller.loaded && !controller.error ? <p className="settings-provider-feedback" role="status" aria-live="polite">{t("tools.loading")}</p> : null}
        {controller.catalog && controller.catalog.items.length === 0 ? <p className="settings-provider-feedback">{t("tools.empty")}</p> : null}
        {controller.catalog ? <div className="settings-tool-list">{controller.catalog.items.map((tool) => {
          const enabled = controller.settings.enabledTools.includes(tool.id);
          const disabled = controlsDisabled || !controller.settings.enabled || !tool.available;
          return <div className="settings-tool-row" key={tool.id}>
            <span className="settings-tool-identity">
              <strong>{toolName(tool.id, t)}</strong>
              <span className="settings-tool-meta">{t(sourceKeys[tool.source])} · {t(effectKeys[tool.effect])}</span>
              <span className="settings-control-description">{toolDescription(tool.id, t)}</span>
              <span className={`settings-tool-status${tool.available ? " is-available" : ""}`}>{tool.available ? t("tools.available") : t("tools.unavailable")}</span>
            </span>
            <Switch aria-label={t("tools.toggleTool", { tool: toolName(tool.id, t) })} checked={enabled} disabled={disabled} onChange={(nextEnabled) => void controller.saveToolEnabled(tool.id, nextEnabled)} />
          </div>;
        })}</div> : null}
      </SettingsCard>

      <SettingsCard icon="connections" title={t("tools.externalTitle")}>
        <FutureSettingRow label={t("tools.mcpConnections")} description={t("tools.mcpConnectionsDescription")} />
        <FutureSettingRow label={t("tools.customTools")} description={t("tools.customToolsDescription")} />
        <FutureSettingRow label={t("tools.thirdPartyServices")} description={t("tools.thirdPartyServicesDescription")} />
      </SettingsCard>
    </div>
  );
}
