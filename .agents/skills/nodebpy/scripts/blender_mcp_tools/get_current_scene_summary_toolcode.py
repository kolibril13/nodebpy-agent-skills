# SPDX-FileCopyrightText: 2026 Blender MCP Fast Server contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Blender-side code for a deterministic, bounded current-scene summary."""

__all__ = ("Result", "main")

from typing import Any, Iterable, NamedTuple


_MAX_OBJECTS = 100
_MAX_COLLECTIONS = 100
_MAX_NODE_GROUPS = 100
_MAX_SCENES = 64
_MAX_SELECTED = 100
_MAX_COLLECTION_OBJECTS = 100
_MAX_OBJECT_COLLECTIONS = 32
_MAX_MATERIALS = 32
_MAX_MODIFIERS = 32


class Result(NamedTuple):
    status: str
    file: dict[str, Any]
    scene: dict[str, Any]
    render: dict[str, Any]
    active_object: str | None
    selected_objects: list[str]
    selected_objects_omitted: int
    object_count: int
    object_type_counts: dict[str, int]
    objects_omitted: int
    objects: list[dict[str, Any]]
    collection_count: int
    collections_omitted: int
    collections: list[dict[str, Any]]
    node_group_count: int
    node_groups_omitted: int
    node_groups: list[str]


def _name_key(value: str) -> tuple[str, str]:
    return (value.casefold(), value)


def _bounded_names(values: Iterable[str], limit: int) -> tuple[list[str], int]:
    names = sorted(set(values), key=_name_key)
    return names[:limit], max(0, len(names) - limit)


def _float(value: Any) -> float:
    rounded = round(float(value), 6)
    return 0.0 if rounded == 0.0 else rounded


def _vector(value: Iterable[Any]) -> list[float]:
    return [_float(item) for item in value]


def _rotation(obj: Any) -> list[float]:
    if obj.rotation_mode == "QUATERNION":
        return _vector(obj.rotation_quaternion)
    if obj.rotation_mode == "AXIS_ANGLE":
        return _vector(obj.rotation_axis_angle)
    return _vector(obj.rotation_euler)


def _materials(obj: Any) -> tuple[list[str], int]:
    names = {
        slot.material.name
        for slot in obj.material_slots
        if slot.material is not None
    }
    return _bounded_names(names, _MAX_MATERIALS)


def _modifiers(obj: Any) -> tuple[list[dict[str, str]], int]:
    # Modifier order is semantically significant, so preserve stack order.
    modifiers = [
        {"name": modifier.name, "type": modifier.type}
        for modifier in obj.modifiers
    ]
    return modifiers[:_MAX_MODIFIERS], max(0, len(modifiers) - _MAX_MODIFIERS)


def _object_info(obj: Any, selected_names: set[str]) -> dict[str, Any]:
    collection_names, collections_omitted = _bounded_names(
        (collection.name for collection in obj.users_collection),
        _MAX_OBJECT_COLLECTIONS,
    )
    materials, materials_omitted = _materials(obj)
    modifiers, modifiers_omitted = _modifiers(obj)
    result: dict[str, Any] = {
        "name": obj.name,
        "type": obj.type,
        "data": obj.data.name if obj.data is not None else None,
        "parent": obj.parent.name if obj.parent is not None else None,
        "selected": obj.name in selected_names,
        "collections": collection_names,
        "transform": {
            "local_location": _vector(obj.location),
            "rotation_mode": obj.rotation_mode,
            "local_rotation": _rotation(obj),
            "local_scale": _vector(obj.scale),
            "world_location": _vector(obj.matrix_world.translation),
            "world_dimensions": _vector(obj.dimensions),
        },
        "materials": materials,
        "modifiers": modifiers,
    }
    if collections_omitted:
        result["collections_omitted"] = collections_omitted
    if materials_omitted:
        result["materials_omitted"] = materials_omitted
    if modifiers_omitted:
        result["modifiers_omitted"] = modifiers_omitted
    return result


