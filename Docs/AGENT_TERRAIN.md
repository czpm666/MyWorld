# AGENT_TERRAIN — 城外地形（v24 → v25）

子智能体：TERRAIN。范围：`E:\My World\Blender\kingdom\hd_landscape.py` 及其新拆出的五个子模块。
禁止改动的东西没有动过：`capital.py` / `capital_hd_glue.py` / `hd_dense.py` / `hd_plan2.py` /
`look/render.py` / `look/spots.py` / `look/contact.py`，也没有打开任何 `capital_*.blend`。

---

## 1. 一句话结论

城外那层"绿坡 + 拼布被"换成了：连续的田块马赛克（近郊 11 m 小田，远处 60–200 m 条田）、真垄沟几何
（近处 2.5–3.4 m 垄距，远处由着色器按田块属性画）、带缺口和高度起伏的树篱带、四档树种三档 LOD 的树、
四门外的车辙土路与近郊手工业带（菜园/果园/牧栏/柴垛/伐木场/采石场/磨坊引水渠）、11 个中景地标，
以及一个由城墙 20 边形轮廓直接驱动的柔和地形过渡（俯视下的圆边消失）。
`build()` 从 29.1 s / 611 k faces 变成 **10.9 s / 2.35 M faces**，峰值内存 734 MB。

---

## 2. 改了什么（逐项对应七项缺陷）

### 2.1 农田（缺陷 1）
- **两层结构，各司其职**：
  - *几何层*：距城 < 2250 m 的田块铺真垄沟。每垄 7 点横截面 × 3 段 = 12 三角，**与垄长无关**
    （120 m 长的垄和 20 m 长的垄同价），垄距 2.2–3.4 m、垄高 0.22–0.42 m，沿垄有起伏和高度噪声。
    199/257 块田吃到这一层，共 607 k 三角。
  - *材质层*：田块 mesh 带两个自定义属性 —— `Fdir`（rgb = 垄向 cos/sin 的 0..1 编码）与
    `Fur`（r = 每米垄数、g = 强度、b = 作物 id、a = 土块尺寸）。`land_crop` 用世界坐标点乘垄向得到
    `u`，做 `abs(frac(u) - 0.5) * 4 - 1` 的三角波（-1 沟 / +1 垄）当 bump 与色调制，所以 2 km 外
    没有几何的田块仍然读得出垄向；强度按相机距离 120→420 m 从 1 衰减到 0.18，避免 8 spp 闪烁。
- 9 种作物分色分纹理：麦 / 黑麦 / 油菜 / 牧草 / 犁田 / 休耕 / 根茎 / 葡萄 / 果园；近城偏菜园与根茎，
  外缘偏麦与牧草（`_pick_crop` 按 t 线性混合）。
- 田埂：`_ring` 的**外侧四个顶点落到地面**、内侧抬 0.40 m，形成从地面爬上田面的斜坡；田内另有一圈
  0.26 m 高的土脊。每块田因此有亮脊 + 暗影两条边线，这是"拼布被"最有效的解药。
- 田边：树篱 / 干砌石墙 / 木栅 / 土路四种，按 700 m 网格分风格；**共享边按 0.25 m 吸附去重**，
  一条边只放一次特征，所以不会出现两条树篱叠在一起。
- **踩过的坑**：田面网格 22 m、地形网格 20 m，相位不同，线性插值误差 ≈ 0.30 m > 原来 0.045 m 的抬升，
  地形从田面里戳出来变成"田里一块块深绿岛"。抬升改成 0.40 m 才对。

### 2.2 树篱 / 树列（缺陷 2）
- `hedge_band()`：8 点圆角横截面（不是两面竖墙），宽 3.0–4.6 m、高 1.6–3.2 m，沿弧长 2.6 m 采样，
  宽度噪声 `1 + 0.30 sin(41t) + 0.18 sin(17t)`、高度噪声 `1 + 0.26 sin(29t) + 0.14 sin(61t)`，
  随机缺口至少 3 站宽，末端三角封口。每 28–30 m 在脊顶种一棵标准乔木（橡树 LOD1）。
- `drystone()`：0.9–1.3 m 高、0.6 m 厚、6 点横截面、顶部高度噪声 ±16 %，带压顶石。
- `fence_line()`：3.4 m 一根柱 + 两道横杆。

### 2.3 树（缺陷 3）
- 4 种轮廓 × 3 档 LOD，全部三角形（吃 `mk_obj` 的 `foreach_set` 快路径）：

  | 树种 | LOD0（近） | LOD1（中） | LOD2（远） |
  |---|---|---|---|
  | 云杉 | 5 段干 + 17 层裙摆锥 | 4 段干 + 7 层 | 2 片交叉面 + 树桩 |
  | 橡树 | 倾斜干 + 3 枝 + 6 个抖动 icosphere 团 | 干 + 2 团 | 交叉四边形 |
  | 杨树 | 10–14 环纺锤体 | 6 × 6 | 交叉细长三角 |
  | 果树 | 矮干 + 3 枝 + 4 团 | 1 团 | 交叉矮四边形 |

