"""Linux XDG Desktop Portal FileChooser adapter."""

from __future__ import annotations

import asyncio
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from .service import LocalPathPickerError, PathKind


_DESTINATION = "org.freedesktop.portal.Desktop"
_OBJECT_PATH = "/org/freedesktop/portal/desktop"


def _path_from_file_uri(value: object) -> str:
    if type(value) is not str:
        raise LocalPathPickerError("invalid_selection")
    parsed = urlsplit(value)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise LocalPathPickerError("invalid_selection")
    path = unquote(parsed.path)
    if not path or not PurePosixPath(path).is_absolute():
        raise LocalPathPickerError("invalid_selection")
    return path


class LinuxPortalPathPicker:
    def __init__(
        self,
        message_bus_factory=None,
        variant_type=None,
        session_bus=None,
    ) -> None:
        self._message_bus_factory = message_bus_factory
        self._variant_type = variant_type
        self._session_bus = session_bus

    async def pick(self, kind: PathKind) -> str | None:
        MessageBus = self._message_bus_factory
        Variant = self._variant_type
        session_bus = self._session_bus
        if MessageBus is None or Variant is None:
            try:
                from dbus_next import BusType, Variant as DbusVariant
                from dbus_next.aio import MessageBus as DbusMessageBus
            except ImportError:
                raise LocalPathPickerError("picker_unavailable") from None
            MessageBus = DbusMessageBus
            Variant = DbusVariant
            session_bus = BusType.SESSION

        bus = await MessageBus(bus_type=session_bus).connect()
        try:
            introspection = await bus.introspect(_DESTINATION, _OBJECT_PATH)
            proxy = bus.get_proxy_object(_DESTINATION, _OBJECT_PATH, introspection)
            chooser = proxy.get_interface("org.freedesktop.portal.FileChooser")
            handle = await chooser.call_open_file(
                "",
                "Select working directory" if kind == "directory" else "Select executable",
                {
                    "handle_token": Variant("s", f"opensprite_{uuid4().hex}"),
                    "modal": Variant("b", True),
                    "multiple": Variant("b", False),
                    "directory": Variant("b", kind == "directory"),
                },
            )
            request_data = await bus.introspect(_DESTINATION, handle)
            request_proxy = bus.get_proxy_object(_DESTINATION, handle, request_data)
            request = request_proxy.get_interface("org.freedesktop.portal.Request")
            loop = asyncio.get_running_loop()
            response: asyncio.Future[tuple[int, dict[str, object]]] = loop.create_future()

            def on_response(code: int, results: dict[str, object]) -> None:
                if not response.done():
                    response.set_result((code, results))

            request.on_response(on_response)
            code, results = await response
            if code == 1:
                return None
            if code != 0:
                raise LocalPathPickerError("picker_unavailable")
            uris_variant = results.get("uris")
            uris = getattr(uris_variant, "value", None)
            if type(uris) is not list or len(uris) != 1:
                raise LocalPathPickerError("invalid_selection")
            return _path_from_file_uri(uris[0])
        except LocalPathPickerError:
            raise
        except Exception:
            raise LocalPathPickerError("picker_unavailable") from None
        finally:
            bus.disconnect()
