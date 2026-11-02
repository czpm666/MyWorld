# AGENT_TYPES — 六种大型建筑类型（TYPES）

2026-11-02。新文件只有两个，**没有改动**任何别人的文件：
- `E:\My World\Blender\kingdom\hd_types.py`（新，约 2030 行）
- `E:\My World\Blender\kingdom\look\types_lab.py`（新）

渲染：`E:\My World\Blender\renders\kingdom\look\types_<kind>_{fit,game,eye}.png` + `TYPES_sheet.png`（6×2 拼图，960×540 单格）。

## 为什么是「街区级」而不是「单元级」

量过 `layout.json`：`DN.placements(res, seed=7)` 出 **6098 个 unit**，其中 5947 住宅 + 151 商店。所有 unit 的边最长 **12.80 m**（`hd_dense.MAX_D = 12.5`）。训练场最低要求 46×34 m，**任何 unit 的 quad 都装不下 5/6 种类型**。

所以 `place()` 有两趟：
1. **in-quad**：quad 够大（放得下 brief 最小值 + margin）时原地换 `kind`。绝大多数情况这一趟什么都不做。
2. **block-site**：在街区的**后排余量**里塞一整块矩形 —— 对 `DN._offset(DN._ccw(poly), DN.SETBACK + 1.15)` 求内接矩形，只**丢弃**被它压到的 unit（从不移动任何 unit，符合 brief），再 append 一个 `source="types_site"` 的新 unit。临街那一排住宅完整保留。

`layout.json` 里 358 个街区中 **293 个** bbox ≥ 46×34 m、325 个 ≥ 30×40 m，所以大类型真的放得下去。

## 尺寸 / 面数（lab 实测，base = 物体多边形三角数，eval = 加 bevel 后）

| kind | 中文 | w×d×h (m) | objs | base tris | eval tris |
|---|---|---|---|---|---|
| `training_ground` | 训练场 | 52×40×8.4 | 253 | 20 269 | 106 189 |
| `barracks` | 军营 | 34×22×16.0 | 629 | 15 331 | 66 019 |
| `stable_yard` | 马厩院 | 30×21×10.5 | 267 | 7 273 | 19 753 |
| `bathhouse` | 浴场 | 23×19×9.8 | 331 | 6 667 | 20 875 |
| `mill` | 磨坊 | 14×14×10.6 | 235 | 5 805 | 17 421 |
| `chapel_small` | 小礼拜堂 | 14×23×13.2 | 431 | 8 089 | 28 729 |

eval/base ≈ 5.2×，全部来自 `medkit.bevel(segments=2)`。城里如果要压预算，第一个该关的就是 palisade（栅栏柱）的 bevel。

## 内容

- **training_ground**（用户点名，最高优先级）：自建地面网格 z=0.100（`ty_sand` #a8875a），上面 12 条耙痕（`ty_track`）、踩踏带、14 根木桩围出的**决斗圈**、10 处翻动沙斑；三面木栅栏 + 门垛 + 两根军旗；两座看台（布篷）；15 m 兵器棚；箭靶墙（3 个带环草垛靶）+ 兵器架（7 支长矛）+ 草人靶排 + 水槽。z=0.10 的地面 **高于** z=0.05..0.09 的街区板，不会打架。
- **barracks**（用户点名）：石木三层主体 + **底层拱廊**（连续拱券）+ 外廊石梯 + 走廊盾架 + 兵器架 + 校场 + **瞭望塔**（四坡尖顶 + 金球 + 军旗）+ 井 + 马厩边角。
- **stable_yard**：长马厩 + 一排半门（half-door）+ 干草棚吊臂 + 粪堆 + 水槽 + 车棚 + 围场栅栏 + 自建 z=0.10 的院地。
- **bathhouse**：**平屋顶露台**（不是大圆顶，改过了）+ 铅皮穹顶 + 屋顶蒸汽口冒白汽 + 户外水池 + 布篷 + 拱廊门。
- **mill**：水磨 —— 山墙外侧水轮（轮辐/轮圈 `wood`，叶片 `pale`，能看出十字）、引水槽、蓝色水渠、料斗吊臂。
- **chapel_small**：中殿 + **圣坛**（两个体量，剪影不再是单块红板）+ 钟塔/钟 + 尖拱窗 + 西立面玫瑰窗 + 墓地矮墙 + **15 块墓碑**（朝东，受光）+ 草地。

风格与住宅一致：`HP.plinth` / `_wall`（`hd_houses._wall` 的逐行克隆）/ `HP.timber_frame` / `HP.roof(end_mat=…，用 tiled 变体)` / `HP.window` / `HP.door`，材质走 `palette(MAT)` = MAT 的拷贝 + `HP.house_materials()` + `HP.roof_materials(MAT["tile"])[1]` 重新贴皮。

## API

