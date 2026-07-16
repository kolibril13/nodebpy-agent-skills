#!/usr/bin/env python3
"""Inspect or persist low-latency settings for the official Blender MCP add-on."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from typing import Any


MAX_RESPONSE_BYTES = 1_048_576
OFFICIAL_ADDON_KEY = "bl_ext.lab_blender_org.mcp"


def _blender_code(apply: bool) -> str:
    return f'''
import bpy

required = (
    "host",
    "port",
    "use_autostart",
    "autostart_delay",
    "timer_interval_active",
    "timer_interval_idle",
    "timer_interval_idle_delay",
)

matches = []
for addon_key, addon in bpy.context.preferences.addons.items():
    prefs = getattr(addon, "preferences", None)
    if prefs is not None and all(hasattr(prefs, name) for name in required):
        matches.append((addon_key, prefs))

preferred = [item for item in matches if item[0] == {OFFICIAL_ADDON_KEY!r}]
if preferred:
    addon_key, prefs = preferred[0]
elif len(matches) == 1:
    addon_key, prefs = matches[0]
else:
    raise RuntimeError(
        "Expected one official MCP add-on, found: " +
        ", ".join(key for key, _prefs in matches)
    )

def snapshot():
    return {{
        "host": prefs.host,
        "port": prefs.port,
        "autostart": prefs.use_autostart,
        "autostart_delay": prefs.autostart_delay,
        "timer_interval_active": prefs.timer_interval_active,
        "timer_interval_idle": prefs.timer_interval_idle,
        "timer_interval_idle_delay": prefs.timer_interval_idle_delay,
        "logging": getattr(prefs, "use_log", None),
    }}

before = snapshot()
saved = False
if {apply!r}:
    prefs.host = "127.0.0.1"
    prefs.port = 9876
    prefs.use_autostart = True
    prefs.autostart_delay = 0.0
    prefs.timer_interval_active = 0.05
    prefs.timer_interval_idle = 0.10
    prefs.timer_interval_idle_delay = 60.0
    if hasattr(prefs, "use_log"):
        prefs.use_log = False
    save_result = sorted(bpy.ops.wm.save_userpref())
    saved = "FINISHED" in save_result

result = {{
    "addon": addon_key,
    "applied": {apply!r},
    "saved": saved,
    "before": before,
    "after": snapshot(),
}}
'''


def _request(
    host: str,
    port: int,
    connect_timeout: float,
    response_timeout: float,
    apply: bool,
) -> dict[str, Any]:
    payload = (
        json.dumps(
            {
                "type": "execute",
                "code": _blender_code(apply),
                "strict_json": True,
            }
        ).encode("utf-8")
        + b"\0"
    )

    with socket.create_connection((host, port), timeout=connect_timeout) as sock:
        sock.settimeout(response_timeout)
        sock.sendall(payload)
        buffer = bytearray()
        while b"\0" not in buffer:
            chunk = sock.recv(65_536)
            if not chunk:
                raise ConnectionError("Blender closed the bridge before replying")
            buffer.extend(chunk)
            if len(buffer) > MAX_RESPONSE_BYTES:
                raise ConnectionError("Blender MCP tuning response exceeded 1 MiB")

    response = json.loads(buffer.partition(b"\0")[0].decode("utf-8"))
    if response.get("status") != "ok":
        raise RuntimeError(str(response.get("message", response)))
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected Blender MCP response: {response!r}")
    return result


def _positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host",
        default=os.environ.get("BLENDER_MCP_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("BLENDER_MCP_PORT", "9876")),
    )
    parser.add_argument("--connect-timeout", type=_positive_float, default=0.5)
    parser.add_argument("--response-timeout", type=_positive_float, default=5.0)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply and save the low-latency settings; otherwise only inspect them",
    )
    args = parser.parse_args()

    try:
        result = _request(
            args.host,
            args.port,
            args.connect_timeout,
            args.response_timeout,
            args.apply,
        )
    except (OSError, ValueError, RuntimeError, ConnectionError) as exc:
        print(f"Blender MCP tuning failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
