# AGENT_PLAZA — 广场与市场工程师

## 状态（2026-11-02 15:45 断电前）

- **已完成**：侦察与集成契约测绘（读 BRIEF、hd_market.py、capital.py、hd_common.py、medkit.py、hd_nature.py、look/cath_lab.py、look/export_run.py、look/_lock.py）。**没有写任何代码**。
- **进行到一半**：无。`hd_market.py` **一个字节都没改**（保持 138,262 B / 2823 行原样），`look/market_lab.py` **尚未创建**。断电不会留下半截代码。
- **未验证的改动（重要）**：无。当前工程状态 = 断电前的干净状态。
- **下一步第一件事**：写 `look/market_lab.py`（照抄 `look/cath_lab.py` 的骨架：argparse + build + tri/bbox 统计 + 相机循环 + `H.setup_engine`），然后在 `hd_market.py` 里加 `plaza()`。
- **我改过的文件**：仅本文件 `E:\My World\Docs\AGENT_PLAZA.md`（新建）。

---

## 1. 已确认的集成契约（省掉重新侦察的 40 分钟）

### 1.1 三个广场的真实位置与占地（`Blender\kingdom\capital.py`）

| 广场 | 中心 | r | 地标 | 地标占地 |
|---|---|---|---|---|
| 中心大市场 | `(0, 0)` | 96 | `market_hall` 在 `(0, 34)`，正面朝 -Y | x ±23，y 19.35..48.65（FOOTPRINT 46.0 × 29.3） |
| 教堂广场 | `CATH_C = (-152.0*CITY_SCALE, 58.0*CITY_SCALE)` | 78 | 主教座堂在广场**中心** | 50 × 94 m（半宽 27 / 半长 49） |
| 公会广场 | `GUILD_C = (142.0*CITY_SCALE, 66.0*CITY_SCALE)` | 52 | 公会厅在广场**中心** | 23 × 38 m（半宽 11.5 / 半长 19） |

- 喷泉在 `(0, 0)`，直径 13.7 m → 保留 r≈7.4 圆盘。
- `capital.py:1550 build_market_hd()`：`hy = 34.0`；`hd_glue().market_hall(M, rng, 0.0, hy, 0.0, 0.0)` + `fountain(M, rng, 0.0, 0.0, 0.0, 0.0)`。
- `capital.py:1559-1578` 还有一段**遗留摊位循环**：`B.market_stall` 6+6 个，在 `y = ±13.0`、`x = -22.0 + i*8.6`，以及 5 组 `B.cart`/`B.barrel_cluster` 在 r=30 的环上。**这批道具就是渲染里那些"漂浮的薄板遮阳篷"**（见下 §3 判读）。我的 `plaza()` 应该取代它们，报告里要写清楚删哪几行。
- `capital.py:1913-1927` 已经给三个广场铺了 `disc(...)` 整块铺地 + 48 段路缘（`kerb_%s_%d`，在 `r+0.30`，高 0.16、z=0.14）。**所以 `plaza()` 的铺地纹样必须做成"铺在上面的一层"（z ≥ 0.10），或者用 `floor=False` 关掉自带地面。**
- `capital.py:1603 _plaza_dress(res)` 给三个广场注入了 `role="square"` 的合成街区，`hd_streetlife.market_spots` 会往广场铺摊位行 —— 我加的东西必须和它共存，不要指望它消失。

### 1.2 `hd_market.py` 现有 API（2823 行，全部可复用）

```
market_hall(MAT, rng) -> list     # 40 x 22 m；拱廊 10 跨、跳层木构、3 老虎窗、脊上钟塔、
                                  # 4 块吊招牌、3 座藤棚、5 个摊、货箱、2 车、-X 侧外楼梯
guild_hall(MAT, rng)  -> list     # 18 x 28 m
fountain(MAT, rng)    -> list     # 12 x 12 m 八角池 + 2 层水盘 + 铜像
build(kind, MAT, rng, at=None, rz=0.0, **kw)   # 统一入口，at 会把变换烘进 mesh
footprint(kind) -> (x, y)
MAT_KEYS, FOOTPRINT, preview()
```

