# Mountain Mining Town — `mine_a` / `mine_b` / `mine_c`

Asura Kingdom — medieval fantasy mining settlement archetype. Built procedurally with
`E:\My World\Blender\kingdom\mine_town.py` on top of the shared kit
(`E:\My World\Blender\medkit.py`, `medbuild.py`). Z up, metres, ground plane at z = 0,
everything inside a 120 × 120 m footprint centred on the origin.

## Variants at a glance

| | `mine_a` | `mine_b` | `mine_c` |
|---|---|---|---|
| Lane axis / terrace side | runs +Y, hillside east (+X) | runs +X, hillside north (+Y) | runs +Y, hillside **west** (−X) |
| Retaining-wall tiers | **3** (z 1.9 / 3.8 / 5.7) | **2** (z 1.9 / 3.8) | **3** (z 1.9 / 3.8 / 5.7) |
| Miners' cottages | **12** (rows of 4+3+3+2) | **9** (3+3+2+1) | **10** (4+3+2+1) |
| Mine adit | +U end (north-east) | −U end (west) | +U end (north-east) |
| Smelter / forge | −U side of lane (left) | +U side (right) | +U side (right) |
| Ore sorting yard | +U, far side | −U, far end | −U, near side |
| Grand building | tavern + bracketed sign, 10.0 × 6.4 m | company office/tavern 9.4 × 6.4 m | tavern 9.6 × 6.6 m |
| Water | open stone **well** | roofed **cistern** | open stone **well** |
| Terrain below lane | 8.4 m bench at −2.35 m + valley at −4.9 m | 8.0 m bench at −2.20 m + valley at −4.7 m | 8.6 m bench at −2.50 m + valley at −5.1 m |
| Camera (lane coords u,v,z → target, lens) | (−24,−50,46) → (18,5,3), 22 mm | (24,−50,46) → (−18,5,3), 22 mm | (−32,−58,56) → (14,4,3), 22 mm |

Shared by all three: terraced ashlar retaining walls with coping, buttresses and stone
stairs through each tier; timber mine portal with voussoir ring, hood and lanterns; dark
recess with an ember glow; four-legged headframe with winch wheel, rope and cage; rail
line with an ore cart running ~19 m into town; smelter with pyramidal smoke hood, 15.4 m
banded stack, emissive furnace mouth, quench trough, bellows, anvil; ore yard with sorting
shed, table, ore pyramids, crates and sacks; pick racks, ladders, rope coils, plank stacks,
barrels, scaffold, hand carts; post lanterns, flare posts and a bell/whistle post; dark
narrow conifers on the terraces, berms and ridge; a 7 m walkable cobbled lane with ruts and
mud.

## Measured results (fresh-process FBX re-import)

Each FBX was re-opened in a separate headless Blender 5.2.2 process
(`E:\My World\Blender\kingdom\verify_mine.py`), not measured from the build session.

| | `mine_a` | `mine_b` | `mine_c` |
|---|---|---|---|
| Mesh objects | 41 | 36 | 40 |
| Triangles | **153,584** | **131,092** | **139,264** |
| Faces (quads incl.) | 74,989 | 63,959 | 67,946 |
| Materials | 126 | 116 | 122 |
| BBox min (m) | −58.00, −60.00, −6.12 | −60.00, −56.67, −5.97 | −56.36, −60.00, −6.30 |
| BBox max (m) | 54.51, 60.00, 32.04 | 60.00, 49.00, 31.08 | 57.23, 60.00, 33.18 |
| BBox size (m) | 112.51 × 120.00 × 38.16 | 120.00 × 105.67 × 37.05 | 113.58 × 120.00 × 39.48 |
| FBX size | 2,191,804 B | 1,907,452 B | 2,003,468 B |

All three pass the "nothing is zero" check. Footprint X/Y stays inside ±60 m.
`z min` is the sunken valley/scree floor at the foot of the lower retaining wall; every
building, road, prop and wall sits at or above z = 0. `z max` is the backdrop ridge
(stepped rock slabs), not a building — the tallest built element is the 15.4 m smelter
chimney, everything else is 4–14 m.

