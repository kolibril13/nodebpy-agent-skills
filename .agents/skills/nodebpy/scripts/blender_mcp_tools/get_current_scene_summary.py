# SPDX-FileCopyrightText: 2026 Blender MCP Fast Server contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Register the bounded, read-only current-scene summary tool."""

__all__ = ("register",)

from typing import Any

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


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _names(value: object, empty: str = "none") -> str:
    names = [str(item) for item in _list(value)]
    return ", ".join(names) if names else empty


def _vector(value: object) -> str:
    return "(" + ", ".join(str(item) for item in _list(value)) + ")"


def _format_summary(payload: dict[str, object]) -> str:
    """Compress structured Blender data into a model-ready scene inventory."""
    file_info = _dict(payload.get("file"))
    scene = _dict(payload.get("scene"))
    render = _dict(payload.get("render"))
    resolution = _list(render.get("resolution"))
    selected = _names(payload.get("selected_objects"))

    path = str(file_info.get("path") or "unsaved")
    save_state = "saved" if file_info.get("saved") else "unsaved"
    dirty_state = "dirty" if file_info.get("dirty") else "clean"
    lines = [
        "File: {:s} ({:s}, {:s})".format(path, save_state, dirty_state),
        "Scene: {name}; frame {frame} (range {start}-{end}); workspace {workspace}; mode {mode}".format(
            name=scene.get("name"),
            frame=scene.get("frame"),
            start=scene.get("frame_start"),
            end=scene.get("frame_end"),
            workspace=scene.get("active_workspace"),
            mode=scene.get("mode"),
        ),
        "Render: {engine}; {resolution}; {fps} fps".format(
            engine=render.get("engine"),
            resolution=(
                "{:s}x{:s} at {:s}%".format(*map(str, resolution[:3]))
                if len(resolution) >= 3
                else "resolution unknown"
            ),
            fps=render.get("fps"),
        ),
        "World: {world}; camera {camera}; active {active}; selected {selected}".format(
            world=scene.get("world"),
            camera=scene.get("camera"),
            active=payload.get("active_object"),
            selected=selected,
        ),
    ]

    type_counts = _dict(payload.get("object_type_counts"))
    type_text = ", ".join(
        "{:s}={:s}".format(str(name), str(count))
        for name, count in type_counts.items()
    ) or "none"
    lines.append(
        "Objects: {:s} ({:s}); showing {:d}, omitted {:s}".format(
            str(payload.get("object_count")),
            type_text,
            len(_list(payload.get("objects"))),
            str(payload.get("objects_omitted", 0)),
        )
    )
    for item_value in _list(payload.get("objects")):
        item = _dict(item_value)
        transform = _dict(item.get("transform"))
        parts = [
            "- {name} [{type}]".format(name=item.get("name"), type=item.get("type")),
            "location " + _vector(transform.get("world_location")),
            "dimensions " + _vector(transform.get("world_dimensions")),
        ]
        if item.get("data"):
            parts.append("data " + str(item["data"]))
        if item.get("parent"):
            parts.append("parent " + str(item["parent"]))
        collections = _names(item.get("collections"), empty="")
        if collections:
            parts.append("collections " + collections)
        materials = _names(item.get("materials"), empty="")
        if materials:
            parts.append("materials " + materials)
        modifiers = [
            "{:s}:{:s}".format(str(modifier.get("name")), str(modifier.get("type")))
            for modifier in (_dict(value) for value in _list(item.get("modifiers")))
        ]
        if modifiers:
            parts.append("modifiers " + ", ".join(modifiers))
        lines.append("; ".join(parts))

    lines.append(
        "Collections: {:s}; showing {:d}, omitted {:s}".format(
            str(payload.get("collection_count")),
            len(_list(payload.get("collections"))),
            str(payload.get("collections_omitted", 0)),
        )
    )
    for item_value in _list(payload.get("collections")):
        item = _dict(item_value)
        details = []
        for label, key in (("parents", "parents"), ("children", "children"), ("objects", "objects")):
            names = _names(item.get(key), empty="")
            if names:
                details.append(label + " " + names)
        line = "- " + str(item.get("name"))
        if details:
            line += "; " + "; ".join(details)
        lines.append(line)

    lines.append(
        "Node groups: {:s}; showing {:d}, omitted {:s}: {:s}".format(
            str(payload.get("node_group_count")),
            len(_list(payload.get("node_groups"))),
            str(payload.get("node_groups_omitted", 0)),
            _names(payload.get("node_groups")),
        )
    )
    return "\n".join(lines)


def register(mcp: FastMCP) -> None:
    """Register one-call scene orientation with upstream FastMCP."""

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Current Scene Summary",
            readOnlyHint=True,
        )
    )
    def get_current_scene_summary() -> str:
        """Return a concise current-scene inventory in one read-only call."""
        response = send_code(
            toolcode_format_call(_TOOL_CALL, None),
            strict_json=True,
        )
        if response.get("status") != "ok":
            raise RuntimeError(str(response.get("message", "Blender call failed")))
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Blender returned an invalid scene summary")
        return _format_summary(result)
