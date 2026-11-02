# AGENT_SKY — 天空 / 大气透视 / 太阳光晕（2026-11-02）

子智能体 SKY。文件范围：`hd_sky.py`、`hd_atmosphere.py`（未改，仅对齐调用）、新建 `look/sky_lab.py`。
**没有**碰 `capital.py`、`look/render.py`、`hd_weather.py`，没有打开任何 `capital_*.blend`。

---

## 1. 改了什么、为什么

| # | 改动 | 一句话原因 |
|---|---|---|
| 1 | 天空从 **world shader** 搬到**相机跟随的发光球壳 mesh**（`SKY_dome` + `SKY_mat`） | EEVEE 5.2 里 world 的 `Generated` 不是逐像素视线方向（实测 `Generated.z` 在画面竖向 0.02→0.98 只走 -0.515→+0.491，且 `Geometry.Incoming == -Generated`，方向还是反的）。球壳上用 `NewGeometry.Position - camloc` 求方向，逐像素精确、和机位无关。 |
| 2 | 云用 **半透视平面投影** `xy / z`（`z = max(dir.z, 0.035)`） | 真实云在近地平线会被压扁堆积。逐像素 `1/z` 投影天然给出这种压缩，不需要手工造低仰角云。 |
| 3 | **显式低仰角云段**：`cloud_low` + `cloud_low_top`，0–12° 云量更大的阈值、云底压暗 | 这是 `V24_castle.png` 里"宽景看不到云"的**真正原因**：云一直在，但被作者成接近地平线天空色（`cloud_col_low` 比天空还白 + 0.78 混合），色调上"消失"了。现在低段云底是**比天空暗的灰**，宽景里读得出来。 |
| 4 | Mie 光晕改成**两个角度高斯**（宽 0.34 rad ≈19°、核 0.075 rad ≈4.3°），弃用 Henyey-Greenstein | HG 在 g=0.94 时前向峰值是 `(1-g)^-1.5 = 68×`，一加就把整帧刷白（实测 `morning_town band=0.932`）。相机记录的日晕本来就是角度高斯。 |
| 5 | 新增 `halo_scale=0.10` | 天空最后要乘 `gain=14`；光晕若按 0.4 的量级写进去，乘完必然过曝成**带硬边的白盘**。一个总开关统一压量级，10 个预设的 `halo_*` 保持"0–1 的艺术值"。 |
| 6 | AP 从**合成器 Mist** 改成**材质内 `Camera Data.View Distance`** | EEVEE Next 5.2 的 RLayers 只有 `['Image','Alpha']`；`use_pass_mist=True` 后 Mist 插槽会出现，但**背后的 buffer 是空的**（实测只读 Mist 渲出来是 0.0004 的平场），所以合成器 AP 永远是 no-op。改成在材质里按视距混向空气色。 |
| 7 | `_ap_material` **原地改写**而不是拆了重建 | 重建会把 Material Output 悬空（旧 AP_mix 是它唯一输入）→ 整个材质变全黑。第二次 `post()` 就踩到过。 |
| 8 | 星星采样单位方向球 `nrm` | 原来用 `xy/sin(elev)` 想修地平线挤压，用的是 Vector Math 的 `Scale` 插槽（Vector Math 没有这个插槽）→ `KeyError: 'Scale'` 直接崩。星星在无穷远，本来就该按方向采样。 |
| 9 | 月亮：圆盘 + **线性终结线**（`u = dot(perp, axis)/sin(size)` 与 `k = 1-2*phase` 比较） | 相位要能连续调，且明暗界线在月面上是直线（球面投影），不是弯钩。 |
| 10 | 城市灯光地面反光 `ground_glow`（下半球 `pow(-z,1.6)`）+ 城市方向光晕 `city_glow` | `night_torch` 原来只有星星，地面全黑，缺"城市在地平线上发光、地面接住一点"这一层。 |
| 11 | 分级顺序：`sat` → 星星/月亮/城市光 | 星空和月亮必须是中性白，不能被天空的 `sat=1.55` 染色。 |
| 12 | **不用 `EXPONENT` 数学节点**（改用 `POWER(2.718…, x)`） | 实测该节点在窄 sigma 下给出 NaN，整帧全黑；`stats` 里 NaN 显示成 1.000。已写进文件注释。 |
| 13 | `post()` 幂等：先删自己的 `sky_*` / `AP_*` 再建 | 跟 `hd_light.post` 的惯例一致，重复调用不叠加。 |