def _scene_collections(root: Any) -> tuple[list[Any], dict[str, set[str]]]:
    found: dict[str, Any] = {}
    parent_names: dict[str, set[str]] = {}
    pending = [root]

    while pending:
        collection = pending.pop()
        if collection.name in found:
            continue
        found[collection.name] = collection
        children = sorted(collection.children, key=lambda item: _name_key(item.name))
        for child in children:
            parent_names.setdefault(child.name, set()).add(collection.name)
        pending.extend(reversed(children))

    return sorted(found.values(), key=lambda item: _name_key(item.name)), parent_names


def _collection_info(collection: Any, parent_names: dict[str, set[str]]) -> dict[str, Any]:
    objects, objects_omitted = _bounded_names(
        (obj.name for obj in collection.objects),
        _MAX_COLLECTION_OBJECTS,
    )
    children, children_omitted = _bounded_names(
        (child.name for child in collection.children),
        _MAX_COLLECTIONS,
    )
    parents, parents_omitted = _bounded_names(
        parent_names.get(collection.name, set()),
        _MAX_COLLECTIONS,
    )
    result: dict[str, Any] = {
        "name": collection.name,
        "parents": parents,
        "children": children,
        "objects": objects,
    }
    if parents_omitted:
        result["parents_omitted"] = parents_omitted
    if children_omitted:
        result["children_omitted"] = children_omitted
    if objects_omitted:
        result["objects_omitted"] = objects_omitted
    return result


def main(params: None) -> Result:
    del params
    import bpy  # pylint: disable=import-error,no-name-in-module,import-outside-toplevel

    context = bpy.context
    data = bpy.data
    scene = context.scene
    view_layer = context.view_layer

    all_selected_names = [obj.name for obj in context.selected_objects]
    selected_names, selected_omitted = _bounded_names(
        all_selected_names,
        _MAX_SELECTED,
    )
    selected_name_set = set(all_selected_names)

    all_objects = sorted(scene.objects, key=lambda item: _name_key(item.name))
    object_type_counts: dict[str, int] = {}
    for obj in all_objects:
        object_type_counts[obj.type] = object_type_counts.get(obj.type, 0) + 1
    object_type_counts = {
        object_type: object_type_counts[object_type]
        for object_type in sorted(object_type_counts, key=_name_key)
    }
    objects = [
        _object_info(obj, selected_name_set)
        for obj in all_objects[:_MAX_OBJECTS]
    ]

    all_collections, parent_names = _scene_collections(scene.collection)
    collections = [
        _collection_info(collection, parent_names)
        for collection in all_collections[:_MAX_COLLECTIONS]
    ]

    active = view_layer.objects.active
    render = scene.render
    scene_names, scenes_omitted = _bounded_names(
        (item.name for item in data.scenes),
        _MAX_SCENES,
    )
    file_info: dict[str, Any] = {
        "path": data.filepath,
        "saved": data.is_saved,
        "dirty": data.is_dirty,
        "scenes": scene_names,
    }
    if scenes_omitted:
        file_info["scenes_omitted"] = scenes_omitted

    node_group_names, node_groups_omitted = _bounded_names(
        (item.name for item in data.node_groups),
        _MAX_NODE_GROUPS,
    )
    window = getattr(context, "window", None)

    return Result(
        status="ok",
        file=file_info,
        scene={
            "name": scene.name,
            "frame": scene.frame_current,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "camera": scene.camera.name if scene.camera is not None else None,
            "world": scene.world.name if scene.world is not None else None,
            "active_workspace": window.workspace.name if window is not None else None,
            "mode": context.mode,
        },
        render={
            "engine": render.engine,
            "resolution": [
                render.resolution_x,
                render.resolution_y,
                render.resolution_percentage,
            ],
            "fps": render.fps,
            "fps_base": _float(render.fps_base),
        },
        active_object=active.name if active is not None else None,
        selected_objects=selected_names,
        selected_objects_omitted=selected_omitted,
        object_count=len(all_objects),
        object_type_counts=object_type_counts,
        objects_omitted=max(0, len(all_objects) - _MAX_OBJECTS),
        objects=objects,
        collection_count=len(all_collections),
        collections_omitted=max(0, len(all_collections) - _MAX_COLLECTIONS),
        collections=collections,
        node_group_count=len(data.node_groups),
        node_groups_omitted=node_groups_omitted,
        node_groups=node_group_names,
    )
