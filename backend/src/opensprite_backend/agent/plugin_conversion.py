"""Explicit copies between the stable SDK and internal persistence/transport."""
from opensprite_backend.conversations import models as stored
from opensprite_backend.inference import models as inference
from opensprite_backend.agent import plugin_data as public


def message(value: stored.Message) -> public.Message:
    return public.Message(value.id, value.conversation_id, value.run_id, value.role,
                          value.content, value.sequence, value.created_at)


def summary(value: stored.ConversationCompaction | None) -> public.ConversationCompaction | None:
    if value is None:
        return None
    return public.ConversationCompaction(
        value.id, value.conversation_id, value.covers_through_sequence, value.summary,
        value.summary_version, value.source_hash, value.provider_id, value.model_id,
        value.input_tokens, value.output_tokens, value.created_at, value.producer_plugin_id,
        value.producer_plugin_version, value.summary_format, value.source_step_id,
        value.source_first_sequence, value.previous_summary_id)


def error(value: stored.PublicRunError | None) -> public.PublicRunError | None:
    return None if value is None else public.PublicRunError(value.code, value.message, value.retryable)


def stored_error(value: public.PublicRunError) -> stored.PublicRunError:
    return stored.PublicRunError(value.code, value.message, value.retryable)


def model_messages(values: tuple[public.ModelMessage, ...]) -> tuple[inference.ModelMessage, ...]:
    return tuple(inference.ModelMessage(value.role, value.content) for value in values)


def finish_reason(value: inference.ModelFinishReason | None) -> public.ModelFinishReason | None:
    return None if value is None else public.ModelFinishReason(value.value)


def completion_reason(value: public.CompletionReason) -> stored.CompletionReason:
    return stored.CompletionReason(value.value)
