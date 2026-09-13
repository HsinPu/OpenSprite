"""Application boundary for transactional custom-provider configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from .catalog_models import ProviderEndpointSnapshot, canonical_base_url, provider_name
from .catalog_store import CatalogError, CustomModel, CustomProvider, ProviderCatalog
from .catalog_transaction import ProviderCatalogTransaction


class CustomProviderService:
    def __init__(self, transaction: ProviderCatalogTransaction) -> None:
        self.transaction = transaction
        self.store = transaction.catalog

    def list(self) -> ProviderCatalog:
        with self.store.gate:
            self.transaction.recover()
            return self.store.get()

    def get(self, provider_id: str) -> CustomProvider:
        for item in self.list().providers:
            if item.id == provider_id:
                return item
        raise CatalogError("provider_not_found")

    def execution_endpoint(self, provider_id: str) -> ProviderEndpointSnapshot:
        """Resolve once at Run acceptance; callers retain this immutable value."""
        provider = self.get(provider_id)
        from opensprite_backend.inference.capabilities import ModelCapability
        models = tuple(ModelCapability(provider.id, model.model_id, model.name,
            model.context_limit, model.output_limit, model.tools) for model in provider.models)
        return ProviderEndpointSnapshot(provider.id, provider.revision, provider.protocol,
            provider.base_url, provider.auth_mode, models)

    def save(self, *, provider_id: str | None, name: str, base_url: str, auth_mode: str, allow_insecure_local: bool, expected_revision: int, secret: str | None) -> CustomProvider:
        """Called inside the shared application mutation gate after busy checks."""
        with self.store.gate:
            catalog = self.list()
            previous = self.get(provider_id) if provider_id is not None else None
            revision = previous.revision if previous else catalog.revision
            if expected_revision != revision:
                raise CatalogError("revision_conflict")
            try:
                name = provider_name(name)
                base_url = canonical_base_url(base_url, allow_insecure_local=allow_insecure_local)
            except ValueError:
                raise CatalogError("invalid_request") from None
            if any(p.name.casefold() == name.casefold() and p.id != provider_id for p in catalog.providers):
                raise CatalogError("duplicate_name")
            identifier = previous.id if previous else str(uuid4())
            if auth_mode == "bearer" and not secret:
                try:
                    existing = self.transaction.credentials.get(f"provider:{identifier}:bearer")
                except Exception:
                    raise CatalogError("credential_store_unavailable") from None
                if existing is None:
                    raise CatalogError("credential_required")
                existing = None
            now = datetime.now(UTC).isoformat()
            try:
                record = CustomProvider(id=identifier, name=name, revision=previous.revision + 1 if previous else 1,
                    base_url=base_url, auth_mode=auth_mode, allow_insecure_local=allow_insecure_local,
                    created_at=previous.created_at if previous else now, updated_at=now,
                    models=previous.models if previous else ())
                providers = tuple(record if p.id == identifier else p for p in catalog.providers) if previous else (*catalog.providers, record)
                target = ProviderCatalog(revision=catalog.revision + 1, providers=providers)
            except ValueError:
                raise CatalogError("invalid_request") from None
            self.transaction.commit(target, identifier, expected_revision=catalog.revision,
                secret=secret if auth_mode == "bearer" else None, remove_secret=auth_mode == "none")
            return record

    def delete(self, provider_id: str, *, expected_revision: int) -> None:
        """Caller holds application mutation gate and has rejected live references."""
        with self.store.gate:
            catalog = self.list()
            previous = self.get(provider_id)
            if previous.revision != expected_revision:
                raise CatalogError("revision_conflict")
            target = ProviderCatalog(revision=catalog.revision + 1, providers=tuple(p for p in catalog.providers if p.id != provider_id))
            self.transaction.commit(target, provider_id, expected_revision=catalog.revision, remove_secret=True)

    def merge_discovered_models(self, provider_id: str, model_ids: list[str], *, expected_revision: int) -> CustomProvider:
        """Commit discovery through the same recovery and transaction boundary."""
        with self.store.gate:
            current = self.get(provider_id)
            if current.revision != expected_revision:
                raise CatalogError("revision_conflict")
            existing = {model.model_id: model for model in current.models}
            models = [model for model in current.models if model.source == "manual"]
            manual_ids = {model.model_id for model in models}
            try:
                for model_id in dict.fromkeys(model_ids):
                    if model_id not in manual_ids:
                        models.append(existing.get(model_id) or CustomModel(
                            key=str(uuid4()), model_id=model_id, name=model_id,
                            context_limit=8192, output_limit=2048, tools=True, source="discovered"))
            except ValueError:
                raise CatalogError("invalid_request") from None
            return self._replace_models(current, tuple(models))

    def save_model(self, provider_id: str, model: CustomModel, *, expected_revision: int) -> CustomProvider:
        with self.store.gate:
            current = self.get(provider_id)
            if current.revision != expected_revision:
                raise CatalogError("revision_conflict")
            if model.source != "manual":
                raise CatalogError("invalid_request")
            if any(item.model_id == model.model_id and item.key != model.key for item in current.models):
                raise CatalogError("duplicate_model")
            found = any(item.key == model.key for item in current.models)
            models = tuple(model if item.key == model.key else item for item in current.models)
            return self._replace_models(current, models if found else (*models, model))

    def _replace_models(self, current: CustomProvider, models: tuple[CustomModel, ...]) -> CustomProvider:
        catalog = self.list()
        data = current.model_dump()
        data.update(models=models, revision=current.revision + 1, updated_at=datetime.now(UTC).isoformat())
        record = CustomProvider.model_validate(data)
        target = ProviderCatalog(revision=catalog.revision + 1,
            providers=tuple(record if item.id == record.id else item for item in catalog.providers))
        self.transaction.commit(target, current.id, expected_revision=catalog.revision)
        return record

    def delete_model(self, provider_id: str, model_key: str, *, expected_revision: int) -> CustomProvider:
        """Remove only catalog metadata after the caller checks live references."""
        with self.store.gate:
            current = self.get(provider_id)
            if current.revision != expected_revision:
                raise CatalogError("revision_conflict")
            if not any(model.key == model_key for model in current.models):
                raise CatalogError("model_not_found")
            return self._replace_models(current, tuple(model for model in current.models if model.key != model_key))
