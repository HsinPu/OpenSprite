import { Collapse, Switch, Tag } from "antd";

import type { MessageKey } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import type { ToolEffect, ToolSource } from "../../api/toolSettings";
import type { ToolSettingsController } from "../tool-settings/useToolSettings";
import type { McpConnectionsController } from "../mcp-settings/useMcpConnections";
import { McpServersSettings } from "./McpServersSettings";
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

export function ToolsSettings({ controller, mcpConnections, modalContainer = null }: { controller: ToolSettingsController; mcpConnections: McpConnectionsController; modalContainer?: HTMLElement | null }) {
  const { t } = useI18n();
  const controlsDisabled = !controller.loaded || controller.saving;
  return (
    <div className="settings-form-stack settings-tools-layout">
      <div className="settings-tools-header">
        <div className="settings-intro"><h2>{t("settings.category.tools")}</h2><p>{t("settings.toolsIntro")}</p></div>
        <div className="settings-tools-global">
          <span>
            <span className="settings-control-label">{t("tools.globalEnabled")}</span>
          </span>
          <Switch aria-label={t("tools.globalEnabled")} checked={controller.settings.enabled} disabled={controlsDisabled} onChange={(enabled) => void controller.saveEnabled(enabled)} />
        </div>
      </div>
        {controller.loaded && !controller.settings.enabled ? <p role="status" className="settings-control-description">{t("tools.paused")}</p> : null}
        {controller.error ? <div className="settings-model-load-error" role="alert"><p>{controller.error}</p><button type="button" className="settings-secondary-button settings-model-retry" onClick={() => void controller.reload()}>{t("common.retry")}</button></div> : null}

      <SettingsCard icon="connections" title={t("tools.availableTitle")}>
        <p className="settings-card-description">{t("tools.availableDescription")}</p>
        {!controller.loaded && !controller.error ? <p className="settings-provider-feedback" role="status" aria-live="polite">{t("tools.loading")}</p> : null}
        {controller.catalog && controller.catalog.items.length === 0 ? <p className="settings-provider-feedback">{t("tools.empty")}</p> : null}
        {controller.catalog ? <div className="settings-tool-list">{controller.catalog.items.map((tool) => {
          const enabled = controller.settings.enabledTools.includes(tool.id);
          const disabled = controlsDisabled || !controller.settings.enabled || !tool.available;
          return <div className="settings-tool-row" key={tool.id}>
            <span className="settings-tool-identity">
              <span className="settings-tool-name"><strong>{toolName(tool.id, t)}</strong><Tag>{t(sourceKeys[tool.source])}</Tag><Tag>{t(effectKeys[tool.effect])}</Tag></span>
              <span className="settings-control-description">{toolDescription(tool.id, t)}</span>
              {!tool.available ? <span className="settings-tool-status">{t("tools.unavailable")}</span> : null}
            </span>
            <Switch aria-label={t("tools.toggleTool", { tool: toolName(tool.id, t) })} checked={enabled} disabled={disabled} onChange={(nextEnabled) => void controller.saveToolEnabled(tool.id, nextEnabled)} />
          </div>;
        })}</div> : null}
      </SettingsCard>

      <McpServersSettings controller={mcpConnections} toolSettings={controller} modalContainer={modalContainer} />

      <Collapse className="settings-tools-planned" items={[{ key: "planned", label: t("general.planned"), children: <>
        <FutureSettingRow label={t("tools.customTools")} description={t("tools.customToolsDescription")} />
        <FutureSettingRow label={t("tools.thirdPartyServices")} description={t("tools.thirdPartyServicesDescription")} />
      </> }]} />
    </div>
  );
}
