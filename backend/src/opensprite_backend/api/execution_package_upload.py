"""Bounded one-wheel multipart ingress; filenames never choose disk paths."""

from fastapi import Request
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from opensprite_backend.execution_plugins.models import ExecutionPackageError, MAX_WHEEL_BYTES

MAX_REQUEST_BYTES = MAX_WHEEL_BYTES + 65536


class BoundedWheelParser(MultiPartParser):
    spool_max_size = MAX_REQUEST_BYTES

    def on_part_begin(self):
        super().on_part_begin()
        self.part_bytes = 0

    def on_part_data(self, data, start, end):
        self.part_bytes += end - start
        if self.part_bytes > MAX_WHEEL_BYTES:
            raise MultiPartException("package_too_large")
        super().on_part_data(data, start, end)


async def read_wheel_upload(request: Request):
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data;"):
        raise ExecutionPackageError("invalid_request")
    async def bounded_stream():
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                raise MultiPartException("package_too_large")
            yield chunk
    parser = BoundedWheelParser(request.headers, bounded_stream(), max_files=1, max_fields=0)
    form = None
    try:
        form = await parser.parse()
        values = list(form.multi_items())
        if len(values) != 1 or values[0][0] != "file" or not isinstance(values[0][1], UploadFile):
            raise ExecutionPackageError("invalid_request")
        upload = values[0][1]
        if not isinstance(upload.filename, str):
            raise ExecutionPackageError("invalid_request")
        data = await upload.read(MAX_WHEEL_BYTES + 1)
        if len(data) > MAX_WHEEL_BYTES:
            raise ExecutionPackageError("package_too_large")
        return upload.filename, data
    except MultiPartException as error:
        raise ExecutionPackageError("package_too_large" if error.message == "package_too_large" else "invalid_request") from None
    except (ValueError, UnicodeError):
        raise ExecutionPackageError("invalid_request") from None
    finally:
        if form is not None:
            await form.close()
        else:
            for stream in parser._files_to_close_on_error:
                stream.close()
