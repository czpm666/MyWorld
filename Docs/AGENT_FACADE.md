# AGENT_FACADE — 分户山墙 / 侧墙 / 背墙的构造化

日期 2026-11-02。只改了 `hd_houses.py`、`hd_houses_parts.py`，另加 lab：
`look/facade_lab.py`、`look/_fac_shot.py`、`look/_fac_panel.py`、`look/_fac_dbg.py`。
未触碰 capital.py / capital_hd_glue.py / hd_dense.py / hd_plan2.py / hd_roof.py /
hd_surface.py / hd_paving.py / look/render.py / look/spots.py。

---

## 0. 一句话

`house()` 以前把**所有非临街面**都造成一块无开口的 `K.box`（背墙 `gb`/`ub%d`，
地坪层侧墙 `gs%d`），上层侧墙也只有每层一扇 0.86 m 的洞；而 `P.window()` 的窗台、
滴水、过梁、拱券**全都用墙体自己的材质**。于是 34 m 机位下：墙是一整块，窗是一块黑。
现在非临街面是有开口、有勒脚、有楼层石带、有檐口、有隅石、有落水管、有百叶的墙；
窗的投出件全部换成与墙**不同明度**的石材，并加了抹灰洞口衬里。

## 1. 证据链（先证明问题在哪，再动手）

| 证据 | 结论 |
|---|---|
| `renders/kingdom/look/V24_gate.png` 右侧 45% 浅绿平墙 | 不是"山墙"，是**背墙**：背墙代码就是两个无开口 box |
| `fac_old_flank.png`（1.72 m 眼高、13 m 正对端头侧墙） | 整面 sage 绿平墙，每层 1 扇小窗，勒脚只有一条苔线 |
| `fac_old_backs.png`（1.72 m、30 m 正对背墙） | 背墙完全无窗；两块相邻背墙同色，**接头看不见**，形成 15 m 连续平面 |
| V24 blend mtime 2026-11-01 15:57 > hd_houses.py 13:31 | 新城建已在 v24 里，不是"图是旧的" |

三个根因，按影响排序：

1. **非临街面没有几何**：背墙、地坪层侧墙是纯 box；上层侧墙每层一个洞。
2. **明度不成立**：窗台/滴水/过梁/拱券用 `wall_mat`（= 墙的材质），
   34 m 下 0.09 m 窗台 = 2.7 px 同色 → 等于不存在；玻璃在洞内 0.17 m，
   框只有 0.075 m 宽，于是"洞+玻璃+框"糊成一团黑。
3. **没有楼层/分户的竖向与横向节奏**：没有檐口、没有楼层石带、没有隅石、
   没有落水管（落水管只有临街檐口那一根）。

### 1.1 先把"看得见"量化（后面所有尺寸都由这两个数决定）

960×540、30° vFOV、34 m 机位 = **29.6 px/m**（480×270 折半 14.8 px/m）：

| 尺寸 | 34 m 下 | 判断 |
|---|---|---|
| 0.09 m | 2.7 px | 不可读（旧窗台） |
| 0.15 m | 4.4 px | 勉强 |
| 0.26 m | 7.7 px | 可读 |
| 0.34 m | 10 px | 清楚 |

**规则：小于 0.15 m 的投出件在游戏机位等于没做。** 这条规则直接决定了
下面的 0.14 m 窗台、0.34 m 檐口、0.065 m 半径落水管、1.02 m 窗宽。

## 2. 改了什么，为什么

### 2.1 非临街面：从 box 到有开口的墙（核心改动）

- 地坪层侧墙 `gs%d` → `_wall(...)`，开口 = 1 或 2 扇 0.92×1.06 的带铁棂小窗。
- 地坪层背墙 `gb` → `_wall(...)`，开口 = 后门 1.06×2.10 + 1 扇窗；
  后门带门框、门扇、石门槛、一级台阶（`P.door` + `steps=1`）。
- 上层背墙 `ub%d`（原来一个 box）→ `_wall(...)` + 1–3 扇窗；
  与侧墙同一套配件。
- 窗数按面宽定：侧面 `nsw = 3 (d≥9.8) / 2 (d≥7.2) / 1`；
  背面 `nsb = 3 (w≥8.6) / 2 (w≥5.6) / 1`；塔楼恒 1，仓库封顶 2。
