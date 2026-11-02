# AGENT_WEATHER — 天气系统 / 空气感（2026-11-02）

子智能体 WEATHER。文件范围：新建 `hd_weather.py`（主战场）、`look/weather_lab.py`、
`hd_weather_sheet.py`、`hd_weather_probe*.py`；**没有**碰 `capital.py`、`hd_sky.py`、
`look/render.py`、`look/spots.py`、`look/contact.py`，没有打开任何 `capital_*.blend`。
所有 Blender 调用都走 `look/_lock.py` 的 `run_blender()`。

---

## 1. 改了什么、为什么

| # | 改动 | 一句话原因 |
|---|---|---|
| 1 | 天气做成**纯数据的状态机**：`PRESETS` 8 态 → `state(name, **over)` → 一个扁平 dict，Blender 之外也能跑 | 同一份参数要同时喂 Blender 和 Unity；`python hd_weather.py table` 不开 Blender 就能校验全部 8 态 |
| 2 | `visibility_km` **不再手写**，由 `fog_density`/`fog_height` 反算（`T(d) = exp(-∫σ)`，取 5% 对比度） | 旧的预设里出现过"声明 20 km、参数算出 5 km"的自相矛盾；现在预设撒不了谎 |
| 3 | 雨/雪用**真实小 mesh + 一次烘焙合并**（`WX_RainNear/Far`、`WX_SnowNear/Far`），不用粒子系统 | 要能原样导出 Unity；一个 field 一个 object，对象数稳定 ≤ 8 |
| 4 | 雨丝按**视距等比放大**：`L = max(0.85, 0.055·d)`、`W = max(0.022, 0.0026·d)` | 固定 0.85 m 的雨丝在 2 m 处是 180 px 的白墙、在 60 m 处是 2 px 看不见。等比之后任何距离都是 ~20 px，雨在任何构图里都成立 |
| 5 | 近场雨/雪改成**沿 eye→look 的截锥采样**（`_cone_sampler`），不是球壳 | 均匀球壳 ~90% 的三角面在画面外、且落在镜头背后；截锥把预算全压在画面里 |
| 6 | `build(..., look=)` + `weather_lab` 从相机矩阵取视轴 | 52° 俯视的玩家机位看不到地平线，雨必须在**镜头正前方**；只给 `eye` 时旧的锥体朝着地平线打，雨全在画外 |
| 7 | 湿材质用**世界坐标**的 `NewGeometry.Position` 取噪声（Scale 0.055 ≈ 18 m 水洼） | 原来用 `TexCoord.Object`，在 340 m 的地面上噪声周期只有 3 m → 整块地板一个均匀灰 |
| 8 | 湿的**决定性旋钮是 roughness**，不是 F0：`pud=0.24`、`damp=max(0.48, min(0.68, rough*0.72))`、Specular 由 `spec` 降到 `spec*0.55` | 大平面在掠射角下无论 F0 多小都会反射天空；压不住 roughness 就永远是一片镜面湖 |
| 9 | 只对 **地面/屋顶/石材** 生效：白名单 `_ALLOW`（stone/tile/slate/cobble/flag/ground/plaster/bark/leaf…）+ 黑名单 `_SKIP`（glass/water/banner/iron/glow…） | 布里要求"只对地面/屋顶/石材"；玻璃、水、旗子、灯火不能跟着变湿 |
| 10 | `apply_materials` 把调用方 dict 与**场景里真实挂着的材质**求并集（`_scene_materials()`） | 这是"雪落满了屋顶却一块都不白"的真正原因：`capital_hd_glue.house_mats` 另外造了 16 个per-roof 材质，不在调色板 dict 里，于是雪一个屋顶都没摸到 |
| 11 | 积雪权重用 `|Normal.Z|` 而不是 `Normal.Z` | 屋顶是 52° 坡，`|n.z|=0.61`；只要 mesh 法线翻过一次，带符号的 z 就变负，雪量归零。取绝对值后正反两种法线都吃得下 |
| 12 | 天空走 `hd_sky.world(preset, **over)`，**不要**再叠 `hd_light.haze` | 两套体雾叠在一起密度翻倍，远景全白；`apply_atmos` 会先删掉 `Atmosphere*` 再建自己的 `WX_Fog` |
| 13 | 补光：`apply_fill()` 调 `hd_light.bounce(preset, energy_mul=cfg["bounce_mul"])` | 我只建了太阳没建 bounce 卡，所有阴影面比正常暗 3 档——"天气在**打光**，不是**压暗**" |
| 14 | `apply_post` 的节点串接**按名字**判重、幂等 | `is` 判断在 bpy 里永远不成立（每次属性访问给新的 wrapper），第二次调用会把 `WX_Sat` 的输出接回它自己的输入 → 自环 → 整帧全黑 |
| 15 | 闪电 = 真几何折线 + 一盏 `WX_FlashSun` + 曝光抬升 `0.55·flash` | 需求里的"曝光帧"是一个参数：`flash` 0→1 同时驱动折线亮度、补光强度和曝光 |
| 16 | 彩虹 `_rainbow_mesh` 放在 **`sun_azim` 方向**（不是反方向），`dist=430 m`，七色走顶点色 | `sun_azim` 在本代码库里是**光传播方向**，太阳在 `azim+180`，彩虹在 `azim`；且材质必须 `vcol=True`，否则就是一条白弧 |