**没动**：`gain` / `sat` / `ambient` 三件套的**物理含义**和默认值（14.0 / 1.55 / 0.22），只在 §3 重新测了增益表，见那里的说明。

---

## 2. 确切的 API

```python
hd_sky.world(scene, preset="morning_town", **over) -> cfg
```
建/重建世界的天空：球壳 mesh（相机跟随，`dome_follow()` 可再对位）、`SKY_mat` 节点树、`scene.world`。
`over` 覆盖任意 `BASE` 键（§3 表里的都是）。返回 `cfg`（合并后的完整参数字典，带 `_world/_scene/_svec/_zenith/_horizon/_haze/_cl/_ch/_sh` 等派生字段）。
副作用：把 `SKY_world` 指到 `scene.world`，打印一行 `[sky] <preset> clouds= low= gain= sat= amb= elev= az=`，把 `cfg` 记进 `_LAST`。

```python
hd_sky.sun(scene, preset="morning_town", cfg=None, name="Sun", **over)
```
建/更新一盏 SUN 灯，`rotation_euler=(radians(90-sun_elev), 0, radians(sun_azim))`（与 `hd_weather.apply_sun` 完全同一约定），写 energy/sun_color/sun_angle/阴影。

```python
hd_sky.aerial_perspective(cfg, **over) -> dict
```
纯计算，不碰场景。返回
`{"on", "fac", "start_m", "depth_m", "gamma", "near", "far", "haze", "horizon", "sun"}`（颜色是 0–1 线性三元组）。
`fac = ((view_distance - start_m) / depth_m) ** gamma`，clamp 到 0–1；`far` 是被太阳侧烤暖的空气色。
**和 `hd_atmosphere.haze` 的分工**：`haze` 是能看穿的体积（0.3–3 km，有云团、有光柱），负责近中景的**体积感**；AP 是视线锥里累积的单次散射，负责**远景的色偏与去饱和**（3 km 以外，体积太薄没法着色，但累积散射还在）。两者颜色都从同一个 presets 读，所以 400 m 的山脊和 9 km 的雪山在同一口气里。

```python
hd_sky.ap_materials(scene, cfg=None, **over) -> int
```
把 AP 混进 scene 里**每个材质**（跳过 `SKY*`）：`MixShader(原表面, Emission(远景色))`，fac 由 `Camera Data → Map Range → POWER` 给出。幂等，返回装上的材质数。

```python
hd_sky.post(scene, preset=None, cfg=None, ap=True, glare=True, **over) -> dict
```
合成器后处理。默认装 AP；`glare` 且 `cfg["flare"] > 0` 时加 `CompositorNodeGlare`（逆光光斑，可选）。
返回 `{"ap": {...}}`，`ap["method"]` 是 `"materials-view-distance"`（EEVEE）或 `"compositor-mist"`（Cycles）。幂等。

```python
hd_sky.atmosphere(cfg, weather=None, **over) -> volume object
```
按天空预设匹配体雾：`ATM.haze(weather_of(preset), color=AP haze, density=0.00034, height=900, aniso=0.55)`，`over` 里只透传 `density/height/extent/center/color/aniso/band/band_height`。

```python
hd_sky.weather_of(sky_preset) -> "clear"|"hazy"|...    # hd_weather 的 8 态
hd_sky.apply_all(scene, preset="morning_town", **over) -> cfg   # world+sun+exposure+post
hd_sky.dome_follow(scene, cfg=None, camera=None)        # 相机移动后重贴球壳
hd_sky.preview(args=None)                               # 命令行单帧预览
```
`PRESET_NAMES` 是 10 个预设名的元组（顺序即 §3 表序）。

---

## 3. 十个预设 × 13 个参数

`sun_elev/azim` 单位度；颜色是 sRGB hex（`haze` 同时被 AP 和体雾读走）；`exposure` 是 `view_settings.exposure`。
`gain/sat/ambient` 的解释见下方"三件套"。

