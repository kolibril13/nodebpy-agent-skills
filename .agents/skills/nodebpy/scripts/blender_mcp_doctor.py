#!/usr/bin/env python3
"""Check that the Blender MCP bridge can accept and execute a safe request."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import socket
import sys
import time
from typing import Any


DEFAULT_HOST = os.environ.get("BLENDER_MCP_HOST", "127.0.0.1")
DEFAULT_PORT = os.environ.get("BLENDER_MCP_PORT", "9876")
DEFAULT_CONNECT_TIMEOUT = 0.5
DEFAULT_RESPONSE_TIMEOUT = 1.5
DEFAULT_WAIT = 0.0
MAX_RESPONSE_BYTES = 1024 * 1024
INITIAL_BACKOFF = 0.05
MAX_BACKOFF = 0.5

_PROBE_CODE = (
    "import bpy, os\n"
    "result = {\n"
    "    'ready': True,\n"
    "    'pid': os.getpid(),\n"
    "    'version': bpy.app.version_string,\n"
    "    'file': bpy.data.filepath,\n"
    "}\n"
)


class ProbeError(RuntimeError):
    """Raised when the bridge response is missing or invalid."""


def _positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def _non_negative_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def _port(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("must be between 1 and 65535")
    return number


def _remaining_timeout(configured: float, deadline: float | None) -> float:
    if deadline is None:
        return configured
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        raise TimeoutError("readiness deadline reached")
    return min(configured, remaining)


def _request_bytes() -> bytes:
    request = {
        "type": "execute",
        "code": _PROBE_CODE,
        "strict_json": True,
    }
    return (json.dumps(request, separators=(",", ":")) + "\0").encode("utf-8")


def _probe(
    host: str,
    port: int,
    connect_timeout: float,
    response_timeout: float,
    deadline: float | None,
) -> tuple[dict[str, Any], float, float]:
    connect_started = time.monotonic()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(_remaining_timeout(connect_timeout, deadline))
        sock.connect((host, port))
        connected = time.monotonic()

        sock.settimeout(_remaining_timeout(response_timeout, deadline))
        sock.sendall(_request_bytes())

        response = bytearray()
        while b"\0" not in response:
            chunk = sock.recv(65536)
            if not chunk:
                raise ProbeError("Blender closed the bridge without a response")
            response.extend(chunk)
            if len(response) > MAX_RESPONSE_BYTES:
                raise ProbeError("response exceeded the 1 MiB limit")
        received = time.monotonic()
    finally:
        sock.close()

    raw_response = bytes(response).partition(b"\0")[0]
    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError("Blender returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ProbeError("Blender returned a non-object response")
    if payload.get("status") != "ok":
        message = payload.get("message", "unknown Blender error")
        raise ProbeError(str(message).splitlines()[0])

    result = payload.get("result")
    if not isinstance(result, dict) or result.get("ready") is not True:
        raise ProbeError("Blender returned an invalid readiness result")

    connect_ms = (connected - connect_started) * 1000.0
    response_ms = (received - connected) * 1000.0
    return result, connect_ms, response_ms


def _error_summary(exc: BaseException) -> str:
    if isinstance(exc, ConnectionRefusedError):
        return "connection refused"
    if isinstance(exc, socket.timeout):
        return "timed out waiting for Blender"
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return text


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe the local Blender Lab MCP bridge without changing the scene.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Blender bridge host")
    parser.add_argument("--port", type=_port, default=DEFAULT_PORT, help="Blender bridge port")
    parser.add_argument(
        "--connect-timeout",
        type=_positive_float,
        default=DEFAULT_CONNECT_TIMEOUT,
        metavar="SECONDS",
        help="per-attempt TCP connect timeout (default: 0.5)",
    )
    parser.add_argument(
        "--response-timeout",
        type=_positive_float,
        default=DEFAULT_RESPONSE_TIMEOUT,
        metavar="SECONDS",
        help="per-attempt Blender response timeout (default: 1.5)",
    )
    parser.add_argument(
        "--wait",
        type=_non_negative_float,
        default=DEFAULT_WAIT,
        metavar="SECONDS",
        help="total retry window; 0 performs one attempt (default: 0)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started = time.monotonic()
    deadline = started + args.wait if args.wait > 0.0 else None
    attempts = 0
    backoff = INITIAL_BACKOFF
    last_error: BaseException | None = None

    while True:
        if attempts and deadline is not None and time.monotonic() >= deadline:
            break
        attempts += 1
        try:
            blender, connect_ms, response_ms = _probe(
                args.host,
                args.port,
                args.connect_timeout,
                args.response_timeout,
                deadline,
            )
        except PermissionError as exc:
            # A sandbox or policy denial cannot recover through backoff.
            last_error = exc
            break
        except (OSError, ProbeError) as exc:
            last_error = exc
            if deadline is None:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            sleep_for = min(backoff * random.uniform(0.8, 1.2), remaining)
            time.sleep(sleep_for)
            backoff = min(backoff * 2.0, MAX_BACKOFF)
            continue

        output = {
            "ok": True,
            "host": args.host,
            "port": args.port,
            "attempts": attempts,
            "connect_ms": round(connect_ms, 3),
            "response_ms": round(response_ms, 3),
            "total_ms": round((time.monotonic() - started) * 1000.0, 3),
            "blender": blender,
        }
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))
        return 0

    elapsed = time.monotonic() - started
    detail = _error_summary(last_error or ProbeError("unknown error"))
    print(
        f"blender-mcp-doctor: unavailable after {elapsed:.2f}s "
        f"({attempts} attempt{'s' if attempts != 1 else ''}): {detail}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("blender-mcp-doctor: interrupted", file=sys.stderr)
        raise SystemExit(130) from None
