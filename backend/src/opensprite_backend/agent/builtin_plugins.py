"""Built-in implementations of the single Agent Loop plugin contract."""

from dataclasses import dataclass

from .plugin import CompletionState, ContextRetryState, DriverResult, ExecutionHost


class StandardLoopPlugin:
    async def execute(self, host: ExecutionHost) -> DriverResult:
        await host.checkpoint()
        turn = await host.next_turn()
        return await host.finish(turn)

    def allow_context_retry(self, state: ContextRetryState) -> bool:
        return True

    def allow_output_continuation(self, state: CompletionState) -> bool:
        return True


class NoRecoveryLoopPlugin(StandardLoopPlugin):
    def allow_context_retry(self, state: ContextRetryState) -> bool:
        return False

    def allow_output_continuation(self, state: CompletionState) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class BuiltinLoopFactory:
    no_recovery: bool = False
    api_version: int = 3

    def create(self) -> StandardLoopPlugin:
        return NoRecoveryLoopPlugin() if self.no_recovery else StandardLoopPlugin()
