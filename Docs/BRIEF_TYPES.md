# TYPES agent brief — 6 new building types for the Asura capital

Read `E:\My World\Docs\BRIEF_2026-11-02.md` first. It has the user's hard
requirements, the environment table, the discipline rules and the file-ownership
list. This file only adds what is specific to your job.

## Why you exist

The user asked, in Chinese, for roughly twenty building types in the capital,
and named two of them explicitly: **训练场 (training ground)** and **军营
(barracks)**. The city currently has houses, shops, taverns, inns, a guild hall,
a market hall, a cathedral, a castle and a few warehouses — the military and
civic layer is missing, so the capital reads as a merchant town, not the seat of
a kingdom that is at war.

## Your deliverable

New file `E:\My World\Blender\kingdom\hd_types.py` (you own it exclusively),
plus `E:\My World\Blender\kingdom\look\types_lab.py` (you own it exclusively),
plus `E:\My World\Docs\AGENT_TYPES.md`.

### Six types

| kind | footprint | notes |
|---|---|---|
| `training_ground` | 46–60 x 34–46 m | open sanded yard, wooden palisade on 2–3 sides, archery butts at the far end, weapon racks, a straw dummy row, one long low shed, banner poles. Must read from 34 m up: the *empty yard* is the subject, so the ground treatment (raked sand, trodden patches, straw) matters more than the buildings. |
| `barracks` | 30–40 x 18–26 m | 2–3 storey stone-and-timber block, external stone stair, arcaded ground floor, shield racks under the arcade, a small muster yard, a bell/lookout turret. |
| `stable_yard` | 26–34 x 18–24 m | long stable with a row of half-doors, hay loft, manure heap, trough, cart shed, paddock fence. |
| `bathhouse` | 20–26 x 16–22 m | steam vent on the roof, a domed hypocaust roof, an outdoor basin, awning. |
| `mill` | 12–16 x 12–16 m | water wheel on one gable or a windmill sail set; a mill race or a sail cross that is readable in silhouette. |
| `chapel_small` | 12–16 x 20–26 m | single nave, bell cote, small rose or lancet window, graveyard wall with 8–14 headstones. |

Everything must be built from the existing kit helpers so it sits in the same
world: `import hd_houses as S`, `import hd_houses_parts as HP`,
`import medkit as K` (`box/cyl/disc/mesh_obj/assign/T_at`), and the material
dict `MAT` passed in. Look at `hd_shops.py` (108 KB) for the house-adjacent
vocabulary and `hd_gate.py` for the military vocabulary — reuse, do not
re-invent.

### Placement API

```python
def place(units, res, seed=7, share=0.055, only=None):
    """Return a NEW list of unit dicts with `kind` swapped on a fraction of them.

    - never move x / y / yaw / quad; a type that does not fit its unit's quad
      must be skipped, not resized past it
    - `share` is the fraction of eligible units to convert (default ~5.5% of the
      city = ~700 sites, which is too many for barracks; use per-kind quotas)
    - respect `unit["district"]`: training_ground + barracks only in
      palace / guild / outer districts, stable_yard in dock / craft,
      bathhouse in residential / guild, mill in outer / craft, chapel_small
      anywhere
    - deterministic for a given seed
    """
```

Also expose `BUILDERS = {kind: callable}` where each callable has the signature
`fn(MAT, rng, x, y, yaw, w, d, floors, **kw)` and returns a list of Blender
objects, exactly like `hd_shops.build`.

### Ground treatment

`training_ground` and `stable_yard` have yards that will be *paved over* by the
block slab (`town_ground`) and then dressed by `hd_streetlife`. To keep them
readable you must emit your own ground mesh at z = 0.10 (above the 0.09 slab),
and register a keep-out so streetlife does not drop barrels in the middle of the
archery range. Ask the main AI before changing any file outside your two files.

## Lab

`look/types_lab.py` must:
- build a mock 40 x 40 m plot for each of the six kinds at real size,
- light it with `hd_light.apply("morning_town")` + `hd_sky.world("morning_town", ambient=0.38)`
  + exposure -2.20 (copy the exact block from `look/house_lab.py`),
- render two cameras per type: the real game camera (pitch 52°, distance 34 m,
  vfov 30°, lens 18/tan(15°) = 37.8 mm) and a 1.72 m eye-level view,
- write `TYPES_sheet.png` (a 2 x 6 contact sheet) into
  `E:\My World\Blender\renders\kingdom\look\`,
- run headless: `python look\types_lab.py` from a Blender `--background` run,
  and accept `--only kind`.

Iterate at 480x270 / 8 samples. Final acceptance renders at 960x540 / 24.

## Discipline (non-negotiable)

1. **One Blender at a time, globally.** Always go through
   `look/_lock.py:run_blender(args, tag, timeout=1800)`. Never call
   `blender.exe` directly.
2. **Never open** `capital_v24.blend` (860 MB), `capital_c1.blend` (807 MB),
   `capital_low.blend` (594 MB). Your lab builds its own 40 x 40 m scene.
3. Your RSS budget is 4 GB. If a render exceeds it, lower samples or resolution.
4. Do not edit `capital.py`, `hd_dense.py`, `hd_plan2.py`, `hd_houses.py`,
   `hd_houses_parts.py`, `hd_streetlife.py`, `look/render.py`, `look/spots.py`,
   `look/shots.json` — the main AI owns those and will wire your module in.
5. Write files with the `write`/`edit` tools only. PowerShell
   `Get-Content | Set-Content -Encoding UTF8` destroys Chinese text and eats
   newlines.
6. Report to the main AI with `send_message` when you have something to show,
   not only at the end. Include the render path and what you changed.

## Report format (final)

`Docs/AGENT_TYPES.md` with: what you built, the exact `place()` signature and
semantics, per-type tri counts, the lab command, the sheet path, the three
things you are least happy about, and a one-paragraph note on how the main AI
should wire it into `capital.py`.
