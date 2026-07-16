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
from typing import Any

import blmcp
from blmcp.tools_helpers import connection as _connection
from mcp.types import ToolAnnotations


_DEFAULT_CONNECT_TIMEOUT = 0.5
_DEFAULT_RESPONSE_TIMEOUT = 30.0
_DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_RECV_BUFFER_SIZE = 65536
_SEND_LOCK = threading.Lock()
_COMPACT_INSTRUCTIONS = """\
Use these tools to inspect and edit the connected Blender session. Inspect first,
preserve existing names and structure, and prefer a specific tool over arbitrary
Python. Start general scene questions with get_current_scene_summary; keep later
reads focused instead of dumping large scenes.

Treat mutations as potentially destructive. Do not delete, overwrite, apply, or
irreversibly change data without clear user intent. Check active object, selection,
and mode before context-dependent operators; operators may change all three. Shared
datablocks affect every user, so inspect user counts before editing them.

For execute_blender_code, assign JSON-serializable dicts/lists to `result`; do not
rely on printed output. Consult the bundled API/manual search tools when an API is
uncertain. After edits, update the dependency graph before reading evaluated data.
"""
_UPSTREAM_FAST_MCP = blmcp.FastMCP


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


_SCENE_SUMMARY_TOOL_CODE = r'''\
import bpy

MAX_OBJECTS = 100
MAX_COLLECTIONS = 100
MAX_NODE_GROUPS = 100
MAX_SCENES = 64
MAX_SELECTED = 100
MAX_COLLECTION_OBJECTS = 100
MAX_OBJECT_COLLECTIONS = 32
MAX_MATERIALS = 32
MAX_MODIFIERS = 32


def name_key(value):
    return (value.casefold(), value)


def bounded_names(values, limit):
    names = sorted(set(values), key=name_key)
    return names[:limit], max(0, len(names) - limit)


def clean_float(value):
    rounded = round(float(value), 4)
    return 0.0 if rounded == 0.0 else rounded


def vector(value):
    return [clean_float(item) for item in value]


def rotation(obj):
    if obj.rotation_mode == "QUATERNION":
        return vector(obj.rotation_quaternion)
    if obj.rotation_mode == "AXIS_ANGLE":
        return vector(obj.rotation_axis_angle)
    return vector(obj.rotation_euler)


def object_info(obj, selected_names):
    collections, collections_omitted = bounded_names(
        (collection.name for collection in obj.users_collection),
        MAX_OBJECT_COLLECTIONS,
    )
    materials, materials_omitted = bounded_names(
        (
            slot.material.name
            for slot in obj.material_slots
            if slot.material is not None
        ),
        MAX_MATERIALS,
    )
    all_modifiers = [
        {"name": modifier.name, "type": modifier.type}
        for modifier in obj.modifiers
    ]
    value = {
        "name": obj.name,
        "type": obj.type,
        "data": obj.data.name if obj.data is not None else None,
        "parent": obj.parent.name if obj.parent is not None else None,
        "selected": obj.name in selected_names,
        "collections": collections,
        "transform": {
            "local_location": vector(obj.location),
            "rotation_mode": obj.rotation_mode,
            "local_rotation": rotation(obj),
            "local_scale": vector(obj.scale),
            "world_location": vector(obj.matrix_world.translation),
            "world_dimensions": vector(obj.dimensions),
        },
        "materials": materials,
        "modifiers": all_modifiers[:MAX_MODIFIERS],
    }
    if collections_omitted:
        value["collections_omitted"] = collections_omitted
    if materials_omitted:
        value["materials_omitted"] = materials_omitted
    if len(all_modifiers) > MAX_MODIFIERS:
        value["modifiers_omitted"] = len(all_modifiers) - MAX_MODIFIERS
    return value


def scene_collections(root):
    found = {}
    parent_names = {}
    pending = [root]
    while pending:
        collection = pending.pop()
        if collection.name in found:
            continue
        found[collection.name] = collection
        children = sorted(collection.children, key=lambda item: name_key(item.name))
        for child in children:
            parent_names.setdefault(child.name, set()).add(collection.name)
        pending.extend(reversed(children))
    return (
        sorted(found.values(), key=lambda item: name_key(item.name)),
        parent_names,
    )


def collection_info(collection, parent_names):
    objects, objects_omitted = bounded_names(
        (obj.name for obj in collection.objects),
        MAX_COLLECTION_OBJECTS,
    )
    children, children_omitted = bounded_names(
        (child.name for child in collection.children),
        MAX_COLLECTIONS,
    )
    parents, parents_omitted = bounded_names(
        parent_names.get(collection.name, set()),
        MAX_COLLECTIONS,
    )
    value = {
        "name": collection.name,
        "parents": parents,
        "children": children,
        "objects": objects,
    }
    if parents_omitted:
        value["parents_omitted"] = parents_omitted
    if children_omitted:
        value["children_omitted"] = children_omitted
    if objects_omitted:
        value["objects_omitted"] = objects_omitted
    return value


context = bpy.context
data = bpy.data
scene = context.scene
view_layer = context.view_layer

all_selected_names = [obj.name for obj in context.selected_objects]
selected_names, selected_omitted = bounded_names(
    all_selected_names,
    MAX_SELECTED,
)
selected_name_set = set(all_selected_names)
all_objects = sorted(scene.objects, key=lambda item: name_key(item.name))
object_type_counts = {}
for obj in all_objects:
    object_type_counts[obj.type] = object_type_counts.get(obj.type, 0) + 1
object_type_counts = {
    object_type: object_type_counts[object_type]
    for object_type in sorted(object_type_counts, key=name_key)
}

all_collections, parent_names = scene_collections(scene.collection)
active = view_layer.objects.active
render = scene.render
scene_names, scenes_omitted = bounded_names(
    (item.name for item in data.scenes),
    MAX_SCENES,
)
file_info = {
    "path": data.filepath,
    "saved": data.is_saved,
    "dirty": data.is_dirty,
    "scenes": scene_names,
}
if scenes_omitted:
    file_info["scenes_omitted"] = scenes_omitted

node_group_names, node_groups_omitted = bounded_names(
    (item.name for item in data.node_groups),
    MAX_NODE_GROUPS,
)
window = getattr(context, "window", None)

result = {
    "status": "ok",
    "file": file_info,
    "scene": {
        "name": scene.name,
        "frame": scene.frame_current,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "camera": scene.camera.name if scene.camera is not None else None,
        "world": scene.world.name if scene.world is not None else None,
        "active_workspace": window.workspace.name if window is not None else None,
        "mode": context.mode,
    },
    "render": {
        "engine": render.engine,
        "resolution": [
            render.resolution_x,
            render.resolution_y,
            render.resolution_percentage,
        ],
        "fps": render.fps,
        "fps_base": clean_float(render.fps_base),
    },
    "active_object": active.name if active is not None else None,
    "selected_objects": selected_names,
    "selected_objects_omitted": selected_omitted,
    "object_count": len(all_objects),
    "object_type_counts": object_type_counts,
    "objects_omitted": max(0, len(all_objects) - MAX_OBJECTS),
    "objects": [
        object_info(obj, selected_name_set)
        for obj in all_objects[:MAX_OBJECTS]
    ],
    "collection_count": len(all_collections),
    "collections_omitted": max(0, len(all_collections) - MAX_COLLECTIONS),
    "collections": [
        collection_info(collection, parent_names)
        for collection in all_collections[:MAX_COLLECTIONS]
    ],
    "node_group_count": len(data.node_groups),
    "node_groups_omitted": node_groups_omitted,
    "node_groups": node_group_names,
}
'''


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _names(value: object, empty: str = "none") -> str:
    names = [str(item) for item in _list(value)]
    return ", ".join(names) if names else empty