```python
build(kind, MAT=None, rng=None, at=None, rz=0.0, x=0.0, y=0.0, rot=None, z=0.0,
      w=None, d=None, **kw)   # rz 用「度」(与 hd_shops 一致)，rot 用弧度 (= p["yaw"])
types(kind, MAT, rng, x, y, rot=0.0, z=0.0)   # 与 capital_hd_glue.shop() 同形
BUILDERS = {kind: fn}          # fn 同时接受 fn(kind, MAT, rng, ...) 和 fn(MAT, rng, ...)
place(units, res, seed=7, share=0.055, only=None, sites=True, quota=None, margin=0.6)
keepouts() -> [(x, y, radius, kind)]     # 训练场/马厩院的地面，给 hd_streetlife 用
report(units) -> str
```

`place()` 的语义：
- 入参 `units` 是 `DN.placements()` 的列表，`res` 是 `layout.json` 的 dict。
- 返回**新列表**；x/y/yaw/quad 一律不动。被换掉的 unit 保留原 `kind` 之外的字段，加上 `foot_override=(w, d)`（`capital.py` 用它判断走哪个 builder）。
- 每街区按 `district` 配额度（`QUOTA` = 训练场 2 / 军营 3 / 马厩 4 / 浴场 3 / 磨坊 4 / 礼拜堂 5，按 `share/0.055` 等比缩放），再按 `RADIAL` 从外圈往内城扫：训练场、军营只要 palace/guild/outer，磨坊要 outer/craft（靠河/城门），浴场要 residential/guild（内城），马厩 dock/craft，礼拜堂全城。
- **确定性**：只用一个 `random.Random(seed)`；同 seed 同 res → 同结果。
- `only=("barracks",)` 可以只放一种；`sites=False` 只做 in-quad 那一趟。

## 接进 capital.py（逐字）

`capital.py` 的 `hd_pick()`（`pl = DN.placements(...)` 之后、过滤之后、缓存 `HD_LAY["picked"]` 之前）加：

```python
    try:
        import hd_types as TY
        pl = TY.place(pl, res, seed=SEED)
        print("[types] " + TY.report(pl))
    except Exception as e:
        print("[types] skipped: %r" % (e,))
```

`build_city_hd()` 的分发处加一个分支（在 `if p["source"] == "shop":` 之后）：

```python
                elif p.get("foot_override"):
                    ob = G.types(p["kind"], M, rng, p["x"], p["y"], p["yaw"], p["z"])
```

`capital_hd_glue.py` 里补一个和 `shop()` 一模一样的壳（我自己没有权限改，请主 AI 加）：

```python
def types(kind, MAT, rng, x, y, rot=0.0, z=0.0):
    import hd_types as mod
    return place(guard("types_" + kind,
                       lambda: mod.build(kind, type_mats(MAT), rng)), x, y, z, rot)
```

其中 `type_mats(MAT)` 就是 `hd_types.palette` 对 `house_mats(MAT)` 结果的再加工，可以先用 `house_mats(MAT)` 顶上。

## lab

```
python look\export_run.py types_lab 900 LIGHT -- -b --python look/types_lab.py
python look\export_run.py types_lab 900 LIGHT -- -b --python look/types_lab.py -- --fast
python look\export_run.py types_lab 900 LIGHT -- -b --python look/types_lab.py -- --only mill,chapel_small
```

`--fast` = 480×270 / 8 samples；默认 960×540 / 24 samples，14 张图 + `TYPES_sheet.png`。

## 状态（2026-11-02 15:45 断电前）

- 已完成（哪些类型可用）：六种全部可用、已渲染、已拼图 —— `training_ground`、`barracks`、`stable_yard`、`bathhouse`、`mill`、`chapel_small`。`hd_types.py` + `look/types_lab.py` 均已落盘，`ast.parse` 通过；最终批次 `types_final` exit=0，`TYPES_sheet.png` 与 14 张 `types_*.png` 已生成。
- 进行到一半：没有跑到一半的代码。`place()` 的 block-site 一趟**只做了逻辑与自测，没有在整城里跑过**（那要开 capital 大场景，纪律禁止）。
- 未验证的改动（重要）：最后一次改动是训练场决斗圈从 `stone` 换成 `dark` 木桩、磨坊轮辐从 `dark` 换成 `wood` —— 这两处**只在最终渲染里出图，我没来得及逐张看图确认**。`FOOT` 高度是按几何量出来的，不是从 `eval` 包围盒自动取。
- 下一步第一件事：看 `types_training_ground_fit.png` 和 `types_mill_fit.png` 确认那两处材质改动；然后按上面的逐字代码把 `place()` 接进 `capital.py`，跑一次 `[types]` 日志确认放置数量（预计每城 ~18 座）。
- 我改过的文件：`E:\My World\Blender\kingdom\hd_types.py`（新）、`E:\My World\Blender\kingdom\look\types_lab.py`（新）、本文件（新）。别人的文件一个都没动。