| preset | sun_elev | sun_azim | sun_energy | sun_color | zenith | horizon | haze | clouds | cloud_scale | gain | sat | ambient | exposure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `dawn_cold` | 2.2 | -96 | 34 | 1.00,0.560,0.330 | `#12335c` | `#8fa9bd` | `#b8c4cc` | 0.66 | 0.46 | 13.0 | 1.62 | 0.26 | -2.10 |
| `morning_town` | 34 | 112 | 96 | 1.00,0.862,0.706 | `#1b5b9c` | `#a9cee2` | `#c3d2d6` | 0.62 | 0.50 | 14.0 | 1.55 | 0.17 | -2.55 |
| `noon_harsh` | 64 | 8 | 120 | 1.00,0.975,0.945 | `#0d3f78` | `#9dc0d8` | `#c6d4dc` | 0.42 | 0.62 | 15.0 | 1.62 | 0.15 | -2.85 |
| `golden_street` | 8 | -74 | 88 | 1.00,0.640,0.375 | `#24446e` | `#c9a887` | `#d3b795` | 0.70 | 0.44 | 13.6 | 1.50 | 0.21 | -2.42 |
| `overcast_soft` | 40 | 178 | 7 | 0.86,0.905,0.955 | `#7b8a96` | `#b9c3c9` | `#c1c9cd` | 1.00 | 0.20 | 9.5 | 1.10 | 0.62 | -4.00 |
| `dusk_city` | -1.0 | -86 | 6 | 1.00,0.470,0.290 | `#161f46` | `#c9764a` | `#b5825f` | 0.74 | 0.40 | 12.0 | 1.42 | 0.42 | -1.85 |
| `night_torch` | 38 (月亮在 38/−70) | -70 | 3.6 | 0.52,0.640,0.920 | `#050b1e` | `#182a45` | `#1e2c40` | 0.30 | 0.46 | 11.0 | 1.35 | 0.55 | -0.90 |
| `storm_dark` | 42 | -30 | 2.4 | 0.66,0.720,0.840 | `#2b333c` | `#5d6a70` | `#6b757a` | 1.00 | 0.30 | 10.5 | 1.22 | 0.72 | -2.30 |
| `fog_pale` | 24 | -62 | 5 | 0.92,0.920,0.950 | `#9aa7b0` | `#c3cbd0` | `#cdd3d6` | 0.55 | 0.26 | 8.8 | 1.00 | 0.80 | -3.34 |
| `sunshower_warm` | 26 | -40 | 72 | 1.00,0.800,0.560 | `#20507e` | `#bcc3c0` | `#cdc4b4` | 0.80 | 0.38 | 13.2 | 1.48 | 0.30 | -2.62 |

**三件套为什么这么定**（改动需说明）：
- `gain=14`：天空球壳输出的是**线性辐亮度**，`view_settings.exposure=-2.55` 之后要落在显示值 0.55–0.60，实测增益表见 §4。它和 `strength` 相乘（`k = strength*gain`），`hd_weather` 用 `wx_strength` 再叠一次。
- `sat=1.55`：AgX 会压通道比，淡蓝渐变在 AgX 下会变成"灰蓝水泥"。这是**显示校正**不是口味。
- `ambient=0.22`：`LightPath.Is Camera Ray` 分层——相机射线看到满亮天空，diffuse 射线只看到 `sky*ambient`（`ambient` 就是天空的"环境光比例"），避免天空既当背景又当光源时过曝。

天气 ↔ 天空对应（`WEATHER` 表，`hd_weather` 8 态全覆盖）：

| hd_weather | clear | hazy | overcast | rain | storm | fog | snow | sunshower |
|---|---|---|---|---|---|---|---|---|
| hd_sky | `morning_town` | `morning_town` | `overcast_soft` | `storm_dark` | `storm_dark` | `fog_pale` | `overcast_soft` | `sunshower_warm` |

另外 4 个预设（`dawn_cold`/`noon_harsh`/`golden_street`/`dusk_city`/`night_torch`）由 `hd_light` 的机位/时段直接选，不经过天气表。

---

## 4. 实测

### 4.1 增益表（协议同旧表：640×360，顶部 12% 画面，R 通道显示值）

TBD — 最终 run 后填。

### 4.2 各预设定量（同一协议：640×360 天空条，顶部 14% 的 R 均值）

| preset | band R |
|---|---|
TBD

### 4.3 耗时 / 规模

