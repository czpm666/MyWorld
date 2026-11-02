# AGENT_CASTLE_INT — 王城室内（Great Hall / Feast Hall / 螺旋楼梯塔）

日期：2026-11-02 · 子智能体：CASTLE_INT · 文件：`E:\My World\Blender\kingdom\hd_castle_int.py`

---

## 1. 我改了什么、为什么

| 改动 | 为什么 |
|---|---|
| **整体重写 `hd_castle_int.py`**（原 2203 行 → 现 ~2300 行） | 审计结论：旧文件能跑、API 齐全，但它是 30 m × 52 m 的**教堂式中殿**（`HALL_W=30`/`HALL_L=52`/`Z_RIDGE=21.2`，nave+aisle+narthex+chancel），装不进 keep 的 30×22 空腔；且签名是 `build(MAT, rng)`，与外壳对不上。渲染实测复现了「王座读不出」：8 m 以上全黑，王座是一块红色平板 + 拱形红背板。 |
| 平面从「长中殿」改为「紧凑大厅」：清空体 **18.0 m 净宽 × 26.0 m 净长 × 14.0 m 净高** | 用户硬指标 18 m / 14 m；26 m 净长是 keep 内腔 30 m 减两侧各 1.25 m 墙厚后的最大值。 |
| 竖向分三层：大厅（0–14 m，脊 19.6）→ 屋架层（14–20.2）→ 宴会厅（20.2–28.4）→ 顶（30.9） | 18 m 净宽的大厅独占整个 26×18 平面，宴会厅只能叠在上层；「keep 分层 + 螺旋梯连接」正是真实中世纪 keep 的组织方式，也让玩家必须爬塔才能看到第二个空间。 |
| 螺旋楼梯塔放在东北角、与两面墙相切（`ST_CX/ST_CY = 9.45/5.45`，`ST_R=3.55`） | 塔不需要额外占地；13°/步 × 112 步 = 顶部抵达角 216°，正好落在顶层门（206°–226°）里，两端门都朝向房间内侧。这是解方程选 13° 的理由。 |
| **王座整体重做**（竖向剪影：1.38 m 宽 / 3.20 m 高，浅色大理石 + 深红绒幕布） | 「王座读不出」的根因不是缺几何，而是**比例**：原来是一块宽 > 高的红板，在 23 m 外读成「墙上一幅画」。现在高宽比 2.3:1、背后 4.28 m 红绒垂幕、顶部山墙冠 + 金球 + 双尖塔，剪影在门口第一眼就能认。 |
| 石墙材质换成**朝向无关**的 3D 噪声（`_ashlar`） | 原 `ShaderNodeTexBrick` 只采样向量的 XY 平面，墙上（XZ）会拉成 14 m 高的涂抹状条纹；而且 `ShaderNodeMix` 的 RGBA factor 实际满强度相乘，把每面墙刷成 2 m 迷彩斑。 |
| 12 盏高窗补光 + 8 盏宴会厅窗补光的**朝向修正**（`rotation_euler=(∓90°,0,0)`） | 原来是 `+90°`，AREA 灯沿局部 -Z 出光 → 光全部打进石头里，室内只剩反射光。这是「大厅发灰发闷」的直接原因。补光同时 `use_shadow=False`：灯距离墙面 0.45 m，投影光线在预览采样数下不收敛，去噪后会变成豹纹。 |
| `build_floor` 把 3000 块石板合成**单一 mesh** | 每块石板独立对象时，各自的 bevel/高度差造成高光不一致，渲出来是棋盘格。 |
| 甲胄架重写为窄肩骑士甲（总高 2.12 / 肩宽 0.62） | 原版是「球胸甲 + 球肩甲」，近看像黑色米其林玩偶。 |
| 吊灯从实心圆盘改为 26 段铁条环 | 实心 `cyl(r=1.36,h=0.10)` 从下面看是一个黑鼓。 |
| 楼梯火把龛重做（龛 + 颊 + 压顶 + 托架 + 火把，灯位移到 `ST_RIN-0.42`） | 原来龛和灯都在 `r=ST_R-0.10=3.45`，**埋在塔壁石头里**，所以「火把光」那张图全黑。 |
| 加 `build_seals()`：屋架封板 + 楼梯井顶 `ci_st_vault`(15.62) + 吊灯 | 屋架望板在 y=5.45 处 z≈16.2，会横穿楼梯井；井顶封在 15.5 m 后，从大厅看屋架正好把塔切开的部分完全遮住，且井里有了光源。 |
| `_cam()` 自己算矩阵（列 = r, u, -f） | `hd_common.camera()` 用 `d.to_track_quat("-Z","Y")` 实测指向错误（相机朝天看，渲出来是大厅拱顶）。**主线请勿信任 `H.camera`。** |
| `build()` 里对非 MESH 对象也做变换 | `hd_common.apply()` 只处理 MESH（`if ob.type != "MESH": continue`），灯会留在原点。 |

---

## 2. 确切的 API

