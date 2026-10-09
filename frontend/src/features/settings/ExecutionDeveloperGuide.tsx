import { DownloadOutlined } from "@ant-design/icons";
import { Alert, Button, Drawer, Grid, Tabs, Typography } from "antd";

import { useI18n } from "../../i18n/I18nProvider";

export type DeveloperGuideTab = "loop" | "install" | "limits";
const loopSource = `"""API v4: a replaceable draft -> review -> final flow."""
from opensprite_backend.agent.plugin import ExecutionHost, FinalOutput, RunResult, StepRequest
from opensprite_backend.conversations.models import CompletionReason
from opensprite_backend.inference.models import ModelFinishReason, ModelMessage


class ReviewLoop:
    async def execute(self, host: ExecutionHost) -> RunResult:
        context = await host.context()
        draft = await host.infer(StepRequest(context, label="draft", channel="draft",
            instruction="Prepare a concise draft answering the current user request."))
        if draft.error:
            return await host.finish(FinalOutput(error_step=draft))
        await host.checkpoint()
        review = await host.infer(StepRequest(context, label="review", channel="draft",
            instruction="Check the draft for errors and missing requirements. Return a brief critique.",
            messages=(ModelMessage("assistant", draft.text),)))
        if review.error:
            return await host.finish(FinalOutput(error_step=review))
        await host.checkpoint()
        final = await host.infer(StepRequest(context, label="final", channel="answer",
            instruction="Answer the current user request using the draft and critique. Return the final answer only.",
            messages=(ModelMessage("assistant", draft.text), ModelMessage("user", "Draft review:\\n" + review.text))))
        if final.error:
            return await host.finish(FinalOutput(error_step=final))
        reason = CompletionReason.OUTPUT_LIMIT if final.finish_reason is ModelFinishReason.OUTPUT_LIMIT else CompletionReason.STOP
        return await host.finish(FinalOutput(final.text, (final,), reason))


class ReviewFactory:
    api_version = 4
    def create(self) -> ReviewLoop:
        return ReviewLoop()


def create_plugin_factory() -> ReviewFactory:
    return ReviewFactory()`;
const manifestSource = `[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[project]
name = "opensprite-execution-example"
version = "0.4.0"
description = "OpenSprite Agent Loop with private draft, review and final answer steps"
readme = "README.md"
requires-python = ">=3.12,<3.14"
dependencies = ["opensprite-backend>=0.21.34,<0.22"]

[project.entry-points."opensprite_backend.agent_loops.v4"]
example_review = "opensprite_execution_example.plugin:create_plugin_factory"

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
    tmp/execution-plugin-wheel/opensprite_execution_example-0.4.0-py3-none-any.whl
uv pip check --python /ABS/opensprite/backend/.venv/bin/python`;
const localWindowsSource = `$taskBackendPython = 'D:/ABS/opensprite/backend/.venv/Scripts/python.exe'
uv pip install --python $taskBackendPython --offline --no-deps --force-reinstall ./tmp/execution-plugin-wheel/opensprite_execution_example-0.4.0-py3-none-any.whl
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
