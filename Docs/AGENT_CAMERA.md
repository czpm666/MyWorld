# AGENT_CAMERA — 机位与构图（2026-11-02）

> 子智能体：CAMERA。独占 `look/render.py`、`look/spots.py`、`look/contact.py`、`look/shots.json`、`look/_shot*.py`。
> 未改动 `capital.py` / `hd_*.py` / `look/_lock.py`。
> 所有 Blender 调用都经 `look/_lock.py` 的 `run_blender()`（`look/_shotrun.py` 只是它的命令行包装）。

---

## 1. 改了什么、为什么（一条一句）

| 文件 | 动作 | 为什么 |
|---|---|---|
| `look/_shotqa.py` | **新建**（700 行） | 唯一能"不渲染就判断一帧里有什么"的工具：ray_cast 网格 + 材质家族分类 + 实体/站立/视线探针 + 按 kind 的判据。33 ms/射线，336 条 ≈ 11 s/机位。 |
| `look/_shotgrid.py` | **新建** | 从 blend 里真实读出 485 个 `city_blk*` 合并网格的 2D 凸包 → `look/_shotblocks.json`。**没有它，任何选点工具都是在猜。** |
| `look/spots.py` | **重写 v3** | 旧版用 `hd_plan2.build(seed=7)` 在 python 里重建城市再选点；实测重建出 326 街区 / 12922 单元，真实 blend 是 642 街区 / 12215 栋——**它在一个不存在的城市里评分**，所以 pick1 在它眼里"前方 30 m 畅通"，真实世界 2.55 m 就是墙。v3 只读真实几何，并且加了三道旧版没有的闸门：`density`（40 m 窗内实心占比）、`los_eye`（眼高 12 m 每 0.5 m 采样）、四邻地平整度。 |
| `look/shots.json` | **新建** | 33 个验证过的机位库（game 9 / eye 8 / aerial 3 / overview 1 / landmark 12），每条带 `note` 说明"这一帧里应该有什么"。 |
| `look/_shotgen.py` | **新建** | 从实测地图坐标生成 `shots.json`，并把 QA 实测占比回写进 note（`[measured: …]`），所以 JSON 自带证据。 |
| `look/render.py` | 改 | ① `shot_library()` 读 `shots.json` 并入 `shot_table()`；② `--shots all` / `--shots "game_*"` 通配 / `--shots-file`；③ `--weather`（WEATHER 的契约，见 §2.6）与 `--weather-sky`。 |
| `look/contact.py` | **重写** | 旧版只会从 `spots.json` 抖动出 40 个随机游戏机位。现在两种模式：`library`（把整个机位库渲成 320×180 并拼成一张 contact sheet）+ `jitter`（保留）。看 33 帧的成本 = 2 帧全尺寸。 |
| `look/_shotrun.py` | 重写（早前） | 旧版用 `-- @blend` 传参，PowerShell 把 `@blend` 当 splat 解析成空 → 实际跑的是 `blender --python <script>`，**没有 `-b`、没有 blend**，于是所有 ray_cast 都打在默认立方体上（336 条射线只中 2 条）。这就是第一轮"QA 全是 100% sky"的全部原因。 |

### 1.1 简报里那条"人眼机位穿墙"的真实根因

不是 `clearance` 算法错，是**输入数据错**：`spots.py` 旧版重建城市，街区数对不上真实 blend（326 vs 642）。pick1 `(-204,-22)` 在旧版看来是"前方 30 m 空"，实测 **2.55 m 就是 `hd_plaster_c3` 的墙**，人眼高度上还有 4.4 m 高的天花——即机位在建筑体内。

v3 的三道闸门都能单独拦住它：`density`（在实心街区里 den≈0.9 > 0.75）、`los_eye`（12 m 内第 5 个采样点就撞墙）、`spread`（四邻地面高差 1.32 m，说明站在台基上）。实测 v3 的 10 个 eye pick 全部 `los = 40 m`、`spread ≤ 0.9`、`clear 4.4–5.5 m`。

---

## 2. 确切的 API

