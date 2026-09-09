"""Bounded internal Skill call phase; no task or connection ownership."""
import asyncio
import json
from opensprite_backend.skills.models import SkillError
from opensprite_backend.skills.execution import SkillRunState
from opensprite_backend.inference.models import ModelMessage, ModelToolCall, ModelToolDefinition
from opensprite_backend.conversations.models import RunEventType
from opensprite_backend.conversations.repository import ConversationRepository
from .context.counter import ConservativeTokenCounter


async def handle_skill_call(*, call: ModelToolCall, skill_state: SkillRunState,
    base_system_prompt: str, system_prompt: str, transcript: list[ModelMessage],
    tool_definitions: tuple[ModelToolDefinition, ...], input_budget_tokens: int,
    counter: ConservativeTokenCounter, repository: ConversationRepository, run_id: str,
) -> tuple[str, list[ModelMessage]]:
    if call.name == "discover_skills":
        try:
            result = skill_state.discover(call.arguments)
            while True:
                response = ModelMessage(role="tool", content=json.dumps(result, ensure_ascii=False),
                                        tool_call_id=call.call_id, tool_name=call.name)
                if counter.request(tuple([*transcript, response]), tool_definitions) <= input_budget_tokens:
                    break
                if len(result["items"]) <= 1:
                    raise SkillError("context_limit")
                result["items"].pop()
                result["nextOffset"] = call.arguments["offset"] + len(result["items"])
            transcript.append(response)
        except SkillError as error:
            transcript.append(ModelMessage(role="tool", content="Skill discovery failed: " + error.code,
                                           tool_call_id=call.call_id, tool_name=call.name))
        return system_prompt, transcript
    if call.name == "load_skill":
        identifier = call.arguments.get("skillId") if isinstance(call.arguments, dict) else None
        try:
            if not isinstance(call.arguments, dict) or set(call.arguments) != {"skillId"} or not isinstance(identifier, str):
                raise SkillError("invalid_request")
            candidate = skill_state.candidate(identifier)
            candidate_prompt = skill_state.prompt(base_system_prompt, candidate)
            confirmation = ModelMessage(role="tool", content="Skill loaded for this run.", tool_call_id=call.call_id, tool_name=call.name)
            updated = [ModelMessage(role="system", content=candidate_prompt), *transcript[1:], confirmation]
            if counter.request(tuple(updated), tool_definitions) > input_budget_tokens:
                raise SkillError("context_limit")
            if identifier not in skill_state.loaded:
                await asyncio.to_thread(repository.append_run_event, run_id, RunEventType.SKILL_LOADED,
                                        skill_state.event(identifier, "model"))
            skill_state.loaded = candidate
            system_prompt = candidate_prompt
            transcript = updated
        except SkillError as error:
            await asyncio.to_thread(repository.append_run_event, run_id, RunEventType.SKILL_LOAD_FAILED,
                                    skill_state.failure(identifier, error.code))
            transcript.append(ModelMessage(role="tool", content="Skill could not be loaded: " + error.code,
                                           tool_call_id=call.call_id, tool_name=call.name))
        return system_prompt, transcript
    raise ValueError("Not an internal Skill call")
