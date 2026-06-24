"""opensprite/llms/registry.py - LLM Provider Registry

用 Registry 模式管理所有 LLM Provider，方便擴充。
"""

from .provider_factory import create_llm
from .provider_specs import PROVIDERS, ProviderSpec, find_provider, provider_spec_default_base_url