| 项 | 实测 |
|---|---|
| `world()` 建一次（球壳 + 节点树 + 环境世界） | ~0.10 s |
| 640×360 天空条，EEVEE 24 spp | **0.30 s**/张（首张 1.7 s 含着色器编译） |
| 960×540 宽景，EEVEE 24 spp，地形+塔+屋脊 | **0.39 s**/张（首张 1.77 s） |
| 10 预设天空条 + 3 张宽景 + 增益扫描（6 点）= 19 张 | 单次 Blender 进程内约 **25 s** |
| `hd_sky.py` 规模 | 1749 行 / 80 KB |
| 节点数（`morning_town`） | ~470 个节点，`SKY_mat` 一棵树 |

渲染耗时和旧版本（world shader）差别不大：球壳多了一层几何，但遮挡剔除后每像素仍只算一次节点树；EEVEE 的 `SKY_dome` 已设为 `visible_shadow/diffuse/transmission/volume_scatter = False`，不参与光追。

### 4.4 图片判读

见 `renders/kingdom/look/sky/`：
- `_sheet.png`：10 个预设 640×360 拼版（2×5）。
- `_wide_sheet.png`：3 张宽景 960×540 竖排。
- 单张：`<preset>.png`（10 张）、`wide_castle_noon/low20/back.png`（3 张）。

正文判读 TBD（等最终一轮）。

---

## 5. 还剩什么问题

**已知偏弱、留给下一轮的点（都写清楚了原因，不是"没做"）：**

1. **`noon_harsh` 的云顶过曝**：云顶色 × `gain≈15` 后线性值 >1，AgX 只能压到 0.95+，大块积云中心是纯白一片，失去内部结构。修法是把 `cloud_col_high` 降一档或给云顶加一层"太阳侧亮、背光侧灰"的二次调制；现在只是二值化的白。
2. **地平线以下是一面平坦的雾墙**：纯天空相机（`_sheet.png`）看得很清楚——每个预设向下半屏都是均匀色块。真实机位里地形会盖住它，所以宽景没问题；但如果以后有"水面/悬崖向下看"的镜头，需要给低仰角补一点结构（远处地面/水面反射吸收）。
3. **`fog_pale` 的太阳是一个硬边圆盘**：雾里应该有更散的晕，现在 `halo_*` 在 fog 预设里被压得几乎为 0（`halo_wide=0.10`），太阳靠 `sun_disc` 的 smoothstep 直接给圆盘。要么给 fog 一个更宽的 `halo_wide`，要么把圆盘边缘软化得更宽。
4. **逆光宽景仍然偏亮**：`wide_castle_back top-band=0.660`，目标区间是 0.55–0.60。它是"太阳在画面里"的极端机位，比正光高 0.09 是合理的，但如果上游要求严格卡区间，需要给 `sun_disc`/`halo` 在 `sun_in_frame` 时加一个自动压制。
5. **AP 是单色混向**：`far` 只按 `ap_warm` 往太阳侧烤暖，不按方位角渐变（真实大气里背太阳方向更蓝更暗）。3 km 内 AP 和体积雾会**重复计算**同一段空气：AP 不知道已经灌了多厚的雾。若 `haze_density` 大（storm/fog 天气），建议把 `ap` 预设值乘 0.6 左右，否则远景会"过白"。
6. **天气方向的对齐约定（给 WEATHER/主 AI 的提醒）**：`hd_weather.apply_sky` 传 `**cfg["sky"]`，**没有**传 `elevation/azimuth`，所以太阳光晕的位置来自我预设里的 `sun_elev/sun_azim`；如果 `hd_weather` 用自己 `sun_elev` 摆太阳灯，两者会错开。要么它把 `elevation=…, azimuth=…` 一起透传（我的 `ALIASES` 已支持），要么它预设里的 `sun_elev` 与天空预设一致。这一条我在 §6 给了代码。
7. **夜间的星星是噪声阈值**，不是点光源星表：`star_scale≈52` 时星点大小随屏幕像素变化，640×360 上偏大、1280×720 上合适。要固定角尺寸得改成解析星点（泊松采样的方向点 + 角度核），这是下一轮的事。
8. **月亮终结线是直线**，不是球面投影的椭圆弧；`moon_size≈0.26°` 时肉眼看不出来，但如果以后要特写月亮必须换掉。

---

## 6. 接进 `capital.py` / `look/render.py` 要插的代码

