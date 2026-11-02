# AGENT_NATURE — 阿斯拉王都植被层

代号 **NATURE**。只拥有两个文件：`Blender/kingdom/hd_nature.py`、`Blender/kingdom/look/nature_lab.py`。

## 问题诊断

V24 的树是棒棒糖：一根细杆顶一个光滑绿球。根因不是"细节不够"，而是**结构**——单个凸包只能读成一个球。要读成树，必须：

1. 树冠是 **8–20 个独立的团块**，每块长在一根看得见的枝的末端 → 轮廓有裂口、有空洞；
2. 树干有锥度、分叉、纵向凹槽（圆柱两样都没有）；
3. 叶团被几百片**不透明**小叶板打碎。**不用 alpha 卡片**：EEVEE 按物体排序，一冠卡片会闪、会透出自己的背面。本模块所有叶板都是不透明几何、双面绕序，不需要 alpha。

另一半是布置：12,990 栋房子配 2,596 棵树 = 五栋一棵。中世纪城镇是每个院子有果树、街角有榆树、广场一圈椴树、水边有柳树。

## 已实现（`hd_nature.py`，1861 行，重写）

纯几何核心不 import bpy，可以用 `E:\GameProject\Python313\python.exe` 直接跑自检（省 Blender 配额的关键）。

- 7 种：`oak` `elm` `linden` `poplar` `willow` `spruce` `fruit`
- 3 档 LOD，每档 5/4/3 个变体，模板缓存
- `build(MAT, units=None, res=None, seed=7, cell=64.0, lod=2, **kw)` — 城市树层，按 cell 合批，2 个材质槽
- `place(units=None, res=None, seed=7, ...)` — 纯 python，返回 record 列表
- `tree(kind, rng, scale=1.0, lod=0) -> (V, F, M, C, L)`
- `tree_template(kind, lod, seed=0) -> (V, F, shade)` — 兼容 `hd_landscape_geo` 契约
- `tint(t) -> (r,g,b)` 季节/颜色乘子，0.5 中性，0.84 黄，1.0 橙
- `forest(...)` 城外林带，实例化 + 逐树 LOD + 真实尺寸分布
- `wind(objects, t, amp, dir)` 顶点级风摆（`hd_weather.sway` 是整物体绕原点旋转，对合批 cell 无效，所以另写）
- 布置角色：`courtyard`(fruit) `corner`(elm/linden/oak) `square`(linden) `avenue`(poplar/elm/linden) `river`(willow) `landmark` `wall` `forest`
- 拒斥：车道（`street.near` + 半宽 + 1.35 m）、房屋四边形 +1.25 m、`blocked()` 回调、城墙内 2.5 m、树间距

## 面数（实测，`python hd_nature.py`）

| kind | L0 | L1 | L2 | L1/L0 |
|---|---|---|---|---|
| oak | 1890 | 440 | 20 | 23.3% |
| elm | 1915 | 505 | 20 | 26.4% |
| linden | 1786 | 455 | 20 | 25.5% |
| poplar | 924 | 450 | 20 | 48.7% |
| willow | 1717 | 505 | 20 | 29.4% |
| spruce | 384 | 122 | 14 | 31.8% |
| fruit | 838 | 430 | 20 | 51.3% |

1,000 棵混合 LOD ≈ **215,000 三角面**。
2,600 棵城市树全 L0 ≈ **4.9 M 三角面**（这是内存风险点，见下）。

## 关键设计决定（理由）

- **`hash()` 换 crc32**：Python 对字符串 hash 每进程加盐，`hash((kind,variant,lod))` 每次启动都不同 → 同一个 seed 每次构建出不同的树。已改成 `zlib.crc32`，两次运行面数表逐位一致（已验证）。
- **`_finish()` 归一化**：生成器按比例放枝和团，落点差几个百分点；柳树冠低会短一截。`scale` 文档说是"树高"，所以统一校正到精确 H。
- **叶板近乎水平**：游戏相机俯角 52°，法线水平的叶片会变成一条线消失。所有叶板法线朝上、只向外倾 25–35°。
- **L2 加伞盖**：远处树从上往下看主要是树顶，只有垂直卡片的 billboard 会变成一根细线加天空——这就是远景林带读成"绿点"的原因。所以 3 张交叉卡 + 0.74H 的六边形伞盖。
- **LOD 策略**：`focus=None` 自动取城墙内缩 40 m 的 60 m 网格 → 城内全 L0（玩家能走到任何地方），L1 从墙外开始。`lod` 参数是**上限**，传 1 可整体降档。

## 未验证 / 风险（重要）

- **Blender 内一次都没跑过**。`_mk_obj`、`make_materials`、`build`、`forest`、`wind` 全部未执行。纯 python 部分（几何、布置、面数、可复现性）已自检通过。
- `_peak_mb()` 在纯 python 下返回 0.0（psapi 调用没拿到值），内存数据还没有。
- 没有渲染图。
- L1/L0 比例 23–51%，简报要 ~20%；poplar 和 fruit 的 L0 本来就轻，所以比例偏高。绝对面数（L1 430–505）是合理的。

## 状态（2026-11-02 15:45 断电前）

- **已完成**：`hd_nature.py` 全量重写（1861 行，`ast.parse` 通过）；7 种 × 3 LOD 模板；`place()` 纯 python 布置（合成城镇测试 407 棵，拒斥分类正确）；`tint()` 季节色；`forest()`；`wind()` 顶点风摆；crc32 可复现性修复；高度归一化修复。
- **进行到一半**：LOD 面数调优（L1 想压到 L0 的 20%，现在 23–51%）；`look/nature_lab.py` **还没开始写**。
- **未验证的改动（重要）**：所有 bpy 路径（`_mk_obj` 的 `mesh.polygons.foreach_set("loop_total")` 在 Blender 5.2 是否还存在、`color_attributes.new` 之后 `foreach_set("color")` 的长度、`ShaderNodeMix` 的 `inputs[6]/[7]` 索引、`ShaderNodeAttribute` 读 "Col" 是否走 POINT domain）。第一次 Blender 运行必须只做"建 1 棵树 + 打印对象/面数"，不要直接出图。
- **下一步第一件事**：写 `look/nature_lab.py`（照 `look/land_lab.py` 的结构），先用 `--python-expr` 或最小脚本在 Blender 里跑 `import hd_nature; t=hd_nature.tree("oak",None,10.0,0)` + `_mk_obj`，确认 mesh 建得出来、材质槽对、Col 属性在；再出 480×270 / 8 samples 的单株三视图。
- **我改过的文件**：`E:\My World\Blender\kingdom\hd_nature.py`（唯一一个）。`look/nature_lab.py` 尚未创建。`Docs/AGENT_NATURE.md`（本文件）。
- **Blender 进程**：0（从未启动过，没有占用配额）。

## 下一步

1. 最小 Blender 冒烟测试（只建 1 棵 oak L0，打印 verts/faces/material slots）
2. `look/nature_lab.py`：单株三视图（oak/elm/willow/spruce × 正/侧/俯）、近景林缘、街角树、远景林带
3. 480×270 / 8 samples 迭代，看轮廓和叶板密度
4. 定稿 4–6 张 960×540，前缀 `nat_`，放 `Blender/renders/kingdom/look/`
5. 用真实 `hd_plan2`/`hd_dense` 数据跑 `place()`，报 1,500–3,000 棵的实际数字和内存
