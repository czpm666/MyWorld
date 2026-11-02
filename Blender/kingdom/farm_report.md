# Farm Village — Asura Kingdom archetype (3 variants)

Procedural medieval farm village for Unity. Three layouts built from one shared kit,
same palette, same prop vocabulary, different footprints and focal points.

All numbers below are **measured from a fresh-process re-import of the exported FBX**
(`verify_farm.py`), not from the builder.

| | `farm_a` — Crossroads hamlet | `farm_b` — Street + green | `farm_c` — Forked lane |
|---|---|---|---|
| **Object count** (exported meshes) | **214** | **174** | **195** |
| **Triangles** | **294,191** | **297,410** | **281,459** |
| **Faces** (quads/tris as built) | 148,496 | 149,737 | 142,321 |
| **Material count** | **53** | **53** | **54** |
| **Bounding box X** | **−52.95 … 48.11 m** | **−52.70 … 52.70 m** | **−48.70 … 48.70 m** |
| **Bounding box Y** | **−46.12 … 46.10 m** | **−43.70 … 45.50 m** | **−44.70 … 45.50 m** |
| **Bounding box Z** | **−2.00 … 12.68 m** | **−2.00 … 12.68 m** | **−2.00 … 12.68 m** |
| Extents (x × y × z) | 101.1 × 92.2 × 14.7 m | 105.4 × 89.2 × 14.7 m | 97.4 × 90.2 × 14.7 m |
| Vertices | 160,478 | 160,843 | 153,404 |
| FBX size | 4.70 MB | 4.64 MB | 4.53 MB |
| Cottages | 9 (4 west row, 5 east row) | 10 (6 south row, 4 north row) | 9 (3 east, 2 west, 2 NE branch, 2 NW branch) |
| Barns | 2 (NW, SE of the junction) | 2 (flanking the green, E and W) | 1 (on the NE branch) |
| Windmill | east shoulder, sails toward the lane | north end, closes the street vista | west shoulder, above the fork |
| Civic | well + notice board + banner + cobbled junction | well + wayside shrine on the green + notice board + banner | well + shrine on the fork island + notice board + banner + cobbled forecourt |
| Fields | wheat 24×24 W, vegetables 20×16 E, meadow + 3 haystacks | wheat 24×18 NE, vegetables 24×18 SW, meadow SE | wheat 24×24 SW, vegetables 20×22 E, meadow W |
| Trees (trunk + 3–4 canopy lobes) | 20 (12 avenue + 4 orchard + 4 woodlot) | 20 | 16 (12 avenue + 4 orchard) |
| Bushes / hedges | 8 bushes, 3 hedge runs | 8 bushes, 2 hedge runs | 8 bushes, 3 hedge runs |
| Gardens / paddocks | 6 walled gardens, 3 fenced paddocks | 2 gardens, 3 paddocks | 2 gardens, 4 paddocks |

Z minimum is −2.00 m on purpose: every ground surface (lane, apron, field soil, ditch) is a
plate whose **top sits at y = 0.00** and which continues 2 m down as a skirt, so nothing
shows a floating riser against the Unity terrain.

## What makes the three variants different

- **`farm_a` — crossroads hamlet.** A north–south lane bends through an open cobbled
  junction with an east spur; the well, banner and notice board sit in the middle of the
  carriageway as the village's meeting point. Two barns and a windmill frame the
  settlement, wheat west and vegetables east. Character: *busy, commercial crossroads.*
- **`farm_b` — linear street village.** One long crooked street with a wide open green on
  its north side, ringed by the well, a small wayside shrine, the notice board and the
  banner; cottages line both sides in two rows. The windmill closes the north vista.
  Character: *tidy, spaced-out roadside village.*
- **`farm_c` — forked lane.** The street splits around a wooded island holding the well and
  a shrine, one branch climbing north-west toward the windmill, the other north-east past
  the barn; houses follow the branches off-axis. Only one barn, more paddocks, more
  hedgerows. Character: *irregular, terrain-following hamlet.*

## Build / verification

Everything is procedural; nothing is hand-modelled.

