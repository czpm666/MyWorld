# AGENT_HOUSES — HD house pass (hd_houses.py)

Owner: houses agent. Files I own: `Blender/kingdom/hd_houses.py`,
`Blender/kingdom/hd_houses_parts.py` (new), `Blender/kingdom/look/house_lab.py` (new),
`Blender/kingdom/look/_hu_one.py` (new). Nothing else was edited.

## TL;DR

`hd_houses.house()` was rebuilt on top of a parametric detail kit
(`hd_houses_parts.py`) instead of `hd_common.tiled_roof` + a stack of boxes.
Every house now gets a real roof system (courses, ridges, verge boards,
dormers, chimneys with pots, gutters), a real window system (recess, frame,
mullions, sill, shutters, dark glass), wall articulation (plinth, jetty with
joist ends, timber framing, quoins) and a per-type style table.

| metric (mean over the 12-house lab row) | before | after |
|---|---|---|
| base-mesh tris / house | 2 956 | **4 037** |
| base-mesh polys / house | 1 459 | 1 947 |
| modifier-evaluated tris / house | 19 940 | **15 781** |
| objects / house | 231 | 223 |

Base tris is the number that matters for the city: `capital.py:638` does
`return [join_parts(name, parts)]`, and `bpy.ops.object.join()` keeps only the
active object's modifiers, so almost every bevel modifier is discarded anyway.
The new builder emits **no bevels at all**, which is why the evaluated count
went *down* by 21 % while the silhouette got much richer.

Budget asked for: < ~4 000 tris. Delivered: 4 037 mean over the mixed row
(2-floor timber / stone / craft / shop / inn / manor / warehouse / tower plus
two 1-floor houses).

## What the renders said, round by round

Renders are in `Blender/renders/kingdom/look/`, 960x540, Cycles GPU, 32 spp,
preset `morning_town` (`hd_light.apply` + `hd_sky.world`).

1. **Round 1** (`hu_new_*` v1). Timber framing, jetties, dormer, chimney,
   gutter all present, but the roof slope read as a **brick wall** and the
   roofs were too tall (a 3-storey inn at 52° on a 10 m depth = 17.2 m).
2. **Round 2**. Pitches lowered to 43–52°, chimneys enlarged, ground-floor
   timber added. Roof still flat.
3. **Round 3** (course sawtooth added). Sawtooth invisible. Found and fixed a
   rake brace that speared out through the roof, chimney-soot z-fighting,
   a hoist hanging below ground, and moss that read as green leaves.
4. **Round 4**. Found the real roof problem (see below), replaced the roof
   shader, rebuilt the dormer from scratch, trimmed the tri budget.
5. **Round 5** (final). Moss sunk into the course joints, tile band
   strengthened. Shipped.

## The three findings that mattered

### 1. At the game camera the roof plane is seen face-on
The camera is `pitch 52°, distance 34 m, lens 37.8 mm`, and the roofs are at
43–52°. The view direction is therefore almost perpendicular to the slope:
course *relief* is seen edge-on and is invisible. Anything that only exists as
relief is wasted at the hero framing (it still matters for the 3/4 and eye
shots, so it was kept). What reads at 34 m is anything that **stands up out of
the slope** — dormers, chimneys, ridge caps, verge boards — plus the roof
**outline** and its colour value. All of the budget went there.

### 2. `medkit.mat_tile` is a brick shader
`medkit.py: mat_tile(name, base, dark, light)` builds a `ShaderNodeTexBrick`
with `Brick Width 0.30, Row Height 0.17, Mortar 0.012`, driven by **Object**
coordinates. Object space is world-aligned, so on a 45–58° slope those rows run
horizontally across the slope and every roof in the city read as masonry. At
the game camera the roofs are 60–90 % of the frame, so this one shader was the
dominant surface in the shot.