def _vector(value: object) -> str:
    return "(" + ", ".join(str(item) for item in _list(value)) + ")"


def _format_scene_summary(payload: dict[str, object]) -> str:
    """Compress structured Blender data into a model-ready scene inventory."""
    file_info = _dict(payload.get("file"))
    scene = _dict(payload.get("scene"))
    render = _dict(payload.get("render"))
    resolution = _list(render.get("resolution"))
    lines = [
        "File: {:s} ({:s}, {:s})".format(
            str(file_info.get("path") or "untitled"),
            "saved" if file_info.get("saved") else "unsaved",
            "dirty" if file_info.get("dirty") else "clean",
        ),
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
            selected=_names(payload.get("selected_objects")),
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
        for label, key in (
            ("parents", "parents"),
            ("children", "children"),
            ("objects", "objects"),
        ):
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


def _register_scene_summary(mcp: Any) -> None:
    """Register the only launcher-owned tool directly on this MCP instance."""

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Current Scene Summary",
            readOnlyHint=True,
        )
    )
    def get_current_scene_summary() -> str:
        """Return a concise, bounded current-scene inventory in one read-only call."""
        response = _send_code(_SCENE_SUMMARY_TOOL_CODE, strict_json=True)
        if response.get("status") != "ok":
            raise RuntimeError(str(response.get("message", "Blender call failed")))
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Blender returned an invalid scene summary")
        return _format_scene_summary(result)


def _fast_mcp_with_compact_instructions(*args: Any, **kwargs: Any) -> Any:
    """Construct compact upstream FastMCP and register the one local tool."""
    kwargs["instructions"] = _COMPACT_INSTRUCTIONS
    mcp = _UPSTREAM_FAST_MCP(*args, **kwargs)
    _register_scene_summary(mcp)
    return mcp


def main() -> int:
    """Apply local low-latency extensions, then delegate CLI handling upstream."""
    _connection.send_code = _send_code
    blmcp.FastMCP = _fast_mcp_with_compact_instructions
    return blmcp.main()


if __name__ == "__main__":
    raise SystemExit(main())
