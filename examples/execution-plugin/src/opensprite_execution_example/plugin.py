"""API v4: a replaceable draft -> review -> final flow."""
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
            messages=(ModelMessage("assistant", draft.text), ModelMessage("user", "Draft review:\n" + review.text))))
        if final.error:
            return await host.finish(FinalOutput(error_step=final))
        reason = CompletionReason.OUTPUT_LIMIT if final.finish_reason is ModelFinishReason.OUTPUT_LIMIT else CompletionReason.STOP
        return await host.finish(FinalOutput(final.text, (final,), reason))


class ReviewFactory:
    api_version = 4
    def create(self) -> ReviewLoop:
        return ReviewLoop()


def create_plugin_factory() -> ReviewFactory:
    return ReviewFactory()