`capital_hd_glue.house_mats()` overrides `pal["tile"]`/`pal["slate"]`, so the
material cannot be fixed at source from my file. Instead
`hd_houses_parts.roof_material(src, shade)` re-skins the instance: it reads the
variant colour back out of the source material (`Color1` of the brick node, or
the Principled base colour) so the 8 terracotta families and 3 slates survive,
then builds a fresh Principled material with a **slope-projected** pattern —
`Geometry.Normal` × world-up gives the along-ridge axis, crossed again gives
down-slope, so `du`/`dv` are correct on any slope, on hips and on dormers, from
one shared material per variant. One shadow band per 0.34 m course plus faint
staggered tile joints, and the same ramp drives a bump. `roof_materials(src)`
returns three value steps (0.86 / 1.00 / 1.12) cycled course by course, because
sun shadow alone does not separate courses under a bright key.

### 3. A dormer must stand vertical, not square to the roof
`roof()["dormer_T"]` originally returned the slope frame itself, so the dormer
was tipped over with the tiles: its "vertical" was the roof normal, its roof
planes ended up ~25° from horizontal with the ridge running downhill, and it
rendered as two flat wings. The frame is now **world-up** (`+Z` vertical, `+Y`
the horizontal down-slope direction, origin on the roof surface), and
`dormer()` sinks its body `0.55 + hd*tan(pitch)` below that origin so the front
face stays buried in the tiles.

## Roof system

* **Courses** — 0.34 m overlapping slabs, coplanar, with real lip bars
  (`0.085 x run x riser`) merged into one mesh per slope, and three value
  steps cycled course by course. Lips are only built for the first three
  courses (where the eye and 3/4 shots see them) to stay inside the tri budget.
* **Eave** — a double-thickness first course, fascia + soffit, and barge/rake
  boards down both verges.
* **Ridge** — a bed slab plus half-round ridge tiles (r 0.165, `seg=6`) and
  end finials, deliberately overscaled: the ridge is the roofline read against
  the sky.
* **Hip** — `hip_roof()` builds all four slopes at one pitch so the hip
  arrises are straight lines to the ridge ends, with hip rolls, fascia and
  soffit on all four eaves. Used by the manor.
* **Dormers** — fully rebuilt: seven body boxes around a real opening, a
  closed gable triangle, two pitched roof planes, a ridge bead, a window with
  a sill and lintel, and barge boards on the gable outline (a gabled dormer is
  seen head-on at the game camera, so its outline has to be drawn or it
  dissolves into the tiles behind it).
* **Chimneys** — gathered base, shaft, corbelled cap, clay pots with dark
  mouths, soot sheets down the slope. Sized up on manor / warehouse / inn /
  stone, and moved onto the ridge.
* **Gutters** — lead channel along the street eave plus a corner downpipe and
  bend, on the types that get one.
* **Moss / lichen** — a broken damp strip along the eave, half sunk into the
  course joints. Raised patches read as green leaves lying on the roof, which
  is worse than no moss at all.

## Window / door system

`P.window()` gives a dark void behind, glazing set back `deep` (0.16–0.17) so a
0.40 m wall reads as a real reveal, a frame ring inset in the hole, mullion +
transom, lead cames, a projecting sill with a drip, an optional hood, and open
shutters with iron straps. Stone houses get a segmental arch head and a stone
frame; timber houses get a timber frame. Ground floors get shop openings,
counters, awnings and a dark interior plate.

`P.door()` gives a void, planked leaves, iron straps, a ring knocker, stone
jambs and lintel, a threshold, steps and an optional hood canopy. The ground
floor sits **on** the plinth (wall base at `z = pl_h`), so the door steps have
something to descend.

## Wall articulation

* Stone plinth under every house, with a moss line and a spout on some.
* Jetty: bressumer + joist ends + corner brackets, upper floor overhanging
  0.30–0.38 m. This is the single strongest element at eye level.
* Timber framing merged into one mesh per wall, centred on the wall face so the
  members sink 0.07 into the plaster — that is what gives the shadow line where
  the beam meets the wall.
* Quoins on the stone houses, a string course on the manor.

## Type differentiation

One `_STYLE` row per kind drives wall material, pitch, jetty depth, floor
height, frame material, stud spacing, window count/size, shutters, roof type,
plinth, moss, dormer count, gutter, hood, steps, slate, quoins and ornament:

| kind | pitch | jetty | roof | signature |
|---|---|---|---|---|
| timber | 50° | 0.36 | tile | jetty + framing, 2 dormers |
| stone | 46° | – | tile | quoins, arched windows, 1 dormer |
| craft | 48° | 0.30 | tile | shop opening + counter + awning |
| shop | 51° | 0.38 | tile | awning, sign, counter, 2 dormers |
| inn | 52° | 0.40 | tile | balcony, big sign, market board, 3 dormers |
| manor | 44° | – | **hip** | string course, symmetric screen walls, balcony |
| warehouse | 43° | – | slate | hoist + loading door, 1 dormer |
| tower | – | – | crenellated | battlements, arrow slits, bartizan |

## Things I could not do / found in files I do not own

1. **`capital_hd_glue.house_mats()` creates the per-variant plaster and tile
   materials *after* `capital.py:2055` runs `SFC.apply_weathering(MAT)`, so the
   HD houses reach the render with un-weathered plaster and tile.** Roof tile
   and slate cannot be weathered at all — `hd_surface.FROZEN` returns `None` for
   `tile`/`slate`/`cobble`/`flag`/`ground` by design. The plaster problem I
   worked around from inside my own file: `hd_houses._age(mat, kind, strength)`
   calls `SFC.weather_material()` once per material on first use, at strength
   1.85 for plaster (the shipped recipe is deliberately faint — `patch=0.14,
   patch_scale=0.22, bump_str=0.07` at `hd_surface.py:292-296` — which reads as
   an untextured plane on a single facade). **The proper fix belongs in
   `capital_hd_glue.house_mats()`**: weather the per-variant plaster right after
   creating it. That is a one-line change in a file I do not own.
2. **City integration was never verified.** `capital_v23.blend` is 474 MB and
   ~10 GB of RAM; loading it was ruled out by the parent after the machine ran
   out of memory. Everything here was verified on the standalone lab. The city
   build should be re-run once and spot-checked — `hd_shops.py` is the main
   risk, since it calls `S._wall`, `S._jetty` and `S._timber_frame` and those
   signatures were kept but their internals were rewritten.
3. **The eye-level shot is very dark** — the facades face away from the sun in
   `morning_town` and the neighbouring house shadows them. That is the preset,
   not the geometry, but it makes the eye comparison hard to read.
4. Moss/lichen is now very subtle. It could take a proper damp-gradient mask in
   the roof shader (dark green creeping up from the eave) instead of blobs.

## How to reproduce

```
blender -b --factory-startup --python "E:\My World\Blender\kingdom\look\house_lab.py" -- new all
blender -b --factory-startup --python "E:\My World\Blender\kingdom\look\house_lab.py" -- old all
blender -b --factory-startup --python "E:\My World\Blender\kingdom\look\house_lab.py" -- new hero,row,eye,close
blender -b --factory-startup --python "E:\My World\Blender\kingdom\look\_hu_one.py" -- inn
```
`old` loads `_hu_old_houses.py`, a frozen copy of the original module, so the
before/after use the same camera, seed and palette path.
`--fast` drops to 480x270 / 8 samples for iteration.

## 状态（2026-11-02 15:45 断电前）

