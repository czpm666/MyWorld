# Landscape pass — the world outside the walls of Ars

Owner: landscape agent.  Files owned: `Blender/kingdom/hd_landscape.py`,
`Blender/kingdom/look/land_lab.py`.  Nothing else was edited.

---

## 1. What this replaces

| before | after |
| --- | --- |
| `ground_outer` — 150-face flat disc, x/y ±980, z=-0.35, `grass_dry` | a 361×361 heightfield over 7.2 × 7.2 km + 60 adaptive ridge rings out to 23 km |
| 22 × squashed UV spheres named `hill0..hill21` (`hill_far`) | layered ridged-fbm mountain ranges: near foothills at 1.6 km, massifs at 2.4–4.7 km, a far wall at ~9 km, snow above 1450 m, forest to 860–1060 m |
| 52 `field*` + 52 `hedge*` flat boxes at radius 700–950 | ~600 BSP parcels, 60–200 m, each with its own crop colour, bounded by 3–5 m hedgerows with hedgerow oaks, or dry-stone walls |
| no water outside the wall | a river from the western mountains, past the city, out to the south-east, two stone bridges, a lake |
| 4 short `road_out*` stubs | those stubs continued as 4 curving earth roads that cross the river at bridges and disappear into the hills |
| nothing | 4 hamlets (31 cottages), a chapel, a farmyard, a watermill, a windmill, a ruined tower, 2 bridges |

Everything is deterministic from `seed`.

## 2. API

```python
import hd_landscape

hd_landscape.strip_old()                    # drop disc, hills, flat field decals
info = hd_landscape.build(MAT, res=20.0, seed=1337)
# info -> {"objects", "count", "faces", "tris", "verts", "seconds",
#          "ram_mb", "peak_mb"}

hd_landscape.height(x, y)                   # scalar
hd_landscape.heights(xs, ys)                # vectorised
```

* `MAT` is `capital.py`'s material dict.  Any key it does not have is resolved
  by name against the .blend (e.g. `grass` → `grass_dry`), and if that fails a
  plain Principled material is generated — so `build({})` works in a cold
  Blender with no city materials at all.  **Never re-run `init_mats()`** before
  this or you will get `.001` duplicates.
* `res` is the **terrain cell size in metres**, not a quality multiplier:
  `20.0` ships, `40.0` drafts in half the time, `10.0` is a hero still.
* `opts`: `town=`, `fields=`, `woods=`, `rings=`, `water=` booleans to build
  only part of the world (the lab uses these to isolate artefacts).
* Two new materials are created inside the module and only inside it:
  `land_ground` (one material for terrain, fields, roads, verges — it reads a
  per-vertex `Col` attribute and fades to haze with distance) and `land_water`.

Wiring into `capital.py:build()`, after the city and after `init_mats()`:

```python
import hd_landscape
hd_landscape.strip_old()
info = hd_landscape.build(MAT, res=20.0, seed=1337)
```

## 3. Measured (cold factory Blender, no .blend)

`build({}, res=20.0, seed=1337)`:

* **109 objects**, **611 373 faces**, **1 034 058 triangles**, 706 138 verts
* **30 s** wall clock (terrain 5 s, ridges 3 s, fields 6 s, woods 5 s,
  buildings 9 s, roads/water 2 s)
* peak RSS **not measurable from inside Blender** — the `PROCESS_MEMORY_COUNTERS`
  ctypes call returns 0 in this build; measure from outside if you need it.
  The build never holds more than one numpy array of the full grid plus a
  ~1 GB vertex buffer, so expect 1.5–2.5 GB.

Budget headroom: 109/400 objects, 1.03M/6M triangles.

## 4. How the pieces work

