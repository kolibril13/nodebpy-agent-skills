# Gaussian Integral animation — workflow notes

Blender 5.2 · Typst importer add-on · Blender MCP · 24 fps · EEVEE + Grease Pencil Line Art
File: `Gauss/idea_4.blend`

The animation derives ∫₋∞^∞ e^(−x²) dx = √π step by step. Extruded Typst glyphs sit on a
beige plate, rise in and sink out, slide into new layouts, and swap via "flip tiles"
(a piece of the plate that turns over to reveal new glyphs on its back).

---

## 1. Scene structure

| Thing | Notes |
|---|---|
| `Plane` | The plate (21.8 m box, top at z = 0, material `New`). Carries Boolean "pocket" modifiers for the flip tiles. Not in `Equation`, but still hides Line Art lines. |
| `Equation` collection | **Line Art source.** Every glyph must live here (or in a child) to get outlines. Children are named by story step (`02 …` to `12 …`). |
| `Flip Tiles` (in `Equation`) | The tile objects (Line Art usage *Include*). Cutter boxes live in `Flip Tile Cutters …` sub-collections with usage *Exclude*. |
| `LineArt` | Grease Pencil object, Line Art modifier with source = `Equation`, silhouette filtering **Contour**, radius keyed 2.5 mm → 4 mm (frames 22–40). |
| `Camera` | Single animated camera, rotation fixed at 34.86° about X; only location is animated. |

Materials: `New` for all math glyphs, `Black` (pencil material) for text headings
like "Using polar coordinates".

---

## 2. Adding a new Typst step (the routine)

1. Write the next line in Typst, import as **Mesh**, extruded (depth setting 40 mm).
   Import it *in place* where it should end up, as a **reference layout**.
2. Decide per glyph: does an existing glyph **move** there, does it **flip**, or is it **new**?
3. For glyphs that stay as reference only: record positions, then **delete** the reference
   objects + their collection.
4. For genuinely new glyphs:
   - Fix the mesh (§6): degenerate cap triangles, then **weld** (remove doubles).
   - Glyph depth must be **0 → 0.04 m** (bottom on the plate).
   - Material `New` (math) or `Black` (headings).
   - Move their collection under `Equation`.
   - Key the **intro** (§3).
5. **Force a Line Art refresh** after linking collections from a script
   (`LineArt.update_tag()` + `view_layer.update()` + frame step), otherwise new glyphs
   have no outline until the file is reopened.
6. Run the **pocket conflict scan** (§5.4) if anything waits under the plate near a tile.

---

## 3. Animation templates

All curves Bézier with **Auto Clamped** handles unless noted.

### Intro — rise out of the plate (offsets from start frame `t`)
| channel | keys |
|---|---|
| loc z | t−1: −0.06, t: −0.06, t+3: −0.0092, t+5: +0.0173, t+11: 0 |
| scale x | t: 1, t+4: 0.9993, t+7: 1.0465, t+10: 1.0022 |
| scale z | t: 1, t+5: 1.1769, t+10: 1.0022 |

Stagger: equations **2 frames** per glyph (left → right; fractions top first),
headings **1 frame** per letter. A brace opens from the centre outward.

### Sink / fade out — reverse intro
loc z: t: 0, t+3: +0.012, t+11: −0.06 · scale z: t: 1, t+3: 1.08, t+9: 1.
For glyphs attached to an upside-down tile, measure which way "down" is first (sign).

### Move — "v2" style (user favourite)
Relative to start `S`, travel vector `d`, `dur = 12 + 4·√|d|`:
| frame | position | scale (along / across travel) |
|---|---|---|
| S | p0 | 1 / 1 |
| S+3 | p0 − 0.035 d (wind-up) | 0.95 / 1.04 |
| mid | p0 + 0.5 d (+ lane offset) | 1 + 0.14 st / 1 − 0.07 st |
| S+dur | p0 + 1.02 d (overshoot) | 0.93 / 1.06 |
| S+dur+4 | p0 + 0.995 d | 1.04 / 0.98 (at +3) |
| S+dur+7 | p0 + d | 1 / 1 |