---

## 2. 确切的 API

```python
ORDER = ("clear", "hazy", "overcast", "rain", "storm", "fog", "snow", "sunshower")
PRESETS          # {name: dict}，8 个；每个都是 BASE 的全量覆盖
BASE             # 全部键的默认值（含 16 个必填键 + 几何/材质用的扩展键）

state(name, **over) -> dict
```
返回一棵**完整**的参数字典（`BASE` ← `PRESETS[name]` ← `over`），并派生
`_wind_speed / _wind_azim / _rain_tilt / visibility_km / _vis_m / grade_preset`。
必填的 16 个键：`sun_energy / sun_color / sun_elev / sun_azim / sky_preset /
fog_density / fog_height / fog_color / exposure / saturation / wetness /
snow_cover / wind / particle_kind / particle_rate / flash`。
`wind` 是 `(speed_m_s, azimuth_deg)` 二元组。

```python
build(scene, name, MAT=None, center=(0, 0), radius=1200, seed=9,
      eye=None, ground_z=0.0, look=None) -> {"objects": [...], "cfg": {...},
                                             "objects_n": n, "tris": n,
                                             "assets": {...}, "materials_changed": n}
```
建一个天气态的全部几何：雨丝/雪花/涟漪/水洼/雾团/闪电折线/彩虹。
`name` 可以是状态名，也可以是 `state()` 返回的 dict（推荐后者，能带 over）。
`center` 是天气场的中心 `(x, y)`，**传镜头枢轴，不要传世界原点**。
`radius` 只用来定远场雨幕的半径。`eye` 是相机位置（billboard 与雨丝取向要用），
`look` 是相机瞄准点（近场截锥的轴线）。`MAT` 给了就顺手调一次 `apply_materials`。
会先 `clear()` 掉上一场的天气物体，所以连续调用不会叠加。

```python
apply_atmos(scene, cfg, center=(0, 0), extent=None, flash=None, sky=True) -> dict
```
**一次装完所有"大气"**：世界天空（`hd_sky.world`）+ 太阳（`WX_apply_sun`）+
补光（`apply_fill`）+ 闪电（`apply_flash`）+ 体雾（`apply_fog`，物体名 `WX_Fog`）+
曝光/饱和（`apply_post`）。`extent` 是雾盒半宽，缺省 `max(1200, 2.4*radius)`（`build` 记下的）。
`sky=False` 保留调用方已经建好的世界。

```python
apply_materials(MAT, cfg) -> int          # 返回被改的材质数
reset_materials(MAT=None) -> int          # 还原成建材质时的样子
wet_material(mat, wetness) -> bool        # 单材质，湿
snow_material(mat, cover) -> bool         # 单材质，积雪
```
`MAT` 可以是 dict、list 或 `None`；**总会与场景里实际挂着的材质求并集**。
幂等：重复调用只改系数，不会越插越多节点。

```python
sway(objects, cfg, t=0.0, factor=1.0) -> int
```
按 `cfg["wind"]/gust` 摆树/旗（绕物体原点摇，`build` 前用 `H.apply` 把原点压到树根）。

```python
clear() -> None
```
删掉本次 `build` 建的所有 `WX_*` 物体（不动灯、相机、体雾）。