**Terrain.** One uniform 20 m grid, `[-3600, 3600]²`, z from a sum of
domain-warped ridged fbm bands × per-bearing strength, then a river carve, then
a plateau guard that forces `z = -0.14` inside r = 620 and blends to 0 by 690.
The 700 m disc the brief protects is therefore provably untouched (verified at
16 bearings: exactly -0.140 inside, 0.000 at r = 700).  Beyond 3.6 km the grid
is continued by rings whose loop vertices coincide exactly with the boundary
loop — no cracks, no T-junctions — with radial spacing chosen from the local
gradient (`26 m` minimum on a mountain face, up to `900 m` over flat ground).

**Colour.** Per-vertex `Col` written in numpy: meadow/scrub/forest patches,
farmland warmth near the city, rock on slopes above 0.72 and on high ground,
snow above 1450 m with noise jitter, river silt.  `land_ground` multiplies it
by broad noise and overlays fine grain, then fades toward haze from 3 km to
13 km (max 0.46) for aerial perspective.

**Farmland.** A rotated 16° square is BSP-subdivided into non-overlapping
rectangles; leaves are filtered by radius (902–2600 m), slope, altitude, forest
mask, road distance and river distance.  Each leaf is a conforming quad grid
0.10 m above the terrain with a per-field crop tint and row stripes for wheat
and plough.  Hedges live only on each field's north and west edges, so every
internal boundary is drawn exactly once; oaks are dropped along the longer
runs.  Farmland thins out stochastically between 1700 and 2550 m instead of
ending on a circle.

**Water.** The river is a Catmull-Rom ribbon; its surface level is derived from
the terrain (smoothed *and* rolling-minimum over ±120 m, sunk 1.6 m) and forced
monotone-descending so it can never run uphill or lake over a flat plain.  The
channel is a V-carve confined to 170 m outside the half-width.  Bridges measure
the actual open-water width along the deck axis and size themselves to it —
that is what makes them land on both banks.

**Woods.** A 30 m jittered grid whose keep-probability comes from the same
`_forest_mask` field the terrain colour uses, so painted forest and instanced
forest agree.  Kept out of fields (rotated-box test), roads (11 m), the river
(26 m) and the lake; thinned above the 860–1060 m tree line.

## 5. Verification renders

`Blender/kingdom/look/land_lab.py` builds a **stand-in city** (flat disc,
20-gon wall, 900 roof boxes) because `capital_v23.blend` must not be opened
(474 MB, ~10 GB RAM, and this machine already BSOD'd once).  Every image below
therefore shows a crude placeholder where the 9 532-house city will be — the
landscape around it is real and is what should be judged.

```
blender -b -P look/land_lab.py -- --shots p_wide,p_aerial2,p_pan,p_river,p_eye,p_aerial \
                                  --samples 32 --res 960x540
```

| shot | frame | what it tests |
| --- | --- | --- |
| `p_wide` | (420,-2700,1150) → (0,600,300), 26 mm | whole basin: range, valley, patchwork, city in landscape |
| `p_aerial` | (700,-1240,480) → (0,20,15), 50 mm | the frame requested by the parent |
| `p_aerial2` | (1020,-1980,640) → (-40,220,90), 32 mm | back off far enough to include the skyline |
| `p_pan` | (-1560,-980,260) → (1200,900,420), 30 mm | panorama at 90° to the sun |
| `p_river` | (-1230,-235,96) → (-1000,0,6), 50 mm | bridge, banks, water colour |
| `p_eye` | (-40,1490, ground+1.72) → (0,0,26), 35 mm | eye level on the north road, city in the distance |

Renders land in `Blender/renders/kingdom/look/`.

## 6. Known limitations / what I could not do

1. **The stand-in city.** I cannot open `capital_v23.blend` under the new rules,
   so the city in every image is a placeholder.  The parent should re-shoot the
   six frames against the real city — the lab already accepts `--no_city`.
2. **Peak RAM is unmeasured** (ctypes struct fails inside Blender).
3. **Farmland stops at r = 902 m** and there is a bare ring between the wall
   (640 m) and the first fields.  In the real scene the `sub*` suburbs occupy
   674–868 m, so the visible gap is ~30 m — acceptable, but if the suburbs ever
   move, `_fields()`'s lower radius bound is the knob.
4. **Buffers are flat-shaded plates.** Hedgerows and oaks are sub-pixel above
   ~1 km, so from high altitude the patchwork reads as a quilt rather than as
   3D banks and ditches.  I widened the hedges to 3–5 m and scattered 9–17 m
   oaks along them to compensate; a displacement map would be the next step.
5. **The eastern and south-eastern bearings are deliberately lower** (the river
   has to leave somewhere).  They read as wooded hills, not as alps.  The north
   and west read as a proper snow-capped range.
6. **No paths inside the farmland** other than the four radial roads and the
   tracks the hedgerows leave between fields — a network of footpaths and a
   ford would be the next addition.
7. **The city's own river is buried** under `ground_town` (a r = 642 disc at
   z = 0 covers the `river` box whose top is at z = -0.1), so the harbour
   district, its quay and its boats are invisible.  This is a pre-existing
   defect in `capital.py`, not something my module can fix.  Reported.