**可直接复用的私有件**（签名逐字）：
```
_sign(name, T, w, h, iron, wood, board, mat_emblem, gold)
_cloth(name, T, w, d, mats, sag=0.16, folds=4, fold=0.045, seg=12, rows=4,
       scallop=0.055, rng=None, drop=0.0, thick=None)     # 悬挂布幔/条纹棚
_awning(name, T, w, d, z_hi, z_lo, wood, cloth, iron, rng=None)
_stall(name, T, w, d, wood, cloth, cloth2, iron, goods, rng)   # 2.75x1.6，~23 对象
_crate_pile(name, T, rng, wood, goods, n=5)
_sacks(name, T, rng, cloth)
_bench(name, T, w, stone)
_pigeon(name, T, body, head, s=1.0)
_ring_slabs(name, T, r0, r1, n, mats, thick=0.055, z=0.0, gap=0.035, rng=None,
            a0=0.0, a1=math.pi*2)          # 一圈放射铺石，按材质合批
_pave_disc(name, T, r_out, r_in, rings, n, mats, rng, thick=0.06, z=0.0)
_flag_field(name, T, x0, x1, y0, y1, cw, ch, mats, rng, gap=0.04, thick=0.05, wear=0.006)
_water_disc(name, T, r, mat, seg=64, rings=14, amp=0.012, wl=0.9, thick=0.03)
_loft(name, T, rings, mat, seg=20, fold=0.0, folds=6, smooth=True, cap_bottom=True, cap_top=True)
_seg(name, T, p0, p1, w, d, mat, bev=0.0, y=0.0)   # 局部 XZ 平面内的斜撑
_flat(seq)                                          # 展平 + 丢 None
_palette(MAT)                                       # 补齐缺失键，不会 KeyError
```

### 1.3 通用件（`hd_common as H` / `medkit as K`）

```
H.poly(name, verts, faces, mat, T=None)     H.lathe(name, profile, mat, seg=32, T=None, ...)
H.prism / wedge / apply(parts, T) / bbox / tri_count / _clear()
H.lantern_post(name, T, h, iron, glow)      H.barrel(name, T, r=0.30, h=0.84, wood, hoop)
H.crate(name, T, s=0.62, wood)              H.cart(name, T, wood, iron, L=2.0, W=1.1)
H.market_stall(name, T, w, d, wood, cloth, cloth2)   # 薄板棚，别用，用 _stall
H.banner(name, T, w, h, cloth_mat, pole_mat, pole_h=None)
H.statue(name, T, h, stone)                 H.stairs(name, T, w, steps, rise=0.18, run=0.32, mat)
H.diorama_floor(mat, size=260)              H.setup_world(sun_energy=4.2, sky, fill=0)
H.setup_engine(samples, res, gpu)           H.camera(name, loc, look_at, lens=50, ortho)
H.render_to(path, cam)                      H.three_views(name, center, size, dist)
K.box(name, T, size, mat, bev) / cyl(name,T,radius,height,mat,seg,cap,r2) /
  cone / sphere(name,T,radius,mat,seg,ring,squash) / lantern(name,T,iron,glow,scale) /
  mat_flag/mat_stone/mat_wood/mat_cloth/mat_earth / T_at(x,y,z,rz,ry,rx) as Ts
```
**所有基本体的枢轴都在 T 的原点中心**（box/cyl/cone/sphere 都是），`H.stairs` 从 T 向上长。
`hd_common` 的约定：**正面朝 -Y**（太阳在 -Y 天顶，`setup_world` 用 euler (52,0,38)）。

### 1.4 `hd_nature` 椴树

