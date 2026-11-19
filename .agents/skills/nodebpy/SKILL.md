---
name: nodebpy
description: Build Blender node trees (geometry nodes, shader nodes, compositor) programmatically with the nodebpy Python library, executed via the Blender MCP. Use when the user wants to create or modify Blender node setups, geometry nodes, shaders, or compositor trees. Do not use for generic scene inspection or scene summaries; call the configured scene-summary MCP tool directly.
---

# nodebpy — Blender node trees from Python

All node-tree work goes through [nodebpy](https://bradyajohnston.github.io/nodebpy/) via the Blender MCP.

## Runtime and repository scope

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
- **Keep node auto-arrange on.** `TreeBuilder`/`g.tree(...)` default to
  `arrange="sugiyama"`, so a plain `with g.tree("Name") as tree:` auto-lays-out
  the tree on exit — rely on that default and do **not** pass `arrange=None`.
  `arrange=None` disables auto-layout and is only correct when you also supply an
  explicit `tree.node_positions = {...}` map (as the nodes-to-code export does to
  round-trip exact positions). For newly authored trees, never turn arranging off.

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

2. **Edit as code.** Modify the generated nodebpy code and re-run it with
   `clear=True` to rebuild the tree in place:

   ```python
   with g.tree("Existing Name", clear=True) as tree:
       ...
   ```

   `clear=True` empties and refills the *same* datablock, so the modifier stays
   attached, its exposed input values survive, keyframes on node defaults keep
   working, and no `.001` duplicate is left behind. `to_python(..., in_place=True)`
   generates code that rebuilds this way.

   Without `clear=True` a re-run creates a *new* node group — then you have to
   repoint the modifier to it and remove the stale one yourself.

   Keyframes on node defaults live on the tree datablock and their paths go
   through node names (`nodes["Set Position"].inputs[3].default_value`), so they
   survive a `clear=True` rebuild but break if the rebuild renames that node or
   reorders its sockets. To read them first: Blender 5 uses slotted actions, so
   walk `action.layers[*].strips[*].channelbags[*].fcurves` — `action.fcurves` no
   longer exists.

3. **New trees when needed.** Add separate node groups with `with g.tree("Name"):`
   when logic is reusable; they nest into other trees like any node.


Note:

- `with g.tree(...) as tree` yields a `TreeBuilder`, not the underlying
  `bpy.types.NodeTree`. Anything that needs a real ID datablock — assigning to a
  modifier, `bpy.data.node_groups` lookups — needs the unwrapped tree:
  `modifier.node_group = tree` raises `TypeError: expected a NodeTree type, not
  TreeBuilder`; use `modifier.node_group = tree.tree` instead.
- `g.tree()` takes a `fake_user` kwarg (`g.tree("Name", fake_user=True)`), and
  `tree.fake_user = True` on the *builder* works too. If you've already unwrapped
  via `tree.tree`, that's a plain bpy ID and needs its real property name instead:
  `tree.tree.use_fake_user = True` (`.fake_user` doesn't exist on it and raises
  `AttributeError`).
- Interface sockets are created once via `tree.inputs.*` / `tree.outputs.*`; keep a
  variable to link to them (`tree.outputs` is not subscriptable).

## Further instructions

- **The installed nodebpy ships its own skill and CLI, matched to its version.**
  When a node's arguments, enum options or socket methods are in question, look them
  up instead of guessing: `nodebpy lookup search "named attribute"`,
  `nodebpy lookup show StoreNamedAttribute` (`--tree shader` / `compositor`),
  `nodebpy lookup socket Vector` — run it in an environment that can `import bpy`
  (inside Blender: `python -m nodebpy ...`). The package also carries
  `nodebpy/skills/nodebpy/` (SKILL.md plus references on writing trees, zones and
  items, shader/compositor trees, existing trees, and verifying); read those for
  anything this skill does not cover, since they ship with the library itself.
- If `import nodebpy` fails in Blender, run:
```python
import sys, subprocess
subprocess.check_call([sys.executable, "-m", "pip", "install", "nodebpy"])
```

- **Rebuilding `CustomGeometryGroup` trees:** existing nested groups with the same
  `_name` are reused, so a changed `_build_group` is not picked up by a plain
  re-run. Rebuild the outer tree with `clear=True` and delete only the nested
  groups whose `_build_group` changed, then re-export to verify. Keep unchanged
  nested groups intact. In a live Blender session, `nodebpy.live.run_source` re-runs
  a script that defines group classes and does this bookkeeping for you.
- **Grafting nodes into an existing tree:** place the new node between the two
  nodes it links to (midpoint of upstream and downstream partner). Compute this
  in absolute coords: nodes inside a node frame store `.location` relative to that frame — and frames nest — so sum `.location` up the `.parent` chain first.

- **Setting a Geometry Nodes modifier's input values from Python** (e.g. to drive
  test values into a tree without rendering): the classic `mod["Socket_0"] = value`
  raises `TypeError: id properties not supported for this type` on recent Blender
  (5.x). Inputs live under `mod.properties.inputs`, reached by **attribute access**,
  and each socket is a wrapper — read/write through `.value`:

  ```python
  inputs = mod.properties.inputs
  inputs.Socket_0.value = (0.0, 0.0, 0.0)   # vector socket
  inputs.Socket_2.value = 0.05              # float socket
  ```

  Only attribute access gives you that wrapper. `inputs["Socket_2"]` and
  `inputs.items()` hand back a raw `IDPropertyGroup` and `.value` on it raises
  `AttributeError: 'IDPropertyGroup' object has no attribute 'value'`; go through
  `getattr(inputs, key)` when the identifier is in a variable. Link-only sockets
  (Geometry above all) have *no* `.value` at all, so `hasattr(socket, "value")` is
  the test before reading or writing one.

  `inputs.keys()` lists the identifiers of the exposed inputs. To go the other way,
  from a name to its `Socket_N`, read `tree.interface.items_tree` (match on `.name`,
  filter `i.item_type == "SOCKET" and i.in_out == "INPUT"`, take `.identifier`) —
  don't assume numbering matches declaration order: inputs and outputs draw from the
  same counter, and a rebuild renumbers all of them.