```python
to_unity(cfg) -> dict        # 扁平、float 截 4 位，给 Unity 的 ScriptableObject
dump_json(path=None)         # 8 态全量 → renders/kingdom/look/weather_presets.json
visibility(cfg, eye=1.7, at=0.05) -> m
transmittance(cfg, dist, eye=1.7) -> 0..1
report(cfg) -> dict          # 一行统计（表里那些数就是它算的）
```

---

## 3. 实测数据

（见 §3 表格，由 `look/weather_lab.py` 自己写进 `_wx_stats.json`；下面是从该文件读出的实测值。）

<!--STATS-->

---

## 4. 图片

<!--IMAGES-->

---

## 5. 还剩什么问题、下一步建议

<!--TODO-->

---

## 6. 需要主 AI 插的代码（逐字）

<!--WIRE-->

---

## 状态（2026-11-02 15:45 断电前）

- **已完成**
  - `look/weather_lab.py` 重写完毕（513 行，`ast.parse` 通过）：lab 现在直接调 `render.build_rig("morning_town", …, haze=False, ambient=0.38, exposure=-2.20)`，即**主渲染的同一条管线**（`hd_sky.world` + `hd_light.sun/bounce/contact` + `hd_light.post`），并在每态后强制 `view_settings.exposure = -2.20`，复刻 `render.py:apply_weather` 里 CLI 曝光覆盖预设的行为。另有 `--rig hdsky`（brief 的短配方）和 `--rig none`（旧 lab）两个 A/B 模式。
  - **基线结论（已实测，推翻原假设）**：旧 lab 与主渲染的亮度差只有 **0.04 档**（clear：lab mean 55.7 / p50 34.3 vs main mean 54.1 / p50 32.2，同为 -2.20 曝光）。`WX_accept_clear/rain` 暗 2 档**不是基线问题**，是①accept 机位 52° 俯视、画面 80% 是 `#5d5649` 深石板地面（城市参考 `V24_gate` mean 89.9 / p25 71.7、`V24_plaza` 110.6）②rain 预设自己的曝光 -1.92 且天空/太阳过暗。
  - 新增 `hd_weather.py` 机制 **`sky_fill`**（`_sky_fill()`，BASE 键 `sky_fill=0.0`，`apply_fill` 里第一件事）：在镇子上空 62 m 放一张 1700 m 朝下的 AREA 灯（无阴影/无镜面/不可见），功率 = `sky_fill × hd_light.BOUNCE_W_PER_RATIO`，色取 `fog_color`。原因：`hd_light.bounce()` 的补光在 z=0.30 **朝上**，只照檐口车底，照不到 52° 相机看的铺地与墙面——这才是"背光面近黑"的物理原因。fill→亮度线性（accept 机位 clear gnd_p25：0→26.4、0.15→29.3、0.30→32.2、0.45→34.5），且几乎不动太阳高光（p50 74.2→77.1）。
  - rain 预设已重写成"明亮湿午后"：太阳 4 W / 38° / angle 16，天空 `#8f9aa6`→`#6d7a8a`、`gain 11.5 ambient 0.86`，雾 0.00075/220 m、`#b8c2ce` 级灰蓝，`exposure -2.05`、`wetness 1.0`、`puddle 0.8`、`ripple 1.2`；雨丝长度改为 `min(1.10, max(length, 0.030*dist))`（≈1.7° 恒定视角），水洼 roughness 0.04 / 高光 1.0，涟漪按距离定尺寸（3–8 px 而非 40 px 白圈）。
  - **8 态全表已跑出**（480×270 / 8 spp / wide 机位 / 全部 -2.20，83.7 s，日志 `Logs/wx8.log`，表在 `renders/kingdom/look/_wx2_table.md`）：

| weather | sky | shadow | gnd_p10 | p50 | dead% | vis_km | 粒子覆盖% |
|---|---|---|---|---|---|---|---|
| clear | 178.2 | 31.1 | 22.9 | 104.7 | 0.47 | 20.01 | 0.00 |
| hazy | 181.9 | 56.1 | 45.0 | 131.1 | 0.00 | 4.50 | 0.01 |
| overcast | 174.9 | 43.3 | 36.2 | 79.8 | 0.04 | 3.36 | – |
| rain | 159.6 | 30.0 | 23.9 | 55.3 | 0.31 | 4.03 | 7.90 |
| storm | 104.7 | 96.9 | 79.9 | 116.7 | 0.00 | 2.44 | 19.65 |
| fog | 156.4 | 119.6 | 111.1 | 145.5 | 0.00 | 0.06 | 0.00 |
| snow | 184.0 | 82.4 | 68.0 | 148.0 | 0.00 | 1.90 | **0.03** |
| sunshower | 169.9 | 68.9 | 45.8 | 109.8 | 0.00 | 5.06 | 10.14 |

