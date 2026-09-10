"""Strict custom-provider mutation inputs; secrets never appear in repr."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from opensprite_backend.providers.catalog_models import canonical_base_url, provider_name


class ProviderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    baseUrl: str
    protocol: Literal["openai_chat_completions"]
    authMode: Literal["none", "bearer"]
    allowInsecureLocal: bool = False
    apiKey: SecretStr | None = Field(default=None, repr=False, exclude=True)
    expectedRevision: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def name_policy(cls, value: str) -> str:
        return provider_name(value)

    @model_validator(mode="after")
    def endpoint_policy(self) -> "ProviderCreateRequest":
        self.baseUrl = canonical_base_url(self.baseUrl, allow_insecure_local=self.allowInsecureLocal)
        if self.authMode == "none" and self.apiKey is not None:
            raise ValueError("unexpected_credential")
        if self.apiKey is not None:
            key = self.apiKey.get_secret_value()
            if not key or len(key) > 16384 or any(ord(char) < 33 or ord(char) > 126 for char in key):
                raise ValueError("invalid_credential")
        return self


class ProviderUpdateRequest(ProviderCreateRequest):
    expectedRevision: int = Field(ge=1)

    @field_validator("apiKey", mode="before")
    @classmethod
    def preserve_empty_key(cls, value):
        return None if value == "" else value


class ProviderRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expectedRevision: int = Field(ge=1)


class ProviderModelRequest(ProviderRevisionRequest):
    modelId: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    contextLimit: int = Field(ge=1024)
    outputLimit: int = Field(ge=1)
    tools: bool = False

    @model_validator(mode="after")
    def limits_policy(self) -> "ProviderModelRequest":
        if self.outputLimit > self.contextLimit or self.modelId != self.modelId.strip() or any(ord(c) < 32 for c in self.modelId):
            raise ValueError("invalid_model")
        return self
