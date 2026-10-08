"""Use only the public Host API; keep runtime effects in the OpenSprite core."""

from opensprite_backend.agent.driver import DriverResult, ExecutionHost
from opensprite_backend.agent.strategies import CompletionState, ContextRetryState


class CheckpointedDriver:
    """Add cancellation checkpoints around the core-owned model turn."""

    async def execute(self, host: ExecutionHost) -> DriverResult:
        await host.checkpoint()
        turn = await host.next_turn()
        await host.checkpoint()
        return await host.finish(turn)


class CheckpointedDriverFactory:
    api_version = 2

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
    api_version = 2

    def create(self) -> MainRetryOnlyPolicy:
        return MainRetryOnlyPolicy()


def create_loop_factory() -> CheckpointedDriverFactory:
    """The entry point exports a no-argument provider, not a driver instance."""
    return CheckpointedDriverFactory()


def create_policy_factory() -> MainRetryOnlyPolicyFactory:
    return MainRetryOnlyPolicyFactory()
