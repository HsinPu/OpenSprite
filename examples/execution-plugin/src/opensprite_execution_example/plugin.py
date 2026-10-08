"""A single API v3 Loop coordinates flow and decides eligible recovery."""
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
    return MainRetryOnlyFactory()