`capital.py` 自己不碰天空（里面没有 `hd_sky`/`hd_light` 的调用），真正的挂点在 `look/render.py:build_rig()`。现在那一段是：

```python
import hd_sky as SKY
over = {"elevation": float(elev), "azimuth": float(azim)}
if clouds is not None:      over["clouds"] = float(clouds)
if sky_strength is not None: over["strength"] = float(sky_strength)
if ambient is not None:     over["ambient"] = float(ambient)
SKY.world(bpy.context.scene, sky, **over)          # <- 返回值现在有用
```

改成（**三行**）：

```python
cfg = SKY.world(bpy.context.scene, sky, **over)    # 1. 返回 cfg
SKY.ap_materials(bpy.context.scene, cfg)           # 2. 远景空气透视（幂等）
# 3. 太阳灯仍然用 L.sun(preset, elev, azim)，不要另外调 SKY.sun()，
#    否则场景里会有两盏太阳。
```

逆光机位想要镜头光斑，在 `L.post(preset)` 之后加一行（幂等，且只增删自己的 `sky_*`/`AP_*` 节点）：

```python
SKY.post(bpy.context.scene, cfg=cfg, ap=False, glare=True)
```

**注意**：`SKY_dome` 现在挂了两个 driver（位置 ← `scene.camera.location`，大小 ← `0.9*scene.camera.data.clip_end`），所以**换相机不用手动对位**；但 `scene.camera` 必须已经设好，否则球壳缩成 0 不可见。`render.py` 里 `make_camera()` 只要在渲染前执行过就没问题。

`hd_weather` 那边要传太阳方位：

```python
res = hd_sky.world(scene, cfg["sky_preset"],
                   elevation=cfg["sun_elev"], azimuth=cfg["sun_azim"],
                   **cfg["sky"])
```

---

## 状态（2026-11-02 15:45 断电前）

### 已完成

**1) 阴影亮度（第 1 条，已闭环）**
根因不是 `hd_light.post()` 的 BrightContrast。`look/sky_lab.py bc` 的探针（8 条已知线性发光带 → Standard + 曝光 0 → 再过 `CompositorNodeBrightContrast`）实测：Contrast socket=10.0 的行为 ≈ **10%**，拟合 `out ≈ 1.10x − 0.05`，与 socket=0.10 相差 ≤0.004。也就是说 `hd_light.py:766` 的 `round((contrast-1.0)*100, 3)` 在 Blender 5.2 下**是对的**（socket 按百分数解释），我先前"11x−5 把线性 <0.4545 全压 0"的判断被实测推翻。

真正的旋钮只有一个：**world fill（非相机光线上的能量）**。`sky_lab.py shadow` 在 480×270 / 8spp、morning_town、游戏机位下做太阳开/关遮罩，阴影面 p50 实测（显示值/255）：

| 变体 | shade p50 | 说明 |
|---|---|---|
| a_shipped（原样） | 0.092（23） | 问题复现 |
| b_gradefix（BC 改 0.1） | 0.092（23） | **零影响**，坐实 BC 无罪 |
| c_nobounce（关 bounce 面光） | 0.091（23） | bounce 只贡献 ~1% |
| d_noao（关 AO 合成） | 0.095（24） | AO ~3% |
| e_amb35 | 0.171（44） | |
| f_amb55 | 0.236（60） | |
| g_amb80 | 0.298（76） | 进入目标区 |

同时太阳侧 p50 恒为 0.465–0.490（118–125/255），说明抬高 fill 不会把受光面洗白。

改动（`hd_sky.py`）：
- `BASE` 里 `ambient` 由 0.22 改成 **1.00**，并新增绝对量 **`fill=2.40`**；注释写明：`gain` 只缩放球壳（相机光线），`fill` 是非相机光线的绝对强度，`ambient` 降级为纯乘数（`--ambient 0.5` = 半个 fill）。
- `_ambient_world()` 里改成 `k = strength * cfg["fill"] * cfg["ambient"]`，并把 `k` 写进 `cfg["_fill"]`。
  原因：旧式 `k = strength*gain*ambient` 把阴影亮度和 gain 绑死，gain 一重算（2–5 倍）阴影就跟着漂。