- 面数预算放在轮廓上：所有窗按**材质**合并（见 2.2），
  一面墙的窗 = 最多 6 个 mesh，而不是每窗 ~20 个 object。

### 2.2 `_win_batch()`：让侧/背窗付得起

新增函数（`hd_houses.py`，`_band`/`_pipe` 之后）。每个窗只往
`trim/wood/glass/void/rev/shut` 六个桶里 append `(matrix, size)`，
最后每桶一次 `P.boxmesh()`。一栋 3 层、8 个侧背窗的房子从 ~160 个 object
降到 ~28 个。**没有这一步，改动会让每街区构建时间超 3 s（实测 5.50 s / 20 栋）。**

### 2.3 窗的明度结构（对应 brief 第 2 条）

| 构件 | 旧 | 新 | 为什么 |
|---|---|---|---|
| 窗台 | (w+0.26)×0.34×**0.09**，`wall_mat` | (w+0.34)×0.40×**0.14**，`trim` 石材 | 0.09 m = 2.7 px 同色，看不见 |
| 滴水 | 0.055 高，`wall_mat` | 0.07 高，前挑 0.20，`trim` | 阴天靠这条线 |
| 过梁 | (w+0.40)×0.20×0.11，`wall_mat` | (w+0.46)×0.22×0.13，`trim` | 洞口上沿要有一条亮带 |
| 框 | 0.075 宽 | 0.08 宽，两梃+上下槛+中梃+横档 | 分格，否则是黑块 |
| 玻璃 | 洞内 0.17 | 洞内 **0.16**，前面加 0.06 黑洞 | 保持"深"的读感 |
| 洞口衬里 | 无 | `reveal=plaster` 抹灰三面（`yr=-deep*0.5+0.02`） | 黑洞口的一圈亮边 = 进深 |
| 百叶 | 只有街面部分类型 | 侧/背窗按 `st["shut"]`（0.12–0.62）随机加 | 灰墙上唯一的饱和色，34 m 唯一还认得出的"这是住宅" |

`P.window()` 因此新增两个关键字参数：`trim=None`、`reveal=None`
（默认值保持旧行为，`hd_houses.py` 三处街面调用都显式传了）。
全工程只有 `hd_houses.py` 调 `P.window`（grep 确认），改签名安全。

### 2.4 横向与竖向节奏（对应 brief 第 1、4 条）

- **楼层石带** `_band()`：侧墙 `sb%d_%d`、背墙 `bb%d`，每个楼层线一条
  0.20 m 高 / 外挑 0.11 m 的石带；地坪层 0.18 m。
- **檐口** `ec%d`/`ecb`：`eave_z-0.34`，0.34 m 高、外挑 0.26 m。
  整个立面以前没有顶边，瓦片直接停在墙上。
- **脚木 sole plate** `spl%d`/`splb`：0.20 m 高、外挑 0.07 m 的深色木，
  压在勒脚顶上。石墙+石勒脚时基座本来没有任何边界。
- **隅石** `qk_f`/`qk_b`：`_quoins()` 在我改之前**从未被调用过**
  （`_STYLE["quoin"]` 是死字段）。现在临街 + 背面四个角都贴，
  长 0.34/0.26 m、外挑 0.05 m，交错叠到檐口。这是"两户分界"最直接的信号。
- **落水管** `_pipe()`：背面一个角，r=0.065、8 边、每 ~1 m 一个抱箍、
  顶部集水斗、底部弯头。有出挑的层从出挑下沿起（`pz0 = pl_h + fh`），
  否则管子会悬在挑出墙体后面的空气里。
- **地坪层侧墙木构架** `tgfs%d`：以前只有临街地坪层有 `tfg`，
  侧墙地坪层是一整块空板——那恰恰是玩家贴脸走过去的墙。

### 2.5 材质：两个新石材（走既有 pal 通道）

`hd_houses_parts.house_materials()` 新增：

```python
"stone_trim": K.mat_stone("hu_stone_trim", "#bdb3a1", "#8b8271", "#d2c9b6", 3.4),
"stone_dark": K.mat_stone("hu_stone_dark", "#6a6255", "#3f3a31", "#847a6a", 3.0),
```

