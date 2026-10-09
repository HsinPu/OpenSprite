"""API v5: the Loop owns complete draft, review and final inputs."""
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
            messages = (ModelMessage("system", base[0].content + "\n\n" + instruction), *base[1:], *extras)
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
            (ModelMessage("assistant", draft.text), ModelMessage("user", "Draft review:\n" + review.text)),
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
    return ReviewFactory()