## 状态（2026-11-02 15:45 断电前）

第二轮地形返工（v25a 之后，用户嫌"农田像打翻的调色板、远山是绿糊块"）。
迭代全部在 `look\land_lab.py` 冷启动 lab 里做，从没碰过任何 `capital_*.blend`。

### 已完成（都已渲染验证）
- **`hd_landscape_fields.py` 的四边形索引 bug（最严重的一项）**：`emit()` 用
  `a = j*(nu+1) + i` 拼顶点，但 `_grid()` 是 `np.meshgrid(us, vs, indexing="ij")`
  展平的（步长应为 `i*(nv+1)+j`）。只有正方形地块两者才巧合相等，所有非方形地块
  都把四边形接到错误的角上，渲染成一扇黑色碎片。之前看到的"农田上的尖刺"就是
  这个，不是配色问题。已改成 `a = i*(nv+1) + j`。
- **硬边**：`LIFT` 0.40 → 0.12（那 0.4 m 台阶加它自己的影子就是"尺子画的边"）。
- **配色**：`P` 调色板整体重切成低饱和土色系；`_ground_col` 里原来的
  "farmland warmth 14 %" 换成 4 档 `fbm` 拼布（stubble/fallow/pasture/hay）。
  地块颜色改用 `k2 = (0.155/lum)**0.72` 加 `TONE` 作物高度权重
  （wheat 1.12 / rapeseed 1.18 / plough 0.74 …），明度先分、色相后分；
  每个地块加逐顶点斑驳 `0.92+0.16*random`。
- **地块尺寸层级**：`_tgt(r) = 44 + 128*((r-250)/2150)**0.72` 让远处地块变大，
  另加 `_strips()` 把 42 % 的大地块切成 3–6 条条田；BSP 早停 34 %。
- **田界**：districts 新增 `ditch`（`_ditch()`，3.5 m 六点剖面，槽底压暗到 0.52）；
  敞开的长边 14 %→5 %、短边 55 %→26 %；树篱加宽到 3.0–5.0 m。
- **远山**：`_relief` 加径向蜿蜒、山脊 crest 指数提到 1.65；`SNOW_Z` 1450→1600；
  `_ground_col` 重写 rock/strata/snow；`mat_ground` 里**删掉了全局绿色乘数
  `(0.60,0.85,0.68)`**（它把石灰岩和雪变成橄榄色），并新增**着色器端的岩层+雪线**
  （见下）。
- **大气透视**：三个 bug 一起修好了 —— (a) 旧的 fade 被 `_view_dist` 和世界半径
  重复连线，后连的赢，所以按"离城中心的半径"而不是"离相机"算；(b) `HAZE`
  (0.556,0.635,0.722) 是**显示用天空色**，当反照率混进去会让远山比天空还亮，
  就是那层白石膏 —— 新增 `HAZE_A = HAZE*0.28`；(c) `mat_leaf/stone/track` 原本
  完全没有 fade，远山侧壁一直是饱和绿。现在统一走 `_air()`，按世界半径 5 档
  (0.5→16 km) 淡向 HAZE_A。