```
tree_beech(seed=0, MAT=None) -> [ob]     # MAT 来自 N.make_materials()
tree_oak(seed=0, MAT=None) -> [ob]       # 14-18 m 高，clump_count=680 → 每棵约 5-20 万面
```
**风险**：`_broadleaf` 的 `clump_count=680`、`clump_sub=1`，单棵可能 5 万+ 面；12 棵 = 60 万+。必须先测。`_finalize(center="keep")` 会把对象压到 z=0 且 `matrix_world = Identity`，可以直接 `H.apply(parts, Ts(x,y,0,rz=...))`。
备选：自己在 hd_market 里写 `_lime_tree()`（干 + 3-4 主枝 + 12-14 个压扁球冠，约 3k tris/棵），织梦岛风格更读得出来。

### 1.5 运行方式（已确认锁是空的：`python look\_lock.py` → `free  light slots: 0/3 used`）

```
python look\export_run.py <tag> 900 LIGHT -- -b <lab.blend> --python look\market_lab.py -- --tag t1 --res 480x270 --samples 8
```
`_NO_BIG` 哨兵在 `E:\My World\Logs\_NO_BIG`：任何命令行里出现 >400 MB 的 blend 会被拒绝启动。`MAX_LIGHT=3`，`LIGHT_STALE=240`，看门狗 `IDLE_KILL=360`。
**绝不打开 `capital_*.blend`。**

---

## 2. 设计（已定，按此实现）

### 2.1 `plaza()` 签名

```python
def plaza(center=(0.0, 0.0), r=96.0, MAT=None, seed=7, kind="market",
          reserve=None, floor=True, kerb=True, density=1.0, trees="auto"):
    """往一个 r 米的圆盘广场里布置城市客厅。返回对象列表（世界坐标，identity 变换）。

    kind: "market" | "church" | "guild"
    reserve: [(kind, x, y, a, b)]，广场局部坐标；默认按 kind 自动生成
             market -> [("rect",0,34,23.0,14.65), ("disc",0,0,7.4)]
             church -> [("rect",0,0,27.0,49.0)]
             guild  -> [("rect",0,0,11.5,19.0)]
    floor: 自带圆盘地面 + 铺地纹样（独立 lab 用 True；capital.py 已铺过用 False）
    kerb:  自带外圈路缘 + 排水沟
    """
```
外加 `church_plaza(...)` / `guild_plaza(...)` 薄包装。

### 2.2 铺地纹样（ROI 最高，先做）

- 中心圆盘纹样 r 7.4→18：实心浅色路缘 → 32 块放射石（pale/warm 交替）→ 深色细环 →
  48 块日芒 → 深环 → 24 块外圈 → 浅色外缘。用 `_ring_slabs` 合批，约 12 个对象 / 1.5k tris。
- 4 条**正交大道**（0/90/180/270°）r 18→92，宽 7→9.5 m，`stone_pale` 铺石带（1.5 m 横 × 2.5 m 纵，错缝）。
- 4 条**斜向踩踏小径**（45/135/225/315°）r 18→90，宽 4.2→6 m，`ground_worn`，每条 course 边缘 ±0.6 m 抖动（读作"人踩出来的"）。
- 2 条环形道：r=44（宽 6 m）、r=76（宽 5 m），把放射路串起来。
- 外圈路缘 64 段（`r+0.30`，9.4×0.7×0.18）+ 内侧排水沟环（r 93.0..93.7，深 0.10）+ 8 个铁篦子。
- 对比度是全部意义：大道/纹样必须比底铺**亮 2 档**，斜径**暗 1 档**，否则 52° 俯角下什么都看不见。

### 2.3 四象限（market，局部坐标）

| 象限 | 内容 |
|---|---|
| SE (x>0,y<0) | 主摊区：沿 S 大道东侧 6 摊（x=+6.5, y=-24..-54, step 6.0）+ 沿 E 大道 5 摊（y=-8.5, x=26..54）；`_crate_pile`/`_sacks`/`H.cart`/`H.barrel` 补缝 |
| SW (x<0,y<0) | 牲畜交易角：26×16 围栏（柱距 2.2 m，2 道横杆 + 斜撑 + 5 杆门），稻草地面，草架、水槽，3 羊 + 1 牛 + 1 猪（压扁椭球 + 头 + 4 腿桩），干草堆 |
| NE (x>0,y>0) | 水井（石鼓 r1.5 + 双木柱 + 小瓦顶 + 辘轳 + 绳桶）+ 饮马槽（4.0×0.9×0.75 石槽 + 水面 + 拴马横杆）+ 车 + 桶 |
| NW (x<0,y>0) | 公告角：公告板（双柱 + 小双坡顶 + 4 张羊皮纸 + 火漆印）、枷锁台（0.35 m 台 + 带孔横板）、传令台（3 级石台 + 旗杆）、绞刑架（r≈78 边缘，4.2 m 双柱 + 4.5 m 横梁 + 绳套） |

