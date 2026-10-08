import { DownloadOutlined } from "@ant-design/icons";
import { Alert, Button, Drawer, Grid, Tabs, Typography } from "antd";

import { useI18n } from "../../i18n/I18nProvider";

export type DeveloperGuideTab = "loop" | "install" | "limits";
const loopSource = `"""A single API v3 Loop coordinates flow and decides eligible recovery."""
from opensprite_backend.agent.plugin import (
    CompletionState, ContextRetryState, DriverResult, ExecutionHost,
)


class MainRetryOnlyLoop:
    async def execute(self, host: ExecutionHost) -> DriverResult:
        await host.checkpoint()
        turn = await host.next_turn()
        await host.checkpoint()
        return await host.finish(turn)

    def allow_context_retry(self, state: ContextRetryState) -> bool:
        return state.phase == "main" and state.cause == "provider_context_limit"

    def allow_output_continuation(self, state: CompletionState) -> bool:
        return False


class MainRetryOnlyFactory:
    api_version = 3

    def create(self) -> MainRetryOnlyLoop:
        return MainRetryOnlyLoop()


def create_plugin_factory() -> MainRetryOnlyFactory:
    return MainRetryOnlyFactory()`;
const manifestSource = `[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[project]
name = "opensprite-execution-example"
version = "0.3.0"
description = "Checkpointed OpenSprite driver and a main-retry-only recovery policy"
readme = "README.md"
requires-python = ">=3.12,<3.14"
dependencies = ["opensprite-backend>=0.21.33,<0.22"]

[project.entry-points."opensprite_backend.agent_loops.v3"]
example_main_retry_only = "opensprite_execution_example.plugin:create_plugin_factory"

[tool.hatch.build.targets.wheel]
packages = ["src/opensprite_execution_example"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
filterwarnings = ["error"]`;
const bundleSource = `$env:OPENSPRITE_PLUGIN_BUNDLE_DIR = (Get-Location).Path
# Replace both paths; keep your existing compose project and options.
docker compose -f D:/ABS/OpenSprite/compose.yaml -f D:/ABS/extracted/compose.override.yaml up -d --build --wait`;
const localLinuxSource = `uv pip install --python /ABS/opensprite/backend/.venv/bin/python \\
    --offline --no-deps --force-reinstall \\
    tmp/execution-plugin-wheel/opensprite_execution_example-0.3.0-py3-none-any.whl
uv pip check --python /ABS/opensprite/backend/.venv/bin/python`;
const localWindowsSource = `$taskBackendPython = 'D:/ABS/opensprite/backend/.venv/Scripts/python.exe'
uv pip install --python $taskBackendPython --offline --no-deps --force-reinstall ./tmp/execution-plugin-wheel/opensprite_execution_example-0.3.0-py3-none-any.whl
uv pip check --python $taskBackendPython`;

export function ExecutionDeveloperGuide({ open, tab, onTab, onClose }: { open: boolean; tab: DeveloperGuideTab; onTab: (tab: DeveloperGuideTab) => void; onClose: () => void }) {
  const { t } = useI18n();
  const screens = Grid.useBreakpoint();
  const code = (label: string, source: string) => <div className="execution-guide__code"><div className="execution-guide__code-header"><span>{label}</span><Typography.Paragraph copyable={{ text: source, tooltips: [t("chat.copyCode"), t("chat.copiedCode")] }} /></div><pre><code>{source}</code></pre></div>;
  const limits = ["execution.guide.hostBoundary", "execution.guide.turnBoundary", "execution.guide.finishBoundary", "execution.guide.decisionBoundary", "execution.guide.authorRules"] as const;
  const workflow = ["execution.guide.workflowImport", "execution.guide.workflowBundle", "execution.guide.workflowBuild", "execution.guide.workflowRefresh", "execution.guide.workflowApply"] as const;
  return <Drawer open={open} title={t("execution.developerGuide")} size={screens.md ? 760 : "100%"} onClose={onClose} destroyOnHidden className="execution-settings__drawer execution-guide" extra={<Button icon={<DownloadOutlined aria-hidden />} href="/execution-plugin-example.zip" download="execution-plugin-example.zip">{t("execution.guide.downloadExample")}</Button>}>
    <p className="execution-guide__intro">{t("execution.guide.intro")}</p>
    <Tabs activeKey={tab} onChange={(key) => onTab(key as DeveloperGuideTab)} items={[
      { key: "loop", label: t("execution.loop"), children: <><h3>{t("execution.guide.loopTitle")}</h3><p>{t("execution.guide.loopHelp")}</p>{code("plugin.py · Loop", loopSource)}</> },
      { key: "install", label: t("execution.guide.packageTab"), children: <><h3>{t("execution.guide.workflowTitle")}</h3><ol>{workflow.map((key) => <li key={key}>{t(key)}</li>)}</ol>{code("PowerShell · Docker Compose", bundleSource)}<h3>{t("execution.guide.packageTitle")}</h3><p>{t("execution.guide.packageHelp")}</p>{code("pyproject.toml", manifestSource)}{code(t("execution.guide.buildLabel"), "uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin")}<h3>{t("execution.guide.localTitle")}</h3><p>{t("execution.guide.localHelp")}</p>{code("Linux", localLinuxSource)}{code("PowerShell", localWindowsSource)}<p>{t("execution.guide.restartHelp")}</p></> },
      { key: "limits", label: t("execution.guide.limitsTab"), children: <><Alert type="info" showIcon title={t("execution.guide.trustedCode")} /><h3>{t("execution.guide.limitsTitle")}</h3><ul>{limits.map((key) => <li key={key}>{t(key)}</li>)}</ul><p>{t("execution.guide.noHarness")}</p></> },
    ]} />
  </Drawer>;
}
