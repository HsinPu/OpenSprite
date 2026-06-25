"""Provider settings error types shared across config modules."""


class ProviderSettingsError(Exception):
    """Base error for provider settings operations."""


class ProviderSettingsValidationError(ProviderSettingsError):
    """Raised when a request is malformed."""


class ProviderSettingsNotFound(ProviderSettingsError):
    """Raised when a provider cannot be found."""


class ProviderSettingsConflict(ProviderSettingsError):
    """Raised when an operation would leave settings inconsistent."""