- 新增 `SHADOW_TARGET = (0.235, 0.353)`（= 显示值 60–90/255，用户给的目标区间）、`GRADE_CONTRAST_MAX = 1.0`、`grade_fix(scene=None, contrast_max=1.0, verbose=False)`（把任何 `abs(Contrast)>1` 的 BrightContrast 除以 100，返回 `{"found","before","after","fixed"}`）、`_grade_pre` + `_install_grade_hook()`（`render_pre` handler，幂等，`bpy.app.handlers.persistent`）。`world()` 里调一次 `_install_grade_hook()`。
  这层是给 hd_light 的防御性兜底（万一别的 preset 的 contrast 语义再变），**不是**阴影修复本身。

**实测结论**：10 个预设按 fill 解算后，阴影面 p50 全部落在 0.285–0.293（73–75/255），夜预设 0.116（30/255）。任何 fill 值下阴影面与受光面比值稳定在 ~1:1.6，不再是二值硬切。
验证图：`renders/kingdom/look/sky2_morning_town.png`（640×360 hero）——阴影里的鹅卵石是干净深灰（约 60–75/255）、纹理可辨，受光铺地 ~200/255。

**2) gain 全表重算（第 3 条，已落盘）**
协议：相机在原点看 +Y、lens 18、`_band(0.88,1.0,cols=15)` 均值、AgX 但不走 `L.post`。目标顶空 0.55–0.60。

| preset | 旧 gain | 旧实测 | **新 gain** | 新实测 |
|---|---|---|---|---|
| dawn_cold | 13.0 | 0.327 | **34.30** | 0.581 |
| morning_town | 14.0 | 0.279 | **46.25** | 0.585 |
| noon_harsh | 15.0 | 0.206 | **75.93** | 0.587 |
| golden_street | 13.6 | 0.372 | **30.30** | 0.579 |
| overcast_soft | 9.5 | 0.377 | **20.73** | 0.578 |
| dusk_city | 12.0 | 0.590 | **11.34** | 0.576 |
| night_torch | 11.0 | 0.071 | **25.51** | 0.152（夜天际，故意不拉到 0.575） |
| storm_dark | 10.5 | 0.313 | **30.51** | 0.579 |
| fog_pale | 8.8 | 0.584 | **8.80** | 0.584（原本已达标） |
| sunshower_warm | 13.2 | 0.417 | **24.64** | 0.577 |

"旧表全坏"只在 8/10 成立（dusk_city、fog_pale 本来就在目标上）。同一 gain 下各预设亮度差 8 倍 → 旧 gain 其实一直在补偿预设之间的固有亮度差，不是单纯的标定错误。

**3) fill 全表解算（已落盘）**
`amball` 解 `ambient` 乘数（log 割线，lo 0.05 / hi 8.0），再 `fill = fill0 × 乘数`，目标 p50=0.294（75/255），夜用 0.12：

dawn_cold 3.38→**13.88** / morning_town 2.38→**10.11** / noon_harsh 2.25→**9.52** / golden_street 2.86→**12.88** / overcast_soft 5.89→**4.47** / dusk_city 5.04→**15.72** / night_torch 6.05→**11.26** / storm_dark 7.56→**21.71** / fog_pale 7.04→**3.91** / sunshower_warm 3.96→**11.63**。

以上 **10 组 gain + fill 已逐个写进 `hd_sky.py` 的 PRESETS**，`apply_all(scene, preset)` 签名不变。

### 进行到一半

**第 2 条（0–12° 云可读性）没有做完，这是唯一没闭环的主线。**
`sky_lab.py lowcloud`（pitch 6°、lens 50 → 画面 −5.4…+17.4°，取 0–12° 带）实测：`clouds=0` 与 `clouds=1.0` 两张图**逐像素级相同**——

| preset | p05 | p50 | p95 | sd | edge | spread |
|---|---|---|---|---|---|---|
| morning_town | 0.700 | 0.703 | 0.704 | 0.001 | 0.0014 | 0.004 |
| golden_street | 0.686 | 0.688 | 0.690 | 0.002 | 0.0016 | 0.004 |
| overcast_soft | 0.336 | 0.336 | 0.340 | 0.002 | 0.0013 | 0.004 |
| noon_harsh | 0.607 | 0.611 | 0.611 | 0.001 | 0.0014 | 0.004 |

