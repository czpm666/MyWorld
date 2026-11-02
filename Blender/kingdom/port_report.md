# River port town (河港镇) — 3 variants

Asura Kingdom medieval-fantasy timber-and-stone river port. Metres, Z up, ground z=0,
footprint 120 × 120 m centred on the origin, river band along one edge (water surface
z = −0.60, stone quay walls rising to grade).

Generator: `E:\My World\Blender\portlib.py` (world-space parts kit on top of `medkit.py`)
+ `E:\My World\Blender\kingdom\build_port.py` (per-variant layout, export, render rig).

Build command per variant:

```
& "E:\SteamLibrary\steamapps\common\Blender\blender.exe" -b --factory-startup \
  --python build_port.py -- --variant port_a
```

## Measured numbers

All numbers below are **read back from the exported FBX in a fresh headless Blender**
(`kingdom\verify_port.py`, raw output in `kingdom\port_verify.json`); they match the
build-time counts exactly.

| | port_a | port_b | port_c |
|---|---|---|---|
| FBX | `export\kingdom\port\port_a.fbx` (1,829,660 B) | `port_b.fbx` (1,927,740 B) | `port_c.fbx` (1,889,724 B) |
| .blend | `kingdom\port_a.blend` | `kingdom\port_b.blend` | `kingdom\port_c.blend` |
| Render | `renders\kingdom\port_a.png` | `port_b.png` | `port_c.png` |
| Objects (mesh roots) | 7 | 7 | 7 |
| Triangles | 153,484 | 156,734 | 156,208 |
| Polygons | 74,519 | 75,884 | 75,772 |
| Vertices | 96,587 | 98,697 | 98,189 |
| Materials | 80 | 80 | 78 |
| Bounding box | −60,−60,−3.112 → 60,60,14.003 | same | same |
| Size (m) | 120 × 120 × 17.115 | same | same |
| Root | `port_a_boats`, loc 0,0,0 · rot 0,0,0 · scale 1,1,1 | `port_b_boats` | `port_c_boats` |

Triangles per object bucket (polys / tris):

| bucket | port_a | port_b | port_c |
|---|---|---|---|
| `*_buildings` | 45,422 / 91,270 | 45,426 / 91,280 | 46,679 / 93,782 |
| `*_props` | 8,959 / 20,178 | 8,170 / 18,338 | 8,171 / 18,374 |
| `*_foliage` | 12,481 / 25,560 | 15,028 / 30,772 | 12,296 / 25,184 |
| `*_works` | 4,663 / 10,368 | 4,198 / 10,084 | 5,564 / 12,608 |
| `*_boats` | 2,020 / 4,120 | 2,088 / 4,272 | 2,088 / 4,272 |
| `*_quay` | 968 / 1,976 | 968 / 1,976 | 968 / 1,976 |
| `*_ground` (plate only) | 6 / 12 | 6 / 12 | 6 / 12 |

The `*_ground` object is the base plate and **nothing else** — one box, 6 polygons. Its top
surface is exactly z = 0.00 and it extends *downward* to z = −2.00 as a buried skirt, so no
vertical rim stands proud of the surrounding terrain (see *Ground plate* below). The street,
kerbs, aprons, field, crop strips and hedgerows all live in `*_props`.

Under the face budget: 74.5–75.9k polygons per variant against the ~150k limit (153–157k
triangles — the budget was counted on faces/polygons). No object has a non-identity
transform; the seven mesh roots sit at the origin
with scale 1 and rotation 0, which is what the Unity importer expects from the mirrored
`export_kit.py` settings (`global_scale=1.0`, `apply_unit_scale=True`,
`axis_forward="-Z"`, `axis_up="Y"`, `bake_space_transform=False`).

Material set (~78–80): plaster_0..5, tile_0..4, tile_barn, stone/stone_port/stone_barn/
stone_slab/stone_step/stone_bridge/stone_bridge2/stone_deck, cobble_main/cobble_far,
flag_main, grass_field/far_grass/hedge/crop_strip/crop_strip2, leaf_willow/willow2/poplar/
poplar_hi/broad_hi/fruit/hay/crop, wood_timber/bark/hull/boat/pier/pile/barrel/crate/door/
door_big/basket/cart/fence/rail/rack/hoist/crane/bollard/cork/market/platform/shutter/sign/
barn/willow, iron/iron_port/gold (+ brass_bell in port_b), cloth_sail_canvas/rope/net/sack/
banner_red/banner_trim/bloom, water_port/water_foam, glass/glass_lamp, fish, earth_yard/
earth_path/earth_garden. All procedural (Voronoi/Brick driven by TexCoord.Object), no image
textures.

## What each variant is

**port_a — bridge town.** River to the north. Two timber piers on piles (x = −8, length 13;
x = 16, length 11), each with bollards, rope, gangplank, crate stack and barrels. One
gantry crane on the quay (x 17.6, 5.9 m) plus two deck-mounted jib cranes. Three cargo
boats: one moored alongside pier 1, one mid-channel, one drifting near the east end.
Stone arched bridge at x = −30 (30 m span, 6.6 m wide, four arches, parapets + coping).
Warehouse (15 × 11 m, cargo door + loading platform 13 m) at x = 30, inn with hanging
sign at x = −47, fish market shed (9 × 6 m) at x = −16. Six waterfront houses + six
second-row houses (2–3 storey, jettied, hoist beams), barn, gardens, orchard, three
haystacks, four fenced pens, dirt lanes. 4 far-bank houses.

