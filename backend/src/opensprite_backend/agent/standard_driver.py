"""The default tool loop, expressed entirely through controlled host operations."""

from .driver import DriverResult, ExecutionHost


class StandardDriver:
    async def execute(self, host: ExecutionHost) -> DriverResult:
        while True:
            await host.checkpoint()
            turn = await host.next_turn()
            if turn.tool_calls:
                await host.execute_tools(turn)
            else:
                return await host.finish(turn)


class StandardDriverFactory:
    api_version = 1
    driver_id = "standard"

    def create(self) -> StandardDriver:
        return StandardDriver()
