"""Model and explicit user ceilings; no automatic allocation or selection."""
from ..plugin import ModelLimits


def resolve_model_limits(context_choice, capability, output_choice):
    contexts = {"32k": 32768, "64k": 65536, "128k": 131072, "256k": 262144}
    outputs = {"8k": 8192, "16k": 16384, "32k": 32768, "64k": 65536}
    context = min(capability.context_window_tokens, contexts.get(context_choice, capability.context_window_tokens))
    return ModelLimits(context,
        min(131072, context - 1, capability.max_output_tokens, outputs.get(output_choice, capability.max_output_tokens)))