分配规则（`house()` 里）：

```python
stone_t = MAT.get("stone_trim") or stone_w
stone_d = MAT.get("stone_dark") or stone_t
trim_m  = stone_d if is_stone else stone_t
```

- 灰泥墙（8 个变体 `#cfc6b2…#a8a795`）用**浅色**石灰岩投出件 → 窗台比墙亮。
- 琢石墙（`hu_stone`/`hu_stone_warm`）用**深色**石材 → 因为 `hd_surface` 把
  `-Y` 朝向的背墙判成向阳面并 bleach 到浅灰，浅色窗台会和墙同明度（这是
  `fac_new_backs` 第一轮"窗读不出来"的真正原因，不是尺寸不够）。

这两个 key 加在 `house_materials()` 里，因此自动进入
`capital_hd_glue.house_mats()` 的 pal、自动被 `SFC.apply_weathering` 扫到，
**没有 `bpy.data.materials.new`**。它们也被 `_age(..., "stone", 0.80)` 上了风化，
日志可见 `[surface] hu_stone_trim -> stone s=1.00 blocks=True`。

### 2.6 顺带修掉的三个几何 bug

1. **背墙的配件全埋在房子里**：`_wall()` 把墙放在 `y..y+thick`，所以墙的
   外表面在 `y+thick`，而 `_win_batch`/`_band`/`_quoins`/后门都按"原点在外表面"
   写。结果背墙的窗台、过梁、楼层带、后门扇、隅石全部落在房子中间（不可见，
   却照样付面数）。已改为从外表面起算：`BTF = Ts(0, -(dd*0.5), z, rz=pi)`。
2. `_quoins()` 从未被调用（见上）。
3. 有出挑的房子落水管从地坪起 → 悬空 0.36 m（见 2.4）。

### 2.7 lab（`look/facade_lab.py`）

- 3 排：A 排 10 栋临街，B 排只放前 4 栋（镜像 `back=True`）——**B 排以前一整排
  把 A 排背墙全挡住，任何机位都看不到背墙**，这是 lab 自己的 bug。
- 7 个机位：`hero`(52°/34 m)、`eye`(1.72 m)、`backs`(1.72 m、30 m 正对背墙)、
  `backs52`(52°/34 m 看背墙与窄巷)、`row`(22°/62 m)、`close`(3/4)、
  `flank`(1.72 m 正对端头侧墙)。
- **只调 `hd_light.apply("morning_town")`，不叠 `hd_sky.world()`**：
  两者叠加会把整帧渲成纯白（已实测），而且城市的 `look/render.py`
  默认 `sky=None`，本来就不叠。
- 地面换成 lab 专用的深色石材（`_ground()`）：原来用房子的浅色石灰岩，
  在 morning_town 下过曝成白板，会让墙显得比实际更暗。**仅 lab 用，不进城市。**

## 3. 预算（实测，不是估算）

### 3.1 单栋

| | 旧 | 新 | 倍数 |
|---|---|---|---|
| tris/栋（lab 同 14 栋） | 4,192 均（2,873–5,686） | **6,973 均（4,789–11,145）** | 1.66× |
| object/栋 | ~230–250 | 218–408 | 1.3× |
| lab build | 107 ms/栋 | 127 ms/栋 | 1.19× |

最大的是 3 层 inn：11,145 tris / 408 objects。预算 25,000 tris → 余量 2.2×。

### 3.2 城市（build_v25.log，含本次最终代码）

```
[capital] hd city done: 12948 buildings (houses 12755 / shops 193 / failed 0)
          objects=258 faces=46684660 tris=95537793 in 862 s
[capital] hd city blk 3/258  15 buildings  build 0.8 s
[capital] hd city blk 2/258  22 buildings  build 1.4 s
[capital] hd city blk 10/258 34 buildings  build 1.9 s
[capital] hd city blk 1/258  31 buildings  build 3.2 s   (首块，含材质首次 weathering)
[capital] hd city blk 5/258  87 buildings  build 5.2 s
[capital] hd city blk 258/258 120 buildings build 8.0 s
```

