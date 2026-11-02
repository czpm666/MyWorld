# AGENT_ROCK — 岩台与悬崖（子智能体 ROCK）

日期：2026-11-02 · 对应简报 §3 已知缺陷 #3「城堡站在一块平的米灰色水泥板上」
状态：**代码完成、已出图；两项待主 AI 决定（岩台顶面高度实测、断崖是否启用）见 §7**

---

## 1. 改了什么，为什么

原来 `capital.py:build_castle_hd()` 里的岩台是 `rock_mass()`：7–10 个**同轴圆柱环**按 `taper` 缩径堆起来，顶面加一个 `cyl("rock_top", ...)` 圆盘，四周撒 18 个 `rock_boul` 盒子和 26 个 `rock_rim` 盒子。问题不在噪声太少，而在**形状语言错了**：圆柱是"从中心往外摊"的曲面，而人对岩石的识别几乎完全依赖两条**彼此正交**的线——**水平的层理**和**竖直的节理**。任何各向同性的噪声都只会把它做得更像一个面团。

所以 `hd_rock.py` 换了做法：

- 岩台是一个**单值的半径函数 `r(θ, z)`**，不是高度场，也不是旋转体。每一行（层界、层中、路面内/外、碎石坡）都是同一套拓扑上的固定行，扫描 θ 生成条带。这样层理可以是**真几何台阶**（相邻层之间半径差 1.5–4 m），而不是贴图上的假缝。
- 9 层岩层，厚 0.62–2.45 m，其中第 2、5 层强制是 0.62–0.95 m 的**软层**，半径额外内凹 0.45 m ⇒ 每一组硬层下面有一个壁龛，这就是真实石灰岩崖的"层间内凹"。
- 层界随坡向倾斜（`DIP=(0.021, 0.013)`，约 1.4°，横跨 160 m 抬升 ±1.9 m），所以层理面不是水平的圆环，而是斜切的椭圆——这一条对"看起来是真的"贡献极大。
- 每层有**独立**的节理块相位（2.0–5.6 m 一块），块与块之间有 ±0.32 m 的错台和一道 -0.34 m 深的暗缝。竖节理在这一层被层理面切断，下一层重新起算——柱状节理的真实行为。
- 33° 碎石坡（talus）从崖脚一直铺到坡脚，剖面是"贴崖 55–60° → 扇缘 22°"的凹形（直锥只会读成沙丘），上面 2169 块幂律石块 + 46 块 2.2–4.2 m 的崖脚巨块。
- 一条 320° 螺旋凿岩道（宽 4.7 m，5% 坡）从坡脚盘到台顶，路面以上 2.1 m 是竖直路堑面，再往上 2.9 m 斜收回到天然崖面；路面外沿是天然坡，坐 0.60 m 宽 / 0.82 m 高的矮护墙。
- 城外悬崖 `cliff_ring()`：在 `R_OUTER=947.2` 处立一道**环脊**（不是挖沟——外侧地形由 `hd_landscape` 拥有，我不能挖），内侧缓坡没入城内地面，脊顶 6–15 m，外侧是断崖 + 碎石裙，四个城门方向留豁口。

---

## 2. 确切 API

```python
import hd_rock

# 岩台：返回已 link 到当前 collection 的 mesh 对象列表（8 个对象）
objs = hd_rock.build(K, MAT, cx=0.0, cy=303.4, r=82.0, top_z=18.0,
                     seed=11, style="limestone")
# 可选关键字（都有默认值，一般不用管）：
#   nth=1080      环向分段（面数 = 68 行 × nth × 2 tris）
#   plants=True   灌木/草簇/藤蔓/6 棵歪脖子树
#   road=True     上山凿岩道 + 护墙 + 城门台阶
#   drop=17.6     道路总落差（从台顶下到坡脚）
#   gate_deg=-90  城门方位角（度），路从这附近起旋
#   road_deg=(u0,u1)  螺旋起止角，默认 (gate_deg-5, gate_deg-5+320)
#   base_z=0.0    坡脚落地高度
#   verbose=False

# 城外悬崖：返回对象列表（2–3 个对象）
objs = hd_rock.cliff_ring(K, MAT, r=947.2, seed=23, style="limestone",
                          height=(6.0, 15.0), gaps=None, gates=None,
                          nth=1400, cx=0.0, cy=0.0, verbose=False, plants=True)
#   gates 直接传 capital.outer_gaps() 的返回值：[(point, 角度弧度), ...]
#   传了 gates 就自动换算成豁口；gaps=[(度数, 半宽度数), ...] 也可以手给

# 材质（不进 MAT 字典，所以 hd_surface.apply_weathering 不会二次加工它）
m = hd_rock.rock_material(MAT, name="rock_strata", style="limestone")
# 另有 scree_material / turf_material / road_material

# 实测数据（build.LAST / cliff_ring.STATS 里也有）
print(hd_rock.build.LAST.report())
```