```python
build(K, MAT, origin=(0.0, 0.0), rot=0.0, scale=1.0, seed=3,
      lights=True, z=0.0) -> [objects]
```

| 参数 | 含义 |
|---|---|
| `K` | `medkit` 模块本身（用它建网格/材质）。也可以传任何提供 `mesh_obj/box/cyl/sphere/assign/bevel/T_at/link` 的对象。 |
| `MAT` | 材质字典（外壳的 `make_mats()` 结果）。内部会 `prep(MAT)` 覆写 `stone_wall/stone/stone_light/stone_course/stone_dark/stone_floor/stone_step/marble`，**不改你传进来的字典**（`dict(MAT)` 浅拷贝）。 |
| `origin=(x, y)` | 世界坐标平移（米）。z 由 `z=` 单独给，默认 0（模块地面 = 0）。 |
| `rot` | 绕世界 Z 轴弧度。 |
| `scale` | 整体缩放。 |
| `seed` | 随机种子（石板错缝、玻璃每窗图案、柴堆等）。 |
| `lights` | `True` 时一并返回 60 盏灯（POINT/AREA/SPOT），已随 `origin/rot/scale/z` 变换好。`False` 则只出几何，供你自己打光。 |
| `z` | 竖直平移，**默认 0**。放进 keep 时给 `CY=1.30` 或等价的绝对高度。 |

**返回值**：`[bpy.types.Object]`，约 1990 个对象：绝大多数是 MESH（顶点已烘焙，`matrix_world` 为单位矩阵），末尾是灯（`type == "LIGHT"`，`matrix_world` 已带变换）。

**模块几何尺寸（外包，供装箱判断）**

| | 值 |
|---|---|
| X | −14.25 … +14.25（28.50 m） |
| Y | −10.25 … +10.25（20.50 m） |
| Z | 0.00 … 30.90（模块局部） |
| 大厅清空体 | 18.0 宽 × 26.0 长 × 14.0 净高（`Z_PLATE=14.00`） |
| 屋脊 | 19.60（望板顶 19.70） |
| 宴会厅 | 楼板 19.72…20.20，净高到 28.40，顶 30.90 |
| 楼梯塔 | 圆心 (9.45, 5.45)，外径 3.55，井半径 0.92，112 级 × 0.1804 m |

其它可调用：
- `prep(MAT) -> dict`：只做材质覆写，返回新 dict。
- `make_mats()`：本模块自用的材质集（布料 `cloth_panel`、火焰、彩玻 `ci_glass_proc` 等）。`prep()` 之后仍然用你传进来的 MAT 键，缺的键会回退到 `_FB` 缓存。
- `preview(samples=64, res=(480, 270), tag="ci", shots=None)`：`reset_scene()` → `build()` → `setup_engine()` → 世界体积雾 + 太阳 → 渲 6 张 `<tag>_<名字>.png` 到 `E:\My World\Blender\renders\kingdom\look\`。纯自检用，不进主线。

---

## 3. 实测数据

机器：Ryzen 7 8845H / 31.3 GB / RTX 4060 Laptop 8 GB。Blender 5.2.3 LTS，Cycles + OPTIX，
`view_transform="AgX"`、`look="AgX - Punchy"`，`exposure=0.22`，128 samples + OIDN。

| 项目 | 实测 |
|---|---|
| `build()` 纯建模 | **0.2 s**（1438 个对象，其中 MESH 1384、LIGHT 55） |
| 面数 | **60,132 tris**（预算 900k，用了 6.7%） |
| 外包包围盒 | x −14.40…+14.33、y −10.25…+10.25、z −1.20…+31.10（z 的 −1.20 是 1.2 m 厚楼板垫层，藏在地面以下） |
| 渲染 960×540 / 128 spp × 6 张 | **65.3 s**（约 10.9 s/张，含去噪） |
| 渲染 480×270 / 64 spp × 6 张 | 19.5 s（约 3.2 s/张，迭代用） |
| **峰值内存** | **2,132 MB**（`Get-Process blender → PeakWorkingSet64` 轮询；Blender 内 `ctypes GetProcessMemoryInfo` 返回 0，不能用） |

内存/面数都远低于红线（单进程 1 个 Blender、≤900k tris）。


---

## 4. 图片与判读

<!-- IMAGES -->

---

## 5. 还剩什么问题 / 下一步建议

1. **石墙仍是「大面」**。`_ashlar` 现在是朝向无关的 3D 噪声，近看（B 图 3–5 m）能读出石材色差，但在 20 m 外基本是一整片。想再进一步就要**几何接缝**：在墙面上按 1.4×0.5 m 切出 6–8 mm 的凹槽（每面墙 +3000 tris，可接受），这是中世纪石墙最重要的读数线索。
2. **宴会厅只做了「一层楼」的暗示**。长桌/长凳/壁炉/吊灯/酒桶/猎犬都在，但和 W 图相比缺少墙面的叙事（挂毯、盾牌、烛台阵列）。加 3–4 块挂毯 + 2 组墙面盾牌最划算。
3. **螺旋楼梯只有 112 级、到宴会厅为止**（20.2 m）。再往上到塔顶（30.9 m）是封死的实心井——如果主线需要「塔顶瞭望」，要另开一段梯段（约 60 级）。
4. **体积光只在 F 一张图里成立**。大厅空间大（26×18×20 m），雾密度 0.0022 时看不出光柱，0.008 才明显；主线如果用的是 `hd_atmosphere.haze()`，请注意它和我的 `ci_win_fill` 叠加后可能过曝，建议把窗补光降到 120 W 左右再看。
5. **火焰是静态的**。用户要求「闪烁」在静态渲染里给合理亮度——现在 `int_fire` 自发光 9、`int_fire_hot` 20，在 AgX 下不糊。要做实时闪烁得在 Unity 侧驱动（材质自发光强度 × `0.85 + 0.15*sin(t*13)`），模块这边不再处理。
6. **没有碰撞体/入口触发**。`build()` 只出视觉件。主线若要玩家能走进来，需要在 keep 的 +Y 面（`door_arched w=3.4 h=5.2`）和我的侧门（模块 x=0 的 +Y 墙）之间开洞并对齐——我的侧门中心在模块局部 `(0, +9, 0)`，放到世界里就是 keep 的正门内侧。
7. 旧 `hd_castle_int.py` 里 `build_responds()` 已不再被 `build()` 调用（被 `side_wall()` 的墩子取代），留着不占面数，但可以删。

---

## 6. 需要主 AI 在 `capital.py` 里插的代码（逐字）

`hd_glue().castle` 的签名是 `castle(MAT, rng, x, y, rot=0.0, z=0.0, scale=1.0)`（`capital_hd_glue.py:318`），**第 5 位 rot、第 6 位 z、第 7 位 scale**。

⚠️ **不要**把室内交给 `place()` / `castle()`：`place()` 只保留 `type == "MESH"`（`capital_hd_glue.py:131`），`hd_common.apply()` 同样只处理 MESH（`hd_common.py:124-131`）——两者都会把我的 60 盏灯丢在原点。直接调 `build()`，它内部已经把灯一起变换好。

### 6.1 王城（ROCK_C = (0.0, 303.4)，岩顶 18.45，CS = 1.15，yaw = π）

```python
import math
import hd_castle_int as INT