- Groups that belong together (e.g. `e^(−x²) dx`, `y²`) share **one start and one duration**.
- **Crossing paths:** left-movers arc **up** (+y lane), right-movers **dip** (−y lane);
  lanes ±0.65–1.1 m. Then run a bounding-box overlap check frame by frame and tweak
  start frames / lane sizes until zero overlaps.
- Vertical moves stretch in **y** instead of x.
- Always add a **hold key at S−1** — removing keys can leave empty curves that fall back
  to stale values.

### Camera moves
Soft start, long settle: start key right handle at +0.4·dur, end key left handle at −0.6·dur
(handles FREE, flat). After arrival optional slow creep. Frame the content by solving
camera location with the action temporarily unassigned (otherwise animation resets it).

---

## 4. Timeline (current, frames @24 fps)

| frames | beat |
|---|---|
| 1–30 | first equation rises in (I, =, ∫ e^(−x²) dx) |
| 48–79 | I says "hi" (scale), moves; = follows 2 frames later |
| 77–118 | ², brackets, second integral rise in |
| 125–162 | x→y flip (tiles 1 & 2) |
| 178–235 | rearrangement into ∫∫ e^(−(x²+y²)) dx dy |
| 243–263 | camera moves up (breathing room before and after) |
| 267–338 | "Using polar coordinates" block fades in |
| 343–452 | three flips (exponent, integrals, dx dy → r dr dθ), tightening slide |
| 453–485 | polar block fades out |
| 487–584 | "Variable substitution", u = r², du/dr → du = 2r dr |
| 605–649 | ½ and 2 inserted |
| 655–727 | −u / du flips, dθ slide, block fades out |
| 753–827 | underbrace = 1, fades out, dθ moves |
| 831–844 | = π |
| 847–871 | camera to the full "I² = … = π" view |
| 884–928 | camera to I = √π, π slides |
| 941–952 | √ in, ² out |
| 952–976 | hold 1 s on I = √π |
| 976–1002 | camera to final framing |
| 1004–1037 | I sinks, final ∫₋∞^∞ e^(−x²) dx = √π rises |
| → 1084 | end hold |

To insert breathing room: shift **all keys ≥ frame F** in every used action by N frames
(includes tile switches, pocket modifiers, delta keys, camera) and add N to `frame_end`.

---

## 5. Flip tiles

### 5.1 Build
- Tile = box mesh `2hx × 2hy × 0.05`, origin on the rotation axis at `(cx, cy, −0.025)`,
  material `New`, in `Flip Tiles`.
- Size: union of old + new glyph bounds, ~3–5 cm padding, shrink sides until no
  neighbouring glyph vertex is inside (+5 mm). Glyphs need ≥1 cm margin in **y**
  (they sweep in y–z).
- Cutter = box `hx+3mm × hy+3mm`, z from −(radius + 0.06) to +0.1, in its **own**
  collection → its **own** Boolean (Exact, Difference) modifier on `Plane`.
  ⚠ Never nest cutter collections inside another tile's operand collection
  (a collection operand includes children → pockets open at the wrong time).
- Odd shapes (e.g. a tail next to a "d"): extra strips + ring-shaped cutter that keeps
  a solid core near the axis.

### 5.2 Attach glyphs — Child Of constraints
- Old glyphs (on top): `Child Of` target = tile, `inverse = tile_rest_matrix⁻¹`.
- New glyphs (underneath): `inverse = T180⁻¹` where `T180 = translate(tile.loc) · rotX(180°)`;
  their own transform is the imported final position → upside down under the plate
  before, exact position after the flip.
- Works on top of existing parents/constraints (stack multiple Child Ofs).

