"""Internal Windows shell launcher used to assign commands to a Job Object."""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.readline().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 2
    if not isinstance(payload, dict):
        return 2
    argv_payload = payload.get("argv")
    argv = (
        list(argv_payload)
        if isinstance(argv_payload, list)
        and argv_payload
        and all(isinstance(item, str) for item in argv_payload)
        and str(argv_payload[0]).strip()
        else None
    )
    command = str(payload.get("command") or "").strip()
    if argv is None and not command:
        return 2
    try:
        if argv is not None:
            completed = subprocess.run(
                argv,
                shell=False,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        else:
            completed = subprocess.run(
                command,
                shell=True,
                stdin=subprocess.DEVNULL,
                check=False,
            )
    except OSError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 1
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
