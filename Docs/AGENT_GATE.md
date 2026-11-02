# AGENT_GATE — 城门与城墙（GATE v3）

最后更新：2026-11-02 15:42（断电前收尾）。文件：`E:\My World\Blender\kingdom\hd_gate.py`（199 451 B）、
lab：`E:\My World\Blender\kingdom\look\gate_lab.py`、stand：`look/gate_lab.blend`（1.4 MB，可随时重建）。

## 1. 调用签名（向后兼容，capital.py 不用改）

```python
build_gatehouse(MAT, rng)          # 唯一被 capital_hd_glue.gatehouse() 调用的入口
build_gatehouse(MAT, rng, **kw)    # kw 目前只有 with_* 开关，可忽略
build(MAT, rng, **kw)              # lab 主入口：城门 + 两侧各 60 m 城墙 + 护城河 + 地面
                                   #   kw: with_ground=True, with_moat=True, run=60.0
curtain_run(name, p0, p1, MAT, rng, out=None, h=None, t=None,
            crenels=True, bastions=True, step=30.0, ashl=True, batter=True)
                                   # 一段直线城墙（马面/走道/垛口/箭孔/斜坡基座），
                                   # 返回已落在世界坐标的 [MESH, ...]
gate_keepout()                     # [(-11.6, 3.4, 7.507), (+11.6, 3.4, 7.507)] 给 hd_river 挖水面
g3_weather(MAT, strength=1.0, seed=7)   # 只在 lab 用；city 由 capital.py:2313 统一上weathering
```

约定（**不要动**）：`build_gatehouse(MAT, rng)` 必须返回一个扁平的 `bpy` MESH 列表、绝不抛异常
（`hd_glue.guard()` 会吞掉异常并把整座城门丢掉）；局部坐标 +Y = 城外（路/护城河一侧），−Y = 城内，
+Z 向上，原点 = 门洞地面中心。已验证：喂一个只有 capital 键名的 MAT（无 void/sill/moss）
→ 520 个物体 / 19 545 面，无异常。

## 2. 面数

| 部件 | 物体 | 面（quad） | ≈三角 |
|---|---|---|---|
| `build_gatehouse`（单座城门，含双塔+门洞+闸门+吊桥+门楼） | 520 | 19 545 | ≈40 k |
| lab stand（城门 + 2×60 m 城墙 + 护城河 + 地面） | ≈1 000 | — | ≈95 k |
| 其中单段 60 m 城墙（含 2 马面） | ≈210 | — | ≈28 k |

四座城门 city 里合计约 160 k tris（旧版 hd_gate 是 280 k+）。

## 3. 四个城门的朝向

`capital.py:1085 hd_gates()`：`a = k*pi/2`，位置 `(R_WALL*cos a, R_WALL*sin a)`，`rot = a - pi/2`。
本模块局部 +Y 朝城外，调用方旋转后：

| k | 位置 | rot | 门朝 |
|---|---|---|---|
| 0 | (+444, 0) | −π/2 | +X |
| 1 | (0, +444) | 0 | +Y |
| 2 | (−444, 0) | +π/2 | −X |
| 3 | (0, −444) | π | −Y |

外城 4 座（`capital.py:1234 outer_gates()`）来自 `hd_plan2` 的 `city["gates"]`，同样 `rot = ang - pi/2`，
`scale=1.16`，城门宽 30.8 m×1.16 = 35.7 m；外城墙缺口 `HD_GATE_HALF=14.4`，本模块占地 ±15.4，
搭接 1 m，不会露缝。**注意**：`build_gatehouse` 不含两侧城墙（city 的墙由 capital_hd_glue 建），
只有 lab 的 `build()` 才加 60 m 试验墙。

## 4. 三个 P0 的实测（`look/gate_lab.py --make` 会打印，可复跑）

- ① 水面穿角楼：围堰圆 r=7.507 从水面网格里挖掉（0.80 m 格），最近水位顶点到围堰 +0.161 m；
  水面到塔身之间用一圈干燥石apron（`wet_shelf` 材质）盖住 0.57 m 的网格锯齿。
