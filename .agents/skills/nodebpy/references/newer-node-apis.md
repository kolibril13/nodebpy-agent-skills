# Newer Node APIs (Blender 5.x / nodebpy 530)

Features that arrived with Blender 5 and are easy to miss: bundles, closures, lists
and grids, menu sockets and the switch family, plus the display and inspection helpers.

```python
from nodebpy import geometry as g
```

## Bundles

A bundle carries several named values down a single link, so a group can pass a whole
set of parameters through one socket. `CombineBundle` packs, `SeparateBundle` unpacks,
and both declare their contents through the `items` collection — value first, then the
name:

```python
with g.tree("BundleDemo") as tree:
    packed = g.CombineBundle()
    packed.items.float(0.5, "radius")
    packed.items.vector((0.0, 0.0, 1.0), "axis")

    unpacked = g.SeparateBundle(packed)
    radius = unpacked.items.float("radius")
    axis = unpacked.items.vector("axis")

    _ = (
        g.Cube()
        >> g.SetPosition(offset=axis.output * radius.output)
        >> tree.outputs.geometry("Geometry")
    )

tree
```

On the unpacking side the item takes only a name, and `item.output` is the value read
out of it. A bundle socket also has `.store(path, value)` and `.get.<type>(name)` for
adding to or reading from an existing bundle:

```python
with g.tree("BundleStore") as tree:
    packed = g.CombineBundle()
    packed.items.float(0.5, "radius")

    bundle = packed.o.bundle.store("thickness", 0.25)
    thickness = bundle.get.float("thickness")

    _ = (
        g.Cube()
        >> g.SetPosition(offset=g.CombineXYZ(z=thickness))
        >> tree.outputs.geometry("Geometry")
    )

tree
```

Bundles cross the group boundary like any other socket type, with
`tree.inputs.bundle(...)` / `tree.outputs.bundle(...)`.

## Closures

A closure is a piece of node graph passed as a value and evaluated somewhere else.
`ClosureZone` declares the signature with its own `inputs` / `outputs`, `zone.closure`
is the closure socket, and `EvaluateClosure` calls it:

```python
with g.tree("ClosureDemo") as tree:
    doubler = g.ClosureZone()
    x = doubler.inputs.float("x")
    (x.output * 2) >> doubler.outputs.float("y").input

    call = g.EvaluateClosure(doubler.closure)
    call.inputs.float(3.0, "x")
    y = call.outputs.float("y").output

    _ = (
        g.Cube()
        >> g.SetPosition(offset=g.CombineXYZ(z=y))
        >> tree.outputs.geometry("Geometry")
    )

tree
```

Note the sides: inside the zone you read `x.output` and write into `.input`; on the call
you feed `call.inputs.<type>(value, name)` and read `call.outputs.<type>(name).output`.

## Lists and grids

Fields can be materialised into two new structures. `FieldToList(count)` evaluates a
field into a list, `FieldToGrid` into a volume grid; both return wrapper sockets
(`VectorSocketList`, `FloatSocketGrid`, …) that carry the list and grid methods:

```python
with g.tree("ListGridDemo") as tree:
    positions = g.FieldToList(10)
    pos = positions.items.vector(g.Position(), "Pos")

    density = g.FieldToGrid.float()
    d = density.items.float(0.5, "Density")

    _ = g.Points(10) >> tree.outputs.geometry("Geometry")

tree
```

An interface socket declares the same shape with `structure_type`, which decides whether
`tree.inputs.*` hands back a plain socket or a list / grid wrapper:

```python
with g.tree("ListInterface") as tree:
    values = tree.inputs.float("Values", structure_type="LIST")
    geo = tree.inputs.geometry("Geometry")
    _ = geo >> tree.outputs.geometry("Geometry")

tree
```

## Menu sockets and the switch family

`tree.inputs.menu(name, default)` exposes a menu on the group node; its items come from
the Menu Switch it is linked to, so declare the switch's items and link it:

```python
with g.tree("MenuDemo") as tree:
    mode = tree.inputs.menu("Shape", "Cube")
    shape = g.MenuSwitch(mode, {"Cube": g.Cube(), "Sphere": (g.UVSphere(), "A tooltip")})
    _ = shape >> tree.outputs.geometry("Geometry")

tree
```

A `(value, "description")` pair gives the item a tooltip, and the first item declared is
the default. `IndexSwitch` takes a list, or a type and an iterable of values:

```python
with g.tree("IndexSwitchDemo") as tree:
    picked = g.IndexSwitch(g.Index(), [g.Cube(), g.IcoSphere(), g.Cone()])
    weights = g.IndexSwitch.float(items=range(4))
    _ = picked >> tree.outputs.geometry("Geometry")

tree
```

A plain `Switch` takes its type from its values — `g.Switch(cond, g.Cube(), g.Cone())` is
a Geometry switch, `g.Switch(cond, 1, 2)` an Integer one. Values of different types raise
`SocketError` naming each, so use a typed variant (`g.Switch.float(...)`) when the values
don't say.

## Socket methods, not node methods

`.mix` and `.switch` sit on the *value* flowing down the chain, so they need a socket —
reaching for them on a node raises `AttributeError: 'Value' object has no attribute
'mix'`. Go through `.o.<socket>` first:

```python
with g.tree("SocketMethods") as tree:
    fac = g.Value(0.7).o.value
    blended = fac.mix.float(0.0, 10.0)
    picked = (fac > 0.5).switch.float(0.0, 1.0)

    _ = (
        g.Cube()
        >> g.SetPosition(offset=g.CombineXYZ(z=blended), selection=fac > 0.5)
        >> tree.outputs.geometry("Geometry")
    )

tree
```

The bitwise operators also split by type: on booleans `& | ^ ~` build Boolean Math nodes
(see [operators.md](operators.md)), on integers they build **Bit Math** nodes.

## Display and inspection

`.props(...)` sets what every node has and returns the node or socket, so it can end a
chain:

```python
with g.tree("PropsDemo") as tree:
    geo = tree.inputs.geometry("Geometry")
    lifted = (geo >> g.SetPosition(offset=(0.0, 0.0, 1.0))).props(
        label="Lift",
        color="#FFAA00",
        width=200,
        hide_inputs=["Selection"],
        warning_propagation="ERRORS",
    )
    _ = lifted >> tree.outputs.geometry("Geometry")

tree
```

It also takes `hide=True` (collapse the node), `mute=True` and `pin_gizmo=True`.

`muted(source, value=...)` links through a **muted** link — the link stays in the tree but
passes nothing, so the input falls back to its own value (`value`, or the socket default).
That is the scripted form of Ctrl + click-dragging across a link in the editor:

```python
from nodebpy import muted

with g.tree("MutedDemo") as tree:
    geo = tree.inputs.geometry("Geometry")
    _ = (
        geo
        >> g.SetPosition(offset=muted(g.Vector((0.0, 0.0, 1.0)), value=(0.0, 0.0, 2.0)))
        >> tree.outputs.geometry("Geometry")
    )

tree
```

The link's `is_muted` flag is applied when the tree context exits, so read it after the
`with` block, not inside it.

For checking a tree you built, `tree.to_mermaid()` prints the wiring as a Mermaid graph
(nodes, links and the socket names on each link) — cheap to read and diff, and it needs
no screenshot:

```python
with g.tree("MermaidDemo") as tree:
    _ = g.Cube() >> g.SetPosition() >> tree.outputs.geometry("Geometry")

print(tree.to_mermaid())
```

`tree.to_plot("tree.png")` renders the layout instead, but it needs matplotlib
(`pip install nodebpy[plot]`), which Blender does not ship — without it it raises
`ImportError: matplotlib is required for to_plot`.
