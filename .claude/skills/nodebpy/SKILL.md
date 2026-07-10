---
name: nodebpy
description: Build Blender node trees (geometry nodes, shader nodes, compositor) programmatically with the nodebpy Python library, executed live in Blender via the Blender MCP. Use when the user wants to create or modify Blender node setups, geometry nodes, shaders, or compositor trees from code.
---

# nodebpy — Blender node trees from Python

All node-tree work goes through [nodebpy](https://bradyajohnston.github.io/nodebpy/),
executed live in Blender via the Blender MCP code-execution tool. Never wire nodes
with raw `bpy` links.

## Setup

Ensure nodebpy is importable in Blender's Python (install if missing):

```python
import sys, subprocess
try:
    import nodebpy
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "nodebpy"])
```

## Workflow

1. **Nodes to code first.** When a Geometry Nodes tab is active, export the active
   node tree of the currently selected object to nodebpy code before touching it:

   ```python
   import bpy
   from nodebpy.export import to_python

   obj = bpy.context.active_object
   tree = obj.modifiers.active.node_group  # or the tree open in the editor
   print(to_python(tree))
   ```

   This is now the tree you are working on. Read the generated code to understand
   the existing structure.

2. **Edit as code.** Modify the generated nodebpy code and re-run it to rebuild the
   tree. Running the code creates a *new* node group — repoint the modifier to it
   and remove the stale one (or delete the old group first to free the name).

3. **New trees when needed.** Add separate node groups with `with g.tree("Name"):`
   when logic is reusable; they nest into other trees like any node.

Gotchas:

- Capture the selected/active object *before* switching workspace tabs — switching
  tabs can change the active object.
- `g.tree()` takes no `fake_user` kwarg; set `tree.fake_user = True` afterwards.
- Interface sockets are created once via `tree.inputs.*` / `tree.outputs.*`; keep a
  variable to link to them (`tree.outputs` is not subscriptable).

## Special quirks

- **Rebuilding trees that contain a `CustomGeometryGroup`:** instantiating the
  class (e.g. `SafeArrow(...)`) inside a `TreeBuilder` does *not* rebuild the
  nested group if a node group with that `_name` already exists in
  `bpy.data.node_groups` — it silently reuses the stale one, so edits to
  `_build_group` appear to have no effect. Before re-running edited code, delete
  **both** the outer tree **and** every nested custom group it uses:

  ```python
  for ng in list(bpy.data.node_groups):
      if ng.name.startswith(("Safe Arrow", "Geometry Nodes.001")):
          bpy.data.node_groups.remove(ng)
  ```

  Detach the modifier first (`mod.node_group = None`) so removal is safe, rebuild,
  then repoint the modifier to the new group. Verify the edit actually landed by
  re-exporting with `to_python()` or taking a viewport screenshot — don't trust
  that the rebuild picked up the new class definition.
- `nodebpy` has no `__version__` attribute — don't report it in status dicts.

## References

- [references/writing-node-trees.md](references/writing-node-trees.md) — core structure: tree contexts, adding/linking nodes, interface sockets, zones
- [references/node-api.md](references/node-api.md) — socket access (`i`/`o`, slicing, `.x/.y/.z`), enum options, convenience class methods
- [references/operators.md](references/operators.md) — Python operators (`+ * ** % // > & | ~ @ >>`) and the nodes they create
- [references/nodes-to-code.md](references/nodes-to-code.md) — `to_python()` export: options, round-tripping, zones, frames
- [references/custom-node-groups.md](references/custom-node-groups.md) — reusable `CustomGeometryGroup` classes