### 2.1 `look/_shotqa.py` — 构图体检

```bash
blender -b <blend> --python look/_shotqa.py -- --shots look/shots.json --all \
    --grid 24x14 --out look/_qa_shots.json [--ascii] [--seg <dir>] [--raw]
```
| 参数 | 含义 |
|---|---|
| `--shots <path>` | 机位库 JSON（`{"shots":[{name,kind,pos,look,lens\|fov}]}`），或 `render.py` 的 `--list` 风格表 |
| `--names a,b` / `--all` | 选哪些 |
| `--grid 24x14` | 射线网格；**`--res` 是它的旧别名**，改名是为了能和 `contact.py --res 320x180` 共用一条命令行 |
| `--pos x,y,z --look x,y,z --lens/--fov/--kind/--name` | 单个临时机位，不读文件 |
| `--out <json>` | 结果文件 |
| `--ascii` / `--seg <dir>` | 打印/导出每帧的类别图（PNG，20 px/格），用来看"墙在哪一片" |

**返回值（JSON）**：`{"grid":[24,14],"shots":[{name,kind,pos,look,lens,fov,verdict,bad[],warn[],buckets{sky,ground,roof,facade,other},ground_near,detail{},materials{},top_objects[[name,share]],top1_share,nearest{obj,mat,d,z,cls},near3,hit_d_med,hit_z_med,solid{up_hit,ceiling,enclosed,boxed,wedged},stand{ok,stand_h,spread,clear,tight},los{ok,first_hit}}]}`

**判据（`RULES`，可按 kind 调）**
```python
"game":     min_ground=0.10  max_sky=0.40  min_facade=0.10  max_roof=0.85  near_ground=True
"eye":      min_ground=0.06  max_sky=0.45  min_facade=0.12  max_roof=0.80  near_ground=True
"aerial":   min_ground=0.05  max_sky=0.55  min_facade=0.03  max_roof=0.95
"overview": min_ground=0.03  max_sky=0.60  min_facade=0.02  max_roof=0.95
"landmark": min_ground=0.05  max_sky=0.55  min_facade=0.10  max_roof=0.95  near_ground=True
```
硬 FAIL（任何 kind）：`facade > 0.80`（整幅是一面墙）、`roof > 0.90`、`void > 0.18`（黑填充/内部面）、`boxed`（**头顶 30 m 内有顶** ⇒ 相机在实体里）、eye 额外要求 `stand.ok`（1.10–2.30 m 眼高 + 0.75 m 净空）。
WARN：`top1_share > 0.70`（一个对象占了 70% 的命中）、`wedged`（四个水平方向都在 1.6 m 内）、`tight`（眼周净空 < 1.2 m）。

**两个刻意的设计**
- `NEAR_GROUND = 400 m`：`land_terrain` 一个 mesh 同时是"城市铺地底板"和"到地平线的平原"，高机位靠看 2 km 外的田地把 ground 刷到 37%。所以 ground 统计分 `ground`（全部）与 `ground_near`（400 m 内），game/eye/landmark 用后者判。
- **朝向优先分类**：先看面法线 `nz` 再看材质名——`nz>0.80 & z>3.0` 是屋顶，`nz>0.80 & z<3.0` 是地面，`nz<-0.55` 是檐底/挑檐（归 prop），剩下的才看材质名前缀。纯按名字分类会把"屋顶瓦做的地面"和"石板做的屋顶"都算错。

### 2.2 `look/_shotgrid.py` — 真实街区 footprint

```bash
blender -b <blend> --python look/_shotgrid.py          # 约 90 s，读 485 个网格 / 33.99 M 顶点
```
返回 `look/_shotblocks.json`：`{"blocks":[{name,hull:[[x,y],…],z,z0,nv}],"stats":{n,z_p50,z_p90,z_p99,z_max}}`（244 KB）。凸包用 numpy 单调链 + 0.05 m 简化。

### 2.3 `look/spots.py` — 街景选点（纯 python，18–21 s）

