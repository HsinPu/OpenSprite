"""Rules for applying bundled provider profile defaults."""

from .provider_api_modes import ANTHROPIC_MESSAGES_API_MODE
from .provider_ids import MINIMAX_PROVIDER_ID


_PROFILE_BASE_URL_API_MODES = {
    MINIMAX_PROVIDER_ID: (ANTHROPIC_MESSAGES_API_MODE,),
}


def provider_profile_base_url_applies(provider_id: str | None, api_mode: str | None) -> bool:
    """Return whether the profile default URL applies for the selected API mode."""
    api_modes = _PROFILE_BASE_URL_API_MODES.get(str(provider_id or "").strip())
    return api_modes is None or api_mode in api_modes