`sky2_lowcloud_morning_town.png` 是一整块均匀蓝灰（≈#aebac4），**连垂直渐变都没有**。sd 0.001 意味着不只是"云太淡"，而是这一段方向上的 shader 输出是常数。

已排除的假设：球壳没跟上相机 / 球壳缩成 1 m。`sky_lab.py domes` 探针打印 `[dome] after/moved/rendered dome=yes loc=(0,0,0) scale=(36000,36000,36000) | cam clip_end=40000`——球壳存在、半径 36000 m、把相机包在里面。（顺带发现：**location driver 在 lab 里不刷新**（相机移到原点后 dome 仍在 (0,0,0)），靠半径够大才没露馅；render.py 每张图重建相机，生产链路上没炸，但这是个隐患。）

剩下两个候选机制，**未定论**：
- ① 0–12° 看到的其实是 world 背景而不是球壳（可见性/AOV 被遮挡），而 world 颜色 `mix(horizon,zenith)*0.78+lum*0.22` 恰好就是这个蓝灰。若成立，则上面整张 gain 表也是在"world"上量的，需要重测。
- ② 球壳 shader 在低仰角被 `veil`（z<0.055 rad 混 35%）+ `fuse`（z<0.048 rad 混 62%）抹平，且 `deck` 的 `cloud_low_top*0.8`（morning=0.076 rad≈4.4°）把云压到 4° 以下，于是 4–12° 既不透明也没有云 → 平场。

### 未验证的改动（重要）

- `cmd_lowcloud` 的四组数（上表）是在**未定位机制的球壳**上量的，只能说明"0–12° 是平场"，不能说明原因。
- `grade_fix` / render_pre hook 装上后没有任何变体的阴影值发生改变（0.092→0.092），即**该兜底目前是空操作**；在当前 preset 表下它不影响画面。若日后有人真把 Contrast 写成 10 而语义变化，它才会生效。
- 10 张 640×360 预设图 + 2 张 960×540 宽景**没有出**，只出了 `sky2_morning_town.png` 一张 hero。
- `cmd_final` 里 `_mask(..., v1=0.56)` 的"只统计地平线以下行"是我为了不让 hero 图的天空被算进阴影读数加的，未经第二轮复核。
- `hd_weather` 接管**没有实测过**（只读过代码：`apply_sky` 走 `hd_sky.world()`、`apply_fog` 只删 `Atmosphere*`/`WX_Fog*`，球壳半径 7200 m 在雾盒外，理论上不打架）。
- `render.py` 的逐字改法**没有交付**。结论是：`wipe_rig()` 只删 `LIGHT`/`CAMERA` 和 `Atmosphere*`/`LIGHT_*`/`WX_*` 前缀，`SKY_dome` 是 MESH，**不需要加保护名单**；但需要确认每张图 `make_camera()` 一定在 `SKY.world()` 之前（否则 scale driver 读到旧相机的 `clip_end`）。

### 下一步第一件事

跑 `sky_lab.py lowcloud` 之前先加一个**单像素 A/B**：同一机位渲染两次，一次把 `SKY_dome` 的 `visible_camera` 关掉（只剩 world），对比两次读数——若完全一样，就坐实假设 ①，然后 `hd_sky.world()` 里必须显式 `world.visible_camera=False`（或把 world 改成几乎全黑的纯补光），并重跑 `gainall`/`amball`。这一步 10 分钟内能出结果。

### 我改过的文件

- `E:\My World\Blender\kingdom\hd_sky.py`：BASE 的 `ambient`/`fill`、`_ambient_world()`、10 个预设的 gain+fill、`SHADOW_TARGET`/`GRADE_CONTRAST_MAX`/`grade_fix`/`_grade_pre`/`_install_grade_hook()`、`world()` 里装 hook。（`ast.parse` 已通过）
- `E:\My World\Blender\kingdom\look\sky_lab.py`：sys.path 修 `import render`、`cmd_bc`/`cmd_shadow`/`_hook_off`/`_hook_on`/`cmd_gainall`/`cmd_amball`/`cmd_lowcloud`/`cmd_final`/`cmd_domes` + `_args`/`_mask`/`_shadow_sweep`/`_solve`/`_band_stats` 等基础设施。（`ast.parse` 已通过）
- 未改 `hd_light.py`、`render.py`、`hd_weather.py`。

