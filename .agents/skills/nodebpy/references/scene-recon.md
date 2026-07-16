# Scene Reconnaissance

Before touching an unfamiliar scene, orient yourself: what objects exist, what
modifiers and node groups they use, and what attributes are actually flowing
through the evaluated geometry.

```python
import bpy

obj = bpy.context.active_object

result = {
    "active_object": obj.name if obj else None,
    "objects": [
        {
            "name": o.name,
            "type": o.type,
            "modifiers": [
                f"{m.name} ({m.type})" + (f" -> {m.node_group.name}" if getattr(m, "node_group", None) else "")
                for m in o.modifiers
            ],
        }
        for o in bpy.context.scene.objects
    ],
    "node_groups": [ng.name for ng in bpy.data.node_groups],
}

if obj:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(depsgraph)
    try:
        mesh = ev.to_mesh()
        result["active_evaluated_attrs"] = [
            {"name": a.name, "type": a.data_type, "domain": a.domain} for a in mesh.attributes
        ]
        result["point_count"] = len(mesh.vertices)
        ev.to_mesh_clear()
    except Exception as e:
        result["active_evaluated_attrs"] = f"error: {e}"
```

## Gotcha: `to_mesh()` only shows *realized* geometry

`evaluated_get().to_mesh()` gives you the final, realized mesh output of the
modifier stack. Attributes that live on **instancer points** — geometry still in
instance form, not yet realized (e.g. via `RealizeInstances`) — will not appear
in this attribute list, even though they are very much present and readable.

Concretely: if a Geometry Nodes tree stores a `speed_factor` attribute on points
and then feeds them into `InstanceOnPoints` (instead of realizing them), that
attribute won't show up in `to_mesh().attributes` — but a shader `Attribute` node
with `attribute_type="INSTANCER"` reads it just fine at render/viewport time. Do
not read an absent attribute here as "the store failed"; check whether the
geometry is instanced rather than realized before concluding something is
broken. See [attribute-driven-color.md](attribute-driven-color.md) for the
pattern this shows up in.

To inspect attributes on the pre-realized point cloud directly (rather than via
`to_mesh()`), walk the node group's outputs on that branch instead, or
temporarily add a `RealizeInstances` node and re-export/re-evaluate.
