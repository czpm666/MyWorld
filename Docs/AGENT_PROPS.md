# Street life pass — `hd_streetlife.py`

Owner: props agent. Files: `Blender/kingdom/hd_streetlife.py` (new), `Blender/kingdom/look/props_lab.py` (new).
Nothing else in the project was edited.

## What it does

Adds the layer that sits *between* the buildings: yard furniture, plot boundaries,
street furniture, vegetation and a few people. Everything is procedural, numpy-batched
into one mesh per 56 m cell, deterministic from `seed`, and tested against the building
quads, the street raster and itself before it is placed.

## API (wiring)

```python
import hd_streetlife as SL

objs = SL.build(MAT, units, res, seed=7, density=1.0, cell=56.0,
                collection=None, region=None, keep_points=False,
                budget=3950000)
```

* `MAT`    — `capital.MAT` after `capital.init_mats()`. Anything missing falls back to a local `sl_*` material.
* `units`  — `hd_dense.placements(res, foot_override=hd_shops.FOOTPRINT)`.
* `res`    — `layout.json` (needs `streets` and `blocks`).
* `seed`   — one integer drives every placement.
* `density`— global multiplier.
* `cell`   — merge cell, 56 m ≈ one game-camera frame.
* `region` — optional `(x, y, radius)` for a partial build (used by the lab).
* `budget` — hard triangle ceiling; later passes stop when it is reached.

Returns the list of objects (already linked into the scene). Each object is **one mesh**
named `streetlife_<cx>_<cy>` (`cx, cy` = cell indices), one material slot per material
used in that cell, `material_index` set per polygon.

Also public: `SL.stats()` → dict of the last build (`props, faces, objects, seconds,
rejected, kinds, by_kind, by_kind_faces`), `SL.clear()` (delete the last build),
`SL.build_prop_sheet(MAT)` (a grid object with one of every proto, for QA),
`SL.palette(MAT)`, `SL.MATS`, `SL.protos()`.

## Numbers (seed 7, density 1.0, whole city, `capital_v23.blend`)

| metric | value |
|---|---|
| props | **65 613** |
| triangles | **3 950 029** (budget cap 3.95 M; uncapped it wants 4.46 M) |
| objects | **444** |
| build time | **23.0 s** (after 10 s of placements) |
| prop kinds | 108 |
| rejected placements | ~29 000 |
| street stations | 13 793, of which 4 600 (33 %) found no wall within `h + 2.6 m` |

## Prop vocabulary (108 protos)

Yard: woodpile, woodpile_lean, hay, hay_stack, waterbutt, rainbarrel (with downpipe),
bucket, trough, coop, pigpen, garden_0/1 (vegetable rows), herbs, compost, stonepile,
shed, cart, wagon, barrow, wheel, pallet, planks, crates (3), sacks (2), amphorae (2),
well, fountain, grindstone, dovecote, beehives, toolrack, rack, ladder, stoop, bench,
stone_bench, mountblock, hitch, gate, gate_leaf.

Boundaries: fence (wattle), board_panel, board_panel_lo, wall_panel (dry stone),
hedge_150/220, trellis.

Street: stall_0/1/2 (striped awnings), shopawning_0/1/2, sign_0/1/2, signpost_2/3,
notice, lantern, banner_500..950 (8 spans × 2 cloths), laundry_0/1, shrine,
stairs, pigeons_3/4, dog, cat, person_0..5 (≈160 tris, street corridors only).

Vegetation: tree_0/1/2 (yard trees), treebus_0/1, shrub, ivy_0/1, vine, sillbox,
pots_2/3, weeds_55/85, leaves_0/1.

Ground: yardpad_0/1/2 (cobble / straw / earth carpet for bare block floors),
bed_veg / bed_straw / bed_rubble.

## Passes, in order

1. `_streets_pass` — kerb clutter at every street station (march to the real facade).
2. `_overhead_pass` — laundry lines and banners across the street (gap 3.4–15 m).
3. `_people_pass` — figures on the corridor only.
4. `_trees_pass` — kerbside trees + yard trees per block.
5. `_wallhug_pass` — clutter along the back edge of every building quad (fills the
   1–3 m yard strips the area sampler rejects); wall-attached props (ivy, vine,
   shop awning, rain barrel, trellis, shrine, stairs, window box).
6. `_fence_pass` — plot boundaries as modular 1.8 m panels running outward from a
   back corner, sometimes with a gate.
7. `_pad_pass` — cobble/earth pads over the bare block floor.
8. `_bed_pass` — vegetable/straw/rubble beds.
9. `_yards_pass` — courtyard *clusters* (recipes: farm, garden, livestock, workshop,
   wash, seating, yard_lot) chosen by block role.
10. `_market_pass` — stalls on square/plaza blocks.

## Verification harness

`Blender/kingdom/look/props_lab.py`:

```powershell
# whole city, game cameras + eye level + cluster shots
blender -b --python look/props_lab.py -- --full --hero 4 --game 4 --street 2 `
        --shots all --res 960x540 --samples 32 --tag r4

# mock city on an empty scene (1.5 GB, 0.3 s build) — the fast iteration loop
blender -b --python look/props_lab.py -- --mini 1 --shots h0,c1 --res 480x270 --samples 8
```

Renders do not save the .blend. Output goes to `Blender/renders/kingdom/look/`.

## What the renders showed

* Close (1.7–2.5 m) frames are convincing: cobbled square, tree, striped stall,
  two straw-hatted figures, barrels, stone trough, crates, notice board, lanterns.
* The game camera in `capital_v23.blend` is a **roof-scape**: measured roof tops are
  min 5.0 / median 8.8 / max 11.7 m while the camera sits 26.8 m up at 52°, so only
  50–77 % of the frame can ever be ground, and a house between camera and pivot hides
  the street entirely. The props read wherever ground is visible (courtyard top-left
  of `f9_d1_cam.png`).
* The bare beige courtyard is partly the `town_ground` block floor, which no prop
  count fixes — hence the pad/bed passes. They are the cheapest obvious win still
  under-used: pads are 8 tris and should be denser than the current 6.2 m grid.
* Eye-level cameras keep landing inside the cathedral nave or against a facade:
  `street_spots()` stations do not test line of sight for a 1.72 m eye.

## Known limits / next steps

* 33 % of street stations find no facade within `h + 2.6 m` and fall back to a
  guessed inset — those props can drift toward the kerb.
* `ring` from `hd_dense.placements()` is the string `tier` (`outer/mid/core`);
  `_TIER` maps it. If `hd_dense` starts emitting an int plus `tier`, `_TIER` keeps working.
* Trees are still sparse for a capital: 3 000 or so for 43 km of street.
* Market stalls only exist on `square`/`plaza` blocks (6 + 1 in this layout).
