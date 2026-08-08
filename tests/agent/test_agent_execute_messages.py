import asyncio

from agent_test_helpers import make_agent_loop
from opensprite.core.contracts.llm import ChatMessage, LLMResponse


class StreamingDebugProvider:
    async def chat(self, messages, tools=None, model=None, temperature=0.7, max_tokens=2048, **kwargs):
        tool_input_callback = kwargs.get("tool_input_delta_callback")
        if tool_input_callback is not None:
            await tool_input_callback("call-1", "demo_tool", '{"value"', 1)
        reasoning_callback = kwargs.get("reasoning_delta_callback")
        if reasoning_callback is not None:
            await reasoning_callback("thinking")
        return LLMResponse(content="done", model="fake-model")

    def get_default_model(self) -> str:
        return "fake-model"


def test_agent_execute_messages_forwards_streaming_debug_hooks(tmp_path):
    agent = make_agent_loop(tmp_path / "workspace", provider=StreamingDebugProvider())
    tool_input_deltas = []
    reasoning_deltas = []

    async def on_tool_input(call_id, tool_name, delta, sequence):
        tool_input_deltas.append((call_id, tool_name, delta, sequence))

    async def on_reasoning(delta):
        reasoning_deltas.append(delta)

    result = asyncio.run(
        agent._execute_messages(
            "chat-1",
            [ChatMessage(role="user", content="hi")],
            allow_tools=False,
            on_tool_input_delta=on_tool_input,
            on_reasoning_delta=on_reasoning,
        )
    )

    assert result.content == "done"
    assert tool_input_deltas == [("call-1", "demo_tool", '{"value"', 1)]
    assert reasoning_deltas == ["thinking"]