**port_b — ferry town.** River to the west (whole layout rotated 90°). **Ferry landing**
instead of a bridge: stone stage at x ≈ 16 with railings, three steps up the quay, a
3.1 m bell post with brass bell, bench and a mooring buoy. Three piers (−12/14 m,
6/10 m, 26/12 m) and **two** gantry cranes (0 and 21). Three boats. Fish market 10 × 6.5 m
at x = −18; larger warehouse (18 × 12 m, 15 m loading platform) at x = 40; three-storey
inn with cross-gable and two dormers at x = −42. Six waterfront + five second-row houses,
barn, orchard, gardens, haystacks, four pens. Densest foliage of the three (15k polys —
willows and poplars along the quay and far bank) and the only variant with the brass bell
and mooring buoy. 5 far-bank houses.

**port_c — warehouse town.** River to the south (layout rotated 180°). Stone arched bridge
at x = −34 (30 m, 6.2 m wide) with a darker flagstone deck. Three piers (−12/12 m,
8/14 m, 30/11 m), one gantry (x −2, 6.0 m) and one jib crane. Three boats. **Largest
building programme**: a 17 × 12 m warehouse complex with a 14 m loading platform at x = 8,
plus the fish market at x = −25 and a three-storey inn at x = 36.
Five waterfront + seven second-row houses (the densest town wall, 46.7k building polys),
barn, orchard, gardens, three haystacks, four pens. Heaviest `works` bucket (5,564 polys —
bridge + quay steps + bridge parapets). 4 far-bank houses.

## What is shared

Same quay: 120 m of stone quay wall with a cobbled 8 m street (y 18–26) held clear as the
walkable quayside, kerb, 13 mooring rings, stone steps down to the water, iron rungs, and
a handful of rotten piles. Same river: dark teal `water_port` (isotropic low-frequency
noise driven by object coords, roughness variation, gentle bump), foam collars along the
quay lip, around every pier pile and around each boat's waterline, plus a few drifting
foam dashes. Same furniture vocabulary: bollards, lantern posts, rope coils, net racks,
fish crates, carts, sacks, barrels. Same farmland backdrop: grass, seven ploughed crop
strips (wave-texture bands), hedgerows, orchard, haystacks.

## Ground plate

The base plate is a single box `*_ground` (6 polys) with **top surface exactly z = 0.00**
and a skirt running down to **z = −2.00**. It carries no riser above grade: the old 0.60 m
slab was centred at z = −0.30 and its side faces stood 0.60 m proud at the footprint rim,
which read as a brown plinth stripe from outside the town. The skirt's sides are now buried
in terrain. Its +Y edge stops at y = 25.8, i.e. *inside* the quay wall body (y 24.30–26.00),
so the rim never shows at the waterline.

The water mesh sits at z = −0.60 (0.6 m below quay grade) and starts flush at the quay wall
face, running out to y = 53.0 under the far wall. It cannot touch the plate: measured
extents are plate `x −60..60, y −60..25.80, z −2.000..0.000` and water `x −60..60,
y 26.00..53.00, z −0.880..−0.600` — the plate stops 0.20 m short of the water in Y and
0.60 m above it in Z, with the quay wall body (y 24.30..26.00) filling the gap.

Measured max Z per ground/plate/slab/mole object after FBX re-import:

| variant | object | max world Z | ok (≤ 0.001) |
|---|---|---|---|
| port_a | `port_a_ground` | 0.00001 | true |
| port_b | `port_b_ground` | 0.00001 | true |
| port_c | `port_c_ground` | 0.00000 | true |

The 1e-05 on port_a/b is float rounding on the top face, not a riser.

## Verification

`kingdom\verify_port.py` opens each FBX in a **fresh** Blender process with
`read_factory_settings(use_empty=True)`, then prints object count, triangle count, material
count, bounding box and a `plate_check` (every mesh whose name contains
ground/plate/slab/mole, with its max world Z and an `ok` flag for ≤ 0.001) as one
`PORTVERIFY {json}` line per variant, and writes `port_verify.json`. Run:

```
& "E:\SteamLibrary\steamapps\common\Blender\blender.exe" -b --factory-startup --python verify_port.py
```

Result: 7 objects / 153,484 · 156,734 · 156,208 tris / 80 · 80 · 78 materials /
bbox `[-60,-60,-3.112] .. [60,60,14.003]` for a, b, c respectively — no zero/empty
imports, build-time counts match the re-import counts exactly, and all three plate checks
pass.

## Render

EEVEE (`BLENDER_EEVEE`), 1280 × 720, 64 TAA samples, AgX / Medium High Contrast,
sun (energy 3.1, 5° angle, warm) + 480 W sky-blue area fill + 0.72 strength world.
High 3/4 angle from over the water; camera 40 mm. Pre-existing lights and cameras are
deleted before the rig is built. All three PNGs were rendered, read back and critically
re-shot during development (water banding, a flat untextured band, pier piles and a
stray boat spar were all fixed from those reads).