```bash
python look\spots.py --want 12 --eyes 10 --out look\spots.json [--blocks look/_shotblocks.json]
```
返回 `{"src":"blend","blocks":485,"stats":{…},"picks":[{score,x,y,ux,uy,w,kind,r,run,back,clear,game_z,eye}],"eye_picks":[{score,x,y,ux,uy,w,kind,r,run,los,clear,eye}]}`。
`picks` 是游戏机位的"玩家位置 + 朝向"，`eye_picks` 是人眼机位。`render.py` 仍然只读 `picks` 的 `x,y,ux,uy`。

**内部核心**（值得知道，因为它是本工具唯一快的地方）：
```python
runs(grid, x, y, dirs, limit, step=0.5)   # (24, N) float32：每个方向第一次被挡的距离
```
24 个方向 × 180 步一次性算完，`-u` 就是 `(i+12)%24`、`+90°` 就是 `(i+6)%24`，所以"背后是否通畅""两侧是否够宽"不需要额外射线。

### 2.4 `look/shots.json` — schema

```jsonc
{"shots": [{
  "name":  "game_avenue_north",     // 唯一，前缀决定种类：game_/eye_/aerial_/overview_/landmark_/extra_
  "kind":  "game",                  // game | eye | aerial | overview | landmark
  "pos":   [-20.93, 619.07, 28.51], // 世界坐标，米。相机位置（不是玩家位置）
  "look":  [0.0, 641.5, 1.0],       // 相机朝向的目标点
  "lens":  35.0,                    // 焦距 mm（水平 sensor 36 mm），与 fov 二选一
  "fov":   30.0,                    // 垂直 FOV 度（game_* 用这个，复刻 Unity rig）
  "yaw":   90.0, "pitch": -52.0,    // 生成器算出的冗余字段，方便 Unity 侧直接读
  "note":  "这一帧里应该有什么 …… [measured: ground 53%, roof 3%, …]",
  // game_* 额外：
  "player": [0.0, 640.0], "heading": [0.0, 1.0], "offset": 20.93,
  "rig": {"pitch":52,"dist":34,"vfov":30,"cam_up":26.79,"cam_back":20.93,
          "lens_equiv_mm":44.8,"source":"Unity TopDownCameraRig.cs defaults"}
}]}
```
- `pos`/`look` 是唯一必需的几何字段；`lens` 与 `fov` 二选一（`fov` 优先，用 `sensor_fit="VERTICAL"`）。
- `note` 里的 `[measured: …]` 由 `_shotgen.py --fold` 从 QA 结果回写，是实测不是设计意图。
- **game_* 的 `pos` 是算出来的**：`pos = (px − ux·20.931, py − uy·20.931, 1.72 + 26.790)`，`look = (px + ux·1.5, py + uy·1.5, 1.0)`。想改构图就改 `player`/`heading` 再重跑生成器，不要手改 `pos`。

### 2.5 `look/render.py` 新增的 CLI

| 参数 | 含义 |
|---|---|
| `--shots-file <path>` | 机位库，默认 `look/shots.json` |
| `--shots all` / `--shots "game_*"` / `--shots a,b` | `all` 展开全部，含 `*?` 的走 `fnmatch` |
| `--tag CAM` | 输出 `CAM_<name>.png` 到 `renders/kingdom/look` |
| `--list` | 打印机位库里所有名字后退出 |
| `--weather <state>` | 见 §2.6 |
| `--weather-sky 0` | 让 hd_weather 保留 hd_sky 的天空（`apply_atmos(sky=False)`） |

`shot_library(path=None) -> {name: spec}`，spec 里 `kind` 只取 `"wide"`（aerial/overview）或 `"street"`（其余），原始种类保留在 `shot_kind`，`note` 原样透传。

### 2.6 `--weather`（按 WEATHER 的契约逐字实现）

