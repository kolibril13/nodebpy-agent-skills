---
name: nodebpy
description: Build Blender node trees (geometry nodes, shader nodes, compositor) programmatically with the nodebpy Python library, executed live in Blender via the Blender MCP. Use when the user wants to create or modify Blender node setups, geometry nodes, shaders, or compositor trees from code.
---

# nodebpy — Blender node trees from Python

All node-tree work goes through [nodebpy](https://bradyajohnston.github.io/nodebpy/),
executed live in Blender via the Blender MCP code-execution tool. Never wire nodes
with raw `bpy` links — `nodebpy` owns tree *construction and linking*.

Property edits on existing nodes are a different concern and raw `bpy` is fine for
them — e.g. renaming a shader `Attribute` node's `attribute_name`, or restyling a
`ColorRamp`'s stops. This matters especially for shader/material trees, since the
skill's `from nodebpy import geometry as g` surface targets geometry-node trees;
retuning an existing shader node's properties directly is simpler than modeling
the whole material in nodebpy.

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

1. **Nodes to code first.** Assume the node tree is already open and on screen for
   the currently selected object. Export it to nodebpy code before touching it:

   ```python
   import bpy
   from nodebpy.export import to_python

   obj = bpy.context.active_object
   tree = obj.modifiers.active.node_group  # or the tree open in the editor
   print(to_python(tree))
   ```

   This is now the tree you are working on. Read the generated code to understand
   the existing structure. If a node has no `nodebpy` emitter, `to_python()` raises
   by default — pass `strict=False` to instead emit a placeholder and keep going,
   and grep the result for `TODO: unsupported` before trusting the round-trip:

   ```python
   code = to_python(tree, strict=False)
   assert "TODO: unsupported" not in code, "unsupported node(s) — check manually"
   ```

   Also check `tree.animation_data` before deciding to rebuild: keyframes on
   node defaults (e.g. an animated Mix factor) live on the tree datablock and are
   destroyed by a rebuild. If fcurves exist, don't rebuild — graft the change
   into the existing tree instead.

2. **Edit as code.** Modify the generated nodebpy code and re-run it to rebuild the
   tree. Running the code creates a *new* node group — repoint the modifier to it
   and remove the stale one (or delete the old group first to free the name).

3. **New trees when needed.** Add separate node groups with `with g.tree("Name"):`
   when logic is reusable; they nest into other trees like any node.

4. **Never render or screenshot to verify work.** Building and wiring the tree is
   the deliverable; rendering is slow and not needed to confirm correctness.
   Verify instead by re-exporting with `to_python()`, or by inspecting
   `tree.tree.nodes` / `.links` / socket `default_value`s directly. Only render or
   take a screenshot if the user explicitly asks to see an image.

Gotchas:

- `with g.tree(...) as tree` yields a `TreeBuilder`, not the underlying
  `bpy.types.NodeTree`. Anything that needs a real ID datablock — assigning to a
  modifier, `bpy.data.node_groups` lookups — needs the unwrapped tree:
  `modifier.node_group = tree` raises `TypeError: expected a NodeTree type, not
  TreeBuilder`; use `modifier.node_group = tree.tree` instead.
- `g.tree()` takes no `fake_user` kwarg. `tree.fake_user = True` on the *builder*
  works. If you've already unwrapped via `tree.tree`, that's a plain bpy ID and
  needs its real property name instead: `tree.tree.use_fake_user = True`
  (`.fake_user` doesn't exist on it and raises `AttributeError`).
- Interface sockets are created once via `tree.inputs.*` / `tree.outputs.*`; keep a
  variable to link to them (`tree.outputs` is not subscriptable).

## Special quirks

- **Rebuilding trees that contain a `CustomGeometryGroup`:** instantiating the
  class (e.g. `SafeArrow(...)`) inside a `TreeBuilder` does *not* rebuild the
  nested group if a node group with that `_name` already exists in
  `bpy.data.node_groups` — it silently reuses the stale one, so edits to
  `_build_group` appear to have no effect.

  This reuse is a **feature, not a hazard** when the nested group is unchanged:
  leaving it in place preserves any external references to it and avoids
  re-verifying groups you didn't touch. The hazard is only when you *edited* a
  class and forget to delete its cached group. So delete narrowly — only the
  outer tree, plus only the nested groups whose `_build_group` actually changed:

  ```python
  for ng in list(bpy.data.node_groups):
      if ng.name in ("Geometry Nodes", "Safe Arrow"):  # outer tree + only the edited nested group(s)
          bpy.data.node_groups.remove(ng)
  ```

  Detach the modifier first (`mod.node_group = None`) so removal is safe, rebuild,
  then repoint the modifier to the new group. Verify the edit actually landed by
  re-exporting with `to_python()` — don't trust that the rebuild picked up the new
  class definition.
- **Grafting nodes into an existing tree:** place the new node between the two
  nodes it links to (midpoint of upstream and downstream partner). Compute this
  in absolute coords: nodes inside a node frame store `.location` relative to that frame — and frames nest — so sum `.location` up the `.parent` chain first.

- `nodebpy` has no `__version__` attribute — don't report it in status dicts.
- **Setting a Geometry Nodes modifier's input values from Python** (e.g. to drive
  test values into a tree without rendering): the classic `mod["Socket_0"] = value`
  raises `TypeError: id properties not supported for this type` on recent Blender
  (5.x). Inputs live under `mod.properties.inputs`, and each socket is a wrapper —
  read/write through `.value`:

  ```python
  inputs = mod.properties.inputs
  inputs.Socket_0.value = (0.0, 0.0, 0.0)   # vector socket
  inputs.Socket_2.value = 0.05              # float socket
  ```

  Get the `Socket_N` identifier for a given input name from
  `tree.interface.items_tree` (match on `.name`, read `.identifier`) — don't assume
  numbering matches declaration order.

- `render_viewport_to_path`'s `output_path` argument is not authoritative — Blender
  may write the file to its own temp location and return the real path in the
  result. Only relevant if a render is explicitly requested (see Workflow step 4);
  read the returned `filepath`, not the one passed in.
- **Rebuilding a tree that contains a `SimulationZone` orphans the sim cache.**
  Rebuilding always creates a new tree datablock, even if it has the same name as
  the old one — the simulation cache is tied to the old datablock, so playback
  will re-simulate from the scene's start frame on the next frame change. This is
  expected, not a bug; just don't be surprised the timeline "resets."
- **Modifier input values don't survive a rebuild** unless you carry them over
  manually. If the modifier has exposed inputs (`mod.properties.inputs`), read
  them before detaching and reapply them after repointing to the new tree:

  ```python
  before = {k: v.value for k, v in mod.properties.inputs.items()}
  mod.node_group = None
  # ...rebuild...
  mod.node_group = tree.tree
  for k, v in before.items():
      mod.properties.inputs[k].value = v
  ```

## References

- [references/writing-node-trees.md](references/writing-node-trees.md) — core structure: tree contexts, adding/linking nodes, interface sockets, zones
- [references/node-api.md](references/node-api.md) — socket access (`i`/`o`, slicing, `.x/.y/.z`), enum options, convenience class methods
- [references/operators.md](references/operators.md) — Python operators (`+ * ** % // > & | ~ @ >>`) and the nodes they create
- [references/nodes-to-code.md](references/nodes-to-code.md) — `to_python()` export: options, round-tripping, zones, frames
- [references/custom-node-groups.md](references/custom-node-groups.md) — reusable `CustomGeometryGroup` classes
- [references/scene-recon.md](references/scene-recon.md) — orienting in an unfamiliar scene: objects, modifiers, node groups, evaluated attributes
- [references/attribute-driven-color.md](references/attribute-driven-color.md) — pattern for coloring instanced geometry (e.g. particles) by a stored attribute