- LOD 按距城半径分档（<1250 / <1900 / 其余），物种按海拔（>330 m 云杉）、离河与湖（<140 m 杨树）、
  近郊（<430 m 且 55 % 概率果树）。
- 实例化走 `TBuf.add_many()`：一次 concatenate 出 N·V 个顶点与 `(N·nf, 3)` 面索引，
  颜色 = 逐顶点明暗乘子 × 每树色。25 万株树 1.6 s。
- `land_leaf` 材质加了 0.9 m 团簇噪声、7 m 冠层阴阳、法线朝上加亮、emission 微透光 —— 治"黑棒棒糖"。

### 2.4 近郊带（缺陷 4）
- `hd_landscape_near.py`，环带 = 城墙轮廓外 0–430 m：
  - **11 m 连续田块毯**（`_carpet`）：16 003 块小田，每块抬 0.10–0.26 m，相邻格的台阶就是田界线；
    9 种作物按 190 m 噪声成片 + 70 m 噪声抖动，所以是"片"不是"碎纸屑"。**只有 32 k 三角。**
  - 132 个方位尝试 → 92 个墙脚菜园（床 + 蜂房 + 堆肥 + 棚）、32 个果园、16 个牧栏（羊圈 + 干草垛 + 水槽）、
    486 个农家院子、110 个大地块、2765 株果树。
  - 手工业：水磨 + 7 段木制引水槽 + 水轮、伐木场（木工旋床 + 锯坑 + 原木）、采石场（14 块石料 + 木吊臂）、
    废墟菜地（9 段残墙）。
  - 四门外 1 km 的车辙：`ruts()` 在土路上压出两条 0.38 m 宽、下沉 0.055 m 的车辙（4460 段）。

### 2.5 地形与城市的接缝（缺陷 5）
- 新增 `R_OUTER = 947.2`、`OUTER_N = 20`、`CITY_SEED = 20261022`；`_city_pts()` 用
  `random.Random(CITY_SEED + 61)` 复刻 capital.py 的 20 边形（顶点在 9°, 27°, …，3 % 半径抖动）。
- `_city_sd(x, y)`：凸多边形有符号距离（正 = 城外），20 次向量点积，无开方、无半径。
- `_pre()` 里**没有任何半径**：过渡起点 = `smoothstep(sd + wob * 0.42, a, b)`，
  `wob = (fbm 1/430 − 0.5) × 150 + (fbm 1/104 − 0.5) × 44`，即墙外 0–200 m 内随机偏移 ±95 m，
  再加上 `smoothstep(sd, 4, 46)` 保证墙脚 4 m 内绝对平。俯视下的圆边变成不规则的多边形边界。
- `_apron()`：`a = max(245, FLAT_IN − R_OUTER)`、`b = max(a + 780, FLAT_OUT − R_OUTER)`。
  **capital.py 覆盖的 `FLAT_IN / FLAT_OUT` 现在真的生效了**（旧版 `_pre` 硬编码 800/1420，覆盖无效）。
- 城内地面统一 z = 0（`_carve` 的 `city` 掩码按 `sd < 30` 把地面压平），河槽单独直落 −3.22，
  岸墙与水面交给 `hd_river`。
- `strip_old()` 现在**同时删 `ground_town` 和 `ground_outer`**，由 `build()` 重建
  `land_townfloor_n` / `land_townfloor_s`（20 边形按港湾河道 `y = −762 ± 46` 裁成两块，z = +0.03）。
  3 cm 的台阶被 2.4 m 厚的城墙完全遮住。capital.py 的 `_prune_dead(groups)` 会把被删的对象从
  `groups["ground"]` 里摘掉（已确认，见 `capital.py:2201`）。

### 2.6 材质（缺陷 6）
`hd_landscape_mat.py`，7 个材质，全部**每次 `nt.nodes.clear()` 重建**（不再因已存在而提前返回，
避免被上一轮污染的节点树留下），并且 `use_backface_culling = False`（LOD2 交叉面片必须双面）。
所有 mesh 都是恒等变换的世界空间，所以 `TexCoord.Object` 就是世界坐标，着色器可以直接问
"离城多远 / 垄朝哪 / 特征多大"，不需要 UV。