# 城堡原点 = ROCK_C + 岩顶标高；keep 空腔中心 (0,-21)、室内地面 z=1.30 都在
# hd_castle 自己的局部坐标里。
CX, CY_, CZ = 0.0, 303.4, 18.45
CS, YAW = 1.15, math.pi
LX, LY, LZ = 0.0, -21.0, 1.30

_c, _s = math.cos(YAW), math.sin(YAW)
_ox = CX + CS * (LX * _c - LY * _s)     # 0.0
_oy = CY_ + CS * (LX * _s + LY * _c)    # 327.55
_oz = CZ + CS * LZ                      # 19.945

_parts = INT.build(K, MAT, origin=(_ox, _oy), rot=YAW, scale=CS, z=_oz, seed=3)
```

代入常数就是：

```python
_parts = INT.build(K, MAT, origin=(0.0, 327.55), rot=math.pi,
                   scale=1.15, z=19.945, seed=3)
```

`build()` 的变换与 `place()` 完全同序（`Translation(origin, z) @ Rotation(rot, "Z") @ Scale(scale)`），所以 `rot`/`scale` 可以直接沿用城堡自己的。

世界包围盒（已实测）：x −16.39…+16.39、y 315.76…339.34、z 19.945…55.48。
keep 内腔在世界里是 x ±17.25、y 314.90…340.20、z 19.945…68.25 → **四周各余 0.86 m，顶部余 12.8 m**。

### 6.2 教堂（如果主线也想要室内）

本模块是**为王城 keep 量身做的**（18.0 净宽 / 26.0 净长 / 14.0 净高，王座墙在 −X 端），**不能直接塞进教堂**：教堂的平面是长中殿（旧 `hd_castle_int.py` 那种 30 × 52 m），把王座厅放进去会立刻看出「王座在小教堂里」。教堂室内应由 `HD_CATHEDRAL` 那一线自己做，或至少把它的中殿净空压到同一套尺寸后单独调 `origin/rot/z`。

如果只是想复用这里的**零件**（拱廊 `side_wall`、彩玻 `glazed_window`、屋架 `build_roof`、布料 `cloth_panel`、火把/甲胄/吊灯），可以直接 import 调内部函数——它们都接 `(M, rng)` 或 `(nm, T, ...)`，不依赖全局状态：

```python
import hd_castle_int as INT
_parts = INT.build_roof(INT.make_mats(), rng)          # 只要屋架
```
注意这些函数返回的是**模块局部坐标**下的对象，自己套变换。全局常量（`HX/HY/Z_PLATE`…）是模块级的，改动会影响整个模块。

### 6.3 只要几何、不要灯

```python
_parts = INT.build(K, MAT, origin=(0.0, 327.55), rot=math.pi,
                   scale=1.15, z=19.945, seed=3, lights=False)
```

