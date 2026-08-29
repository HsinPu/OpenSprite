from opensprite_backend.inference.capabilities import ModelCapability


class TestCapabilityResolver:
    __test__ = False
    def __init__(self, maximum: int = 262_144) -> None:
        self.maximum = maximum

    async def resolve(self, provider_id: str, model_id: str) -> ModelCapability:
        return ModelCapability(
            provider_id=provider_id,  # type: ignore[arg-type]
            model_id=model_id,
            name="Test model",
            context_window_tokens=self.maximum,
            max_output_tokens=min(8_192, self.maximum),
        )