- **failed 0**，12,948 栋，一栋没崩。
- 边际成本 **56–67 ms/栋**（v24 是 38–44 ms/栋）→ **+50%**；
  15–34 栋的常规街区 **0.8–2.4 s**，在 3 s 预算内；
  87/120 栋的巨块 5.2/8.0 s（这种块在 v24 也超，且不是常态）。
- 全城 24.4 M faces → **46.7 M faces / 95.5 M tris**（1.9×，预算允许 8–9×）。
- 单栋 7,375 tris（v24 是 ~2,000 faces ≈ 4,000 tris）。
- 862 s 建全城（v24 843 s，+2%）——**总构建时间几乎没变**，因为合并策略吃掉了增量。

### 3.3 lab 渲染

480×270/8 spp 七机位 + 14 栋 = 27–31 s（构建 2.9–3.4 s + 每张 ~4 s）。
960×540/32 spp 三机位 = 28–40 s。等锁是大头：实测 44 s–1,862 s 不等
（`build_v25` 是全城构建，pin 住了锁）。

## 4. 四联图判读（老实说）

图：`renders/kingdom/look/FAC_compare.png`（2×2，上=52°/34 m，下=1.7 m 眼高，
左=改前，右=改后）。单张为 `FAC_before_52.png` / `FAC_after_52.png` /
`FAC_before_eye.png` / `FAC_after_eye.png`。

**52° / 34 m（`backs52`）**：改前背墙是两块同色平面拼成的 15 m 灰墙，
楼层的横缝是唯一的几何；改后每户有 1–2 列窗（带深色石台和过梁）、
后门、楼层石带、檐口、隅石、落水管，**两户之间的分界能看出来了**。
仍差：琢石墙本身的砌块尺度很大（`hd_surface` 的 `blocks=True` 图案，不在我文件里），
所以石造房子的背墙在远处仍偏"要塞感"；这是材质图案的锅，不是构造的锅。

**1.7 m / 30 m（`backs`）**：改前是一片墙 + 一条苔线；改后能看到门的石框、
窗台投出的阴影、脚木、隅石。仍差：地坪层背墙 7 m 只有 1 门 1 窗，
中间还有 ~1.5 m 空档；如果要更"住人"，应给背面再加一扇窗或一个披屋
（代码里加一行 `nsb` 即可，但会再加面数，我没做）。

**1.7 m / 13 m（`flank`，brief 里那面 45% 的墙）**：质变。木构架成排、
楼层石带、窗台+滴水+百叶、勒脚苔线、落水管、底部脚木都在。
仍差：地坪层那扇窗偏小偏高（0.92×1.06，窗台 1.28 m），近看仍显空；
远处（34 m）倒是刚好。

**52° / 34 m（`hero`）**：这个机位 60% 画面是屋顶，侧墙背墙全被遮住，
**它验证不了本次改动**。街面窗、jetty 托木、雨棚、招牌都读得出。
结论：判据只能用 `backs`/`backs52`/`flank`。

**已知没解决的**：`fund_flank` 那种 sage 绿来自
`capital_hd_glue.house_mats()` 的 plaster 变体 5 `#a8a795`（"faded sage"），
属于调色板设计，我没动——它现在被构造打散了，但颜色本身没变。

## 5. 没做 / 还差什么

1. **jetty 出挑**：`_STYLE["jetty"]=0.30–0.38` 早就有，`P.jetty` 托木也在，
   但只挑 f=1 一层、f≥2 又缩回地面宽度。要改成"逐层累加"会加大出挑，
   而 `hd_dense` 的 0.22 m GAP + capital 的 `w=hw*sc-0.5` 只给了 0.72 m 净空，
   两层各挑 0.36 就顶死了。**要改必须和 `hd_dense` 的排布一起改，不在我的文件里。**
2. **地坪层背墙/侧墙仍偏空**（见 4）。加窗是一行代码，但面数和"储藏间没有窗"
   的真实性要权衡。