| 材质 | 读的属性 | 尺度分层 |
|---|---|---|
| `land_ground` | `Col` | 340 m 牧场马赛克 / 96 m 裸土 / 26 m 树篱阴影 / 4.2 m 草丛（90→260 m 淡出）/ 0.55 m 土块（仅 bump，18→52 m 淡出）；法线 Z 做陡坡岩石；`length(Object)` 2200→14000 m 混向雾色 |
| `land_crop` | `Col` + `Fdir` + `Fur` | 2.5–3.4 m 垄沟三角波 + 4.7 倍频细行；强度按 120→420 m 衰减 |
| `land_soil` | 仅 `Col` | 2.6 m 土块 + 0.34 m 土屑；只给没有 `Fur` 的床/地块用 |
| `land_prop` | 仅 `Col` | 0.62 m 颗粒；干草垛、柴垛、大车、车辙共用 |
| `land_leaf` | `Col` | 0.9 m 团簇 + 7 m 冠层 + 微透光 |
| `land_stone` | `Col` | 3.4 m 砌层 + 0.26 m bump + 顶面苔藓 |
| `land_track` / `land_water` | `Col` | 1.6 m 路面噪声 / 0.28 m 涟漪 |

**曝光校准（重要）**：地表反照率被刻意压低。88 W 的太阳以 48° 打在 0.16 反照率的草地上时，
像素落在 AgX 的肩部，±30 % 的反照率变化只剩 ±6 % 的像素差 —— 这就是"一片奶油色平板"的根因。
所以 `_ground_col` 输出乘 **0.46**、作物顶点色乘 **0.40/0.31**、田块毯按亮度压到 **0.16 linear**。
同一套 `look/render.py` 光照下，这是让地面回到 AgX 线性段、把纹理变化还回来的唯一办法。

### 2.7 中景地标（缺陷 7）
`hd_landscape_marks.py`，11 个，1.2–3.3 km 分散，每个独立 `Acc` + 异常隔离：

| 地标 | 方位 / 半径 | 内容 |
|---|---|---|
| `land_windmill` | 288° / 1.4–1.6 km | 塔身 + 四叶风车 + 尾杆（西大路旁） |
| `land_gallows` | 10° / 1.3–1.5 km | 绞架丘 + 三柱 + 横梁 |
| `land_circle` | 64° / 1.9–2.4 km | 13 块立石 + 倒地石 + 祭坛 |
| `land_abbey` | 150° / 2.2–2.7 km | 44 × 21 m 残墙 + 8 道尖拱 + 塔残段 + 碎石 |
| `land_beacon` | 96° / 2.7–3.3 km | 山脊圆塔 + 火篮 |
| `land_charcoal` | 36° / 1.7–2.1 km | 3 个炭窑 + 棚 + 柴堆 |
| `land_hermitage` | 202° / 2.4–2.8 km | 岩壁 + 门洞 + 石十字 |
| `land_motte` | 322° / 2.1–2.5 km | 锥形土丘 + 木塔 + 外郭墙 |
| `land_barrow` | 250° / 2.5–3.0 km | 26 m 长冢 + 门石 |
| `land_ferry` | 河道 1.5–2.4 km | 栈桥 + 平底渡船 + 收费棚 |
| `land_bridge` | 河道 1.2–1.7 km | 石拱桥（桥面 + 栏墙 + 3 个桥墩） |

### 2.8 性能（缺陷 7 的硬指标）
- `_woods` 去掉逐树 `Matrix` 变换，改 numpy 批量实例化。
- `_build_rings` 去掉逐顶点 4 次解析梯度（旧版 11.5 s 的来源），改两遍差分法。
- `_carve` 加 bbox 掩码：远环 95 % 的点不再跑 `_poly_dist`。
- `mk_obj` 对 ndarray 面表加 `foreach_set` 快路径（旧版对百万级面做 Python `sum(len(f))`）。
- 所有道具落地改读 `_Z` 网格（`_gz`）而不是 `heights()` 标量噪声。
- `_rss_mb()` 修好：`GetCurrentProcess.restype = c_void_p`（64 位句柄被截断是它一直返回 0 的原因）。

---

## 3. 确切 API

签名不变：

```python
info = hd_landscape.build(MAT, res=20.0, seed=1337, **opts)
```

`info` = `{"objects", "count", "faces", "tris", "verts", "seconds", "ram_mb", "peak_mb", "parts"}`，
`parts` = `{"fields": {"fields", "ridged", "tris"}, "near": {...}, "marks": n}`。

`opts` 可选开关（默认全开）：`rings`、`fields`、`woods`、`town`、`near`、`marks`、`buildings`、`crowns`。

其他公开接口：

| 名字 | 用途 |
|---|---|
| `hd_landscape.strip_old(fields=True)` | 删 `ground_town` / `ground_outer` / `hill*` / `field*` / `hedge*` / 一切 `land_*` |
| `hd_landscape.height(x, y)` / `heights(xs, ys)` | 高度场（纯函数，可脱 Blender 调用） |
| `hd_landscape._gz(x, y)` | 从已建好的 `_Z` 网格双线性采样（比 `heights` 快 100×） |
| `hd_landscape._city_sd(x, y)` | 到城墙轮廓的有符号距离（正 = 城外） |
| `hd_landscape._FIELDS` / `_NEARINFO` / `GARDEN_POS` | 诊断用：田块表 / 近郊统计 / 菜园坐标 |

