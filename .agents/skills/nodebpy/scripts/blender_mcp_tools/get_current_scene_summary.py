# SPDX-FileCopyrightText: 2026 Blender MCP Fast Server contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Register the bounded, read-only current-scene summary tool."""

__all__ = ("register",)

from blmcp.tools_helpers import (
    toolcode_format_call,
    toolcode_load_from_filepath,
    toolcode_wrap_with_calling_convention,
)
from blmcp.tools_helpers.connection import send_code
from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error,no-name-in-module
from mcp.types import ToolAnnotations  # pylint: disable=import-error,no-name-in-module


_TOOL_CALL = toolcode_wrap_with_calling_convention(
    toolcode_load_from_filepath(__file__)
)


def register(mcp: FastMCP) -> None:
    """Register one-call scene orientation with upstream FastMCP."""

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Current Scene Summary",
            readOnlyHint=True,
        )
    )
    def get_current_scene_summary() -> dict[str, object]:
        """Return one bounded overview of scene, render, objects, collections, and nodes."""
        response = send_code(
            toolcode_format_call(_TOOL_CALL, None),
            strict_json=True,
        )
        if response.get("status") != "ok":
            raise RuntimeError(str(response.get("message", "Blender call failed")))
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Blender returned an invalid scene summary")
        return result
