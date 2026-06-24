"""Search embedding provider factory."""

from __future__ import annotations

from ..config import Config
from ..llms.provider_specs import find_provider, provider_spec_default_base_url
from .embeddings import OpenAIEmbeddingProvider


def create_search_embedding_provider(config: Config):
    """Create the optional embedding provider for hybrid search."""

    embedding_config = getattr(config.search, "embedding", None)
    if not embedding_config or not embedding_config.enabled:
        return None

    active_llm = config.llm.get_active()
    api_key = embedding_config.api_key or active_llm.api_key
    base_url = embedding_config.base_url or active_llm.base_url
    if not api_key:
        raise ValueError("search.embedding.api_key is required when enabled=true")

    provider_spec = find_provider(
        api_key=api_key,
        base_url=base_url or "",
        model=embedding_config.model,
        provider_name=embedding_config.provider,
    )
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        model=embedding_config.model,
        provider_name=provider_spec.name,
        base_url=base_url or provider_spec_default_base_url(provider_spec),
        batch_size=embedding_config.batch_size,
    )
