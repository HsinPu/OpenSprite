"""Serialize provider mutations against Run acceptance and durable references."""

from __future__ import annotations

import asyncio

from .catalog_store import CatalogError, CustomModel
from .custom_service import CustomProviderService


async def _owned_thread(function, *args, **kwargs):
    """Do not release the mutation gate while a cancelled HTTP write still runs."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Repeated HTTP cancellation must not cancel the wrapper task while its
        # worker still owns a catalog write. Keep the gate until it really ends.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not task.cancelled():
            task.exception()  # Retrieve a worker failure without replacing cancellation.
        raise


class ProviderMutations:
    def __init__(self, service: CustomProviderService, gate, repository, run_manager, ai_settings, agents) -> None:
        self.service = service
        self.gate = gate
        self.repository = repository
        self.run_manager = run_manager
        self.ai_settings = ai_settings
        self.agents = agents

    async def _check(self, provider_id: str, *, deleting: bool, model_id: str | None = None) -> None:
        # Snapshot references cover possible child execution even before it spawns.
        if self.run_manager.provider_in_use(provider_id):
            raise CatalogError("provider_busy")
        try:
            active, schedules = await asyncio.to_thread(self.repository.provider_usage, provider_id, model_id)
            if active:
                raise CatalogError("provider_busy")
            if not deleting:
                return
            settings = await self.ai_settings.get()
            selected = settings.model
            if schedules or (selected is not None and selected.provider_id == provider_id
                    and (model_id is None or selected.model_id == model_id)):
                raise CatalogError("provider_in_use")
            if await asyncio.to_thread(self.agents.references_provider, provider_id, model_id):
                raise CatalogError("provider_in_use")
        except CatalogError:
            raise
        except Exception:
            raise CatalogError("provider_references_unavailable") from None

    async def update(self, provider_id: str, **fields):
        async with self.gate.hold():
            await self._check(provider_id, deleting=False)
            return await _owned_thread(self.service.save, provider_id=provider_id, **fields)

    async def delete(self, provider_id: str, *, expected_revision: int) -> None:
        async with self.gate.hold():
            await self._check(provider_id, deleting=True)
            await _owned_thread(self.service.delete, provider_id, expected_revision=expected_revision)

    async def update_model(self, provider_id: str, model: CustomModel, *, expected_revision: int):
        async with self.gate.hold():
            current = await asyncio.to_thread(self.service.get, provider_id)
            previous = next((item for item in current.models if item.key == model.key), None)
            if previous is None:
                raise CatalogError("model_not_found")
            await self._check(provider_id, deleting=previous.model_id != model.model_id, model_id=previous.model_id)
            return await _owned_thread(self.service.save_model, provider_id, model, expected_revision=expected_revision)

    async def delete_model(self, provider_id: str, model_key: str, *, expected_revision: int):
        async with self.gate.hold():
            current = await asyncio.to_thread(self.service.get, provider_id)
            model = next((item for item in current.models if item.key == model_key), None)
            if model is None:
                raise CatalogError("model_not_found")
            await self._check(provider_id, deleting=True, model_id=model.model_id)
            return await _owned_thread(self.service.delete_model, provider_id, model_key, expected_revision=expected_revision)

    async def discovery_credentials(self, provider_id: str, *, expected_revision: int):
        """Bind the credential to the endpoint before starting external I/O."""
        async with self.gate.hold():
            provider = await asyncio.to_thread(self.service.get, provider_id)
            if provider.revision != expected_revision:
                raise CatalogError("revision_conflict")
            secret = None
            if provider.auth_mode == "bearer":
                try:
                    secret = await asyncio.to_thread(self.service.transaction.credentials.get, f"provider:{provider_id}:bearer")
                except Exception:
                    raise CatalogError("credential_store_unavailable") from None
                if secret is None:
                    raise CatalogError("credential_required")
            return provider, secret

    async def merge_discovery(self, provider_id: str, model_ids: list[str], *, expected_revision: int):
        async with self.gate.hold():
            current = await asyncio.to_thread(self.service.get, provider_id)
            if current.revision != expected_revision:
                raise CatalogError("revision_conflict")
            await self._check(provider_id, deleting=False)
            returned = set(model_ids)
            for model in current.models:
                if model.source == "discovered" and model.model_id not in returned:
                    await self._check(provider_id, deleting=True, model_id=model.model_id)
            return await _owned_thread(self.service.merge_discovered_models, provider_id, model_ids, expected_revision=expected_revision)