- `render_viewport_to_path`'s `output_path` argument is not authoritative — Blender
  may write the file to its own temp location and return the real path in the
  result. Only relevant if a render is explicitly requested; read the returned
  `filepath`, not the one passed in.
- **Rebuilding a tree that contains a `SimulationZone` without `clear=True`
  orphans the sim cache.** A rebuild that creates a new tree datablock leaves the
  simulation cache behind on the old one, so playback re-simulates from the
  scene's start frame on the next frame change. This is expected, not a bug; just
  don't be surprised the timeline "resets." Rebuilding with `clear=True` keeps the
  datablock the modifier and the cache are tied to.
- **Modifier input values survive a `clear=True` rebuild** (floats, vectors and the
  rest), because the datablock is reused — nothing to carry over. If you do rebuild
  into a *new* tree, carry them over by socket **name**, since the `Socket_N`
  identifiers are reassigned:

  ```python
  def modifier_values(mod):
      """{socket name: value} for every exposed input that carries a value."""
      inputs = mod.properties.inputs
      names = {i.identifier: i.name for i in mod.node_group.interface.items_tree
               if i.item_type == "SOCKET" and i.in_out == "INPUT"}
      out = {}
      for key in inputs.keys():
          socket = getattr(inputs, key, None)
          if hasattr(socket, "value"):
              value = socket.value
              out[names[key]] = tuple(value) if hasattr(value, "__len__") else value
      return out

  def restore_modifier_values(mod, values):
      inputs = mod.properties.inputs
      idents = {i.name: i.identifier for i in mod.node_group.interface.items_tree
                if i.item_type == "SOCKET" and i.in_out == "INPUT"}
      for name, value in values.items():
          socket = getattr(inputs, idents.get(name, ""), None)
          if hasattr(socket, "value"):
              socket.value = value

  before = modifier_values(mod)
  mod.node_group = None
  # ...rebuild...
  mod.node_group = tree.tree
  restore_modifier_values(mod, before)
  ```

  Read vector values out as plain tuples as above: handing the live array proxy back
  to `socket.value` raises `TypeError: bpy_struct: item.attr = val`.

## References

- [references/writing-node-trees.md](references/writing-node-trees.md) — core structure: tree contexts, adding/linking nodes, interface sockets, zones
- [references/node-api.md](references/node-api.md) — socket access (`i`/`o`, slicing, `.x/.y/.z`), enum options, convenience class methods
- [references/operators.md](references/operators.md) — Python operators (`+ * ** % // > & | ~ @ >>`) and the nodes they create
- [references/nodes-to-code.md](references/nodes-to-code.md) — `to_python()` export: options, round-tripping, zones, frames
- [references/newer-node-apis.md](references/newer-node-apis.md) — Blender 5.x additions: bundles, closures, lists/grids, menu sockets and switches, `.props()`, `muted()`, `to_mermaid()`
- [references/custom-node-groups.md](references/custom-node-groups.md) — reusable `CustomGeometryGroup` classes
- [references/scene-recon.md](references/scene-recon.md) — orienting in an unfamiliar scene: objects, modifiers, node groups, evaluated attributes
- [references/attribute-driven-color.md](references/attribute-driven-color.md) — pattern for coloring instanced geometry (e.g. particles) by a stored attribute