```python
apply_weather(scene, name, center=(0,0), ground_z=0.1, radius=200.0,
              extent=1200.0, own_sky=True)
```
顺序固定，不可调换：
1. 本驱动的 rig（`hd_light` 太阳/补光/接触阴影、`hd_sky` 世界、曝光）**先**上；
2. `WX.reset_materials()`；
3. `WX.build(scene, name, MAT, radius=…, center=(cx,cy), seed=9)` —— 雨/雪/水洼/雾团**网格**只有它会建；
4. `WX.apply_atmos(scene, cfg, center=(cx,cy), extent=…, sky=own_sky)` —— 它接管世界、太阳、曝光、`WX_Fog`，并往合成器里插 `WX_Sat`；**此后任何 `build_rig()`/`L.apply()` 都会重建合成器组并静默丢掉 `WX_Sat`**，所以每帧的 rig 必须在它之前建好，之后只允许写 `view_settings.exposure` / `light.energy` 这类属性；
5. `WX.apply_materials(MAT, cfg)`。

`radius/extent` 按机位种类自动选：aerial/overview → `1400/2800`，其余 → `200/1200`。`ground_z=0.1` 是广场石板高度，水洼才坐在石头上。开天气时跳过 `hd_light` 的 haze（否则两套雾叠在一起）。整段包在 try/except 里，`hd_weather` 坏掉只会降级成普通渲染，不会毁掉整张表。只在 EEVEE 路径上开。

### 2.7 `look/contact.py` — 廉价迭代

```bash
blender -b <blend> --python look/contact.py -- --shots look/shots.json --all \
    --tag c320 --res 320x180 --samples 8 --montage 6
```
`--shots-file` 或 `--shots *.json` 都能指定库；`--montage <cols>` 用 numpy + `bpy.data.images` 拼成 `sheet_<tag>.png`（Blender 自带的 python 没有 Pillow）。`--n 40` 则退回 jitter 模式。

---

## 3. 实测数据

| 项 | 数值 |
|---|---|
| `capital_v24.blend` | 860,336,897 B，39,624 对象，30.6 M faces |
| 打开 blend（`-b`） | 13.3 s，峰值 RSS **31.3 GB**（机器空闲 20.1 GB 时也成功了，但这是本项目的硬约束） |
| `scene.ray_cast` | **33 ms/次**（200 次 6.61 s）。336 条射线 ≈ 11 s/机位 |
| QA 31 机位 | 422 s（含 13 s 开 blend） |
| QA 15 个候选 | 229 s（含 85 s 等锁） |
| `_shotgrid.py` | 485 个网格 / 33,990,149 顶点 → 244 KB JSON，约 90 s |
| `spots.py` | 纯 python 18–21 s，栅格 3483×3483 @0.62 m，46.3% 实心 |
| contact sheet 33 帧 @320×180/8spp | 见 §4 |
| 最终验收 960×540/24spp | 见 §4 |

---

## 4. 产出图片 + 每张一句判读