- **Kit:** `E:\My World\Blender\medkit.py` (palette materials, primitives, gable roofs,
  windows/doors), `E:\My World\Blender\medbuild.py` (timber framing, houses, trees, props)
  and `E:\My World\Blender\kingdom\farm_kit.py` (farm palette, barns, windmill, well,
  shrine, notice board, banners, fields, fences, carts, lanterns, cheap trees).
- **Driver:** `E:\My World\Blender\kingdom\build_farm.py`
  ```
  & "E:\SteamLibrary\steamapps\common\Blender\blender.exe" -b --factory-startup `
    --python "E:\My World\Blender\kingdom\build_farm.py" -- --variant farm_a
  ```
  A run resets the scene, builds the layout, joins each assembly group into one mesh
  (`farm_a_house_e_01`, `farm_a_wheat`, …), applies transforms, exports the FBX, then adds
  the render rig (sun + fill + camera + temporary ground) and writes the PNG and the .blend.
- **Verification:** `E:\My World\Blender\kingdom\verify_farm.py` re-imports each FBX in a
  *fresh* headless Blender process and prints object / triangle / material counts and bbox.
  Re-import matches the builder exactly object-for-object, so nothing is lost in export.
- **Unity import contract:** the FBX root imports with location (0,0,0), rotation 0 and
  scale 1 (`global_scale=1.0`, `apply_unit_scale=True`, `axis_forward="-Z"`, `axis_up="Y"`,
  `bake_space_transform=False`) — identical to the existing kit exporter. All geometry is
  world-space with applied transforms, so every mesh drops into a scene without offsets.
- Ground is flat (z = 0) and no terrain is exported: the Unity world supplies it. The
  ground plane, lights and camera in the .blend are render-only and are **not** part of the
  FBX (export happens before the rig is added).
- Budget: all three are under the ~150k face target (142k–150k), Z max 12.68 m (windmill
  sail tips), footprint inside ±53 m — comfortably inside the 120 × 120 m square. The lane
  through every village is ≥ 6.6 m wide and unobstructed.

## QC pass (raised ground slab, fence proportions, field overlap)

- **Ground plate.** Every ground surface is now built by `farm_kit.ground_plate()`:
  top exactly at the requested z (0.00 for lanes, aprons, yards, field soil and the
  perimeter ditch) with a 2 m skirt going down. Measured per-object Z extents on the
  re-imported FBX:

  | object | Z min | Z max |
  |---|---|---|
  | `farm_a_lane_ns` / `_lane_ew` | −2.004 | **0.000** |
  | `farm_a_wheat` (soil plate + crop) | −2.000 | 0.630 (crop, soil top 0.000) |
  | `farm_a_veg_soil` | −2.002 | −0.002 |
  | `farm_a_junction` (cobbled) | −2.002 | **0.0005** |
  | `farm_a_bditch_*` (perimeter ditch) | −2.000 | 0.000 |
  | `farm_a_mill_yard`, `farm_a_yard_a` | −2.000 | 0.000 |

  Largest Z of any ground/plate/slab surface in the three variants: **0.0005 m** (the
  cobbled junction, deliberately 0.5 mm proud so it never z-fights the lane).
- **Fences.** `farm_kit.fence_run()` now uses 0.15 × 0.15 m posts every 2.2 m with a
  0.32 × 0.32 × 0.14 m stone footing, rails 0.075 m thick × 0.10 m tall at z 0.38/0.80 and
  1.10 m posts, so the top rail sits ~0.30 m below the post tops and every bay reads as a
  post-and-rail fence rather than a dropped ladder.
- **Field overlap.** The two lane near the junction used to throw their ragged verge
  patches straight across the cobbled apron (the X on the grass). `verge_quads()` now takes
  a `skip` list of `(x, y, r)` circles and the lanes suppress verges inside the junction
  radius (8.6 m at the farm_a crossing, 7.4 m at the farm_c fork). Crop rows are inset from
  the field edge (soil margin 0.65 m, rows inset ≥ 0.65 m with ragged ends) so no crop
  sticks out onto the grass.
- Everything else (layout, palette, props, cameras) is unchanged.

## Renders

`E:\My World\Blender\renders\kingdom\farm_a.png`, `farm_b.png`, `farm_c.png` — 1280×720,
EEVEE, high three-quarter view, sun + sky fill, AgX (Medium High Contrast).
Matching `farm_a_detail.png` … are close-up crops of the same scene used to check
window/timber craft.