新子模块（都可以单独 import，纯 numpy 部分能脱 Blender 跑）：
`hd_landscape_mat.py`（7 个材质）、`hd_landscape_geo.py`（树 LOD / 树篱 / 干砌墙 / 垄沟 / icosphere）、
`hd_landscape_fields.py`（田块布局与垄沟）、`hd_landscape_props.py`（干草垛 / 柴垛 / 车 / 羊圈 / 畦）、
`hd_landscape_near.py`（近郊带 + 田块毯）、`hd_landscape_marks.py`（11 个地标）。

---

## 4. 实测数据

<!--MEASURE-->

---

## 5. 验收图

<!--SHOTS-->

---

## 6. 剩余问题（诚实清单）

1. **河道的归属**：`hd_landscape` 的 `RIVER` 折线现在严格沿 `hd_river` 的港湾河道走
   （`|x| < 1150` 段 `y = −762`、半宽 46、水面 −0.62），两端才拐出去。地形在城内做的是**干净河槽**
   （直落 −3.22），岸墙、水面、南门桥全部由 `hd_river` 负责。如果 `hd_river` 的 `RIVER_Y` 再改，
   这里的 `HARBOUR_Y` 必须同步，否则河槽会错位。
2. **树篱与树的视觉验收只在 480×270 / 8 spp 下反复看过**，960×540 的最终五张已出（见第 5 节），
   但**没有**和真实城市（`capital.py`）一起渲过 —— 全部用 `look/land_lab.py` 的 standin 城市。
   城市与本模块的接缝（城墙内侧、四门、港湾两岸）需要主 AI 在整合后看一眼。
3. **`ground_town` 被删**：`strip_old()` 删它、`build()` 重建 `land_townfloor_n/s`。
   如果主 AI 在 `strip_old()` 之后还有代码去碰 `groups["ground"]` 里的 `ground_town`，
   会拿到已删对象 —— `_prune_dead(groups)` 已经处理，但调用顺序必须是 prune 在 strip_old 之后。
4. **远处田块的垄沟只有材质层**：`near_r = 2250 m` 之外没有几何垄。俯视 52° 下材质层在
   2 km 内够用，再远会退化成平色块（那时也只有几个像素）。
5. **`land_carpet` 是 16 k 个独立四边形**（一个对象、32 k 三角）。它依赖 `_gz` 采样，所以
   必须在 `_build_terrain` 之后调用；单独调 `hd_landscape_near.build()` 会拿到 `_Z is None` 的慢路径。
6. **西/西南方向田块偏少**：`_forest_mask` 与坡度把那一侧的田块拒了，实际是林地和牧场。
   这在游戏里是对的（那一侧是王室猎苑），但如果主 AI 希望四向均匀，需要调 `layout()` 的
   `_forest_mask > 0.50` 阈值。
7. 地标的选点用**环内最高/最平点**，个别地标（`land_hermitage`、`land_beacon`）会落在很陡的坡上，
   低机位贴近看会发现地基没完全贴合地面。

---

## 7. 需要主 AI 在 capital.py 里确认/插入的逐字代码

`capital.py` 现在的 `stage == "full"` 分支已经是这个形状，**不需要改**，但要确认三点：
`build_ground()` 在它之前、`_prune_dead()` 在它之后、`FLAT_IN/FLAT_OUT` 用的是 `R_OUTER + 常数`。

```python
        # --- the land outside the walls -------------------------------------
        # strip_old() also removes capital's ground_town / ground_outer discs:
        # the landscape rebuilds that floor as a 20-gon split round the
        # harbour, 3 cm proud of the terrain, so the wall foot has no seam.
        import hd_landscape as LS
        LS.FLAT_IN = R_OUTER + 60.0      # apron starts 60 m outside the wall
        LS.FLAT_OUT = R_OUTER + 190.0    # ...and is fully rough by 190 m
        LS.strip_old()
        info = LS.build(MAT, res=20.0, seed=1337)
        print("[capital] land: %s objects, %s faces, %.1fs, peak %.0f MB"
              % (info["objects"], info["faces"], info["seconds"],
                 info["peak_mb"]), flush=True)
```

如果 `capital.py` 里 `groups["ground"]` 还会被后续 pass 遍历，请在 `LS.build()` 之后调用一次：

```python
        _prune_dead(groups)
```

（`_prune_dead` 已在 `capital.py:2201` 定义，只摘掉被删对象，不做别的。）

调试单模块时可以用（不打开大 blend）：

```bash
python look/_lr.py look/land_lab.py -- --shots a_wall --samples 8 --res 480x270 --no_city
```
