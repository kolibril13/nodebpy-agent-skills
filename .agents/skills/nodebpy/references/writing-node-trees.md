# Writing Node Trees

```python
from nodebpy import geometry as g
```

## Adding Nodes

Adding nodes must be done inside of a context. We enter a context using the `with` keyword.
While inside of this context, whenever you call a node class (`g.SetPosition()`) a node of that type will be added to the current tree.

This first example creates a new tree and adds two new nodes, linking the `Set Position` node into the `Transform Geometry` node. The output and input sockets for each are inferred based on simple heuristics around socket type and order.

```python
with g.tree("NewTree") as tree:
    g.SetPosition() >> g.TransformGeometry()

tree
```

These nodes can be saved as variables for re-use later in the node tree as well. After instantiating a class you can specify the input and output sockets using the `i_*` and `o_*` properties on the class.

These two approaches are equivalent:

## Individual Socket Access

```python
with g.tree("AnotherTree") as tree:
    pos = g.SetPosition()

    g.Position() * 0.5 >> pos.i.position
    g.Vector() >> pos.i.offset
```

## Using Arguments to Class

```python
with g.tree("AnotherAnotherTree") as tree:
    g.SetPosition(
        offset = g.Vector(),
        position = g.Position() * 0.5
    )
```

## Node Input Sockets

The socket interface nodes define what values / sockets are available as inputs for the node tree.

We define them with the typed methods on `tree.inputs` and `tree.outputs`
(`tree.inputs.geometry("Geometry")`, `tree.inputs.integer("Count", 10)`,
`tree.outputs.geometry()`), keeping the returned socket in a variable to link to.

```python
with g.tree("NewTree") as tree:
    geom_inputs = [tree.inputs.geometry(f"Geometry_{i}") for i in range(5)]
    g.JoinGeometry(geom_inputs) >> tree.outputs.geometry("The Output Socket")

tree
```

```python
with g.tree() as tree:
    (
        tree.inputs.integer("Count", 10)
        >> g.Points(position=g.RandomValue.vector(min=(-0.1,-0.1,-0.2)))
        >> tree.outputs.geometry()
    )

tree
```

```python
with g.tree() as tree:
    count = tree.inputs.integer("Count", 10)
    pos = g.RandomValue.vector() * 0.5 * g.Position()
    g.Points(count, pos) >> tree.outputs.geometry()

tree
```

## Zones

Zones are initialized with their constructors — `RepeatZone()`, `SimulationZone()`,
`ForEachGeometryElementZone()`, `ClosureZone()`. The repeat zone takes a repeat count,
which can also be linked to from elsewhere.

We can access the input and output nodes with `zone.input` and `zone.output`. The repeat
zone has the `zone.iteration` which is the iteration number of the current zone.
Simulation zone has the `zone.delta_time` which is the time between previous and current
simulation loop.

### Zone items

A zone's state is declared through its `items` collection, with one typed method per
socket type. Each method takes **the value first, then an optional name**
(`zone.items.geometry(g.Cube(), "Geometry")`); omit the value to declare an unlinked
item, and use `items.new(value, name, type="FLOAT")` to pick the type at runtime.
`len(items)`, iteration, `items[0]` and `items["Name"]` all work.

Each method returns an `Item` handle exposing the four sockets of the zone pair:

| Code | Socket |
| --- | --- |
 |`item.initial`| fed into the zone, before it runs |
 |`item.current`| the value read inside the zone |
 |`item.next`| the value written inside the zone |
 |`item.result`| the value after the zone has run |

A handle also stands in for its sockets in a chain: on the left of `>>` it is the output
side, on the right the input side.

```python
with g.tree() as tree:
    zone = g.RepeatZone(10)
    random_pos = g.RandomValue.vector(seed=zone.iteration)
    geo = zone.items.geometry(name="Geometry")
    g.JoinGeometry([geo.current, g.Points(10, random_pos)]) >> geo.next
    geo.result >> tree.outputs.geometry()

tree
```

```python
with g.tree() as tree:
    # each item carries its initial value, and is named after it when no name is given
    sim = g.SimulationZone()
    value = sim.items.float(g.Value(), "Value")
    vector = sim.items.vector((0.0, 0.0, 0.0), "Vector")

    value.current + 10 >> value.next
    vector.current + (0.2, 0.4, 0.6) >> vector.next

    g.Points(10) >> tree.outputs.geometry()

tree
```

The constructors also take the items up front, which is handy when every item has an
initial value: `g.RepeatZone(10, {"Geometry": g.Cube()})`, then `zone.items["Geometry"]`.