`K` = `medkit`（`capital.py` 顶部就是 `import medkit as K`），只需要它提供
`mesh_obj / assign / T_at`。**对象自己 link**（`medkit.mesh_obj` 内部就 link 了），
所以主 AI 那边**不需要**再 `K.link()`，直接 `out += hd_rock.build(...)`。

对象名：`rock_face`（崖面+层理+碎石坡主体，多材质）、`rock_cap`（台顶面）、
`rock_talus`（碎石）、`rock_wall_stones`（贴崖巨石）、`rock_cap_stones`（台顶散石）、
`rock_plants`、`rock_road`、`rock_gate_stair`。

### 材质为什么自己写

`medkit.mat_stone` 是**砌石**材质（Brick 纹理 + Object 坐标），`hd_surface` 会在它上面
再刷一层风化缝，两套缝叠在一起就是"水泥板上的假砖"。岩石要的是**层理**，那是
`abs(几何法线.z)` 的函数：竖面走层理配方，水平面走尘土/裂缝配方。`rock_material`
用的就是 `ShaderNodeNewGeometry.normal → abs(Z) → MapRange(0.88, 0.985)` 来切换，
层理方向由**几何本身**决定，换机位、换朝向都不会漂。它不进 `MAT` 字典，所以
`hd_surface.apply_weathering()`（只遍历传入字典的 key）碰不到它——这是故意的。

---

## 3. 实测数据

（见 §7 的最终实测表：耗时 / 面数 / 峰值内存 / 对象数）

---

## 4. 验收图

（见 §7）

---

## 5. 剩余问题（诚实）

（见 §7）

---

## 6. 主 AI 要在 `capital.py` 里插的代码（逐字）

### 6.1 `build_castle_hd()`：替换岩台

把 `capital.py` 第 **1411–1439** 行（从注释 `# taper 0.30 instead of 0.20:` 到
`out.append(cyl("rock_top", T_at(cx, cy, ROCK_TOP + 0.05), 49.0, 0.9, MAT["stone_warm"], seg=64))`
这一段，含它上面的 `out = [rock_mass("rock_mass", ...)]` 和 18 个 `rock_boul`、
26 个 `rock_rim` 循环）整段换成：

```python
    # -- crag: procedural strata + joints + talus + spiral cut road ----------
    # hd_rock replaces rock_mass + the 18 rock_boul boxes + the 26 rock_rim
    # boxes + the rock_top disc.  See Docs/AGENT_ROCK.md.
    import hd_rock
    out = hd_rock.build(K, M, cx=cx, cy=cy, r=ROCK_R, top_z=ROCK_TOP,
                        seed=11, style="limestone", nth=1080)
```

其余各行（`z = ROCK_TOP + 0.45`、`CS = 1.15`、`out += hd_glue().castle(...)`、
`wedge_ramp(...)`、`mark_disc(...)`）**一个字都不要动**。

### 6.2 `ground_hd()`：加城外悬崖环

在 `capital.py` 第 **1798** 行之后（`except` 分支的
`out.append(disc("ground_outer", 980.0, -0.35, MAT["grass"], seg=150))` 之后、
`# --- terrain blocks ---` 注释之前）插入：

```python
    # -- the town's rim: a rock scarp instead of the edge of a green plate ----
    try:
        import hd_rock as HRK
        out += HRK.cliff_ring(K, MAT, r=R_OUTER, seed=23, style="limestone",
                              height=(6.0, 15.0), gates=outer_gaps(),
                              nth=1400, plants=True)
    except Exception as _exc:
        print("[capital] cliff_ring skipped:", _exc)
```

### 6.3 顺手要改的一处（不改会和悬崖打架）

`ground_hd()` 第 **1848–1858** 行那 22 个 `hill` 球体，`rad = hr.uniform(R_OUTER + 240.0, 930.0)`
会把山心放在 930 m、半径 70–150 m，直接吞掉 947 m 处的环脊。建议改成：

```python
        rad = hr.uniform(R_OUTER + 210.0, 1400.0)
        rr = hr.uniform(70.0, 150.0)
```

（这两行是主 AI 的地形资产，我只给建议，不动。）

---

## 7. 最终实测与判读

（本节在锁释放、最后一轮出图后填写）
