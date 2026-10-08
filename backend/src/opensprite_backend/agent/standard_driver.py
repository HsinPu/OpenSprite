"""The default model turn, expressed through controlled host operations."""

from .driver import DriverResult, ExecutionHost


class StandardDriver:
    async def execute(self, host: ExecutionHost) -> DriverResult:
        await host.checkpoint()
        turn = await host.next_turn()
        return await host.finish(turn)


class StandardDriverFactory:
    api_version = 2
    driver_id = "standard"

    def create(self) -> StandardDriver:
        return StandardDriver()
