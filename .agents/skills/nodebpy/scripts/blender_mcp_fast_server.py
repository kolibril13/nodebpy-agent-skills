#!/usr/bin/env python3
"""Launch the official Blender MCP server with fail-fast socket settings.

Run this script with the Python interpreter from the official Blender MCP
environment.  It changes only the MCP-to-Blender socket client; command-line
arguments are left untouched for :func:`blmcp.main` to handle.

Environment variables:

``BLENDER_MCP_CONNECT_TIMEOUT``
    Seconds allowed for the TCP connection to Blender (default: ``0.5``).
``BLENDER_MCP_RESPONSE_TIMEOUT``
    Seconds allowed for sending a request and receiving its response
    (default: ``30``).
``BLENDER_MCP_MAX_RESPONSE_BYTES``
    Maximum accepted response size (default: 64 MiB).

The official ``BLENDER_MCP_HOST`` and ``BLENDER_MCP_PORT`` variables continue
to be handled by ``blmcp.tools_helpers.connection.get_connection_params``.
"""

from __future__ import annotations

import json
import math
import os
import socket
import threading

import blmcp
from blmcp.tools_helpers import connection as _connection


_DEFAULT_CONNECT_TIMEOUT = 0.5
_DEFAULT_RESPONSE_TIMEOUT = 30.0
_DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_RECV_BUFFER_SIZE = 65536
_SEND_LOCK = threading.Lock()


class _NormalizedConnectionError(ConnectionError):
    """ConnectionError already formatted for the MCP client."""


def _positive_float_from_env(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as ex:
        raise ValueError("{:s} must be a positive number".format(name)) from ex
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("{:s} must be a positive finite number".format(name))
    return value


def _positive_int_from_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as ex:
        raise ValueError("{:s} must be a positive integer".format(name)) from ex
    if value <= 0:
        raise ValueError("{:s} must be a positive integer".format(name))
    return value


def _error(host: str, port: int, detail: str) -> _NormalizedConnectionError:
    return _NormalizedConnectionError(
        "Blender MCP connection to {:s}:{:d} failed: {:s}".format(host, port, detail)
    )


def _send_code_unlocked(code: str, strict_json: bool) -> dict[str, object]:
    """Send one official null-delimited JSON request to the Blender add-on."""
    host, port = _connection.get_connection_params()
    connect_timeout = _positive_float_from_env(
        "BLENDER_MCP_CONNECT_TIMEOUT", _DEFAULT_CONNECT_TIMEOUT
    )
    response_timeout = _positive_float_from_env(
        "BLENDER_MCP_RESPONSE_TIMEOUT", _DEFAULT_RESPONSE_TIMEOUT
    )
    max_response_bytes = _positive_int_from_env(
        "BLENDER_MCP_MAX_RESPONSE_BYTES", _DEFAULT_MAX_RESPONSE_BYTES
    )

    request = json.dumps(
        {
            "type": "execute",
            "code": code,
            "strict_json": strict_json,
        }
    ) + "\0"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(connect_timeout)
        try:
            sock.connect((host, port))
        except ConnectionRefusedError as ex:
            raise _error(
                host,
                port,
                "connection refused; ensure Blender is running with the official "
                "MCP add-on enabled and its server started",
            ) from ex
        except socket.timeout as ex:
            raise _error(
                host,
                port,
                "connect timed out after {:.3g}s".format(connect_timeout),
            ) from ex
        except OSError as ex:
            raise _error(host, port, "connect socket error: {:s}".format(str(ex))) from ex

        sock.settimeout(response_timeout)
        buf = bytearray()
        try:
            sock.sendall(request.encode("utf-8"))
            while True:
                chunk = sock.recv(_RECV_BUFFER_SIZE)
                if not chunk:
                    break
                buf.extend(chunk)

                delimiter_index = buf.find(b"\0")
                if delimiter_index != -1:
                    if delimiter_index > max_response_bytes:
                        raise _error(
                            host,
                            port,
                            "response exceeded the configured {:d}-byte limit".format(
                                max_response_bytes
                            ),
                        )
                    break
                if len(buf) > max_response_bytes:
                    raise _error(
                        host,
                        port,
                        "response exceeded the configured {:d}-byte limit".format(
                            max_response_bytes
                        ),
                    )
        except socket.timeout as ex:
            raise _error(
                host,
                port,
                "response timed out after {:.3g}s".format(response_timeout),
            ) from ex
        except _NormalizedConnectionError:
            raise
        except OSError as ex:
            raise _error(
                host, port, "request/response socket error: {:s}".format(str(ex))
            ) from ex

    if not buf:
        raise _error(host, port, "empty response")
    if b"\0" not in buf:
        raise _error(host, port, "response ended before the null-byte delimiter")

    line, _separator, _remainder = buf.partition(b"\0")
    try:
        response = json.loads(line.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        raise _error(host, port, "invalid JSON response: {:s}".format(str(ex))) from ex
    if not isinstance(response, dict):
        raise _error(host, port, "response was not a JSON object")
    return response


def _send_code(code: str, strict_json: bool) -> dict[str, object]:
    """Allow one in-flight Blender request per MCP server process."""
    if not _SEND_LOCK.acquire(blocking=False):
        host, port = _connection.get_connection_params()
        raise _error(
            host,
            port,
            "another Blender call is already in flight; serialize MCP requests",
        )
    try:
        return _send_code_unlocked(code, strict_json)
    finally:
        _SEND_LOCK.release()


def main() -> int:
    """Patch the connection helper, then delegate all CLI handling upstream."""
    _connection.send_code = _send_code
    return blmcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