### 关键的架构决定（重要）
岩层和雪线**从顶点色移到着色器里算**（`mat_ground` 末尾新增块）：顶点色受网格
分辨率限制，3.6 km 以外的 ridge ring 采样间距 100–200 m，330 m 周期的岩层采样
下来就是噪声 —— 这正是远山渲染成"灰色橡皮泥"的原因。`mat_ground` 现在用
`Geometry.Position.z` + `Geometry.Normal.z` 直接画：岩层 = `sin(z*0.019 +
fold*3.4)` 过一个 4 档 ColorRamp（0.052→0.196），坡度/海拔掩码控制岩石，
`SNOW_Z` 硬边 1530→1640 m 加 340 m 噪声抖动、只落在法线朝上的面上。
**这一步是有效的**：`a_wide` 里 3–13 km 的山体现在能看出岩层、雪斑和前后层次了。

### 进行到一半
- 远山细节只做到"能看出层次"，还没到用户要的"山脊线/岩石露头/三层分明"。
  `a_mount`（90 mm 特写，2.4→6.2 km）看上去仍偏光滑 —— 但那是因为这个视角
  完全在雪线以下、且是 90 mm 贴脸看 ridge ring，不是验收视角。
- 近郊过渡带（60–190 m FLAT_IN/FLAT_OUT 的菜园/果园/柴垛/羊圈/引水渠）**没动**。
- 河流的河岸/浅滩/弯道**没动**（`p_river` 里根本看不到水：`abs(x)<1080` 段由
  `hd_river.py` 负责，不归我）。

### 未验证的改动（重要）
- 最后一次改动（着色器岩层 + `_ground_col` 岩石项 0.66→0.30 + strata 0.052→0.019）
  只跑过 `a_mount/a_wide/a_farm` 三张 480×270 小图，**没跑过 960×540 验收图**，
  也没在 `capital.py` 的真实合成场景里验证过。
- **没有测过最终 `build()` 的耗时和峰值内存**。最后一次完整构建实测：
  `301 objects, 4,540,207 faces, 4,898,450 tris, 19.8–21.3 s, ram 1072/1153 MB`
  （基线是 257 地块 / 2.33 M 面 / 10.8 s / 776 MB）。面数翻了近一倍，离 <40 s /
  <8 GB 还有余量，但需要复测。
- 农田 `a_farm` 里地块偏浅、地块之间的裸地偏深，还没调平。

### 下一步第一件事
1. 重跑一次 `ast.parse` 全模块 + 一次冷启动完整构建，确认没有半截文件。
2. 按上面的"下一步"继续：先把农田地块和裸地的明度调平（`_ground_col` 的
   `c*0.46` 与 `k2` 的 0.155 目标值对齐），再出 960×540 验收图。
3. 近郊过渡带和河流两项还没开始。

### 我改过的文件
- `Blender\kingdom\hd_landscape.py`（调色板、`_relief`、`_ground_col`、`SNOW_Z`）
- `Blender\kingdom\hd_landscape_mat.py`（`_air`/`HAZE_A`/`AIR_STOPS`、删绿色乘数、
  着色器岩层与雪线、`far340`/`far26`）
- `Blender\kingdom\hd_landscape_fields.py`（索引 bug、`LIFT`、`TONE`、`k2`、
  `_tgt`/`_strips`/`_bsp`、`_edges`/`_ditch`、斑驳）
- 新建 `Blender\kingdom\look\_t_probe.py`（我的临时探针，不需要 Blender 就能
  采样地形高度/反照率/雾，出 `Logs\probe_*.png`）
- 验收图**还没出**（`land2_` 前缀的 4–6 张 960×540 未生成）。
