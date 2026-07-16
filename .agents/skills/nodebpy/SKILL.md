---
name: nodebpy
description: Build Blender node trees (geometry nodes, shader nodes, compositor) programmatically with the nodebpy Python library, executed via the Blender MCP. Use when the user wants to create or modify Blender node setups, geometry nodes, shaders, or compositor trees. Do not use for generic scene inspection or scene summaries; call the configured scene-summary MCP tool directly.
---

# nodebpy — Blender node trees from Python

All node-tree work goes through [nodebpy](https://bradyajohnston.github.io/nodebpy/) via the Blender MCP.

## Runtime and repository scope

Work against the connected Blender session, not this repository. Call Blender
MCP directly and serially, never from subagents. On failure, report the MCP
error without probing, searching, retrying, or changing transports. Never retry
an ambiguous mutation or use `*_for_cli` with interactive Blender.

Read only the task-relevant skill references after the active tree is known.
In particular, do not open or analyze `sync_skills.py`, generated symlinks,
plugin metadata, Git history, or README files unless the user explicitly asks
about skill packaging or repository maintenance. Those files do not affect the
node tree in Blender.

For repository reading, treat the task's named files and the selected skill's
direct references as the allowlist. Everything else is out of scope by
default. A project-level `AGENTS.md` can narrow this allowlist further; it
cannot replace the Blender MCP workflow below.

Never wire nodes with raw `bpy` links — `nodebpy` owns tree *construction and linking*.

Property edits on existing nodes with raw `bpy` is fine e.g.
- renaming a shader `Attribute` node's `attribute_name`
- restyling a `ColorRamp`'s stops. 

## Node-group conventions

- **Prefer reusable node groups.** When the logic can be reused or has more
  than a trivial number of nodes, encapsulate it in a node group and expose
  only the useful controls through group inputs.
- **Give exposed inputs reasonable defaults.** Choose useful values, ranges,
  and labels so the group works immediately after insertion. Keep defaults
  close to the nodebpy interface declaration, for example:

  ```python
  scale = tree.inputs.float("Scale", 6.0, min_value=0.1, max_value=50.0)
  color = tree.inputs.color("Color", (1.0, 0.0, 0.0, 1.0))
  ```

- **Hide node option buttons by default.** After constructing a tree, hide the
  option-button strip unless the user explicitly asks to show it:

  ```python
  for node in tree.tree.nodes:
      node.show_options = False
  ```

  This is a display property on the Blender nodes; using raw `bpy` for this
  property edit is allowed. Apply it to the parent material/geometry tree as
  well as to newly created group nodes when appropriate.
- **Set the node-group color tag to match the group’s purpose.** Do not leave
  it at `NONE`: use `SHADER` for shader groups, `GEOMETRY` for geometry groups,
  `TEXTURE` for texture-oriented groups, `VECTOR` for vector utilities, and
  the closest matching tag for other specialized groups. Set it on the real
  node tree after construction, e.g. `tree.tree.color_tag = "SHADER"`.

## Workflow

Minimize Blender MCP latency 
- use one call to read/export the active tree and one call to edit it.
- No verification of the edit result. 
- Extra calls only after an error or when the initial read leaves the requested change ambiguous.

Do not add exploratory shell calls between MCP calls. Most observed latency
variance comes from MCP/session startup and Blender-side execution, not from
nodebpy tree construction.

1. **Nodes to code first.** Assume the node tree is already open and on screen for
   the currently selected object. Export it to nodebpy code:

   ```python
   import bpy
   from nodebpy.export import to_python

   obj = bpy.context.active_object
   tree = obj.modifiers.active.node_group  # or the tree open in the editor
   print(to_python(tree))
   ```
   Read the generated code to understand the existing structure. 

2. **Edit as code.** Modify the generated nodebpy code and re-run it to rebuild the
   tree. Running the code creates a *new* node group — repoint the modifier to it
   and remove the stale one (or delete the old group first to free the name).

   Also check `tree.animation_data` before deciding to rebuild: keyframes on
   node defaults (e.g. an animated Mix factor) live on the tree datablock and are
   destroyed by a rebuild. If fcurves exist, don't rebuild — graft the change
   into the existing tree instead.

3. **New trees when needed.** Add separate node groups with `with g.tree("Name"):`
   when logic is reusable; they nest into other trees like any node.


Note:

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

## Further instructions

- If `import nodebpy` fails in Blender, run:
```python
import sys, subprocess
subprocess.check_call([sys.executable, "-m", "pip", "install", "nodebpy"])
```

- Only render or take a screenshot if the user explicitly asks to see an image.

- **Rebuilding `CustomGeometryGroup` trees:** existing nested groups with the same
  `_name` are reused. Detach the modifier, delete the outer tree and only nested
  groups whose `_build_group` changed, then rebuild, repoint, and re-export to
  verify. Keep unchanged nested groups intact.
- **Grafting nodes into an existing tree:** place the new node between the two
  nodes it links to (midpoint of upstream and downstream partner). Compute this
  in absolute coords: nodes inside a node frame store `.location` relative to that frame — and frames nest — so sum `.location` up the `.parent` chain first.

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