- **rain / clear 的亮度实测值（用户要的两个数，改前）**
  - clear：sky 178.2 / **shadow 31.1** / gnd_p10 22.9 / p50 104.7 / dead 0.47%（目标 shadow ≥35，差 4）
  - rain：sky 159.6 / **shadow 30.0** / gnd_p10 23.9 / p50 55.3 / dead 0.31% / 雨丝画在 7.9% 的像素上（+1.23 luma）
  - 对照：旧版 accept 机位 clear mean 55.7（城市 `V24_gate` 89.9）；现在 wide 机位 p50 104.7 已经**亮过**城市参考，剩下的是暗部不够（shadow 30 vs 35）。

- **进行到一半**
  - 上面三个低值/反向项已改数值但**没有重跑验证**（见下一条）。
  - `AGENT_WEATHER.md` 的 §3 实测数据 / §4 图片 / §5 TODO / §6 接线 仍是占位符 `<!--STATS-->` 等，未填；8 张 `wx2_*.png` 是改动前的 480×270 版，最终 8×640×360 + 2×960×540 还没出。

- **未验证的改动（重要，断电后第一件事就是跑一轮 `--fast` 验证这三条）**
  1. `clear.sky_fill 0.62→0.85`、`rain.sky_fill 0.36→0.50`（目标：把 shadow 从 31.1 / 30.0 推到 ≥35；按 fill 线性响应估算 → 应到 ≈36 / ≈34）。
  2. `storm.sky_fill 0.30→0.12`：storm 原来 shadow 96.9 > sky 104.7，地面比天空亮，读成"灰阴天"。**同时发现并修掉第二个原因**：`apply_flash` 给静帧留下 `140×flash = 77 W` 的补光灯（storm flash 0.55），等于多一盏太阳；`weather_lab.cast()` 现在默认 `flash=0.0`（静帧取"两道闪电之间"），`--flash 0.55` 才渲染闪电帧。
  3. 雪：`snow.flake_size 0.150→0.175`；BASE 新增 `flake_alpha=0.78`、`flake_emit=0.9`；雪片材质从 `(0.72,0.76,0.82)/alpha .78/emit 0` 改为 `(0.88,0.92,0.98)` + 可配 alpha/emission。原因：雪片画上去但对比度不够（在 148 亮度的雪野上灰雪片 Δluma<6），粒子覆盖只有 0.03%。
  4. EEVEE 报过 `Error: Shadow buffer full (4681/4096)`（出现在最后一张之后，8 次）；没来得及在 lab 里调 `scene.eevee.shadow_pool_size`（5.2 属性名未确认）。图片本身阴影正常，但重跑时要盯这个。

- **下一步第一件事**
  `cd E:\My World\Blender\kingdom && python look\export_run.py wx8 900 LIGHT -- -b <lab.blend> --python look/weather_lab.py -- --fast` → 读 `_wx2_table.md`，确认 clear/rain shadow ≥35、storm shadow 明显低于 sky、snow 粒子覆盖 >1%。然后再出最终 8×(640×360) + 2×(960×540 `--game`)，最后填 §3/§4/§5/§6 与 Unity 字段说明。

- **我改过的文件**
  - `E:\My World\Blender\kingdom\hd_weather.py`（BASE +`sky_fill` / +`flake_alpha` / +`flake_emit`、新 `_sky_fill()`、`apply_fill` 改序、`build()` 记 `_ground_z`、`_rain_field` 长度公式、`_splash_field` 尺寸、雨溅/水洼材质、`wet_material` 提亮、雪片材质、clear/rain/storm/snow 预设数值）
  - `E:\My World\Blender\kingdom\look\weather_lab.py`（整篇重写 + `FLASH` 与 `--flash`）
  - `E:\My World\Blender\kingdom\look\wx_probe_rig.py`、`look\wx_probe_fill.py`（两个一次性探针，可删）
  - 本文件（追加本节）
  - **没动** `hd_sky.py` / `look/render.py` / 任何 `capital_*.blend`

