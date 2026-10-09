import { DownloadOutlined } from "@ant-design/icons";
import { Alert, Button, Drawer, Grid, Tabs, Typography } from "antd";

import { useI18n } from "../../i18n/I18nProvider";

export type DeveloperGuideTab = "loop" | "install" | "limits";
const loopSource = `"""API v5: the Loop owns complete draft, review and final inputs."""
from opensprite_backend.agent.plugin import (
    CompletionReason, ContextReadRequest, ExecutionHost, FinalOutput, InputSource,
    ModelFinishReason, ModelMessage, RunResult, StepRequest,
)


class ReviewLoop:
    async def execute(self, host: ExecutionHost) -> RunResult:
        snapshot = await host.read_context(ContextReadRequest(limit=20, summary_format=None))
        history = (*snapshot.history, snapshot.current_user)
        base = (ModelMessage("system", host.run.system_prompt),
                *(ModelMessage(item.role, item.content) for item in history))
        sources = tuple(InputSource(index + 1, snapshot, (item.id,)) for index, item in enumerate(history))
        output = min(1024, host.run.model_limits.output_tokens)

        async def step(label, instruction, extras=(), references=(), channel="draft"):
            messages = (ModelMessage("system", base[0].content + "\\n\\n" + instruction), *base[1:], *extras)
            return await host.infer(StepRequest(messages, output, sources=(*sources, *references),
                label=label, channel=channel))

        draft = await step("draft", "Prepare a concise draft answering the current user request.")
        if draft.error:
            return await host.finish(FinalOutput(error_step=draft))
        await host.checkpoint()
        review = await step("review", "Check the draft for errors and missing requirements. Return a brief critique.",
            (ModelMessage("assistant", draft.text),),
            (InputSource(len(base), steps=(draft,)),))
        if review.error:
            return await host.finish(FinalOutput(error_step=review))
        await host.checkpoint()
        final = await step("final", "Answer the current user request using the draft and critique. Return the final answer only.",
            (ModelMessage("assistant", draft.text), ModelMessage("user", "Draft review:\\n" + review.text)),
            (InputSource(len(base), steps=(draft,)), InputSource(len(base)+1, steps=(review,))), "answer")
        if final.error:
            return await host.finish(FinalOutput(error_step=final))
        reason = CompletionReason.OUTPUT_LIMIT if final.finish_reason is ModelFinishReason.OUTPUT_LIMIT else CompletionReason.STOP
        return await host.finish(FinalOutput(final.text, (final,), reason))


class ReviewFactory:
    api_version = 5
    def create(self) -> ReviewLoop:
        return ReviewLoop()


def create_plugin_factory() -> ReviewFactory:
    return ReviewFactory()`;
const manifestSource = `[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[project]
name = "opensprite-execution-example"
version = "0.5.0"
description = "OpenSprite Agent Loop with private draft, review and final answer steps"
readme = "README.md"
requires-python = ">=3.12,<3.14"
dependencies = ["opensprite-backend>=0.21.35,<0.22"]

[project.entry-points."opensprite_backend.agent_loops.v5"]
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
    tmp/execution-plugin-wheel/opensprite_execution_example-0.5.0-py3-none-any.whl
uv pip check --python /ABS/opensprite/backend/.venv/bin/python`;
const localWindowsSource = `$taskBackendPython = 'D:/ABS/opensprite/backend/.venv/Scripts/python.exe'
uv pip install --python $taskBackendPython --offline --no-deps --force-reinstall ./tmp/execution-plugin-wheel/opensprite_execution_example-0.5.0-py3-none-any.whl
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
