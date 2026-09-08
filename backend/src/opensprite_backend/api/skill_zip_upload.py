"""Bounded multipart ingress; uploaded filenames are never filesystem paths."""
import json

from fastapi import Request
from pydantic import Field, ValidationError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from opensprite_backend.skills.zip_import import MAX_ZIP_BYTES, read_zip
import asyncio
from opensprite_backend.skills.models import StrictModel, SkillError
from opensprite_backend.skills.service import unique

# Bounded strict metadata plus one archive; filenames never select paths.
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = MAX_ZIP_BYTES + MAX_MANIFEST_BYTES + 65536


class ZipManifest(StrictModel):
    scope: str
    workspaceId: str | None
    directoryName: str = Field(min_length=1, max_length=80)
    expectedRevision: int = Field(ge=0)


class BoundedParser(MultiPartParser):
    # Keep bounded upload bytes in memory, never in the OS temporary data root.
    spool_max_size = MAX_REQUEST_BYTES

    def on_part_begin(self):
        super().on_part_begin()
        self.part_bytes = 0

    def on_part_data(self, data, start, end):
        self.part_bytes += end - start
        if self.part_bytes > MAX_ZIP_BYTES:
            raise MultiPartException("file_too_large")
        super().on_part_data(data, start, end)


async def read_zip_upload(request: Request):
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data;"):
        raise SkillError("invalid_request")

    async def bounded_stream():
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                raise MultiPartException("package_too_large")
            yield chunk

    parser = BoundedParser(request.headers, bounded_stream(), max_files=1, max_fields=1, max_part_size=MAX_MANIFEST_BYTES)
    form = None
    try:
        form = await parser.parse()
        values = {}
        for key, value in form.multi_items():
            if key in values:
                raise SkillError("invalid_request")
            values[key] = value
        raw = values.pop("manifest", None)
        if not isinstance(raw, str):
            raise SkillError("invalid_request")
        try:
            manifest = ZipManifest.model_validate(json.loads(raw, object_pairs_hook=unique))
        except SkillError:
            # Duplicate input keys are not a persisted-catalog failure.
            raise SkillError("invalid_request") from None
        if manifest.scope not in {"global", "workspace"} or (manifest.scope == "global") != (manifest.workspaceId is None):
            raise SkillError("invalid_request")
        if set(values) != {"archive"}:
            raise SkillError("invalid_request")
        upload = values["archive"]
        if not isinstance(upload, UploadFile):
            raise SkillError("invalid_request")
        data = await upload.read(MAX_ZIP_BYTES + 1)
        return manifest, await asyncio.to_thread(read_zip, data)
    except MultiPartException as error:
        code = error.message if error.message in {"package_too_large", "file_too_large"} else "invalid_request"
        raise SkillError(code) from None
    except (ValueError, UnicodeError, ValidationError):
        raise SkillError("invalid_request") from None
    finally:
        if form is not None:
            await form.close()
        else:
            # Starlette only cleans MultiPartException; also cover disconnect/cancellation.
            for file in parser._files_to_close_on_error:
                file.close()