- **已完成**
  - **根因定位**：那面占画面 40% 的浅色平墙不是窗墙，是**屋檐线以上的山墙三角**——`H.wedge("atc", ...)` 的斜面加稀疏的 `P.gable_frame`。它按构造没有窗（只有 `frontage=="gable"` 的街山墙有阁楼门，老虎窗只长在 `eaves` 前坡），唯一的竖向构件就是三根柱子和一根斜撑，所以只剩 `_band` 横线；面积 `rh = hw*tan(pitch)`，9 m 进深 / 50° 就是 5.4 m 高的三角形，而且位于立面**最上方**，正是 52° 机位看得最正的地方。
  - **为什么上一轮 lab 没复现**：`capital.py row_along()` 用的是 `depth_range=(6.0, 9.0)`，真实城市房子只有 6–9 m 进深、2 层；上一轮 lab 按简报用 10–13 m、2–3 层，山墙窗更多、墙更大更"耐看"，把 bug 藏住了。
  - `hd_houses.py` 全部改动已落盘、`ast.parse` 通过、`house(MAT, rng, kind, w, d, floors, frontage)` 签名未变：
    1. `_quoins()` 转角石改成**跨过墙角 0.10 m**（只改 box 尺寸，**0 额外面**），石砌转角从侧面才看得见；
    2. 新 `_gable_dress()`：两道斜向封檐板（barge board）、檩条头、山墙中部**百叶通风口**（带石过梁/窗台）、可选阁楼门 + 铁箍；背向山墙 `light=True` 只留封檐板 + 通风口；
    3. 新 `_flank_dress()`：修补块、勒脚湿痕苔藓、爬藤、壁柱、檐口铅皮天沟、椽头；
    4. 新 `_stack()`：**突出侧墙的烟囱体**，顶到 `eave_z + 2.10~2.52`，从屋面立起来；带烟囱帽和陶管；
    5. 侧墙落水管 `_pipe("fp")` + 檐沟；
    6. `_win_batch()` 现在支持逐窗高度 `zs`/`hs`、封砖窗 `brick_xs`、**铰接半开百叶**（原来是贴墙平板，掠射角下没有投影）；
    7. 侧墙窗数门槛 `nsw` 从 9.8/7.2 改成 8.8/6.2——真实城市进深 6–9 m 原来整面只有 2 扇窗。
  - `look/facade_lab.py` 重写成**街道十字路口**（东西两排连排 + 后排），E0 改成城市真实尺寸 d=8.6/2 层；`game` 机位改成城市那种"侧墙从右下切出画面"的构图；新增**射线审计**（140×79 网格，print 每类构件占画面百分比）。
  - 图已出：`fac2_cmp_game.png` / `fac2_cmp_ends.png`（960×540 前后对比，同 lab 同种子同机位，两块面板原生 480×270 不重采样）、`fac2_after_game.png` / `fac2_after_eye.png` / `fac2_after_ends.png`（960×540）。

- **进行到一半**
  - fac2d 批次第 4 张 `fac2_after_close.png`（窗/转角石特写，960×540）没渲完就断电收工了。**所有 Blender 进程已确认结束（`Get-Process blender` = 0）**。
  - `AGENT_HOUSES.md` 的正式交付说明（三条发现 + 完整面数表）还没写，本段是临时状态。

- **未验证的改动（重要，会影响下一次全量构建）**
  - **最后为压面数做的四处削减没有出图验证**：`_gable_dress` 檩条 3 组→2 组、`light` 山墙去掉通风口过梁/窗台、`_flank_dress` 椽头间距 0.62 m→1.70 m、修补块/苔藓/爬藤数量下调。只是删减、不影响正确性，但没有渲染确认。
  - **面数实测来自削减之前**：同参数、同 lab、同种子对比（fac2a 旧代码 → fac2c 新代码，15 栋一一对应）平均 **+836 tris / +406 polys 每栋**；削减后又少约 48 tris，预期 **≈ +790 tris / +400 polys**，这个数是推算不是实测。最差单栋（城市真实尺寸 5.5×8.8 / 2 层）在削减前是 +1268 tris。
  - 6 张成品图只有 5 张齐（缺 close）；其余 480×270 迭代图都在 `renders\kingdom\look\fac2_*`。

- **下一步第一件事**
  1. 480×270 跑一遍确认面数：`python look\export_run.py fac2e 900 LIGHT -- -b --factory-startup --python look\facade_lab.py -- chk all --fast --audit`，再和 `E:\My World\Logs\fac2c.log` 的 per-house 表逐栋对，确认平均 ≤ +800 tris/栋；
  2. 补渲一张 `--big`（960×540/8 spp）的 `close`（约 90 s，单张）；
  3. 把正式交付说明写进本文件（当前状态段可整段替换）。

- **我改过的文件**
  - `E:\My World\Blender\kingdom\hd_houses.py` —— **唯一改动的生成器模块**，签名未变；
  - `E:\My World\Blender\kingdom\look\facade_lab.py` —— lab 场景重写（不参与全量构建）；
  - `E:\My World\Blender\kingdom\look\_fac2_cmp.py` —— 新增，前后对比拼图工具（不参与构建）；
  - `E:\My World\Docs\AGENT_HOUSES.md` —— 本段；
  - `E:\My World\Blender\kingdom\hd_houses_parts.py` —— **未改动**（所有新构件都写在 `hd_houses.py` 里，用的都是 kit 已有的 `P.boxmesh/P.slab/P.bar/P.chimney/...`）。