补充：椴树 8-12 棵在 r 82..90（避开 4 个大道口和市厅）；路灯 12 支在 r=88 + 4 支在纹样外缘；
石凳 8 张围绕 r=20 + 树下若干；乞丐/街头艺人台阶：SW 的 L 形 3 级矮台（12×8 m，0.55 m 高）
+ 2 个坐姿人 + 1 个耍把戏的 + 地上的帽子；鸽子/狗若干。

### 2.4 市场厅要补的（ROI 第 3）

现有已够：10 跨拱廊、跳层、3 老虎窗、脊上钟塔、4 吊招牌、3 藤棚、-X 外楼梯。
**缺**：① 拱廊里的**售货柜台**（5 张矮桌 + 台面货 + 上方吊灯）；② 跳层下的**悬挂布幔/彩旗**（用 `_cloth` 在拱廊柱之间做垂花）；③ 正面两根大幡杆。
在 `market_hall()` 的 `return _flat(out)` 前插入，不碰 `FOOTPRINT`。

### 2.5 教堂广场 / 公会广场

- 教堂（仪式性）：中轴 3 级大台阶 + 两侧长椅列 + 3 座小神龛（aedicula）+ 香炉/火盆柱 + 朝圣者歇脚点（矮凳 + 水钵）+ 十字架纪念柱 + 修剪整齐的椴树行 + 路缘花池。
- 公会（商业性）：马车停靠区（3-4 辆车 + 拴马桩）+ 货栈平台（木台 + 桶/箱堆）+ 公告板 + 护卫岗亭（2 人 + 长矛架）+ 排水沟。

---

## 3. 对现有渲染的判读（`E:\My World\Blender\renders\kingdom\look\v25a_eye_plaza_south.png`，1280×720，1.72 m 眼高朝北）

**好**：市场厅本体读得出来（赤陶屋顶 3 老虎窗、钟塔、木构跳层、拱廊），山体远景有空气感。
**差**（这就是我要修的）：
1. **铺地是一整片无纹样的纸** —— 只有材质噪声，没有路缘、没有排水沟、没有图案，透视里完全没有尺度参照。**这是最大的问题。**
2. **摊位是漂浮的薄板**：`B.market_stall` 的遮阳篷是一块 5 cm 厚的平板，没有下垂、没有缘饰、没有支柱落地感，从 20 m 看像插在地上的彩色卡片。
3. 拱廊底下一片黑，柜台/货物/人全没有 —— 建筑有体量但没有"营业"的感觉。
4. 没有树、没有灯、没有凳子、没有人 —— 广场没有生命。
5. 喷泉正对厅正面，挡住了厅的基座（构图问题，但 52° 机位可以靠偏移解决）。

---

## 4. 待办（按顺序）

1. `look/market_lab.py`：96 m 圆盘 + 市场厅 + `plaza()`，6 个机位，`--res/--samples/--cams/--kind/--cathedral`。
2. `hd_market.py` 加 `_Occ` / `_ring` / `_radial_band` / `_medallion` / `_pen` / `_notice_corner` / `_well` / `_trough` / `_lime_tree` / `_figure` / `plaza()` / `church_plaza()` / `guild_plaza()`。
3. 迭代 480×270 / 8 spp；最后 6 张 960×540（广场 52° 游戏机位、1.72 m 眼高、市场厅正面、摊棚近景、教堂广场、公会广场），前缀 `plz_`。
4. 本文档补实测数据（对象数/面数/耗时/峰值内存）+ 给主 AI 的逐字接线代码。