Triangle budget: the kit's 2-segment bevel on every box was the whole cost (a bare
`medbuild.house` is 2.8 k tris but 19 k after bevel). A shim in `mine_town.py` skips the
bevel for parts under 2.8 m, which brings ~7 k tris per cottage and keeps the heaviest
variant at 153.6 k — just over the ~150 k guideline, no single object above 40 k.

## Unity pixel-QC fixes (round 2)

1. **Step shading.** Every retaining wall now breaks into four values instead of
   two: a dark riser (`mine_riser` #3a342b), a recessed near-black shadow band
   (`mine_shadowline` #12100c) under the coping, a pale dressed coping lip
   (`mine_lip` #a99e87) standing 0.10 m proud of the wall and 0.08 m above the
   tread, and the mid-tone cobble/gravel tread above. The same treatment is
   applied to the lower bench wall, every berm riser and every ridge riser, so
   the whole terraced hillside reads as steps rather than flat stripes.
2. **Ground plate.** The plate is now `ground` with its top at exactly
   **z = 0.000** and a **2 m buried skirt** down to **−2.000** (instead of a
   0.34 m exposed plinth), and its side faces use `ROCK`, never a flat brown
   fill. Lane, yard surface, ruts, mud patches and gutter are separate objects
   (`lane`, `yard`) so they can sit at 0.02–0.11 m above the plate without
   affecting the plate test. Measured after re-import: `ground` z ∈ [−2.000,
   0.000] in all three variants.
3. **Fence.** The first export contained no fence object at all; a proper
   post-and-rail run (`fence`, along the top of the lower retaining wall) is now
   built by `fence_line()`: rails 0.10 × 0.06 m, square posts 0.13 × 0.13 m every
   2.25 m, each post 0.20 m above the top rail and standing on its own
   0.34 × 0.34 × 0.14 m footing. Ladder rails are 0.07 m and scaffold poles
   0.14 m, so nothing else in the set can read as a ladder-fence.

## Export contract

`export_objs()` from `medkit`/`export_kit.py` is used unchanged: world-space geometry,
identity object transforms, `convert(target="MESH")` → `join()` → rename, then

```
bpy.ops.export_scene.fbx(filepath=…, use_selection=True, object_types={"MESH"},
    global_scale=1.0, apply_unit_scale=True, use_mesh_modifiers=True,
    axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE",
    path_mode="AUTO", embed_textures=False, bake_space_transform=False)
```

No root transform is applied and `bake_space_transform` is off, so the Unity importer
sees the expected 100-scale / (270,0,0) root and 1 unit = 1 m. The re-imported bounding
boxes match the build-session numbers exactly, confirming the round trip.

## Renders

1280 × 720, EEVEE (`BLENDER_EEVEE`), AgX + "AgX - Medium High Contrast", exposure 0.85,
sun 5.0 W at 2° from (48°, 0, 197°) with a 620 W cool area fill and a 1100 W warm area
fill placed camera-left, world sky (0.40, 0.55, 0.74) at 0.50, plus one 260 W point light
inside the furnace mouth. Existing lights and cameras are deleted before the rig is built.

* `E:\My World\Blender\renders\kingdom\mine_a.png`
* `E:\My World\Blender\renders\kingdom\mine_b.png`
* `E:\My World\Blender\renders\kingdom\mine_c.png`

## Files

* Scripts: `E:\My World\Blender\kingdom\mine_town.py` (builder, `-- --variant mine_a|mine_b|mine_c|all`), `verify_mine.py`
* Scenes: `E:\My World\Blender\kingdom\mine_a.blend`, `mine_b.blend`, `mine_c.blend`
* Meshes: `E:\My World\Blender\export\kingdom\mine\mine_a.fbx`, `mine_b.fbx`, `mine_c.fbx`

## Known limitations

* No chimney smoke in the renders — alpha-blended plumes read as floating blobs in EEVEE;
  `smoke_plume()` exists in the script but the call is disabled.
* The composition is a high 3/4 plan view; the adit portal is legible but small (~5 % of
  frame width) because the town plan, the terraces and the mine had to fit one 1280 px frame.
* The mountainside behind the top terrace is stepped rock slabs (a quarry look) rather than
  a continuous slope; this keeps the triangle budget and the silhouette readable.
