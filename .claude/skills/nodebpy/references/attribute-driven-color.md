# Attribute-Driven Color (e.g. Coloring Particles by Speed)

A common pattern: color instanced geometry (particles, scattered objects) by
some per-point value computed in Geometry Nodes — speed, age, height, whatever.
The value has to cross from the GN modifier into the shader, which happens
through a **named attribute stored before instancing**, read back by an
`Attribute` node in the material.

## The pattern

1. **Store the attribute on the points, before instancing.** It must exist on
   the point domain *before* `InstanceOnPoints` — storing it after (on the
   realized instances) won't reach the shader the same way.

   ```python
   from nodebpy import geometry as g
   from nodebpy.builder import CustomGeometryGroup
   from nodebpy.types import InputFloat, InputGeometry

   class SpeedColor(CustomGeometryGroup):
       """Map a 'speed' attribute to a 0-1 factor for a shader color ramp."""
       _name = "Speed Color"
       _color_tag = "COLOR"

       def __init__(
           self,
           geometry: InputGeometry = ...,
           min_speed: InputFloat = 0.0,
           max_speed: InputFloat = 1.0,
       ):
           super().__init__(**{"Geometry": geometry, "Min Speed": min_speed, "Max Speed": max_speed})

       def _build_group(self, tree):
           geometry = tree.inputs.geometry("Geometry")
           min_speed = tree.inputs.float("Min Speed", 0.0)
           max_speed = tree.inputs.float("Max Speed", 1.0)

           factor = g.MapRange(g.NamedAttribute("speed"), min_speed, max_speed, 0.0, 1.0)
           (
               geometry
               >> g.StoreNamedAttribute(name="speed_factor", value=factor)
               >> tree.outputs.geometry("Geometry")
           )
   ```

   Wire it in *before* `InstanceOnPoints`:

   ```python
   colored = points >> SpeedColor(min_speed=..., max_speed=...)
   instanced = colored >> g.InstanceOnPoints(instance=g.UVSphere(...))
   ```

2. **Read it back in the material with `attribute_type="INSTANCER"`.** This is
   raw `bpy` on the existing material's shader nodes — nodebpy's `geometry`
   surface targets GN trees, not shader trees, so retuning an existing shader
   `Attribute` node is simpler done directly:

   ```python
   import bpy

   mat = bpy.data.materials["YourMaterial"]
   attr = mat.node_tree.nodes["Attribute"]   # or find by bl_idname == "ShaderNodeAttribute"
   attr.attribute_name = "speed_factor"
   attr.attribute_type = "INSTANCER"          # critical: reads from the source points, not the realized instance
   ```

3. **Drive a `ColorRamp` (or similar) from the Attribute's Factor output** —
   reuse whatever color pipeline the material already has rather than rebuilding
   it. Two-stop ramps (e.g. blue at 0 / red at 1) are enough for a min→max color
   sweep:

   ```python
   ramp = mat.node_tree.nodes["Color Ramp"].color_ramp
   elems = ramp.elements
   while len(elems) > 2:
       elems.remove(elems[1])
   elems[0].position, elems[0].color = 0.0, (0.0, 0.05, 1.0, 1.0)  # slow -> blue
   elems[1].position, elems[1].color = 1.0, (1.0, 0.02, 0.0, 1.0)  # fast -> red
   ```

## Gotchas

- The attribute must be stored **before** `InstanceOnPoints`, not after.
- `attribute_type` on the shader `Attribute` node must be `"INSTANCER"` to read
  a value stored on the source points of an instancer, as opposed to `"GEOMETRY"`
  (the realized mesh) or `"OBJECT"`.
- Verifying via `evaluated_get().to_mesh()` will show the attribute as *absent*
  even when everything is working correctly, because the mesh output only
  contains realized geometry — see
  [scene-recon.md](scene-recon.md#gotcha-to_mesh-only-shows-realized-geometry).
  Don't treat that as a failure signal for this pattern; check the shader
  result (viewport render or `attr.attribute_name`/`attribute_type` on the node)
  instead.