### 5.3 Animate (relative to window start S)
| what | keys |
|---|---|
| scale x,y | S: 1, S+5: 0.95 (gap opens), S+25: 0.95, S+30: 1.006, S+32: 1 |
| rot x | S+5: 0°, S+9: −8°, S+19: 188°, S+22: 177°, S+25: 180° |
| hide_render | 0: True, S: False, S+33: True |
| loc z | inactive −0.026 (1 mm into plate), active −0.025 (CONSTANT) |
| shape key "Collapsed" (all verts → 0) | 1 when inactive, 0 during S…S+33 (CONSTANT) |
| pocket modifier show_render/viewport | on during S…S+33 |
| old glyphs hide_render | True from S+33 |

### 5.4 Gotchas we hit
- **Don't key `hide_viewport`** on tiles — the viewport Line Art then doesn't see them as
  occluders (render is fine). Use the 1 mm drop + collapse shape key instead.
- **Blender 5 slotted actions:** a shape key's animation lands in the **same action** as the
  object. Setting "all curves CONSTANT" also froze rotation/scale → only touch the
  `hide_render`, `location` and `key_blocks` curves.
- Tiles must be inside `Equation` (Occlusion Only or Include), otherwise Line Art never
  re-evaluates against the moving tile.
- **Pocket conflict scan:** glyphs waiting at z −0.06 (before intro / after sinking) get
  exposed when *another* tile's pocket opens over them. Scan every tile window; for each
  hit, key `delta_location.z` ±1.5 m (CONSTANT) during that window only. Re-run after
  adding any new glyphs.

---

## 6. Mesh & Line Art rules (summary)

- Import produces unwelded islands + zero-area cap triangles → per glyph:
  `dissolve_degenerate` → triangulate caps → `beautify_fill` → `remove_doubles(1e-5)`.
  ```python
  import bpy, bmesh
  def fix_glyph(o):
      me = o.data; bm = bmesh.new(); bm.from_mesh(me)
      bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
      zs = [v.co.z for v in bm.verts]
      for z in (max(zs), min(zs)):                      # top and bottom cap
          cap = [f for f in bm.faces if all(abs(v.co.z - z) < 1e-5 for v in f.verts)]
          bmesh.ops.triangulate(bm, faces=[f for f in cap if len(f.verts) > 3])
          cap = [f for f in bm.faces if all(abs(v.co.z - z) < 1e-5 for v in f.verts)]
          cs = set(cap)
          inner = [e for e in {e for f in cap for e in f.edges}
                   if len(e.link_faces) == 2 and all(lf in cs for lf in e.link_faces)]
          bmesh.ops.beautify_fill(bm, faces=cap, edges=inner)
      bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)   # weld
      bm.normal_update(); bm.to_mesh(me); bm.free(); me.update()
  ```
  Why: zero-area triangles make Intersection lines draw across caps; unwelded islands
  mean every outline edge exists twice → solid + dashed double outlines on moving glyphs.
- Faces must be **smooth-shaded** (Smooth by Angle marks the 90° edges sharp); flat-shaded
  faces make Line Art draw every triangle diagonal.
- Joining glyphs (e.g. √ hook + bar): Boolean **Union**, then rebuild from the top-face
  outline (simplify collinear points, extrude 0.04, triangulate caps, set smooth).
- Never script-edit a mesh that is open in Edit Mode — leaving Edit Mode overwrites it.
- Line Art settings: silhouette filtering **Contour** (Group caused flickering gaps),
  crease threshold 98°, depth offset 0.05 (could go to 0.01).
- Viewport overlay "Relationship Lines" is off (Child Of lines were noisy).

---

## 7. Checks worth re-running

- Final positions vs reference (bbox centre, error in mm).
- Frame-by-frame overlap check for moving groups.
- Pocket conflict scan (§5.4).
- Line Art length in a region, **playback order** vs forced refresh (stale = viewport bug).
- Spot renders at key frames (render to PNG temporarily: output is FFMPEG).

## 8. Cleanup done (2026-10-13)
Removed `_backup` / `_preweld` meshes, old action versions (`*_v1`, `*_v3`, `*_Before_*`),
orphans, `Black.001`, scene helper props. Collections renamed by story step.