3. **8 种类型的辨识度**：现在靠（a）屋顶形式 gable/hip/crenel，
   （b）层数，（c）有无 jetty，（d）`st["frame"]` 有无木构架，
   （e）窗排布 nw/ww/wh/shut。这 5 条本来就在 `_STYLE` 里，我只是让 (d)(e)
   在侧背面上也生效了。**没有新做类型专属的立面语言**（比如仓库的吊货门、
   塔楼的箭孔在背面没有）。这是下一个 agent 的活。
4. **砖石砌块尺度**（`hd_surface` 的 `blocks=True`）让石墙背面偏"要塞"，
   要改得动 `hd_surface.py`，不在我的范围内。
5. `_age(plaster, "plaster", 1.85)` 的白色斑块在近景仍像泼漆（`fac_new_close.png`）。
   这是 hd_surface 的 plaster 配方 × 我给的 1.85 强度；降到 1.2 会更好看，
   但会让墙面整体变干净、失去那层灰。**留作取舍，没改。**

## 6. 需要主 AI 插的代码

**不需要插任何代码。** `capital.py` 调的是
`G.house(M, rng, p["x"], p["y"], p["yaw"], max(4.6, hw*sc-0.5), hd_*sc,
int(hf), kind, frontage, variant=vv, back=_ring_no(p)>=1)`，
`house()` 的签名和语义一个字没动，`w`/`d` 仍是地面足迹，
所有新几何都在 `w×d` 投影内（出挑 ≤0.38 m，在 0.72 m 净空内，且只向上）。
`build_v25` 已经用这份代码建了全城：12,948 栋、failed 0。
要看到效果只需**重建城市**（不要复用 v24/v25 的 blend）。

唯一要主 AI 知道的三件事：

1. `hd_houses_parts.house_materials()` 多了 `stone_trim`、`stone_dark` 两个 key，
   自动进 `house_mats()` 的 pal；**不要**在别处再建同名石材。
2. `P.window()` 多了 `trim=None, reveal=None` 两个**带默认值**的参数，
   旧调用行为不变（`_fac_old_houses.py` 与新 parts 混跑验证过）。
3. `hd_sky.py` 在 2026-11-02 13:0x 处于半编辑状态（`hd_sky.py:1395`
   `SyntaxError: '(' was never closed`），任何 `import hd_sky` 的脚本会当场死。
   我的 lab 已改为**不 import hd_sky**（只用 `hd_light.apply`）。
   这不是我的文件，请在合并前确认它已经修好。

如果要调参，全部集中在 `hd_houses.py` 一个区块：

```python
nsw = 3 if d >= 9.8 else (2 if d >= 7.2 else 1)   # 侧墙窗数
nsb = 3 if w >= 8.6 else (2 if w >= 5.6 else 1)   # 背墙窗数
wwin = 1.02 if d >= 6.4 else 0.88                 # 侧/背窗宽
whin = max(0.95, st["wh"] - 0.06)                 # 侧/背窗高
trim_m = stone_d if is_stone else stone_t         # 投出件石材
```

以及三条 `_band()` 的 `h=` / `proud=`（楼层石带 0.20/0.11、檐口 0.34/0.26、
脚木 0.20/0.07）和 `_pipe(..., r=0.065)`。

## 7. 文件

| 文件 | 说明 |
|---|---|
| `Blender/kingdom/hd_houses.py` | 主体改动（`_band` `_pipe` `_win_batch` + house() 的侧/背墙、檐口、隅石、脚木、落水管） |
| `Blender/kingdom/hd_houses_parts.py` | `window(trim=, reveal=)`；`house_materials()` 加 `stone_trim`/`stone_dark` |
| `Blender/kingdom/look/facade_lab.py` | 3 排 14 栋 lab，7 机位，`--fast` |
| `Blender/kingdom/look/_fac_shot.py` | 走 `_lock.run_blender()` 的入口（`old`/`new`/`swatch`/`probe`/`dbg`） |
| `Blender/kingdom/look/_fac_panel.py` | 四联图拼版（纯 PIL，不占 Blender） |
| `Blender/kingdom/look/_fac_old_houses.py` / `_fac_old_parts.py` | 改造前的冻结副本，只用于 before 对比 |
| `renders/kingdom/look/FAC_compare.png` | 四联对比（交付图） |
| `renders/kingdom/look/FAC_before_*.png` / `FAC_after_*.png` | 四张单图 |