- ② 闸门悬空：闸门 11 根栅条 + 矛尖全部从石槛顶面 `z=0.52` 生成，实测
  `lowest point z=0.5200 / sill top z=0.5200 / gap=+0.0000 m`；石槛在门洞内 y=+4.20。
- ③ 读不出是城门：门洞 6.80 m 宽 × **16.40 m 深** × 8.00 m 拱顶，是真通洞（`_g3_arch_head()`
  手工建非凸拱肩，`H.prism` 的扇形三角化会把凹口填死——上一版就是这么把门洞封成石盘的）；
  城内端收成 4.70×3.90 的小门（木过梁），远口比近口小 → 隧道有纵深。
  机位实测：52°/34 m/vFOV30°，相机在玩家后 20.93 m、高 26.79 m，视线顶边 37°，
  墙面可见高度 = 26.79 − 0.754×(20.93+P)：P=0 时 11.0 m、P=4 时 8.0 m、P>8 时为零。
  **所以徽记(9.95)、旗帜(8.30)、栅格、吊桥、塔基必须全部压在 8–11 m 以下**，塔高只对航拍有用。

## 5. 交付图（`renders\kingdom\look\`，960×540）

`gate2_portal`（门洞正面）·`gate2_tower`（塔楼仰角）·`gate2_walk`（城墙走道，**构图没调好，
下一轮第一件事**）·`gate2_bastion`（马面）·`gate2_grille`（闸门落槛特写）·`gate2_water`
（水面与塔基交接）·`gate2_inside`（隧道纵深）·`gate2_gc00`/`gate2_gc04`（真游戏机位）。

## 状态（2026-11-02 15:45 断电前）

- **已完成**：GATE v3 全量重写并从零跑通（520 物体/19.5 k 面，build 1.3 s）；双塔（阶梯基座+斜面+18 道石层线+箭孔+角楼+突堞）、
  16.4 m 贯通门洞（非凸拱肩手工建模）、弓形拱+拱石圈、闸门落地石槛（实测 0.0000 m）、吊桥+铁链+桥墩、城内小门+两扇门扉、
  门楣徽记+门侧低挂旗帜+桥头旗杆、`curtain_run()`（马面/3 m 走道/内女墙/外垛口 1.44 宽 0.62 间隔 1.7 高/箭孔/吐水口/斜坡基座）、
  护城河+水中围堰+湿石apron、城墙走道楼梯、`g3_weather()` 接 `hd_surface.apply_weathering`；
  `gate_lab.py` 的 8 项自动检查全过（含"门洞射线必须穿过立面"和"城墙不得横穿城门"回归测试）；
  9 张 960×540 图。
- **进行到一半**：`gate2_walk` 机位第三次没调好（20 mm 镜头贴在外垛口内侧，画面全是近处石板）；
  石层线在 480p 下偏细（tube 0.042），远看成"划痕"而非连续灰缝。
- **未验证的改动（重要）**：① `hd_surface` 的砖纹材质在整座城上会不会把我的 `gate_shaft`/`wet_shelf`
  等 gate 专用材质按 `KeyError` 跳过——lab 只跑了 `G.materials()` 的 palette，**没跑 capital 的真 MAT**；
  ② 四城门外城 `scale=1.16` 时门洞（6.8→7.9 m）与护城河/桥的相对位置未测；
  ③ `curtain_run()` 还没有接进 city 的墙（capital_hd_glue 的 `wall_arc`/`wall_seg` 不调用 hd_gate，
  我只把函数和 3 行插入说明留在这里，**没改那段代码**）。
- **下一步第一件事**：用 `look/gate_lab.py --only walk` 重设走道机位（建议 `(28,-7.5,13.2)` 看 `(12,0,10.4)`，28 mm），
  5 秒一张，只渲这一张；然后才是 `gate2_tower` 的石层线加粗到 0.06。
- **我改过的文件**：`Blender\kingdom\hd_gate.py`（v3 段追加在 3240 行后，旧段未删）、
  `Blender\kingdom\look\gate_lab.py`（新建）、`Blender\renders\kingdom\look\gate2_*.png`（9 张）、
  `Docs\AGENT_GATE.md`（本文件）。未触碰 capital.py / capital_hd_glue.py / hd_river.py / hd_surface.py。
