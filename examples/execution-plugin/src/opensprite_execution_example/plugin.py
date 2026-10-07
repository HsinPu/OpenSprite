"""Use only the public Host API; keep runtime effects in the OpenSprite core."""

from opensprite_backend.agent.driver import DriverResult, ExecutionHost
from opensprite_backend.agent.strategies import CompletionState, ContextRetryState


class CheckpointedDriver:
    """Resolve each tool-producing turn before requesting or finishing another.

    The extra checkpoint between a model turn and its tools demonstrates a
    driver-owned cancellation boundary. Core host operations also enforce
    cancellation and hard limits. This driver does not inspect hidden state,
    manufacture an answer, or implement a second model/tool gateway.
    """

    async def execute(self, host: ExecutionHost) -> DriverResult:
        await host.checkpoint()
        while True:
            turn = await host.next_turn()
            if not turn.tool_calls:
                return await host.finish(turn)
            await host.checkpoint()
            await host.execute_tools(turn)
            await host.checkpoint()


class CheckpointedDriverFactory:
    api_version = 1

    def create(self) -> CheckpointedDriver:
        return CheckpointedDriver()


class MainRetryOnlyPolicy:
    """Allow eligible main-model context retry, with no automatic continuation.

    A True result never overrides the core's eligibility gates, budgets or
    retry limits. Returning an actual bool is part of the API contract.
    """

    def allow_context_retry(self, state: ContextRetryState) -> bool:
        return state.phase == "main" and state.cause == "provider_context_limit"

    def allow_output_continuation(self, state: CompletionState) -> bool:
        return False


class MainRetryOnlyPolicyFactory:
    api_version = 1

    def create(self) -> MainRetryOnlyPolicy:
        return MainRetryOnlyPolicy()


def create_loop_factory() -> CheckpointedDriverFactory:
    """The entry point exports a no-argument provider, not a driver instance."""
    return CheckpointedDriverFactory()


def create_policy_factory() -> MainRetryOnlyPolicyFactory:
    return MainRetryOnlyPolicyFactory()