（本节在验收渲染完成后回填；路径统一为 `E:\My World\Blender\renders\kingdom\look\`。）

---

## 5. 还剩什么问题

1. **`hd_river.py:286` 的 `bridge_rib` 位置 bug**（不归我改，见 §6）。24 根桥腹石带躺在广场中心 `(0, ±63)` 而不是桥下，于是**每个广场镜头前景都横着一条 1.1 m 高的石带**。`eye_plaza_south` 原来就正好站在它上面（`stand_h 1.01 m` → 被判"站不住"），我把它挪到 `x=-14` 绕开了，但石带还在画面里。
2. **52°/FOV30 的 rig 不可能同时"看得见街"和"屋顶占 50–90%"**。推导：画面上边缘在地平线下 37°、下边缘 67°，相机高 27.79 m，所以高度 z 的点可见 ⟺ `0.7536 ≤ (27.79−z)/d ≤ 1.884`。z=13 m 的屋顶只在相机前 **7.8–19.6 m** 内可见；而相机在玩家**后方 20.93 m**。实测 9 条 game 帧全部是街 40–68% / 屋顶 3–21%。这不是 bug，是镜头决定的；简报 §6 那条"屋顶是第一表面，占 50–90%"应当理解成"更陡的俯角或更贴近屋脊"的情形，或者接受 game 帧就是街道为主。
3. **机位库和 build 绑死**。`shots.json` 的所有坐标都是在 `capital_v24.blend` 上量的。`build_v25` 正在重建城市（街区数会变），**v25 落地后必须重跑** `_shotgrid.py` → `spots.py` → `_shotgen.py` → `_shotqa.py`，`game_street_*`/`eye_street_*` 会整体换位置（8 个 landmark/avenue 机位用的是保留区和实测地标坐标，不会动）。
4. **`eye_*` 只能站在保留区里**。城里唯一"地面可证明没有房子"的地方是 `_reserved()` 划出来的广场/市场厅前/教堂前/公会前/城堡坡道。所以 6 个 eye 机位有 4 个是地标正面的广场照，只有 2 个 `eye_street_*` 来自实测街巷。想让 eye 机位更"街"，需要 build 侧提供"街道走廊"的保留记录（`hd_plan2` 有 63 条街，但没有导出成 spots 能读的形式）。
5. **`game_street_roof` 是 WARN 不是 PASS**：一个 `city_blk62` 占了 70% 的命中。密集街区的合并网格必然如此，这个 WARN 应视为信息而不是缺陷。
6. QA 的 `top1_share`/`near3` 阈值是按这 46 个机位定的经验值，换城市尺度要重标。
7. `_shotqa.py` 的 `void` 家族（`hu_void`/`mkt_void`/`castle_shadow`）只在相机进入实体内部时才会占到大比例，正常帧里几乎为 0——它是"相机在实体里"的强信号，不要删。

---

## 6. 需要主 AI 插的代码（逐字）

### 6.1 `hd_river.py:286` — 桥腹石带位置错（一行，改 3 行）

现在：
```python
        out.append(_box(K, "bridge_rib%d" % k, (u0 + u1) * 0.5 * ca, (u0 + u1) * 0.5 * sa,
                        deck_z((u0 + u1) * 0.5) - 0.42,
                        (u1 - u0) * 1.02, BRIDGE_WIDTH, 0.36, MAT["stone"]))
```
问题：`bridge()` 的局部坐标是 `W(u, v, z) = (cx + u*ca − v*sa, cy + u*sa + v*ca, z)`，同一函数里 `bridge_deck` 用 `W(...)`、`bridge_pier` 用 `cx + u*ca`，**只有 `bridge_rib` 漏了 `cx`/`cy`**，于是以世界原点为桥心。本城桥心是 `(0, −762)`、`ang = π/2`，所以 24 根石带正好落在广场中心 `(0, ±63)`。另外 `_box` 的长边固定沿世界 X，而这里的桥沿 Y，`sx/sy` 也是反的。

建议改成（对本城 `ang = π/2` 与 `ang = 0` 都正确）：
```python
        um = (u0 + u1) * 0.5
        out.append(_box(K, "bridge_rib%d" % k,
                        cx + um * ca, cy + um * sa,
                        deck_z(um) - 0.42,
                        abs((u1 - u0) * ca) + BRIDGE_WIDTH * abs(sa),
                        abs((u1 - u0) * sa) + BRIDGE_WIDTH * abs(ca),
                        0.36, MAT["stone"]))
```
（更干净的做法是用 `W()` 造 8 个顶点、跟 `bridge_deck` 同一个坐标系；但那是 20 行，上面这版是 3 行且本城够用。）

### 6.2 `capital.py` — 没有必须插的代码

`spots.py` 需要的两个输入都不在 `capital.py` 里：街区 footprint 来自 blend（`_shotgrid.py` 读 `city_blk*`），保留区由 `spots.py` 自己按 `_reserved()` 的数值重画。如果以后想省掉 `_shotgrid.py` 那 90 s，可以在 `capital.py` 建完城后顺手把每个 `city_blk` 的凸包写进一个 sidecar JSON（`look/_shotblocks.json` 的 schema 见 §2.2），但**不要**改成让 `spots.py` 重新跑 `hd_plan2.build()`——那正是这次 bug 的来源。
