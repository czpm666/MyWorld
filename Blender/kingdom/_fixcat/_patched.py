"""hd_cathedral_int.py --- 王都圣阿苏拉大教堂 · 室内

坐标约定
--------
* 原点 (0,0,0) = 中厅地面几何中心；z = 0 = 室内地面。
* +Y 指向祭坛（东端半圆室），-Y 是西立面（大门）。
* 与外部外壳 hd_cathedral.py 叠合：外壳局部 +Y 指向西立面，因此叠合时
  需要绕 Z 旋转 180°（radians(180)）并抬高 Z_FLOOR = 1.10 m。
  见 EXTERIOR_MATCH 常量。

净空（对外壳内部空腔的占用）
---------------------------
* 长 76.5 m（y: -41.0 … +35.5），外壳 93.7 → 余量 17.2
* 宽 29.8 m 净（x: ±14.9 墙内表面），外壳 36.2 → 余量 6.4
* 高 37.8 m（拱顶石底面），采光塔顶 39.6，外壳 70.3 → 余量 30.7

公开接口
--------
    MAT_KEYS
    build(MAT, rng) -> list[bpy.types.Object]
    footprint() -> (34.0, 90.0)
    height()    -> 39.6
    interior_lights()   # 可选：把室内补光交给上层复用
    preview()           # 守卫：单独运行本文件时渲图
"""

import math
import os
import random
import sys

from mathutils import Euler, Matrix, Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                    # noqa: E402
import hd_common as H                                          # noqa: E402
import medkit as K                                             # noqa: E402
from medkit import T_at as Ts, box, cyl, cone, sphere          # noqa: E402

TAU = math.tau
R = math.radians

# ===========================================================================
#  1. 尺寸
# ===========================================================================
# ---- 纵向（+Y 指向祭坛）---------------------------------------------------
Y_W = -41.00          # 西墙内表面
BAY = 5.25            # 中厅开间
NBAY = 8
Y_X0 = Y_W + BAY * NBAY          # +1.00  交叉部西缘
CROSS_D = 13.00                  # 交叉部进深
Y_X1 = Y_X0 + CROSS_D            # +14.00 交叉部东缘
CH_BAY = 6.50                    # 唱诗席开间
NCH = 2
Y_APSE = Y_X1 + CH_BAY * NCH     # +27.00 半圆室圆心
APSE_R = 8.50
Y_END = Y_APSE + APSE_R          # +35.50

# ---- 横向 -----------------------------------------------------------------
N_HW = 8.50           # 中厅半宽 = 束柱轴线
AISLE_IN = 14.90      # 侧廊外墙内表面（净宽 29.8）
AISLE_CX = 11.70
WALL_T = 0.30
TR_X = 24.50          # 横厅端墙内表面（两臂各 16 m）
TR_CX = 16.50
WALL_T = 0.30
W_END_T = 1.00        # 西墙厚度（深门斗 + 吞掉西端半柱）
OFF = 0.03            # 所有室内表面从外壳结构面内缩 3 cm

# ---- 竖向 -----------------------------------------------------------------
Z_BASE = 0.90         # 勒脚顶
Z_ARC_SPRING = 8.60   # 连拱廊起拱
Z_ARC_APEX = 11.60    # 矢高 3.00（rr=1.14，双心尖券）
Z_ARC_BAND = 0.42     # 拱券立面厚度
Z_AIS_SPRING = 11.00  # 侧廊拱顶起拱
Z_AIS_CROWN = 14.50
Z_AIS_TR = 2.60       # 侧廊横向肋矢高
Z_AIS_WR = 1.00       # 侧廊墙肋矢高
Z_TRIF_S = 15.40      # triforium 底
Z_TRIF_T = 18.60      # triforium 顶
Z_TRIF_SPR = 15.90
Z_TRIF_RISE = 1.25
Z_TRIF_B = 19.40      # 束带层顶
Z_CLER_S = 20.40      # 高侧窗窗台
Z_CLER_SPR = 27.60
Z_CLER_RISE = 1.50
Z_CORN = 29.40        # 檐口底
Z_VAULT = 30.00       # 中厅拱顶起拱
NAVE_HT = 4.00        # 横肋矢高（跨 17 m）
NAVE_HR = 1.20        # 墙肋矢高（跨一个开间）
Z_CROWN = 37.80       # 拱顶石处净高
Z_TR_SPRING = 24.00   # 横厅/交叉部大券起拱
Z_TR_APEX = 30.00
Z_TR_HT = 4.00
Z_TR_HR = 1.80
Z_TR_CROWN = 29.80
Z_X_ARCH_SPRING = 24.00
Z_X_ARCH_APEX = 30.00
Z_LANT_BASE = 30.20   # 采光塔楼板底
Z_LANT_PLAT = 31.20   # 采光塔鼓座底
Z_LANT_TOP = 38.20
Z_LANT_R = 4.60
Z_LANT_DOME = 39.60
Z_APSE_SPRING = 30.00
Z_APSE_CROWN = 36.20
ROSE_Z = 25.40
ROSE_R = 4.60
PORTAL_W = 3.80
PORTAL_SPR = 4.20
PORTAL_APEX = 7.60
AISLE_WIN_SILL = 3.60
AISLE_WIN_SPR = 8.80
AISLE_WIN_RISE = 1.70

# ---- 平面布置 -------------------------------------------------------------
AISLE_CLEAR = 2.90        # 中央通道半宽（净 5.8 m）
PEW_X0 = 2.90
PEW_X1 = 5.40             # 长椅与柱之间 2.3 m
PEW_Y0 = -37.60
PEW_Y1 = -3.40
ROOD_Y = 1.35          # 唱诗席围屏（rood screen）：立在交叉部西券之后
CHOIR_STALL_Y = (15.60, 26.00)

EXTERIOR_MATCH = {"rot_z": math.pi, "dz": 1.10}

# ===========================================================================
#  2. 材质
# ===========================================================================
MAT_KEYS = (
    "stone", "stone_warm", "stone_dark", "stone_trim", "stone_voussoir",
    "floor", "floor_light", "floor_dark", "grout",
    "wood", "wood_dark", "wood_light",
    "iron", "gold", "lead",
    "cloth_red", "cloth_blue", "cloth_gold", "cloth_white",
    "glass", "glass_blue", "glass_red", "glass_gold", "glass_green",
    "glass_rose", "wax", "flame", "shadow",
)


def _mat_emit(name, hexcol, strength, base=None, rough=0.35, metal=0.0):
    """自发光材质：Principled 的 Emission Color + Emission Strength。"""
    if name in K._MAT_CACHE:
        return K._MAT_CACHE[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = K._bsdf(m)
    col = K.c(hexcol)
    K._put(bsdf, ["Base Color"], base and K.c(base) or col)
    K._put(bsdf, ["Roughness"], rough)
    K._put(bsdf, ["Metallic"], metal)
    K._put(bsdf, ["Emission Color", "Emission"], col)
    K._put(bsdf, ["Emission Strength"], strength)
    K._MAT_CACHE[name] = m
    return m


def _mat_flat(name, hexcol, rough=0.9, metal=0.0):
    """无花纹的哑光纯色材质（用于深龛底、暗部）。"""
    if name in K._MAT_CACHE:
        return K._MAT_CACHE[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = K._bsdf(m)
    K._put(bsdf, ["Base Color"], K.c(hexcol))
    K._put(bsdf, ["Roughness"], rough)
    K._put(bsdf, ["Metallic"], metal)
    K._MAT_CACHE[name] = m
    return m


def _defaults():
    M = {}
    M["stone"] = K.mat_stone("ci_stone", "#cfc8b7", "#a9a292", "#e6e0d0", 2.4)
    M["stone_warm"] = K.mat_stone("ci_stone_warm", "#d6cdb7", "#b0a690", "#ece4cf", 2.0)
    M["stone_dark"] = K.mat_stone("ci_stone_dark", "#a49d8c", "#827c6c", "#c4bdac", 2.8)
    M["stone_trim"] = K.mat_stone("ci_stone_trim", "#ddd6c6", "#b7b0a1", "#f2ecdd", 3.2)
    M["stone_voussoir"] = K.mat_stone("ci_stone_vous", "#e2dccb", "#bdb6a5", "#f6f0e2", 4.0)
    # 拱腹：mat_stone 的砖纹是 (x+y, z) 投影，铺在穹面上的砖缝会变成同心圆
    # 和放射线，远看就是"瓦楞纸"。拱腹改用抹面（只有噪声+凹凸），肋用更细的石纹。
    M["vault_web"] = K.mat_plaster("ci_vault_web", "#d6ceba", "#b9b09b", 3.0)
    M["rib_stone"] = K.mat_stone("ci_stone_rib", "#bdb5a3", "#968e7f", "#d6cfbe", 6.5)
    M["floor"] = K.mat_stone("ci_floor", "#bdb099", "#8f846f", "#d8cdb6", 1.5)
    M["floor_light"] = K.mat_stone("ci_floor_l", "#d3c7ad", "#a89d85", "#ebe1ca", 1.5)
    M["floor_dark"] = K.mat_stone("ci_floor_d", "#8d8373", "#6a6356", "#a79d8e", 1.5)
    M["grout"] = K.mat_stone("ci_grout", "#4a453e", "#332f2a", "#5d5750", 5.0)
    M["wood"] = K.mat_wood("ci_wood", "#6b4a2e", "#8d6640", 0.58, 2.0)
    M["wood_dark"] = K.mat_wood("ci_wood_d", "#4a3220", "#6a4a2e", 0.62, 2.4)
    M["wood_light"] = K.mat_wood("ci_wood_l", "#8a6238", "#ab7f4c", 0.55, 2.0)
    M["iron"] = K.mat_metal("ci_iron", "#2e2d33", 0.44)
    M["gold"] = K.mat_gold("ci_gold", "#c9a44a")
    M["lead"] = K.mat_metal("ci_lead", "#565b62", 0.52)
    M["cloth_red"] = K.mat_cloth("ci_cloth_r", "#7d1f22", 0.86)
    M["cloth_blue"] = K.mat_cloth("ci_cloth_b", "#1f3566", 0.86)
    M["cloth_gold"] = K.mat_cloth("ci_cloth_g", "#a8842e", 0.72)
    M["cloth_white"] = K.mat_cloth("ci_cloth_w", "#ddd6c4", 0.9)

    M["glass"] = _mat_emit("ci_glass", "#3f6f96", 1.00, base="#1b2f3f", rough=0.22)
    M["glass_blue"] = _mat_emit("ci_glass_b", "#1d54a8", 1.25, base="#0d1f3a", rough=0.2)
    M["glass_red"] = _mat_emit("ci_glass_r", "#a8221f", 1.15, base="#2e0c0e", rough=0.2)
    M["glass_gold"] = _mat_emit("ci_glass_g", "#c68a1c", 1.45, base="#3a2a0c", rough=0.2)
    M["glass_green"] = _mat_emit("ci_glass_gn", "#1d7a48", 1.10, base="#0d2417", rough=0.2)
    M["glass_rose"] = _mat_emit("ci_glass_rose", "#b02a52", 1.30, base="#300f1a", rough=0.2)
    # 玫瑰窗专用：更深的玻璃（免得整窗像彩色塑料）+ 更暗的窗棂（要打成剪影）
    M["stone_rose"] = K.mat_stone("ci_stone_rose", "#8b8374", "#6a6355", "#a29a8a", 3.0)
    M["rg_b0"] = _mat_emit("ci_rgb0", "#0f3a86", 1.05, base="#07142e", rough=0.2)
    M["rg_b1"] = _mat_emit("ci_rgb1", "#2f6cc0", 1.30, base="#0d2244", rough=0.2)
    M["rg_r0"] = _mat_emit("ci_rgr0", "#80161f", 0.95, base="#220508", rough=0.2)
    M["rg_r1"] = _mat_emit("ci_rgr1", "#c02a30", 1.20, base="#2e0809", rough=0.2)
    M["rg_g0"] = _mat_emit("ci_rgg0", "#b8801a", 1.35, base="#2e2007", rough=0.2)
    M["rg_g1"] = _mat_emit("ci_rgg1", "#e2ab3c", 1.55, base="#3a2a0c", rough=0.2)

    M["wax"] = K.mat_stone("ci_wax", "#efe6cd", "#d6cbae", "#fbf5e2", 6.0)
    M["flame"] = _mat_emit("ci_flame", "#ffb347", 11.0, base="#ff9b32", rough=0.4)
    # 深壁龛/廊道底：近黑哑光，用来把 triforium、盲连拱的内腔压成阴影
    M["shadow"] = _mat_flat("ci_shadow", "#1a1712", 0.94)
    return M


_MAT = {}


def _ensure(MAT):
    """合并外部材质表：外部给了的优先，缺的用默认。"""
    global _MAT
    M = _defaults()
    if MAT:
        for k, v in MAT.items():
            if v is not None:
                M[k] = v
    _MAT = M
    return M


# ===========================================================================
#  3. 基础几何工具
# ===========================================================================
PARTS = []
RNG = random.Random(7)


def _reg(ob):
    if ob is None:
        return None
    if isinstance(ob, (list, tuple)):
        for o in ob:
            _reg(o)
        return ob
    PARTS.append(ob)
    return ob


def _box(name, T, size, mat, bev=0.0):
    return _reg(box(name, T, size, mat, bev))


def _cyl(name, T, r, h, mat, seg=20, cap=True, r2=None):
    return _reg(cyl(name, T, r, h, mat, seg, cap, r2))


def _sph(name, T, radius, mat, seg=20, ring=12, squash=1.0):
    return _reg(sphere(name, T, radius, mat, seg, ring, squash))


def _lathe(name, prof, mat, seg=24, T=None, cb=True, ct=True, smooth=True):
    return _reg(H.lathe(name, prof, mat, seg, T, cb, ct, smooth))


def _polyv(name, verts, faces, mat, smooth=False):
    ob = K.mesh_obj(name, verts, faces, smooth)
    if mat is not None:
        K.assign(ob, mat)
    return _reg(ob)


def pf(t, rr):
    """券形高度系数：t=0 拱顶(=1)，t=1 起拱点(=0)；rr = 矢高/半跨。

    rr >= 1 用双心尖券（两个圆心在跨外，顶部带尖）；rr < 1 用弓形券
    （单圆心在跨中下方），否则双心公式在 t≈cx 处会过冲到 1.30 倍，
    把拱顶抬得比矢高还高（曾导致 bbox 爆到 z=41.1）。
    """
    if rr <= 1e-6:
        return 0.0
    t = 1.0 if t > 1.0 else (-1.0 if t < -1.0 else t)
    t = abs(t)
    if rr >= 1.0:
        cx = 0.5 * (1.0 - rr * rr)
        rad = 0.5 * (1.0 + rr * rr)
        v = rad * rad - (t - cx) * (t - cx)
        if v <= 0.0:
            return 0.0
        return math.sqrt(v) / rr
    rho = (1.0 + rr * rr) / (2.0 * rr)
    v = rho * rho - t * t
    if v <= 0.0:
        return 0.0
    return (rr - rho + math.sqrt(v)) / rr


def arch_z(a, a0, a1, zspr, rise):
    """尖券在横向位置 a 处的高度。"""
    if a1 - a0 < 1e-9:
        return zspr
    half = 0.5 * (a1 - a0)
    u = (a - 0.5 * (a0 + a1)) / half
    return zspr + rise * pf(u, rise / half)


def arch_uv(a0, a1, zspr, rise, n=8):
    """尖券轮廓点（含两端）。"""
    return [(a0 + (a1 - a0) * i / n, arch_z(a0 + (a1 - a0) * i / n, a0, a1, zspr, rise))
            for i in range(n + 1)]


def _ribprof(w, d, ch=0.035, sink=0.10, n=14):
    """肋断面：(side, up) 平面内的椭圆，up > 0 的部分插进拱腹里。

    旧断面是顶面 0.72w 宽的平梯形，而且整条肋被压到拱腹以下 0.21 m，平顶
    和 1.2 m 一折的拱腹浅角相交，就渲染成一节一节的"鳞片"
    （qc_cat_ribs 里那种 8 px 接茬）。椭圆没有平面顶，上缘只和拱腹相切，
    得到一条干净的连续棱线，滚动高光也连续。ch 保留只为兼容旧调用。
    """
    hw = 0.5 * w
    return [(hw * math.cos(TAU * i / n),
             sink - 0.5 * d + 0.5 * d * math.sin(TAU * i / n)) for i in range(n)]


def sweep(name, pts, prof, mat, up=(0, 0, 1), caps=True, smooth=True, closed=False):
    """断面 prof 沿折线 pts 扫掠。prof 为 (side, up) 平面内的逆时针点列。"""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    if n < 2:
        return None
    U = Vector(up)
    rings = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        if t.length < 1e-9:
            t = Vector((0, 0, 1))
        t.normalize()
        u = U - t * U.dot(t)
        if u.length < 1e-7:
            u = Vector((0, 1, 0)) - t * t.y
            if u.length < 1e-7:
                u = Vector((1, 0, 0)) - t * t.x
        u.normalize()
        s = u.cross(t)
        rings.append([pts[i] + s * a + u * b for (a, b) in prof])
    m = len(prof)
    verts = []
    for ring in rings:
        verts += [(v.x, v.y, v.z) for v in ring]
    faces = []
    for i in range(n - 1):
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
    if closed:
        for j in range(m):
            j2 = (j + 1) % m
            faces.append(((n - 1) * m + j, (n - 1) * m + j2, j2, j))
    if caps and not closed:
        faces.append(tuple(range(m - 1, -1, -1)))
        faces.append(tuple((n - 1) * m + j for j in range(m)))
    return _polyv(name, verts, faces, mat, smooth)


def prism2d(name, origin, u, v, n, d0, d1, poly, mat, smooth=False):
    """二维多边形 poly（(u,v) 坐标）沿法向 n 从 d0 拉伸到 d1。"""
    if d1 < d0:
        d0, d1 = d1, d0
    O = Vector(origin)
    U = Vector(u)
    V = Vector(v)
    N = Vector(n)
    m = len(poly)
    verts = [(O + U * a + V * b + N * d0) for (a, b) in poly]
    verts += [(O + U * a + V * b + N * d1) for (a, b) in poly]
    faces = [tuple(range(m - 1, -1, -1)), tuple(m + j for j in range(m))]
    for j in range(m):
        j2 = (j + 1) % m
        faces.append((j, j2, m + j2, m + j))
    return _polyv(name, [tuple(x) for x in verts], faces, mat, smooth)


def box_poly(name, origin, u, v, n, d0, d1, a0, a1, b0, b1, mat):
    return prism2d(name, origin, u, v, n, d0, d1,
                   [(a0, b0), (a1, b0), (a1, b1), (a0, b1)], mat)


# ---- 拱顶曲面 -------------------------------------------------------------
def vault_z(x, y, x0, x1, y0, y1, zs, ht, hr, hc):
    """四分拱顶曲面：四边精确贴合起拱线，中心精确等于 hc。"""
    a = 0.5 * (x1 - x0) or 1.0
    b = 0.5 * (y1 - y0) or 1.0
    A = ht * pf((x - 0.5 * (x0 + x1)) / a, ht / a)
    B = hr * pf((y - 0.5 * (y0 + y1)) / b, hr / b)
    return zs + A + B + (hc - ht - hr) * (A / ht) * (B / hr)


def vault_sheet(name, x0, x1, y0, y1, zs, ht, hr, hc, nx=12, ny=4, mat=None, flip=False):
    verts = []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        for j in range(ny + 1):
            y = y0 + (y1 - y0) * j / ny
            verts.append((x, y, vault_z(x, y, x0, x1, y0, y1, zs, ht, hr, hc)))
    faces = []
    for i in range(nx):
        for j in range(ny):
            a = i * (ny + 1) + j
            b = (i + 1) * (ny + 1) + j
            f = (a, b, b + 1, a + 1)
            faces.append(f[::-1] if flip else f)
    return _polyv(name, verts, faces, mat, True)


def vault_rib(name, x0, x1, y0, y1, zs, ht, hr, hc, p0, p1, w, d, mat, n=12, drop=1.0):
    # 路径加密到至少 36 段：10 段扫一条 17 m 的斜肋，每段 1.7 m，
    # 光靠 smooth 是掩盖不了折线的（这是"一节一节"的另一半原因）。
    nn = max(int(n), 36)
    pts = []
    for i in range(nn + 1):
        t = i / nn
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t
        z = vault_z(x, y, x0, x1, y0, y1, zs, ht, hr, hc)
        pts.append((x, y, z))
    return sweep(name, pts, _ribprof(w, d), mat)


def boss(name, x, y, z, r, mat, mat2=None, drop=0.40):
    """拱顶石（keystone 圆盘）：从拱腹下挂出来的一块石盘 + 中心垂饰。

    旧版把整个盘放在 z+0.30 .. z+0.30 之间（Ts(x,y,z+0.30)，profile 是
    0..-0.30），也就是说盘完全在拱腹**上方**、埋进屋面里 —— 所以四肋交汇处
    永远看不到拱心石，只剩一个黑缺口。现在改成从 z 往下挂。
    """
    _lathe(name + "_a",
           [(r * 0.30, 0.10), (r * 0.78, 0.08), (r * 1.02, -0.02),
            (r * 1.00, -drop * 0.34), (r * 0.88, -drop * 0.56),
            (r * 0.62, -drop * 0.76), (r * 0.30, -drop * 0.90), (0.0, -drop)],
           mat, 24, Ts(x, y, z), True, True)
    if mat2:
        _lathe(name + "_b",
               [(0.0, -drop - 0.02), (r * 0.20, -drop * 1.02), (r * 0.26, -drop * 0.72),
                (r * 0.18, -drop * 0.50), (0.0, -drop * 0.44)],
               mat2, 14, Ts(x, y, z), False, True)


# ---- 蜡烛 / 烛台 ----------------------------------------------------------
def candle(name, x, y, z, r=0.035, h=0.24, mat=None, flame=True):
    mat = mat or _MAT.get("wax")
    _lathe(name + "_w", [(0.0, 0.0), (r, 0.0), (r, h), (r * 0.86, h + 0.012),
                         (0.0, h + 0.012)], mat, 8, Ts(x, y, z))
    if flame:
        fm = _MAT.get("flame")
        _lathe(name + "_f", [(0.0, 0.0), (r * 0.8, 0.035), (r * 0.55, 0.10),
                             (0.0, 0.155)], fm, 7, Ts(x, y, z + h + 0.012))


def candlestick(name, x, y, z, h=1.15, mat=None, spread=1.0, fl=3):
    """烛台：底座 + 杆 + 上部托盘，托盘上 fl 支蜡烛。"""
    mat = mat or _MAT.get("gold")
    mm = mat
    _lathe(name + "_b", [(0.0, 0.0), (0.20 * spread, 0.0), (0.20 * spread, 0.05),
                         (0.10 * spread, 0.09), (0.05, 0.13), (0.032, 0.20),
                         (0.022, 0.40), (0.048, h * 0.62), (0.022, h * 0.68),
                         (0.020, h - 0.10)], mm, 12, Ts(x, y, z))
    _lathe(name + "_c", [(0.0, 0.0), (0.11 * spread, 0.0), (0.13 * spread, 0.045),
                         (0.02, 0.06), (0.0, 0.06)], mm, 12, Ts(x, y, z + h - 0.10))
    if fl > 1:
        for i in range(fl - 1):
            a = TAU * i / (fl - 1) + 0.4
            ox = math.cos(a) * 0.11 * spread
            oy = math.sin(a) * 0.11 * spread
            _lathe(name + "_a%d" % i, [(0.0, 0.0), (0.016, 0.0), (0.014, 0.18)],
                   mm, 8, Ts(x + ox, y + oy, z + h - 0.10))
            candle(name + "_k%d" % i, x + ox, y + oy, z + h + 0.08, 0.028, 0.30)
        candle(name + "_k0", x, y, z + h - 0.03, 0.034, 0.34)
    else:
        candle(name + "_k0", x, y, z + h - 0.03, 0.034, 0.34)


# ===========================================================================
#  4. 墙体工具（约定：origin+u*a+v*b 为内表面，n 朝外，墙体占 d∈[0,th]，
#     房间在 d<0 一侧）
# ===========================================================================
def wall_band(name, O, U, V, N, d0, d1, a0, a1, mat, bot=None, top=None,
              na=12, zb=0.0, zt=0.0):
    """一条墙板：底边 bot(a) 或 zb，顶边 top(a) 或 zt。"""
    rng = [a0 + (a1 - a0) * i / na for i in range(na + 1)]
    if bot is None:
        lo = [(a, zb) for a in rng]
    else:
        lo = [(a, bot(a)) for a in rng]
    if top is None:
        hi = [(a, zt) for a in rng]
    else:
        hi = [(a, top(a)) for a in rng]
    poly = lo + hi[::-1]
    return prism2d(name, O, U, V, N, d0, d1, poly, mat)


def wall_zone(name, O, U, V, N, d0, d1, a0, a1, mat, ops, zb=0.0, zt=0.0,
              top=None, na=8):
    """带通高尖券开口的墙板。

    ops = [(oa0, oa1, zsill, zspr, rise)]，开口为 zsill..zspr 直段 + 尖券。
    """
    ops = sorted(ops, key=lambda o: o[0])
    out = []
    cur = a0

    def _strip(sa, sb):
        if sb - sa < 1e-6:
            return
        if top is None:
            out.append(prism2d(name + "_s", O, U, V, N, d0, d1,
                               [(sa, zb), (sb, zb), (sb, zt), (sa, zt)], mat))
        else:
            rng = [sa + (sb - sa) * i / max(1, na // 2) for i in range(max(1, na // 2) + 1)]
            poly = [(a, zb) for a in rng] + [(a, top(a)) for a in rng[::-1]]
            out.append(prism2d(name + "_s", O, U, V, N, d0, d1, poly, mat))

    for (oa0, oa1, zsill, zspr, rise) in ops:
        _strip(cur, oa0)
        if zsill > zb + 1e-6:
            out.append(prism2d(name + "_lo", O, U, V, N, d0, d1,
                               [(oa0, zb), (oa1, zb), (oa1, zsill), (oa0, zsill)], mat))
        pts = arch_uv(oa0, oa1, zspr, rise, na)
        pts = [(oa0, zspr)] + pts[1:]
        if top is None:
            pts += [(oa1, zt), (oa0, zt)]
        else:
            pts += [(oa1, top(oa1))]
            for i in range(na, -1, -1):
                a = oa0 + (oa1 - oa0) * i / na
                pts.append((a, top(a)))
        out.append(prism2d(name + "_up", O, U, V, N, d0, d1, pts, mat))
        cur = oa1
    _strip(cur, a1)
    return out


def lancet(a0, a1, zsill, zspr, rise, inset=0.0, n=10):
    """尖券开口轮廓（逆时针，含直段与券）。"""
    a0 += inset
    a1 -= inset
    pts = [(a0, zsill), (a1, zsill), (a1, zspr)]
    pts += arch_uv(a0, a1, zspr, rise - inset * 1.4, n)[::-1][1:]
    return pts


def _glass_mosaic(name, O, U, V, N, poly, d0, d1, cell, mats, seed=0):
    """彩色玻璃马赛克：把窗口多边形切成小格，每格随机一种玻璃，
    格与格之间留 1.2 cm 铅条缝（背后是深色玻璃底板）。每个颜色合成一个
    网格对象，避免上百个碎对象。"""
    rr = random.Random(seed)
    aa = [p[0] for p in poly]
    zz = [p[1] for p in poly]
    a0, a1 = min(aa), max(aa)
    z0, z1 = min(zz), max(zz)
    na = max(1, int((a1 - a0) / cell))
    nz = max(1, int((z1 - z0) / cell))
    buckets = {}
    for i in range(na):
        for j in range(nz):
            ca = a0 + (a1 - a0) * (i + 0.5) / na
            cz = z0 + (z1 - z0) * (j + 0.5) / nz
            if not _pt_in_poly(ca, cz, poly):
                continue
            qa = a0 + (a1 - a0) * i / na + 0.013
            qb = a0 + (a1 - a0) * (i + 1) / na - 0.013
            qz = z0 + (z1 - z0) * j / nz + 0.013
            qt = z0 + (z1 - z0) * (j + 1) / nz - 0.013
            if qb - qa < 0.02 or qt - qz < 0.02:
                continue
            k = rr.randrange(len(mats))
            buckets.setdefault(k, []).append((qa, qz, qb, qt))
    for k, cells in buckets.items():
        verts = []
        faces = []
        for (qa, qz, qb, qt) in cells:
            b = len(verts)
            for (a, z) in ((qa, qz), (qb, qz), (qb, qt), (qa, qt)):
                p = Vector(O) + Vector(U) * a + Vector(V) * z + Vector(N) * d0
                verts.append((p.x, p.y, p.z))
            faces.append((b + 3, b + 2, b + 1, b + 0))
        _polyv("%s_m%d" % (name, k), verts, faces, mats[k])


def window_fill(name, O, U, V, N, a0, a1, zsill, zspr, rise, glass, frame,
                d_in=0.0, th=WALL_T, tracery=1, transom=0.0, sill=True,
                mosaic=True, seed=0):
    """洞口内的玻璃 + 石框 + 竖棂 + 窗台。"""
    ol = lancet(a0, a1, zsill, zspr, rise)
    gl = lancet(a0, a1, zsill, zspr, rise, inset=0.045)
    prism2d(name + "_gl", O, U, V, N, d_in + 0.09, d_in + 0.15, gl, glass)
    if mosaic:
        m = _MAT
        others = [m["glass_blue"], m["glass_red"], m["glass_gold"],
                  m["glass_green"], m["glass_rose"]]
        others = [o for o in others if o is not glass]
        sd = seed
        for ch in name:
            sd = (sd * 131 + ord(ch)) & 0x7FFFFFFF
        r2 = random.Random(sd)
        acc1 = others[r2.randrange(len(others))]
        acc2 = others[r2.randrange(len(others))]
        # 每扇窗以一种色为主（5/9），两种辅色，少量金色亮片 —— 避免「彩色纸屑」
        pal = [glass, glass, glass, glass, glass, acc1, acc1, acc2, m["glass_gold"]]
        _glass_mosaic(name, O, U, V, N, lancet(a0, a1, zsill, zspr, rise, inset=0.055),
                      d_in + 0.070, d_in + 0.078, 0.34, pal, sd)
    # 石框中线沿洞口一圈
    path = [Vector(O) + Vector(U) * p[0] + Vector(V) * p[1] for p in ol]
    sweep(name + "_fr", path + [path[0]],
          [(-0.055, 0.02), (0.055, 0.02), (0.075, -0.05), (0.045, -0.085), (-0.045, -0.085), (-0.075, -0.05)],
          frame, up=tuple(N), caps=False, smooth=False)
    # 竖棂
    w = a1 - a0
    for i in range(tracery):
        aa = a0 + w * (i + 1) / (tracery + 1)
        prism2d(name + "_tr%d" % i, O, U, V, N, d_in - 0.075, d_in + 0.10,
                [(aa - 0.080, zsill + 0.05), (aa + 0.080, zsill + 0.05),
                 (aa + 0.080, zspr), (aa - 0.080, zspr)], frame)
    if transom > 0.0:
        prism2d(name + "_tm", O, U, V, N, d_in - 0.07, d_in + 0.09,
                [(a0 + 0.02, transom), (a1 - 0.02, transom),
                 (a1 - 0.02, transom + 0.14), (a0 + 0.02, transom + 0.14)], frame)
    if sill:
        prism2d(name + "_si", O, U, V, N, d_in - 0.13, d_in + 0.06,
                [(a0 - 0.10, zsill - 0.16), (a1 + 0.10, zsill - 0.16),
                 (a1 + 0.10, zsill - 0.02), (a0 - 0.10, zsill - 0.02)], frame)
    return None


def plinth(name, O, U, V, N, a0, a1, h=Z_BASE, out=0.16, mat=None, th=0.30):
    mat = mat or _MAT["stone_dark"]
    return prism2d(name, O, U, V, N, -out, 0.004,
                   [(a0, 0.0), (a1, 0.0), (a1, h - 0.06), (a1 - 0.0, h),
                    (a0, h), (a0, h - 0.06)], mat)


def course(name, O, U, V, N, a0, a1, z, h, out=0.16, mat=None, up=0.10):
    """水平线脚：下沿凸 out，上沿做一个小斜面。"""
    mat = mat or _MAT["stone_trim"]
    poly = [(a0, z), (a1, z), (a1, z + h - up), (a1 - 0.0, z + h),
            (a0, z + h), (a0, z + h - up)]
    return prism2d(name, O, U, V, N, -out, 0.004, poly, mat)


# ===========================================================================
#  5. 地面
# ===========================================================================
def _apse_poly(inset=0.0):
    r = APSE_R - inset
    return [(r * math.sin(R(-90 + 36 * i)), Y_APSE + r * math.cos(R(-90 + 36 * i)))
            for i in range(6)]


def _pt_in_poly(x, y, poly):
    ins = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                ins = not ins
    return ins


def _floor_stones(name, x0, x1, y0, y1, inside=None, wide=None, z=0.0,
                  gap=0.011, lo=0.60, hi=0.96, mats=None, rng=None):
    rng = rng or RNG
    mats = mats or (_MAT["floor"], _MAT["floor_light"], _MAT["floor_dark"])
    verts, faces, mi = [], [], []
    y = y0
    while y < y1 - 0.05:
        rh = rng.uniform(lo, hi)
        if y + rh > y1:
            rh = y1 - y
        x = x0 - rng.uniform(0.0, 0.5)
        while x < x1 - 0.05:
            w = rng.uniform(lo, hi)
            if wide and wide(x + 0.5 * w, y + 0.5 * rh):
                w *= 1.5
            xa = max(x0, x)
            xb = min(x1, x + w)
            if xb - xa > 0.10:
                cx = 0.5 * (xa + xb)
                cy = y + 0.5 * rh
                ok = True
                if inside is not None:
                    ok = (inside(cx, cy) and inside(xa + 0.03, y + 0.03)
                          and inside(xb - 0.03, y + rh - 0.03))
                if ok:
                    b = len(verts)
                    verts += [(xa + gap, y + gap, z), (xb - gap, y + gap, z),
                              (xb - gap, y + rh - gap, z), (xa + gap, y + rh - gap, z)]
                    faces.append((b, b + 1, b + 2, b + 3))
                    mi.append(rng.randrange(len(mats)))
            x += w
        y += rh
    ob = _polyv(name, verts, faces, mats[0])
    for m in mats[1:]:
        ob.data.materials.append(m)
    for i, p in enumerate(ob.data.polygons):
        p.material_index = mi[i]
    return ob


def _tomb_slabs(M):
    ys = [-31.5, -26.4, -21.0, -15.8, -10.2, -5.0]
    for i, yy in enumerate(ys):
        w, l = 1.05, 2.25
        _box("ci_tomb%d" % i, Ts(0, yy, 0.022), (w, l, 0.045), M["floor_light"], bev=0.012)
        for (dx, dy, sx, sy) in ((0, l * 0.5 - 0.10, w - 0.18, 0.05),
                                 (0, -l * 0.5 + 0.10, w - 0.18, 0.05),
                                 (w * 0.5 - 0.10, 0, 0.05, l - 0.18),
                                 (-w * 0.5 + 0.10, 0, 0.05, l - 0.18)):
            _box("ci_tomb%d_g" % i, Ts(dx, yy + dy, 0.049), (sx, sy, 0.014), M["grout"])
        _box("ci_tomb%d_c1" % i, Ts(0, yy + 0.10, 0.050), (0.115, l - 0.62, 0.014), M["stone_dark"])
        _box("ci_tomb%d_c2" % i, Ts(0, yy + 0.62, 0.050), (w - 0.42, 0.115, 0.014), M["stone_dark"])
        _cyl("ci_tomb%d_b" % i, Ts(0, yy - l * 0.5 + 0.42, 0.048), 0.20, 0.014, M["stone_dark"], seg=14)


def build_floor(M):
    _box("ci_grout", Ts(0, -3.25, -0.06), (30.4, 77.5, 0.12), M["grout"])
    ap = _apse_poly(0.0)
    _floor_stones("ci_floor_a", -AISLE_IN, AISLE_IN, Y_W, Y_APSE,
                  wide=lambda x, y: abs(x) < 1.5,
                  mats=(M["floor"], M["floor_light"], M["floor_dark"]))
    for sx in (-1, 1):
        _floor_stones("ci_floor_t%d" % sx, sx * AISLE_IN, sx * TR_X, Y_X0, Y_X1,
                      mats=(M["floor"], M["floor_dark"], M["floor_light"]))
    _floor_stones("ci_floor_ap", -APSE_R, APSE_R, Y_APSE - 0.1, Y_APSE + APSE_R + 0.2,
                  inside=lambda x, y: _pt_in_poly(x, y, ap),
                  mats=(M["floor_light"], M["floor"], M["floor_dark"]))
    _tomb_slabs(M)


# ===========================================================================
#  6. 中厅 / 唱诗席侧墙
# ===========================================================================
def _via_bay_wall(M, sx, y0, y1, kind="nave"):
    """一侧一个开间的墙：拱上墙 + triforium + 束带 + 高侧窗 + 檐口 + 拱顶半月板。"""
    O = (sx * N_HW + sx * OFF * 0, 0.0, 0.0)
    O = (sx * (N_HW - OFF), 0.0, 0.0)
    U = (0.0, sx, 0.0)
    V = (0.0, 0.0, 1.0)
    N = (sx, 0.0, 0.0)
    a0, a1 = sx * y0, sx * y1
    if a0 > a1:
        a0, a1 = a1, a0
    span = a1 - a0
    tag = "ci_w%s%s_%d" % (kind[0], "p" if sx > 0 else "n", int(abs(y0) * 10))
    th = WALL_T

    # --- 连拱廊拱背以上的墙 ------------------------------------------------
    ph = 0.62 if kind == "nave" else 0.72
    oa0, oa1 = a0 + ph, a1 - ph
    zs = Z_ARC_SPRING
    rise = Z_ARC_APEX - Z_ARC_SPRING + Z_ARC_BAND

    def bot(a):
        return arch_z(a, oa0, oa1, zs, rise) if oa0 < a < oa1 else zs

    wall_band(tag + "_sp", O, U, V, N, 0.0, th, a0, a1, M["stone"],
              bot=bot, zt=Z_TRIF_S, na=14)

    # --- triforium：4 个小连拱 ---------------------------------------------
    g = span * 0.53 / 5.0
    ow = span * 0.47 / 4.0
    ops = []
    for i in range(4):
        oa = a0 + g + i * (ow + g)
        ops.append((oa, oa + ow, Z_TRIF_S, Z_TRIF_SPR, 0.62))
        window_fill(tag + "_tfs%d" % i, O, U, V, N, oa, oa + ow, Z_TRIF_S,
                    Z_TRIF_SPR, 0.62, M["shadow"], M["stone_trim"],
                    tracery=0, sill=False, mosaic=False)
    wall_zone(tag + "_tf", O, U, V, N, 0.0, th, a0, a1, M["stone"], ops,
              zb=Z_TRIF_S, zt=Z_TRIF_T, na=6)
    course(tag + "_tfc", O, U, V, N, a0, a1, Z_TRIF_T, Z_TRIF_B - Z_TRIF_T,
           out=0.15, mat=M["stone_trim"])

    # --- 束带层下的实墙 ---------------------------------------------------
    wall_band(tag + "_bd", O, U, V, N, 0.0, th, a0, a1, M["stone"],
              zb=Z_TRIF_B, zt=Z_CLER_S, na=2)

    # --- 高侧窗：2 扇 ------------------------------------------------------
    m = span * 0.124
    owc = span * 0.276
    cops = []
    for i in range(2):
        oa = a0 + m + i * (owc + m)
        cops.append((oa, oa + owc, Z_CLER_S, Z_CLER_SPR, Z_CLER_RISE))
        window_fill(tag + "_cl%d" % i, O, U, V, N, oa, oa + owc, Z_CLER_S,
                    Z_CLER_SPR, Z_CLER_RISE, M["glass_gold"], M["stone_trim"],
                    tracery=1, transom=Z_CLER_S + 0.55, sill=False)
    wall_zone(tag + "_cl", O, U, V, N, 0.0, th, a0, a1, M["stone"], cops,
              zb=Z_CLER_S, zt=Z_CORN, na=10)

    # --- 檐口 --------------------------------------------------------------
    course(tag + "_co1", O, U, V, N, a0, a1, Z_CORN, 0.16, out=0.20, mat=M["stone_trim"])
    course(tag + "_co2", O, U, V, N, a0, a1, Z_CORN + 0.16, 0.24, out=0.34, mat=M["stone_trim"])
    course(tag + "_co3", O, U, V, N, a0, a1, Z_CORN + 0.40, 0.20, out=0.16, mat=M["stone"])

    # --- 拱顶半月板（起拱线以上直到拱顶）---------------------------------
    if kind == "nave":
        hr, hc, zs2 = NAVE_HR, Z_CROWN, Z_VAULT
    else:
        hr, hc, zs2 = NAVE_HR, Z_CROWN, Z_VAULT
    half = 0.5 * span

    def top(a):
        u = (a - 0.5 * (a0 + a1)) / half
        return zs2 + hr * pf(u, hr / half)

    wall_band(tag + "_lu", O, U, V, N, 0.0, th, a0, a1, M["stone"],
              zb=Z_CORN + 0.60, top=top, zt=Z_CORN + 0.60, na=12)
    # 拱顶起拱处的小挑檐
    course(tag + "_lu2", O, U, V, N, a0, a1, Z_CORN + 0.44, 0.16, out=0.10, mat=M["stone"])
    return tag


def _nave_walls(M):
    for sx in (1, -1):
        for i in range(NBAY):
            _via_bay_wall(M, sx, Y_W + BAY * i, Y_W + BAY * (i + 1), "nave")
        for i in range(NCH):
            _via_bay_wall(M, sx, Y_X1 + CH_BAY * i, Y_X1 + CH_BAY * (i + 1), "choir")
        # 勒脚（贯通）
        O = (sx * (N_HW - OFF), 0.0, 0.0)
        for (yy0, yy1) in ((Y_W, Y_X0), (Y_X1, Y_APSE)):
            a0, a1 = sx * yy0, sx * yy1
            plinth("ci_pl%d_%d" % (sx, int(yy0)), O, (0, sx, 0), (0, 0, 1), (sx, 0, 0),
                   min(a0, a1), max(a0, a1), mat=M["stone_dark"], out=0.14)
        # 束带层（连续）
        for zz, hh, oo in ((Z_TRIF_B - 0.10, 0.10, 0.12), (Z_CLER_S - 0.16, 0.16, 0.14)):
            pass


def _aisle_walls(M):
    """侧廊外墙：每个开间一扇双联窗 + 拱顶半月板 + 壁柱。"""
    for sx in (1, -1):
        O = (sx * (AISLE_IN - OFF), 0.0, 0.0)
        U = (0.0, sx, 0.0)
        V = (0.0, 0.0, 1.0)
        N = (sx, 0.0, 0.0)
        th = WALL_T
        bays = [(Y_W + BAY * i, Y_W + BAY * (i + 1)) for i in range(NBAY)]
        bays += [(Y_X1 + CH_BAY * i, Y_X1 + CH_BAY * (i + 1)) for i in range(NCH)]
        for k, (y0, y1) in enumerate(bays):
            a0, a1 = sx * y0, sx * y1
            if a0 > a1:
                a0, a1 = a1, a0
            span = a1 - a0
            tag = "ci_aw%d_%d" % (sx, k)
            m = span * 0.185
            ops = [(a0 + m, a1 - m, AISLE_WIN_SILL, AISLE_WIN_SPR, AISLE_WIN_RISE)]
            wall_zone(tag + "_z", O, U, V, N, 0.0, th, a0, a1, M["stone"], ops,
                      zb=0.0, zt=Z_AIS_SPRING, na=10)
            window_fill(tag + "_w", O, U, V, N, a0 + m, a1 - m, AISLE_WIN_SILL,
                        AISLE_WIN_SPR, AISLE_WIN_RISE, M["glass"], M["stone_trim"],
                        tracery=2, transom=6.30)
            half = 0.5 * span

            def top(a, hh=half):
                u = (a - 0.5 * (a0 + a1)) / hh
                return Z_AIS_SPRING + Z_AIS_WR * pf(u, Z_AIS_WR / hh)

            wall_band(tag + "_lu", O, U, V, N, 0.0, th, a0, a1, M["stone"],
                      zb=Z_AIS_SPRING, top=top, zt=Z_AIS_SPRING, na=10)
            # 壁柱
            for aa in (a0 + 0.02, a1 - 0.02):
                prism2d(tag + "_pi", O, U, V, N, -0.22, 0.0,
                        [(aa - 0.20, Z_BASE), (aa + 0.20, Z_BASE),
                         (aa + 0.20, Z_AIS_SPRING), (aa - 0.20, Z_AIS_SPRING)],
                        M["stone_warm"])
                prism2d(tag + "_pc", O, U, V, N, -0.26, 0.0,
                        [(aa - 0.26, Z_AIS_SPRING - 0.22), (aa + 0.26, Z_AIS_SPRING - 0.22),
                         (aa + 0.26, Z_AIS_SPRING), (aa - 0.26, Z_AIS_SPRING)],
                        M["stone_trim"])
            course(tag + "_tc", O, U, V, N, a0, a1, 6.10, 0.14, out=0.12,
                   mat=M["stone_trim"])
        plinth("ci_apl%d" % sx, O, U, V, N, min(sx * Y_W, sx * Y_APSE),
               max(sx * Y_W, sx * Y_APSE), mat=M["stone_dark"], out=0.15)


# ===========================================================================
#  7. 西墙 + 玫瑰窗
# ===========================================================================
def _west_wall(M):
    O = (0.0, Y_W, 0.0)
    U = (1.0, 0.0, 0.0)
    V = (0.0, 0.0, 1.0)
    N = (0.0, -1.0, 0.0)
    th = W_END_T
    hw = N_HW - OFF
    # 中厅部分顶边 = 横向大券
    def top(a):
        return Z_VAULT + NAVE_HT * pf(a / hw, NAVE_HT / hw)

    x0, x1 = -ROSE_R, ROSE_R
    zr0, zr1 = ROSE_Z - ROSE_R, ROSE_Z + ROSE_R
    # 左右大板
    for s in (-1, 1):
        xa, xb = (s * hw, s * x0) if s < 0 else (x0, x1)
        pass
    wall_band("ci_ww_l", O, U, V, N, 0.0, th, -hw, x0, M["stone"],
              zb=0.0, top=top, na=10)
    wall_band("ci_ww_r", O, U, V, N, 0.0, th, x1, hw, M["stone"],
              zb=0.0, top=top, na=10)
    # 中部：门洞两侧
    wall_band("ci_ww_ml", O, U, V, N, 0.0, th, x0, -PORTAL_W * 0.5, M["stone"],
              zb=0.0, zt=zr0, na=4)
    wall_band("ci_ww_mr", O, U, V, N, 0.0, th, PORTAL_W * 0.5, x1, M["stone"],
              zb=0.0, zt=zr0, na=4)
    # 门洞上方
    pts = [(x, arch_z(x, -PORTAL_W * 0.5, PORTAL_W * 0.5, PORTAL_SPR,
                      PORTAL_APEX - PORTAL_SPR)) for x in
           [-PORTAL_W * 0.5 + PORTAL_W * i / 10 for i in range(11)]]
    pts += [(PORTAL_W * 0.5, zr0), (-PORTAL_W * 0.5, zr0)]
    prism2d("ci_ww_pa", O, U, V, N, 0.0, th, pts, M["stone"])
    # 玫瑰窗上方的墙
    wall_band("ci_ww_top", O, U, V, N, 0.0, th, x0, x1, M["stone"],
              zb=zr1, top=top, zt=zr1, na=8)
    # 玫瑰窗方形开口处的角部填充（方形 → 圆形）
    _rose_ring(M, O, U, V, N, th)
    # 侧廊部分（两段）
    for s in (-1, 1):
        a0, a1 = (s * (AISLE_IN - OFF), s * hw)
        if a0 > a1:
            a0, a1 = a1, a0
        def atop(a, s=s):
            u = (a - s * (N_HW + AISLE_IN) * 0.5) / (0.5 * (AISLE_IN - N_HW))
            # 西墙这一段横跨侧廊宽度（U = x），顶边要跟侧廊拱顶在 y=Y_W 处的
            # 横向剖面（rise = Z_AIS_TR）走；用 Z_AIS_WR 会矮 1.6 m 并留下露天缝。
            return Z_AIS_SPRING + Z_AIS_TR * pf(u, Z_AIS_TR / (0.5 * (AISLE_IN - N_HW)))
        wall_band("ci_ww_ail%d" % s, O, U, V, N, 0.0, th, a0, a1, M["stone"],
                  zb=0.0, top=atop, zt=Z_AIS_SPRING, na=8)
    # 大门
    _west_door(M)


def _rose_ring(M, O, U, V, N, th, n=32):
    cx, cz = 0.0, ROSE_Z
    for i in range(n):
        a0 = TAU * i / n
        a1 = TAU * (i + 1) / n
        p0 = (ROSE_R * math.cos(a0), cz + ROSE_R * math.sin(a0))
        p1 = (ROSE_R * math.cos(a1), cz + ROSE_R * math.sin(a1))
        q0 = (ROSE_R / max(abs(math.cos(a0)), abs(math.sin(a0))) * math.cos(a0),
              cz + ROSE_R / max(abs(math.cos(a0)), abs(math.sin(a0))) * math.sin(a0))
        q1 = (ROSE_R / max(abs(math.cos(a1)), abs(math.sin(a1))) * math.cos(a1),
              cz + ROSE_R / max(abs(math.cos(a1)), abs(math.sin(a1))) * math.sin(a1))
        prism2d("ci_rr%d" % i, O, U, V, N, 0.0, th, [p0, p1, q1, q0], M["stone_warm"])


def _stone_bar(name, O, U, V, N, a, b, w, h, d0, d1, mat, ang=0.0):
    """墙面上的扁石条（a,b 中点，宽 w 高 h，绕 n 转 ang）。"""
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for (u, v) in ((-w * 0.5, -h * 0.5), (w * 0.5, -h * 0.5), (w * 0.5, h * 0.5), (-w * 0.5, h * 0.5)):
        pts.append((a + u * ca - v * sa, b + u * sa + v * ca))
    return prism2d(name, O, U, V, N, d0, d1, pts, mat)


# ---- 玫瑰窗：真洞口 ------------------------------------------------------
# 坐标：d = 从西墙内表面往外（沿 N=(0,-1,0)）的进深，d<0 在室内。
ROSE_OPEN = 4.30        # 圆洞口半径（墙洞只有 4.60 见方，四角由 _rose_ring 补石）
ROSE_GLASS_D = 0.25     # 彩玻埋在洞内的深度
ROSE_CAVE_D = 0.55      # 玻璃后 0.30 m 的暗腔后壁
ROSE_TR_D0 = 0.075      # 石窗棂前沿 / 后沿
ROSE_TR_D1 = 0.300


def _rose_xf():
    """玫瑰窗局部矩阵：车削体绕 X 转 90°，(r, d) → (r·cos, Y_W−d, ROSE_Z+r·sin)。"""
    return Ts(0.0, Y_W, ROSE_Z, 0.0, 0.0, math.pi * 0.5)


def _torus(name, r_mid, ra, rb, d_mid, mat, seg=72, n=14):
    """圆/椭圆截面石环：ra = 径向半轴，rb = 进深半轴。"""
    prof = [(r_mid + ra * math.cos(TAU * i / n), d_mid + rb * math.sin(TAU * i / n))
            for i in range(n + 1)]
    return _lathe(name, prof, mat, seg, _rose_xf(), False, False, True)


def _ring_box(name, r0, r1, d0, d1, a0, a1, n, mat):
    """环带扇区实体（玫瑰窗坐标系）：径向 r0..r1、进深 d0..d1、角度 a0..a1。"""
    verts, faces = [], []
    for i in range(n):
        b0 = a0 + (a1 - a0) * i / n
        b1 = a0 + (a1 - a0) * (i + 1) / n
        b = len(verts)
        for (a, r, d) in ((b0, r0, d0), (b0, r1, d0), (b0, r1, d1), (b0, r0, d1),
                          (b1, r0, d0), (b1, r1, d0), (b1, r1, d1), (b1, r0, d1)):
            verts.append((r * math.cos(a), Y_W - d, ROSE_Z + r * math.sin(a)))
        faces += [(b + 3, b + 2, b + 1, b + 0), (b + 4, b + 5, b + 6, b + 7),
                  (b + 0, b + 1, b + 5, b + 4), (b + 1, b + 2, b + 6, b + 5),
                  (b + 2, b + 3, b + 7, b + 6), (b + 3, b + 0, b + 4, b + 7)]
    return _polyv(name, verts, faces, mat, True)


def _rodprof(hw, hd, n=10):
    """椭圆截面（石窗棂）：hw = 切向半宽，hd = 进深半宽。"""
    return [(hw * math.cos(TAU * i / n), hd * math.sin(TAU * i / n))
            for i in range(n)]


def _rose_glass(name, r0, r1, d, nseg, nrad, pal, seed=0, came=0.013):
    """极坐标碎格彩玻：r0..r1 环带切成 nseg×nrad 小格，每格随机一色，
    格间留 1.3 cm 铅条缝；同色格合成一个网格，避免上千个碎对象。"""
    rr = random.Random(seed)
    buckets = {}
    for i in range(nseg):
        a0 = TAU * i / nseg
        a1 = TAU * (i + 1) / nseg
        for j in range(nrad):
            ra = r0 + (r1 - r0) * j / nrad + came
            rb = r0 + (r1 - r0) * (j + 1) / nrad - came
            if rb - ra < 0.014:
                continue
            da = came / max(0.22, rb)
            aa0, aa1 = a0 + da, a1 - da
            if aa1 - aa0 < 0.014:
                continue
            k = rr.randrange(len(pal))
            quad = [(r * math.cos(a), Y_W - d, ROSE_Z + r * math.sin(a))
                    for (a, r) in ((aa0, ra), (aa0, rb), (aa1, rb), (aa1, ra))]
            buckets.setdefault(k, []).append(quad)
    for k, cells in buckets.items():
        verts, faces = [], []
        for quad in cells:
            b = len(verts)
            verts += quad
            faces.append((b + 3, b + 2, b + 1, b + 0))
        _polyv("%s_m%d" % (name, k), verts, faces, pal[k])


def build_rose(M):
    """玫瑰窗：真洞口 + 0.6 m 退台侧壁 + 石窗棂（辐条 / 石环 / 窗台）
    + 埋在洞内 0.25 m 的碎格彩玻 + 玻璃后 0.30 m 的暗腔。"""
    RO = ROSE_OPEN
    # ---- 洞口侧壁：三段退台，越往里越外扩 --------------------------------
    prof = [(RO - 0.02, -0.050), (RO + 0.08, 0.005), (RO + 0.08, 0.22),
            (RO + 0.18, 0.28), (RO + 0.18, 0.50), (RO + 0.28, 0.56),
            (RO + 0.28, 0.72), (RO + 0.42, 0.72), (RO + 0.42, 0.995)]
    _lathe("ci_rsvl", prof, M["stone_warm"], 72, _rose_xf(), False, False, True)
    # 洞口内侧的小圆线脚（把洞口和墙面分开）
    _torus("ci_rsvf", RO + 0.05, 0.085, 0.085, -0.015, M["stone_trim"], 72, 12)
    # ---- 墙面上的凸出边框（把窗洞和墙分开，窗才像开出来的）---------------
    _torus("ci_rfrm", RO + 0.64, 0.30, 0.115, -0.075, M["stone_warm"], 80, 14)
    _torus("ci_rfrm2", RO + 0.34, 0.075, 0.115, -0.132, M["stone_dark"], 72, 10)
    # ---- 石窗棂：外环 / 中环 / 内环 / 12 辐 / 中心圆徽 --------------------
    dm, dh = 0.5 * (ROSE_TR_D0 + ROSE_TR_D1), 0.5 * (ROSE_TR_D1 - ROSE_TR_D0)
    st = M["stone_rose"]
    _torus("ci_rtr0", RO - 0.16, 0.235, dh, dm, M["stone_warm"], 72, 12)
    _torus("ci_rtr1", 2.66, 0.120, dh, dm, st, 64, 10)
    _torus("ci_rtr2", 1.16, 0.135, dh, dm, st, 56, 10)
    for i in range(12):
        a = TAU * i / 12 + math.pi / 12
        ca, sa = math.cos(a), math.sin(a)
        pts = [(r * ca, Y_W - dm, ROSE_Z + r * sa) for r in (1.10, 2.30, 3.20, 4.02)]
        sweep("ci_rsp%d" % i, pts, _rodprof(0.105, dh), st, up=(0, 1, 0))
    _lathe("ci_rhub", [(0.0, ROSE_TR_D1), (0.80, ROSE_TR_D1), (0.84, ROSE_TR_D1 - 0.10),
                       (0.80, ROSE_TR_D0 + 0.02), (0.0, ROSE_TR_D0 - 0.03)],
           M["stone_warm"], 48, _rose_xf())
    _lathe("ci_rhub2", [(0.0, ROSE_TR_D0 - 0.06), (0.30, ROSE_TR_D0 - 0.02),
                        (0.26, ROSE_TR_D0 + 0.10), (0.0, ROSE_TR_D0 + 0.14)],
           M["stone_trim"], 32, _rose_xf())
    _sph("ci_rhubg", Ts(0.0, Y_W - ROSE_TR_D0 + 0.06, ROSE_Z), 0.16, M["gold"], 14, 8, 0.7)
    # ---- 彩玻：三圈同心色带的碎格马赛克（金心 / 红环 / 蓝外圈）---------
    m = M
    gold = [m["rg_g0"], m["rg_g0"], m["rg_g1"], m["rg_g1"], m["rg_r1"],
            m["glass_rose"]]
    red = [m["rg_r0"], m["rg_r0"], m["rg_r1"], m["rg_r1"], m["rg_g1"],
           m["glass_rose"]]
    blue = [m["rg_b0"], m["rg_b0"], m["rg_b1"], m["rg_b1"], m["glass_blue"],
            m["rg_r1"], m["glass_green"]]
    _rose_glass("ci_rgl0", 0.04, 1.05, ROSE_GLASS_D, 20, 3, gold, 11)
    _rose_glass("ci_rgl1", 1.05, 2.60, ROSE_GLASS_D, 48, 5, red, 23)
    _rose_glass("ci_rgl2", 2.60, RO - 0.14, ROSE_GLASS_D, 64, 5, blue, 37)
    # ---- 玻璃后 0.30 m 的暗腔：后壁 + 一圈暗色内衬 ------------------------
    _lathe("ci_rcv0", [(0.02, ROSE_CAVE_D), (RO + 0.34, ROSE_CAVE_D)],
           M["shadow"], 64, _rose_xf(), False, False, False)
    _lathe("ci_rcv1", [(RO + 0.02, ROSE_GLASS_D + 0.01), (RO + 0.02, ROSE_CAVE_D)],
           M["shadow"], 64, _rose_xf(), False, False, True)
    # ---- 窗台：贴着洞口下缘的外挑石台 -----------------------------------
    za = math.pi + 0.28
    zb = TAU - 0.28
    _ring_box("ci_rsill1", RO - 0.42, RO + 0.24, -0.34, 0.10, za, zb, 16,
              M["stone_dark"])
    _ring_box("ci_rsill2", RO - 0.34, RO + 0.24, -0.26, 0.10, za + 0.04, zb - 0.04,
              16, M["stone_trim"])
    for k in range(3):
        a = math.pi + 0.50 + k * 0.80
        _box("ci_rsilb%d" % k,
             Ts((RO - 0.32) * math.cos(a), Y_W + 0.16, ROSE_Z + (RO - 0.32) * math.sin(a),
                0.0, 0.0, a + math.pi * 0.5),
             (0.16, 0.24, 0.26), M["stone_dark"], bev=0.012)


def _west_door(M):
    """大门：门框 + 两扇半开的木门。"""
    y = Y_W
    for s in (-1, 1):
        _box("ci_djamb%d" % s, Ts(s * (PORTAL_W * 0.5 + 0.12), y + 0.10, 2.10),
             (0.24, 0.26, 4.20), M["stone_trim"], bev=0.02)
    # 尖券门套（两圈）
    for k, (ww, dd) in enumerate(((0.30, 0.30), (0.20, 0.22))):
        path = [Vector((x, y + dd * 0.5, arch_z(x, -PORTAL_W * 0.5 - k * 0.30,
                                               PORTAL_W * 0.5 + k * 0.30,
                                               PORTAL_SPR, PORTAL_APEX - PORTAL_SPR)))
                for x in [-PORTAL_W * 0.5 - k * 0.30 + (PORTAL_W + k * 0.6) * i / 12
                          for i in range(13)]]
        sweep("ci_darch%d" % k, path,
              [(-ww * 0.5, 0.0), (ww * 0.5, 0.0), (ww * 0.5, dd), (-ww * 0.5, dd)],
              M["stone_trim"], up=(0, -1, 0), smooth=False)
    # 门扇（向内开 68°）
    for s in (-1, 1):
        leaf = M["wood_dark"]
        _box("ci_dlf%d" % s, Ts(s * 1.02, y + 0.42, 1.90), (1.72, 0.10, 3.70), leaf, bev=0.012)
        for i in range(4):
            _box("ci_dlb%d" % s, Ts(s * 1.02, y + 0.30, 0.55 + i * 0.92),
                 (1.56, 0.05, 0.14), M["iron"])
        _sph("ci_dkn%d" % s, Ts(s * 1.55, y + 0.26, 1.95), 0.06, M["gold"], 10, 6)


# ===========================================================================
#  8. 券 / 束柱 / 肋拱
# ===========================================================================
ARC_PROF = None


def arch_band(name, O, U, V, N, a0, a1, zspr, rise, w, d0, d1, mat, n=16):
    """沿尖券曲线扫掠的券带：沿平面法向 d0..d1、径向 0..w。"""
    pts = [Vector(O) + Vector(U) * a + Vector(V) * z
           for (a, z) in arch_uv(a0, a1, zspr, rise, n)]
    return sweep(name, pts, [(d0, 0.0), (d1, 0.0), (d1, w), (d0, w)],
                 mat, up=tuple(V), smooth=False)


def pier(name, x, y, z1=Z_ARC_SPRING, big=False, r_core=0.46, r_shaft=0.135,
         n_shaft=8):
    """束柱：八边形柱础 + 柱身 + 8 根附柱 + 2 道柱环 + 柱头。"""
    rb = 0.98 if big else 0.82
    hb = 0.40
    _lathe(name + "_b1", [(0.0, 0.0), (rb, 0.0), (rb, hb * 0.55), (rb * 0.92, hb * 0.8),
                          (rb * 0.80, hb), (0.0, hb)], _MAT["stone_dark"], 8,
           Ts(x, y, 0.0))
    _lathe(name + "_b2", [(0.0, 0.0), (rb * 0.86, 0.0), (rb * 0.86, 0.10),
                          (rb * 0.74, 0.16), (0.0, 0.20)], _MAT["stone_trim"], 8,
           Ts(x, y, hb))
    z0 = hb + 0.20
    zt = z1 - 0.62
    _lathe(name + "_c", [(0.0, 0.0), (r_core, 0.0), (r_core * 0.97, zt - z0),
                         (0.0, zt - z0)], _MAT["stone"], 14, Ts(x, y, z0))
    for i in range(n_shaft):
        a = TAU * i / n_shaft + math.pi / n_shaft
        ox = (r_core + r_shaft * 0.55) * math.cos(a)
        oy = (r_core + r_shaft * 0.55) * math.sin(a)
        _lathe(name + "_s%d" % i, [(0.0, 0.0), (r_shaft, 0.0), (r_shaft, zt - z0 - 0.06),
                                   (r_shaft * 0.6, zt - z0), (0.0, zt - z0)],
               _MAT["stone_warm"], 8, Ts(x + ox, y + oy, z0))
    # 柱环
    for zz in (2.95, 5.85):
        _lathe(name + "_r%d" % int(zz * 10),
               [(0.0, 0.0), (r_core + r_shaft * 1.35, 0.0),
                (r_core + r_shaft * 1.55, 0.07),
                (r_core + r_shaft * 1.35, 0.15), (0.0, 0.15)],
               _MAT["stone_trim"], 16, Ts(x, y, zz))
    # 柱头
    rc = (r_core + r_shaft * 1.5)
    _lathe(name + "_cap", [(0.0, 0.0), (rc, 0.0), (rc * 1.02, 0.10),
                           (rc * 1.24, 0.34), (rc * 1.30, 0.44), (0.0, 0.44)],
           _MAT["stone_trim"], 16, Ts(x, y, zt))
    # 柱头卷叶（一圈小圆球）
    for i in range(10):
        a = TAU * i / 10
        _sph(name + "_lv%d" % i,
             Ts(x + (rc * 1.12) * math.cos(a), y + (rc * 1.12) * math.sin(a), zt + 0.30),
             0.085, _MAT["stone_trim"], 8, 6)
    # 顶板
    aw = 1.34 if not big else 1.72
    ad = 1.86 if not big else 2.30
    _box(name + "_ab", Ts(x, y, z1 - 0.16), (aw, ad, 0.20), _MAT["stone_trim"], bev=0.018)
    return z1


def _nave_vault_bay(M, y0, y1, tag):
    """中厅一个开间的四分肋拱。"""
    x0, x1 = -N_HW, N_HW
    zs, ht, hr, hc = Z_VAULT, NAVE_HT, NAVE_HR, Z_CROWN - Z_VAULT
    # 14x4 的网格铺 17 m x 5.25 m，一格 1.2 m，拱腹就成"瓦楞纸"；
    # 加密到 30x14（一格 0.57 / 0.38 m）后 smooth 才真正平滑。
    vault_sheet("ci_vb" + tag, x0, x1, y0, y1, zs, ht, hr, hc, 30, 14, M["vault_web"])
    cx, cy = 0.0, 0.5 * (y0 + y1)
    # 对角肋
    for (px, py) in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        vault_rib("ci_vd%s_%d%d" % (tag, int(px), int(py)), x0, x1, y0, y1, zs, ht, hr, hc,
                  (px, py), (cx, cy), 0.34, 0.42, M["rib_stone"], 10)
    # 脊肋
    vault_rib("ci_vr" + tag, x0, x1, y0, y1, zs, ht, hr, hc,
              (0.0, y0), (0.0, y1), 0.30, 0.34, M["rib_stone"], 8)
    # 墙肋（两端）
    for sx in (x0, x1):
        pts = []
        for i in range(21):
            yy = y0 + (y1 - y0) * i / 20
            pts.append((sx, yy, Z_VAULT + NAVE_HR * pf((yy - cy) / (0.5 * (y1 - y0)),
                                                       NAVE_HR / (0.5 * (y1 - y0)))))
        sweep("ci_vw%s_%d" % (tag, int(sx)), pts, _ribprof(0.28, 0.36), M["rib_stone"])
    boss("ci_vboss" + tag, 0.0, cy, Z_CROWN, 0.46, M["rib_stone"], M["gold"])
    return None


def _transverse_arch(M, y, zspr=Z_VAULT, rise=NAVE_HT, w=0.56, d=0.46, tag="n"):
    """横肋：跨中厅的一榀券（在 x-z 平面）。"""
    pts = []
    for i in range(41):
        a = -N_HW + 2 * N_HW * i / 40
        pts.append((a, y, zspr + rise * pf(a / N_HW, rise / N_HW)))
    sweep("ci_ta" + tag, pts, _ribprof(w, d), M["rib_stone"])
    # 券上的小挑檐
    course("ci_tac" + tag, (0.0, 0.0, 0.0), (1, 0, 0), (0, 0, 1), (0, 1, 0),
           -N_HW, N_HW, zspr - 0.10, 0.10, out=0.0, mat=M["stone"])


def _aisle_vault_bay(M, sx, y0, y1, tag):
    x0, x1 = sx * N_HW, sx * AISLE_IN
    if x0 > x1:
        x0, x1 = x1, x0
    zs = Z_AIS_SPRING
    ht, hr, hc = Z_AIS_TR, Z_AIS_WR, Z_AIS_CROWN - Z_AIS_SPRING
    vault_sheet("ci_av" + tag, x0, x1, y0, y1, zs, ht, hr, hc, 12, 10, M["vault_web"])
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    for (px, py) in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        vault_rib("ci_ad%s_%d%d" % (tag, int(px), int(py)), x0, x1, y0, y1, zs, ht, hr, hc,
                  (px, py), (cx, cy), 0.24, 0.28, M["rib_stone"], 8)
    # hc 是相对高度（Z_AIS_CROWN - Z_AIS_SPRING = 3.5），
    # 原来直接当绝对 z 传进去，拱心石全飘在 3.5 m 高的半空里
    boss("ci_ab" + tag, cx, cy, Z_AIS_CROWN, 0.28, M["rib_stone"])
    # 横向肋
    for yy in (y0, y1):
        pts = [(x, yy, zs + Z_AIS_TR * pf((x - cx) / (0.5 * (x1 - x0)),
                                          Z_AIS_TR / (0.5 * (x1 - x0))))
               for x in [x0 + (x1 - x0) * i / 14 for i in range(15)]]
        sweep("ci_at%s_%d" % (tag, int(yy * 10)), pts, _ribprof(0.34, 0.30), M["rib_stone"])


def build_vaults(M):
    for i in range(NBAY):
        y0, y1 = Y_W + BAY * i, Y_W + BAY * (i + 1)
        _nave_vault_bay(M, y0, y1, "n%d" % i)
        for sx in (1, -1):
            _aisle_vault_bay(M, sx, y0, y1, "n%d%d" % (i, sx))
    for i in range(NCH):
        y0, y1 = Y_X1 + CH_BAY * i, Y_X1 + CH_BAY * (i + 1)
        _nave_vault_bay(M, y0, y1, "c%d" % i)
        for sx in (1, -1):
            _aisle_vault_bay(M, sx, y0, y1, "c%d%d" % (i, sx))
    # 横肋
    ys = [Y_W + BAY * i for i in range(NBAY + 1)]
    ys += [Y_X1 + CH_BAY * i for i in range(NCH + 1)]
    for y in ys:
        _transverse_arch(M, y, tag="y%d" % int(y * 10))
    # 横厅拱顶
    for sx in (1, -1):
        for k in range(2):
            x0 = sx * (N_HW + 8.0 * k)
            x1 = sx * (N_HW + 8.0 * (k + 1))
            if x0 > x1:
                x0, x1 = x1, x0
            vault_sheet("ci_tv%d%d" % (sx, k), x0, x1, Y_X0, Y_X1,
                        Z_TR_SPRING, Z_TR_HT, Z_TR_HR, Z_TR_CROWN - Z_TR_SPRING, 14, 12, M["vault_web"])
            cx, cy = 0.5 * (x0 + x1), 0.5 * (Y_X0 + Y_X1)
            for (px, py) in ((x0, Y_X0), (x0, Y_X1), (x1, Y_X0), (x1, Y_X1)):
                vault_rib("ci_td%d%d_%d%d" % (sx, k, int(px), int(py)), x0, x1, Y_X0, Y_X1,
                          Z_TR_SPRING, Z_TR_HT, Z_TR_HR, Z_TR_CROWN - Z_TR_SPRING, (px, py), (cx, cy),
                          0.32, 0.40, M["rib_stone"], 8)
            boss("ci_tb%d%d" % (sx, k), cx, cy, Z_TR_CROWN, 0.40, M["rib_stone"], M["gold"])
            for yy in (Y_X0, Y_X1):
                pts = [(x, yy, Z_TR_SPRING + Z_TR_HT * pf((x - cx) / (0.5 * (x1 - x0)),
                                                          Z_TR_HT / (0.5 * (x1 - x0))))
                       for x in [x0 + (x1 - x0) * i / 14 for i in range(15)]]
                sweep("ci_tt%d%d_%d" % (sx, k, int(yy)), pts, _ribprof(0.42, 0.38),
                      M["rib_stone"])


# ===========================================================================
#  9. 交叉部 / 采光塔
# ===========================================================================
def build_crossing(M):
    cx, cy = 0.0, 0.5 * (Y_X0 + Y_X1)
    hx, hy = N_HW, 0.5 * CROSS_D
    # 四道大券：南北两道在 y=Y_X0 / Y_X1，东西两道在 x=±hx
    for s in (1, -1):
        yy = Y_X0 if s > 0 else Y_X1
        arch_band("ci_xa_y%d" % s, (0.0, yy, 0.0), (1, 0, 0), (0, 0, 1), (0, -s, 0),
                  -hx, hx, Z_TR_SPRING, Z_TR_APEX - Z_TR_SPRING, 0.72, -0.42, 0.18,
                  M["stone_voussoir"], 18)
        arch_band("ci_xa_x%d" % s, (s * hx, cy, 0.0), (0, -1, 0), (0, 0, 1), (s, 0, 0),
                  -hy, hy, Z_TR_SPRING, Z_TR_APEX - Z_TR_SPRING, 0.72, -0.42, 0.18,
                  M["stone_voussoir"], 14)
    # 券上过梁墙：顶边必须跟着相邻中厅拱顶的横剖面走（原来是一根 z=30 的水平线，
    # 而券背在拱冠处已到 Z_TR_APEX+0.75=30.75，多边形自交，券背上方全是漏天的缝）。
    for yy in (Y_X0, Y_X1):
        s = 1 if yy == Y_X0 else -1
        O = (0.0, yy, 0.0)
        pts = [(x, arch_z(x, -hx, hx, Z_TR_SPRING, Z_TR_APEX - Z_TR_SPRING + 0.75))
               for x in [-hx + 2 * hx * i / 20 for i in range(21)]]
        pts += [(x, Z_VAULT + NAVE_HT * pf(x / hx, NAVE_HT / hx) + 1.0)
                for x in [hx - 2 * hx * i / 20 for i in range(21)]]
        prism2d("ci_xsp%d" % int(yy), O, (1, 0, 0), (0, 0, 1), (0, -s, 0),
                0.0, WALL_T, pts, M["stone"])
    # 穹棱（方 → 圆的斜角过渡）
    _crossing_spandrel(M, cx, cy, hx, hy)
    # 采光塔鼓座
    _lantern(M, cx, cy)


def _crossing_spandrel(M, cx, cy, hx, hy, nseg=36, nring=5):
    """交叉部顶：从四道大券的券腹过渡到采光塔圆口的曲面。"""
    ztop = Z_LANT_PLAT
    verts = []
    for i in range(nseg + 1):
        th = TAU * i / nseg
        dx, dy = math.cos(th), math.sin(th)
        tx = hx / abs(dx) if abs(dx) > 1e-6 else 1e9
        ty = hy / abs(dy) if abs(dy) > 1e-6 else 1e9
        t = min(tx, ty)
        px, py = dx * t, dy * t
        if abs(dx) * t > hx - 1e-4:
            ze = Z_TR_SPRING + (Z_TR_APEX - Z_TR_SPRING) * pf(py / hy,
                                                              (Z_TR_APEX - Z_TR_SPRING) / hy)
        else:
            ze = Z_TR_SPRING + (Z_TR_APEX - Z_TR_SPRING) * pf(px / hx,
                                                              (Z_TR_APEX - Z_TR_SPRING) / hx)
        for j in range(nring + 1):
            u = j / nring
            r = 1.0 - (1.0 - Z_LANT_R / max(1e-6, math.hypot(px, py))) * u
            z = ze + (ztop - ze) * (u ** 1.7)
            verts.append((cx + px * r, cy + py * r, z))
    faces = []
    W = nring + 1
    for i in range(nseg):
        for j in range(nring):
            a = i * W + j
            b = (i + 1) * W + j
            faces.append((a, a + 1, b + 1, b))
    _polyv("ci_xsph", verts, faces, M["vault_web"], True)


def _lantern(M, cx, cy):
    r0, r1 = Z_LANT_R, Z_LANT_R + 0.35
    z0, z1 = Z_LANT_PLAT, Z_LANT_TOP
    # 下环
    _lathe("ci_lt0", [(r0, z0), (r1, z0), (r1, z0 + 1.55), (r0, z0 + 1.55)],
           M["stone_warm"], 24, Ts(cx, cy, 0.0), False, False)
    _lathe("ci_lt0b", [(r0 - 0.14, z0), (r1 + 0.10, z0), (r1 + 0.10, z0 + 0.18),
                       (r0 - 0.14, z0 + 0.18)], M["stone_trim"], 24, Ts(cx, cy, 0.0),
           False, False)
    # 8 根窗间柱 + 8 扇窗
    zw0, zw1 = z0 + 1.55, z1 - 1.35
    for i in range(8):
        a = TAU * i / 8
        mx, my = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
        _box("ci_lp%d" % i, Ts(mx + 0.15 * math.cos(a), my + 0.15 * math.sin(a),
                              0.5 * (zw0 + zw1)),
             (0.62, 0.62, zw1 - zw0), M["stone_warm"], bev=0.02)
        _box("ci_lc%d" % i, Ts(mx + 0.15 * math.cos(a), my + 0.15 * math.sin(a), zw0),
             (0.80, 0.80, 0.16), M["stone_trim"], bev=0.02)
        # 窗
        a2 = a + TAU / 16
        gx, gy = cx + (r0 + 0.10) * math.cos(a2), cy + (r0 + 0.10) * math.sin(a2)
        _box("ci_lg%d" % i, Ts(gx, gy, 0.5 * (zw0 + zw1)),
             (1.30, 0.10, zw1 - zw0 - 0.10), M["glass_gold"], bev=0.0)
        # 中梃
        _box("ci_lm%d" % i, Ts(gx, gy, 0.5 * (zw0 + zw1)),
             (0.10, 0.18, zw1 - zw0 - 0.10), M["stone_trim"])
    # 上环
    _lathe("ci_lt1", [(r0, z1 - 1.35), (r1, z1 - 1.35), (r1, z1), (r0, z1)],
           M["stone_warm"], 24, Ts(cx, cy, 0.0), False, False)
    _lathe("ci_lt1b", [(r0 - 0.15, z1 - 0.20), (r1 + 0.16, z1 - 0.20), (r1 + 0.16, z1),
                       (r0 - 0.15, z1)], M["stone_trim"], 24, Ts(cx, cy, 0.0), False, False)
    # 穹顶
    prof = [(r0 + 0.02, z1), (r1, z1), (r1 * 0.96, z1 + 0.25), (r1 * 0.80, z1 + 0.72),
            (r1 * 0.52, z1 + 1.14), (r1 * 0.24, z1 + 1.36), (0.0, Z_LANT_DOME)]
    _lathe("ci_ld", prof, M["stone_warm"], 24, Ts(cx, cy, 0.0))
    _lathe("ci_ld2", [p for p in prof][::-1] + [(r0 * 0.5, Z_LANT_DOME - 0.04)],
           M["stone_trim"], 24, Ts(cx, cy, 0.0), False, False)
    # 顶部采光眼
    _lathe("ci_lo", [(0.0, Z_LANT_DOME - 0.30), (0.55, Z_LANT_DOME - 0.30),
                     (0.55, Z_LANT_DOME), (0.0, Z_LANT_DOME)], M["glass_blue"], 16,
           Ts(cx, cy, 0.0))
    # 8 条穹顶肋
    for i in range(8):
        a = TAU * i / 8 + TAU / 16
        pts = [(cx + (r1 * (1.0 - u * 0.92)) * math.cos(a),
                cy + (r1 * (1.0 - u * 0.92)) * math.sin(a),
                z1 + 1.40 * (u ** 0.9)) for u in
               [k / 7 for k in range(8)]]
        sweep("ci_lr%d" % i, pts, _ribprof(0.20, 0.20), M["rib_stone"])
    # 垂饰
    _sph("ci_lpnd", Ts(cx, cy, Z_LANT_DOME - 0.10), 0.30, M["gold"], 14, 8, 1.5)


# ===========================================================================
# 10. 半圆室（唱诗席后殿）
# ===========================================================================
def build_apse(M):
    pts = _apse_poly(OFF)
    for i in range(5):
        p0 = Vector((pts[i][0], pts[i][1], 0.0))
        p1 = Vector((pts[(i + 1) % 6][0], pts[(i + 1) % 6][1], 0.0))
        U = (p1 - p0)
        L = U.length
        U.normalize()
        V = Vector((0, 0, 1))
        # 半圆室多边形是顺时针绕向（从 -X 绕过 +Y 到 +X），U×V 指向圆心，
        # 取反才得到指向室外的法线（墙厚、窗、线脚全部依赖这个约定）。
        N = -U.cross(V)
        O = tuple(p0)
        tag = "ci_ap%d" % i
        m = 0.87
        ow = (L - 2 * m - 0.50) * 0.5
        ops = []
        for k in range(2):
            oa = m + k * (ow + 0.50)
            ops.append((oa, oa + ow, 14.0, 23.60, 1.70))
            window_fill(tag + "_w%d" % k, O, U, V, N, oa, oa + ow, 14.0, 23.60, 1.70,
                        M["glass_blue"] if k == 0 else M["glass_rose"],
                        M["stone_trim"], tracery=1, transom=18.20, sill=True)
        wall_zone(tag, O, U, V, N, 0.0, WALL_T, 0.0, L, M["stone"], ops,
                  zb=0.0, zt=Z_APSE_SPRING, na=10)
        # 下部盲连拱
        for k in range(4):
            aa0 = 0.30 + k * (L - 0.60) / 4.0
            aa1 = aa0 + (L - 0.60) / 4.0 - 0.22
            arch_band(tag + "_ba%d" % k, O, U, V, N, aa0, aa1, 1.60, 3.40, 0.22,
                      -0.16, 0.02, M["stone_warm"], 10)
            for aa in (aa0, aa1):
                _lathe(tag + "_bc%d_%d" % (k, int(aa * 10)),
                       [(0.0, 0.0), (0.10, 0.0), (0.10, 5.10), (0.0, 5.10)],
                       M["stone_trim"], 8,
                       Ts(*(Vector(O) + U * aa + Vector(N) * (-0.10))), False, True)
        course(tag + "_sc", O, U, V, N, 0.0, L, 8.90, 0.18, out=0.14, mat=M["stone_trim"])
        course(tag + "_sc2", O, U, V, N, 0.0, L, 11.70, 0.22, out=0.16, mat=M["stone_trim"])
        # 勒脚
        prism2d(tag + "_pl", O, U, V, N, -0.14, 0.004,
                [(0.0, 0.0), (L, 0.0), (L, 0.84), (0.0, 0.84)], M["stone_dark"])
    # 半穹顶
    _apse_dome(M)
    # 半圆室拱（y = Y_APSE 处）
    O = (0.0, Y_APSE, 0.0)
    arch_band("ci_aparch", O, (1, 0, 0), (0, 0, 1), (0, -1, 0),
              -N_HW, N_HW, Z_X_ARCH_SPRING, Z_X_ARCH_APEX - Z_X_ARCH_SPRING,
              0.78, -0.45, 0.20, M["stone_voussoir"], 18)
    pts = [(x, arch_z(x, -N_HW, N_HW, Z_X_ARCH_SPRING, Z_X_ARCH_APEX - Z_X_ARCH_SPRING + 0.80))
           for x in [-N_HW + 2 * N_HW * i / 16 for i in range(17)]]
    # 券背以上、半穹顶在 y=Y_APSE 处的剖切线以下是弦月形墙面。原来只补到
    # Z_APSE_SPRING(30.0)，穹顶在该平面的拱冠却在 Z_APSE_CROWN(36.2)，
    # 于是留下一个直通天空的半圆洞（ci_entry/ci_mid 里那片蓝色即由此而来）。
    _rr = APSE_R - OFF
    zs, zc = Z_APSE_SPRING, Z_APSE_CROWN
    pts += [(x, zs + (zc - zs) * (max(0.0, 1.0 - (x / _rr) ** 2) ** 0.62))
            for x in [_rr - 2.0 * _rr * i / 20 for i in range(21)]]
    prism2d("ci_apsp", O, (1, 0, 0), (0, 0, 1), (0, -1, 0), 0.0, WALL_T, pts, M["stone"])
    # 侧廊尽端封墙
    for s in (1, -1):
        a0 = s * (AISLE_IN - OFF)
        a1 = s * (N_HW + OFF * 0)
        if a0 > a1:
            a0, a1 = a1, a0
        half = 0.5 * (AISLE_IN - N_HW)

        def top(a, s=s, half=half):
            u = (a - s * (N_HW + AISLE_IN) * 0.5) / half
            # 侧廊尽端墙要顶到侧廊拱顶在 y=Y_APSE 处的横剖面（rise = Z_AIS_TR），
            # 原来误用了 Z_AIS_WR(1.0)，墙顶比拱顶低 1.6 m，
            # 于是每个侧廊尽端上方都有一条露天缝（ci_choir 两侧的品红）
            return Z_AIS_SPRING + Z_AIS_TR * pf(u, Z_AIS_TR / half)

        wall_band("ci_aend%d" % s, (0, Y_APSE, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0),
                  0.0, WALL_T, a0, a1, M["stone"], zb=0.0, top=top,
                  zt=Z_AIS_SPRING, na=8)


def _apse_dome(M, nseg=30, nring=6):
    cen = Vector((0.0, Y_APSE, 0.0))
    r_face = (APSE_R - OFF) * math.cos(R(18))
    zs, zc = Z_APSE_SPRING, Z_APSE_CROWN
    # 半圆室多边形是 _apse_poly 的 (r·sin a, Y+r·cos a) 参数化，即标准
    # 极角 0°..180° 覆盖 y > Y_APSE 的那一半。此处曾经用 -90°..90°，
    # 整个穹顶被转到东侧偏南（甚至伸进中厅）的半平面，半圆室西半边直接露天。
    verts = []
    for i in range(nseg + 1):
        th = R(180.0 * i / nseg)
        # 最近的面法线（18, 54, 90, 126, 162 度）
        best = 90.0
        for nf in (18.0, 54.0, 90.0, 126.0, 162.0):
            if abs(math.degrees(th) - nf) < abs(math.degrees(th) - best):
                best = nf
        d = R(best)
        rr = r_face / max(0.35, math.cos(th - d))
        for j in range(nring + 1):
            u = j / nring
            r = rr * u
            verts.append((cen.x + r * math.cos(th), cen.y + r * math.sin(th),
                          zs + (zc - zs) * ((1.0 - u * u) ** 0.62)))
    faces = []
    W = nring + 1
    for i in range(nseg):
        for j in range(nring):
            a = i * W + j
            b = (i + 1) * W + j
            faces.append((a, a + 1, b + 1, b))
    _polyv("ci_apdome", verts, faces, M["vault_web"], True)
    # 11 条肋
    for i in range(11):
        th = R(18.0 * i)
        best = 90.0
        for nf in (18.0, 54.0, 90.0, 126.0, 162.0):
            if abs(math.degrees(th) - nf) < abs(math.degrees(th) - best):
                best = nf
        rr = r_face / max(0.35, math.cos(th - R(best)))
        pts = []
        for j in range(15):
            u = 0.05 + 0.95 * j / 14
            pts.append((cen.x + rr * u * math.cos(th), cen.y + rr * u * math.sin(th),
                        zs + (zc - zs) * ((1.0 - u * u) ** 0.62)))
        sweep("ci_apr%d" % i, pts, _ribprof(0.26, 0.30), M["rib_stone"])
    boss("ci_apboss", cen.x, cen.y, zc, 0.44, M["rib_stone"], M["gold"])


# ===========================================================================
# 11. 横厅
# ===========================================================================
def build_transept(M):
    for s in (1, -1):
        # --- 端墙 -----------------------------------------------------------
        O = (s * (TR_X - OFF), 0.0, 0.0)
        U = (0.0, s, 0.0)
        V = (0.0, 0.0, 1.0)
        N = (s, 0.0, 0.0)
        a0, a1 = s * Y_X0, s * Y_X1
        if a0 > a1:
            a0, a1 = a1, a0
        half = 0.5 * CROSS_D

        def top(a, s=s, half=half):
            y = s * a
            return Z_TR_SPRING + Z_TR_HR * pf((y - 0.5 * (Y_X0 + Y_X1)) / half,
                                              Z_TR_HR / half)

        m = 1.10
        ops = [(a0 + m, a1 - m, 9.00, 20.50, 2.10)]
        wall_zone("ci_te%d" % s, O, U, V, N, 0.0, WALL_T, a0, a1, M["stone"], ops,
                  zb=0.0, top=top, zt=Z_TR_SPRING, na=10)
        window_fill("ci_tew%d" % s, O, U, V, N, a0 + m, a1 - m, 9.00, 20.50, 2.10,
                    M["glass_rose"], M["stone_trim"], tracery=3,
                    transom=15.4, sill=False)
        prism2d("ci_tepl%d" % s, O, U, V, N, -0.16, 0.004,
                [(a0, 0.0), (a1, 0.0), (a1, 1.10), (a0, 1.10)], M["stone_dark"])
        course("ci_tes%d" % s, O, U, V, N, a0, a1, 7.60, 0.20, out=0.16,
               mat=M["stone_trim"])
        # --- 侧墙（y = Y_X0 / Y_X1）----------------------------------------
        for yy, sg in ((Y_X0, 1), (Y_X1, -1)):
            if sg > 0:      # y=1，房间在 y>1 → n=-y，u=+x
                Us = (1.0, 0.0, 0.0)
                Nn = (0.0, -1.0, 0.0)
                xo = s * N_HW if s > 0 else -TR_X
            else:           # y=14，房间在 y<14 → n=+y，u=-x
                Us = (-1.0, 0.0, 0.0)
                Nn = (0.0, 1.0, 0.0)
                xo = TR_X if s > 0 else -N_HW
            Os = (xo, yy, 0.0)
            aa0, aa1 = 0.0, TR_X - N_HW
            tag = "ci_ts%d_%d_%d" % (sg, int(yy), s)
            for k in range(2):
                b0 = k * 8.0
                b1 = b0 + 8.0
                bh = 0.5 * 8.0

                def top2(a, b0=b0, bh=bh):
                    return Z_TR_SPRING + Z_TR_HT * pf((a - b0 - bh) / bh, Z_TR_HT / bh)

                wall_band(tag + "_%d" % k, Os, Us, V, Nn, 0.0, WALL_T, b0, b1,
                          M["stone"], zb=0.0, top=top2, zt=Z_TR_SPRING, na=8)
                if k == 1:
                    ops2 = [(12.0, 15.6, 16.2, 20.2, 1.55),
                            (13.2, 14.4, 16.2, 20.2, 1.55)]
                    wall_zone(tag + "_w%d" % k, Os, Us, V, Nn, 0.0, WALL_T, 11.0, 16.6,
                              M["stone"], [(12.4, 15.2, 16.2, 20.2, 1.55)],
                              zb=0.0, zt=Z_TR_SPRING, top=top2, na=8)
                    window_fill(tag + "_wg%d" % k, Os, Us, V, Nn, 12.4, 15.2, 16.2,
                                20.2, 1.55, M["glass_green"], M["stone_trim"],
                                tracery=1, sill=False)
            # 盲连拱（下部）
            for k in range(6):
                aa0 = 1.0 + k * 2.55
                arch_band(tag + "_ba%d" % k, Os, Us, V, Nn, aa0, aa0 + 1.85, 1.20,
                          3.20, 0.20, -0.14, 0.02, M["stone_warm"], 8)
            course(tag + "_sc", Os, Us, V, Nn, 0.0, TR_X - N_HW, 8.40, 0.18, out=0.12,
                   mat=M["stone_trim"])
            prism2d(tag + "_pl", Os, Us, V, Nn, -0.14, 0.004,
                    [(0.0, 0.0), (TR_X - N_HW, 0.0), (TR_X - N_HW, 1.00), (0.0, 1.00)],
                    M["stone_dark"])


# ===========================================================================
# 12. 骨架装配：束柱 + 连拱廊
# ===========================================================================
def build_structure(M):
    # --- 束柱 --------------------------------------------------------------
    ys = [Y_W + BAY * i for i in range(NBAY + 1)]
    ys += [Y_X1 + CH_BAY * i for i in range(1, NCH + 1)]
    for sx in (1, -1):
        for k, y in enumerate(ys):
            big = abs(y - Y_X0) < 1e-3 or abs(y - Y_X1) < 1e-3 or abs(y - Y_APSE) < 1e-3
            ztop = Z_TR_SPRING if big else Z_ARC_SPRING
            pier("ci_p%d_%d" % (sx, k), sx * N_HW, y, z1=Z_ARC_SPRING, big=False)
            if big:
                # 交叉部/后殿大柱：继续上升到 24 m 的大券起拱
                _box("ci_pb%d_%d" % (sx, k), Ts(sx * N_HW, y, 0.5 * (Z_ARC_SPRING + Z_TR_SPRING)),
                     (1.86, 2.30, Z_TR_SPRING - Z_ARC_SPRING), M["stone_warm"], bev=0.03)
                _box("ci_pbc%d_%d" % (sx, k), Ts(sx * N_HW, y, Z_TR_SPRING - 0.18),
                     (2.20, 2.60, 0.26), M["stone_trim"], bev=0.03)
                for zz in (13.0, 17.5, 21.5):
                    _box("ci_pbr%d_%d_%d" % (sx, k, int(zz)),
                         Ts(sx * N_HW, y, zz), (2.00, 2.44, 0.16),
                         M["stone_trim"], bev=0.02)
                # 附柱
                for a in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
                    ox, oy = 0.98 * math.cos(a), 1.18 * math.sin(a)
                    _cyl("ci_pbs%d_%d_%d" % (sx, k, int(a * 10)),
                         Ts(sx * N_HW + ox, y + oy, 0.5 * (Z_ARC_SPRING + Z_TR_SPRING)),
                         0.16, Z_TR_SPRING - Z_ARC_SPRING, M["stone_warm"], 8)
    # --- 连拱廊 ------------------------------------------------------------
    for sx in (1, -1):
        O = (sx * (N_HW - OFF), 0.0, 0.0)
        U = (0.0, sx, 0.0)
        V = (0.0, 0.0, 1.0)
        N = (sx, 0.0, 0.0)
        for i in range(NBAY):
            y0, y1 = Y_W + BAY * i, Y_W + BAY * (i + 1)
            a0, a1 = (sx * y0, sx * y1)
            if a0 > a1:
                a0, a1 = a1, a0
            arch_band("ci_ar%d_%d" % (sx, i), O, U, V, N, a0 + 0.66, a1 - 0.66,
                      Z_ARC_SPRING, Z_ARC_APEX - Z_ARC_SPRING, 0.44, -0.34, 0.14,
                      M["stone_voussoir"], 14)
            # 券上的滴水线脚
            arch_band("ci_arh%d_%d" % (sx, i), O, U, V, N, a0 + 0.50, a1 - 0.50,
                      Z_ARC_SPRING, Z_ARC_APEX - Z_ARC_SPRING + 0.56, 0.10, -0.44, -0.30,
                      M["stone_trim"], 14)
        for i in range(NCH):
            y0, y1 = Y_X1 + CH_BAY * i, Y_X1 + CH_BAY * (i + 1)
            a0, a1 = (sx * y0, sx * y1)
            if a0 > a1:
                a0, a1 = a1, a0
            arch_band("ci_ac%d_%d" % (sx, i), O, U, V, N, a0 + 0.78, a1 - 0.78,
                      Z_ARC_SPRING, Z_ARC_APEX - Z_ARC_SPRING, 0.46, -0.36, 0.14,
                      M["stone_voussoir"], 14)
    # --- 侧廊拱顶起拱处的挑檐 ---------------------------------------------
    for sx in (1, -1):
        course("ci_asing%d" % sx, (sx * (N_HW - OFF), 0, 0), (0, 1, 0), (0, 0, 1),
               (sx, 0, 0), Y_W, Y_APSE, Z_AIS_SPRING - 0.18, 0.18, out=0.12,
               mat=M["stone_trim"])


# ===========================================================================
# 13. 家具与陈设
# ===========================================================================
def _trefoil(name, x, y, z, s, mat, front=True):
    """三叶饰：3 个圆盘 + 底部小方块（贴在端板顶部）。"""
    for k, ang in enumerate((90, 210, 330)):
        a = R(ang)
        _cyl(name + "_t%d" % k, Ts(x + s * 0.55 * math.cos(a) * (1 if front else 1),
                                   y + 0.0, z + s * 0.55 * math.sin(a)),
             s * 0.42, 0.03, mat, seg=10)
    _box(name + "_tb", Ts(x, y, z - s * 0.55), (s * 0.75, 0.03, s * 0.35), mat)


def _pew(M, sx, y, tag):
    x0, x1 = sx * PEW_X0, sx * PEW_X1
    cx = 0.5 * (x0 + x1)
    w = abs(x1 - x0)
    _box(tag + "_se", Ts(cx, y, 0.45), (w, 0.42, 0.065), M["wood"], bev=0.012)
    _box(tag + "_ba", Ts(cx, y, 0.23), (w - 0.14, 0.34, 0.075), M["wood_dark"])
    for xx in (x0 + 0.10, x1 - 0.10):
        _box(tag + "_lg", Ts(xx, y, 0.16), (0.08, 0.34, 0.28), M["wood_dark"])
    _box(tag + "_bk", Ts(cx, y + 0.27, 0.92), (w, 0.07, 0.62), M["wood"], bev=0.012)
    _box(tag + "_bt", Ts(cx, y + 0.27, 1.24), (w, 0.11, 0.06), M["wood_light"], bev=0.01)
    _box(tag + "_sh", Ts(cx, y + 0.44, 1.10), (w - 0.16, 0.18, 0.055), M["wood_dark"])
    _box(tag + "_kn", Ts(cx, y - 0.60, 0.075), (w - 0.10, 0.26, 0.15), M["wood_dark"], bev=0.012)
    for xe in (x0, x1):
        _box(tag + "_en", Ts(xe, y + 0.03, 0.52), (0.075, 0.56, 1.02), M["wood_dark"], bev=0.012)
        _box(tag + "_en2", Ts(xe, y + 0.03, 1.06), (0.10, 0.62, 0.10), M["wood_light"], bev=0.012)
        _trefoil(tag + "_tr", xe, y + 0.03, 1.20, 0.16, M["wood_light"])


def _pews(M):
    y = PEW_Y0
    i = 0
    while y < PEW_Y1:
        for sx in (1, -1):
            _pew(M, sx, y, "ci_pw%d_%d" % (sx, i))
        y += 1.46
        i += 1


def _stall(M, sx, y, tag):
    """唱诗席座椅：座 + 高靠背 + 华盖 + 雕花扶手 + 前几。"""
    xin = sx * 2.70          # 靠中央一侧
    xout = sx * 4.35
    cx = 0.5 * (xin + xout)
    _box(tag + "_se", Ts(cx, y, 0.46), (1.55, 0.56, 0.07), M["wood"], bev=0.012)
    _box(tag + "_fr", Ts(cx, y - 0.30, 0.22), (1.60, 0.09, 0.44), M["wood_dark"], bev=0.01)
    _box(tag + "_bk", Ts(xout, y, 1.02), (0.10, 0.72, 1.10), M["wood"], bev=0.012)
    _box(tag + "_bt", Ts(xout, y, 1.60), (0.14, 0.80, 0.08), M["wood_light"], bev=0.012)
    # 华盖
    _box(tag + "_ca", Ts(cx + sx * 0.16, y, 2.46), (1.72, 0.80, 0.10), M["wood_dark"], bev=0.012)
    _box(tag + "_cb", Ts(xout, y, 2.10), (0.12, 0.72, 0.70), M["wood_dark"])
    _lathe(tag + "_cp", [(0.0, 0.0), (0.08, -0.02), (0.11, -0.16), (0.06, -0.27), (0.0, -0.30)],
           M["wood_light"], 10, Ts(cx + sx * 0.16, y, 2.44))
    # 扶手（雕花卷涡）
    for yy in (y - 0.22, y + 0.22):
        _box(tag + "_am", Ts(xin + sx * 0.18, yy, 0.72), (0.42, 0.07, 0.07), M["wood_light"])
        _sph(tag + "_as", Ts(xin + sx * 0.02, yy, 0.74), 0.075, M["wood_light"], 8, 6)
        _cyl(tag + "_ap", Ts(xin + sx * 0.36, yy, 0.50), 0.045, 0.46, M["wood_light"], 8)
    # 前几
    _box(tag + "_dk", Ts(xin - sx * 0.30, y, 0.92), (0.22, 0.76, 0.06), M["wood"], bev=0.01)
    _box(tag + "_dl", Ts(xin - sx * 0.40, y, 0.46), (0.06, 0.20, 0.92), M["wood_dark"])


def _choir_stalls(M):
    y0, y1 = CHOIR_STALL_Y
    n = int((y1 - y0) / 0.86)
    for sx in (1, -1):
        for k in range(n):
            _stall(M, sx, y0 + 0.43 + k * 0.86, "ci_st%d_%d" % (sx, k))


def _rood_screen(M):
    """圣坛围屏：石基座 + 尖券格栅（透空）+ 中央门洞 + 上部横梁与十字架组。"""
    y = ROOD_Y
    z_base = 0.52          # 基座高
    z_spr = 3.30           # 券脚
    z_top = 4.72           # 格栅顶（券顶 4.55 + 券肩）
    rise = 1.25
    for sx in (1, -1):
        xa, xb = (2.10, 8.35) if sx > 0 else (-8.35, -2.10)
        w = abs(xb - xa)
        # 石基座
        _box("ci_rsb%d" % sx, Ts(0.5 * (xa + xb), y, z_base * 0.5), (w, 0.34, z_base),
             M["stone_warm"], bev=0.015)
        _box("ci_rsbc%d" % sx, Ts(0.5 * (xa + xb), y, z_base + 0.06),
             (w + 0.10, 0.46, 0.13), M["stone_trim"], bev=0.012)
        # 竖棂 + 尖券（透空格栅，可以从缝里看过去）
        n = 6
        for i in range(n + 1):
            xx = xa + (xb - xa) * i / n
            _box("ci_rsv%d_%d" % (sx, i), Ts(xx, y, 0.5 * (z_base + z_top)),
                 (0.16, 0.30, z_top - z_base), M["stone_trim"], bev=0.012)
            _box("ci_rsvp%d_%d" % (sx, i), Ts(xx, y, z_spr - 0.10),
                 (0.26, 0.36, 0.14), M["stone_trim"], bev=0.010)
            if i < n:
                aa0 = xx + 0.09
                aa1 = xa + (xb - xa) * (i + 1) / n - 0.09
                arch_band("ci_rsa%d_%d" % (sx, i), (0, y, 0), (1, 0, 0), (0, 0, 1),
                          (0, -1, 0), aa0, aa1, z_spr, rise, 0.15, -0.14, 0.14,
                          M["stone_trim"], 10)
                # 券肩填充（券背以上到格栅顶）
                pts = [(aa0, z_top), (aa1, z_top)]
                for k in range(9):
                    a = aa1 + (aa0 - aa1) * k / 8.0
                    pts.append((a, arch_z(a, aa0, aa1, z_spr, rise) + 0.07))
                prism2d("ci_rsp%d_%d" % (sx, i), (0, y, 0), (1, 0, 0), (0, 0, 1),
                        (0, -1, 0), -0.11, 0.11, pts, M["stone_warm"])
        # 顶梁
        _box("ci_rst%d" % sx, Ts(0.5 * (xa + xb), y, z_top + 0.12),
             (w + 0.34, 0.40, 0.24), M["stone_trim"], bev=0.015)
    # 中央门洞的券
    arch_band("ci_rsdoor", (0, y, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0),
              -2.10, 2.10, 3.20, 1.60, 0.32, -0.20, 0.16, M["stone_voussoir"], 14)
    for sx in (1, -1):
        _box("ci_rsdp%d" % sx, Ts(sx * 2.10, y, 1.70), (0.34, 0.50, 3.40),
             M["stone_voussoir"], bev=0.015)
    # 上部横梁 + 十字架组
    _box("ci_rhob", Ts(0, y, 5.98), (17.4, 0.52, 0.26), M["stone_trim"], bev=0.015)
    _box("ci_rhob2", Ts(0, y, 5.70), (17.0, 0.40, 0.30), M["stone_warm"], bev=0.015)
    _cross("ci_rx", 0.0, y, 6.16, 3.30, 0.30, M["gold"], 0.14)
    for sx in (1, -1):
        _figure("ci_rfig%d" % sx, sx * 1.60, y, 6.16, 2.10, M["cloth_gold"], M["gold"])


def _cross(name, x, y, z, h, w, mat, depth=0.16):
    _box(name + "_v", Ts(x, y, z + h * 0.5), (w * 0.55, depth, h), mat, bev=0.012)
    _box(name + "_h", Ts(x, y, z + h * 0.73), (w * 2.6, depth, w * 0.55), mat, bev=0.012)
    _box(name + "_pl", Ts(x, y, z + 0.05), (w * 1.6, depth * 1.8, 0.12), mat, bev=0.012)


def _figure(name, x, y, z, h, cloth, skin, face=True):
    """简化的立像：袍身（收腰，立在底座上）+ 头 + 双臂。h 是总高。"""
    K2 = h / 2.10
    prof = [(0.0, 0.0), (0.150, 0.0), (0.150, 0.030), (0.132, 0.090),
            (0.108, 0.290), (0.092, 0.520), (0.085, 0.640), (0.098, 0.780),
            (0.094, 0.860), (0.072, 0.930), (0.040, 0.975), (0.0, 0.985)]
    _lathe(name + "_ro", [(r * K2, zz * K2) for (r, zz) in prof], cloth, 12,
           Ts(x, y, z), True, True)
    _cyl(name + "_pl", Ts(x, y, z + 0.012 * K2), 0.175 * K2, 0.024 * K2, skin, 12)
    _sph(name + "_hd", Ts(x, y, z + 1.045 * K2), 0.082 * K2, skin, 12, 8)
    for s in (1, -1):
        _cyl(name + "_ar%d" % s, Ts(x + s * 0.105 * K2, y, z + 0.760 * K2),
             0.038 * K2, 0.300 * K2, cloth, 8, r2=0.030 * K2)


def _high_altar(M):
    # 高坛台阶（3 级）
    for i, z in enumerate((0.18, 0.36, 0.54)):
        yy = 26.35 + i * 0.42
        _box("ci_hst%d" % i, Ts(0, yy, z * 0.5), (16.6, 0.46, z), M["floor_light"], bev=0.012)
    # 后殿平台
    pts = _apse_poly(-0.02)
    prism2d("ci_hplat", (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), 0.0, 0.54,
            [(p[0], p[1] - 0.0) for p in pts], M["floor_light"])
    _floor_stones("ci_hpfl", -APSE_R, APSE_R, Y_APSE - 0.1, Y_APSE + APSE_R,
                  inside=lambda x, y: _pt_in_poly(x, y, _apse_poly(0.02)), z=0.545,
                  mats=(M["floor_light"], M["floor"], M["floor_dark"]))
    # 祭坛石台
    _box("ci_alt", Ts(0, 30.40, 1.06), (3.10, 1.32, 1.04), M["stone_warm"], bev=0.02)
    _box("ci_alt_t", Ts(0, 30.40, 1.60), (3.30, 1.50, 0.10), M["stone_trim"], bev=0.015)
    # 白色台布
    _box("ci_alt_c", Ts(0, 30.40, 1.665), (3.36, 1.56, 0.02), M["cloth_white"])
    _box("ci_alt_cf", Ts(0, 29.72, 1.20), (3.36, 0.02, 0.90), M["cloth_white"])
    # 金边与十字绣
    for dz in (0.0,):
        _box("ci_alt_g", Ts(0, 29.70, 1.60), (3.38, 0.03, 0.05), M["cloth_gold"])
        _box("ci_alt_g2", Ts(0, 29.70, 0.80), (3.38, 0.03, 0.05), M["cloth_gold"])
    _cross("ci_altx", 0.0, 29.69, 1.10, 0.62, 0.17, M["cloth_gold"], 0.02)
    # 圣体柜
    _box("ci_tab", Ts(0, 30.95, 2.06), (0.86, 0.62, 0.82), M["gold"], bev=0.02)
    _box("ci_tabd", Ts(0, 30.63, 2.06), (0.56, 0.04, 0.52), M["gold"], bev=0.01)
    _sph("ci_tabb", Ts(0, 30.60, 2.06), 0.06, M["cloth_red"], 8, 6)
    # 十字架 + 烛台
    _cross("ci_altcr", 0.0, 30.55, 1.70, 1.50, 0.19, M["gold"], 0.10)
    for sx in (1, -1):
        candlestick("ci_ac%d" % sx, sx * 1.28, 30.10, 1.70, 1.30, M["gold"], 0.9, 3)
    # 祭坛后的屏风（reredos）
    _box("ci_rr", Ts(0, 32.60, 2.70), (6.40, 0.34, 4.30), M["stone_warm"], bev=0.02)
    for k in range(3):
        _box("ci_rrn%d" % k, Ts((k - 1) * 1.95, 32.36, 2.80), (1.20, 0.16, 2.60),
             M["stone_dark"], bev=0.015)
        _figure("ci_rrf%d" % k, (k - 1) * 1.95, 32.20, 1.65, 2.10,
                (M["cloth_blue"], M["cloth_red"], M["cloth_gold"])[k], M["stone_trim"])
    _box("ci_rrc", Ts(0, 32.30, 4.95), (6.70, 0.55, 0.26), M["stone_trim"], bev=0.02)


def _lectern(M):
    x, y = 2.30, 17.40
    _box("ci_lec_b", Ts(x, y, 0.06), (0.78, 0.78, 0.12), M["wood_dark"], bev=0.015)
    _lathe("ci_lec_c", [(0.0, 0.0), (0.13, 0.0), (0.10, 0.30), (0.07, 1.06), (0.11, 1.14),
                        (0.0, 1.16)], M["wood"], 10, Ts(x, y, 0.12))
    _box("ci_lec_d", Ts(x, y, 1.28), (0.86, 0.62, 0.09), M["wood"], bev=0.012)
    _box("ci_lec_e", Ts(x, y - 0.28, 1.34), (0.86, 0.06, 0.12), M["wood_light"])
    for s in (-1, 1):
        _box("ci_lec_k", Ts(x + s * 0.30, y - 0.02, 1.36), (0.30, 0.26, 0.03), M["cloth_white"])
    _box("ci_lec_l", Ts(x, y + 0.30, 1.60), (0.06, 0.06, 0.60), M["gold"])


def _aisle_shrines(M):
    """侧廊壁龛小祭坛（3 处）+ 烛台。"""
    spots = [(1, -25.5, 0), (-1, -19.0, 1), (1, 20.0, 2), (-1, 9.0, 3)]
    for (sx, yy, k) in spots:
        x = sx * (AISLE_IN - OFF - 0.16)
        tag = "ci_sh%d" % k
        _box(tag + "_n", Ts(x - sx * 0.10, yy, 2.30), (0.34, 2.40, 2.20), M["stone_dark"],
             bev=0.015)
        _box(tag + "_f", Ts(x - sx * 0.26, yy, 1.55), (0.30, 2.70, 0.16), M["stone_trim"],
             bev=0.015)
        _box(tag + "_a", Ts(x - sx * 0.24, yy, 0.72), (0.44, 1.90, 1.06), M["stone_warm"],
             bev=0.02)
        _box(tag + "_t", Ts(x - sx * 0.24, yy, 1.30), (0.54, 2.06, 0.08), M["stone_trim"],
             bev=0.012)
        _figure(tag + "_st", x - sx * 0.20, yy, 1.34, 1.75, M["cloth_blue"], M["stone_trim"])
        for s2 in (-1, 1):
            candlestick(tag + "_c%d" % s2, x - sx * 0.24, yy + s2 * 0.72, 1.36, 0.95,
                        M["gold"], 0.75, 2)
        arch_band(tag + "_ar", (x, yy, 0), (0, 1, 0), (0, 0, 1), (sx, 0, 0),
                  -1.20, 1.20, 3.40, 1.30, 0.22, -0.26, 0.02, M["stone_trim"], 10)


def _confessional(M):
    x, y = -(AISLE_IN - OFF - 0.85), -6.30
    _box("ci_cf_b", Ts(x, y, 1.25), (1.60, 2.90, 2.50), M["wood_dark"], bev=0.02)
    _box("ci_cf_r", Ts(x, y, 2.55), (1.80, 3.10, 0.16), M["wood"], bev=0.02)
    _box("ci_cf_t", Ts(x, y, 2.72), (1.40, 2.70, 0.18), M["wood_dark"], bev=0.015)
    for s in (-1, 1):
        _box("ci_cf_d%d" % s, Ts(x + 0.82, y + s * 1.00, 1.25), (0.06, 0.86, 2.10),
             M["wood"], bev=0.012)
        _box("ci_cf_c%d" % s, Ts(x + 0.82, y + s * 1.00, 2.30), (0.10, 0.96, 0.12),
             M["wood_light"])
    # 中间格栅
    for i in range(9):
        _box("ci_cf_g%d" % i, Ts(x + 0.84, y - 0.40 + i * 0.10, 1.30), (0.04, 0.045, 0.60),
             M["iron"])
    _box("ci_cf_h", Ts(x + 0.84, y + 0.02, 1.62), (0.05, 1.10, 0.08), M["wood_light"])


def _font(M):
    x, y = -(AISLE_IN - OFF - 1.35), -37.20
    _lathe("ci_fn_b", [(0.0, 0.0), (0.62, 0.0), (0.58, 0.16), (0.36, 0.30), (0.30, 0.52),
                       (0.42, 0.62), (0.60, 0.72), (0.62, 0.74), (0.0, 0.74)],
           M["stone_warm"], 8, Ts(x, y, 0.0))
    _lathe("ci_fn_c", [(0.0, 0.0), (0.74, 0.0), (0.78, 0.10), (0.66, 0.34), (0.56, 0.36),
                       (0.0, 0.36)], M["stone_trim"], 8, Ts(x, y, 0.74))
    _lathe("ci_fn_w", [(0.0, 0.0), (0.52, 0.0), (0.52, 0.06), (0.0, 0.06)],
           M["glass"], 8, Ts(x, y, 1.02))
    # 木盖
    _lathe("ci_fn_l", [(0.0, 0.0), (0.80, 0.0), (0.62, 0.34), (0.26, 0.56), (0.0, 0.62)],
           M["wood"], 8, Ts(x, y, 1.10))
    _sph("ci_fn_k", Ts(x, y, 1.78), 0.10, M["gold"], 10, 6)
    _box("ci_fn_st", Ts(x - 0.1, y, 0.30), (0.66, 0.66, 0.60), M["stone_dark"], bev=0.02)


def _chandelier(M, x, y, ztop, tag, r=1.15):
    """铁环吊灯 + 12 支蜡烛：3 条短链收到一个小吊环，再由一根细杆挂到顶。
    以前是 3 条 25 m 长链直接吊到拱顶，在广角里会横穿整个画面。"""
    zc = 4.60
    ring = []
    for i in range(28):
        a = TAU * i / 28
        ring.append((x + r * math.cos(a), y + r * math.sin(a), zc))
    sweep(tag + "_ring", ring, [(-0.055, -0.05), (0.055, -0.05), (0.055, 0.05),
                                (-0.055, 0.05)],
          M["iron"], up=(0.0, 0.0, 1.0), closed=True, smooth=False)
    for i in range(12):
        a = TAU * i / 12
        cx, cy = x + r * math.cos(a), y + r * math.sin(a)
        _lathe(tag + "_c%d" % i, [(0.0, 0.0), (0.10, 0.0), (0.12, 0.05), (0.03, 0.08),
                                  (0.0, 0.08)], M["iron"], 6, Ts(cx, cy, zc + 0.03))
        candle(tag + "_k%d" % i, cx, cy, zc + 0.10, 0.035, 0.26)
    zh = zc + 2.10
    for i in range(3):
        a = TAU * i / 3 + 0.4
        p0 = (x + r * 0.80 * math.cos(a), y + r * 0.80 * math.sin(a), zc + 0.05)
        p1 = (x + 0.11 * math.cos(a), y + 0.11 * math.sin(a), zh - 0.10)
        sweep(tag + "_ch%d" % i, [p0, p1], [(0.030, -0.030), (0.030, 0.030),
                                            (-0.030, 0.030), (-0.030, -0.030)],
              M["iron"], caps=False)
    _lathe(tag + "_hb", [(0.0, 0.12), (0.13, 0.12), (0.16, -0.01), (0.10, -0.10),
                         (0.0, -0.12)], M["iron"], 12, Ts(x, y, zh))
    _cyl(tag + "_rod", Ts(x, y, 0.5 * (zh + ztop)), 0.032, ztop - zh, M["iron"], 8)
    _sph(tag + "_hub", Ts(x, y, zc - 0.12), 0.16, M["iron"], 10, 6)
    _lathe(tag + "_pd", [(0.0, 0.0), (0.10, -0.02), (0.14, -0.24), (0.06, -0.44), (0.0, -0.48)],
           M["gold"], 10, Ts(x, y, zc - 0.20))


def _chandeliers(M):
    # 玫瑰窗机位在 (0,-24)，所以 y<-22 一律不摆吊灯，否则链条正好横穿窗心
    for k, y in enumerate((-20.0, -11.0, -2.0)):
        _chandelier(M, 0.0, y, Z_CROWN - 0.25, "ci_chd%d" % k,
                    1.15 if k % 2 == 0 else 0.95)
    _chandelier(M, 0.0, 7.5, Z_LANT_BASE, "ci_chdc", 1.35)


def _banner(name, x, y, z, w, h, cloth, rod, along="y"):
    """旗幡：带微波纹的布面 + 上下横杆。along: 布面展开方向。"""
    nx, ny = 6, 10
    verts = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            u = i / nx
            v = j / ny
            wave = 0.055 * math.sin(u * math.pi * 2.2) * (0.3 + 0.7 * v)
            s = (u - 0.5) * w
            if along == "y":
                verts.append((x + wave, y + s, z - v * h))
            else:
                verts.append((x + s + wave, y, z - v * h))
    faces = []
    for i in range(nx):
        for j in range(ny):
            a = i * (ny + 1) + j
            b = (i + 1) * (ny + 1) + j
            faces.append((a, a + 1, b + 1, b))
            faces.append((a, b, b + 1, a + 1))
    _polyv(name + "_c", verts, faces, cloth, True)
    for zz in (z + 0.06, z - h - 0.06):
        if along == "y":
            _cyl(name + "_r%d" % int(zz * 10), Ts(x, y, zz, 0.0, 0.0, math.pi / 2),
                 0.045, w + 0.36, rod, 8, r2=0.045)
        else:
            _cyl(name + "_r%d" % int(zz * 10), Ts(x, y, zz, 0.0, math.pi / 2), 0.045,
                 w + 0.36, rod, 8, r2=0.045)
        _sph(name + "_b%d" % int(zz * 10), Ts(x, y, zz), 0.07, rod, 8, 6)


def _banners(M):
    for k, (sx, y) in enumerate(((1, -33.0), (-1, -33.0), (1, -13.0), (-1, -13.0))):
        _banner("ci_bn%d" % k, sx * (N_HW - 0.55), y, 8.20, 1.10, 3.10,
                (M["cloth_red"], M["cloth_blue"])[k % 2], M["gold"], along="y")
    for k, sx in enumerate((1, -1)):
        _banner("ci_bnc%d" % k, sx * (N_HW - 0.55), 18.0, 8.20, 1.10, 3.10,
                M["cloth_gold"], M["gold"], along="y")


def _floor_candles(M):
    for k, (x, y, n) in enumerate(((-4.30, -29.0, 12), (4.30, -29.0, 12),
                                   (-4.30, 3.6, 9), (4.30, 3.6, 9))):
        for i in range(n):
            a = TAU * i / n
            rr = 0.20 + 0.16 * (i % 3)
            cx = x + rr * math.cos(a)
            cy = y + rr * math.sin(a)
            _cyl("ci_fc%d_%d" % (k, i), Ts(cx, cy, 0.02), 0.055, 0.16, M["iron"], 6)
            candle("ci_fck%d_%d" % (k, i), cx, cy, 0.18, 0.030, 0.30)


def _thurible(M):
    """交叉部垂下的香炉：长链从采光塔垂到 6.6 m，链下挂金香炉。"""
    x, y = 0.0, 9.60
    ztop, zbody = Z_LANT_BASE - 0.25, 6.60
    n = 26
    pts = [(x, y, ztop + (zbody + 0.60 - ztop) * i / float(n)) for i in range(n + 1)]
    sweep("ci_thc", pts, [(0.022, -0.022), (0.022, 0.022), (-0.022, 0.022), (-0.022, -0.022)],
          M["iron"], caps=False)
    # 每 2 m 一个链环
    for i in range(1, 12):
        zz = ztop + (zbody + 0.60 - ztop) * i / 12.0
        _sph("ci_thl%d" % i, Ts(x, y, zz), 0.045, M["iron"], 6, 4)
    _lathe("ci_thb", [(0.0, 0.0), (0.20, 0.0), (0.24, 0.14), (0.19, 0.38), (0.10, 0.50),
                      (0.0, 0.52)], M["gold"], 14, Ts(x, y, zbody))
    _cyl("ci_tht", Ts(x, y, zbody + 0.56), 0.17, 0.10, M["gold"], 14, r2=0.10)
    _sph("ci_thf", Ts(x, y, zbody - 0.04), 0.14, M["iron"], 10, 6)
    for i in range(6):
        a = TAU * i / 6.0
        _cyl("ci_ths%d" % i, Ts(x + 0.30 * math.cos(a), y + 0.30 * math.sin(a), zbody + 0.66),
             0.018, 0.16, M["iron"], 6)
        candle("ci_thcd%d" % i, x + 0.30 * math.cos(a), y + 0.30 * math.sin(a),
               zbody + 0.74, 0.030, 0.16)


def _statues(M):
    """柱前圣像（4 尊）。"""
    for k, (sx, y) in enumerate(((1, -37.9), (-1, -37.9), (1, -2.0), (-1, 18.0))):
        x = sx * (N_HW - 0.95)
        _box("ci_stb%d" % k, Ts(x, y, 0.55), (0.86, 0.86, 1.10), M["stone_warm"], bev=0.02)
        _box("ci_stb2%d" % k, Ts(x, y, 1.14), (0.96, 0.96, 0.10), M["stone_trim"], bev=0.015)
        _figure("ci_stf%d" % k, x, y, 1.20, 2.30,
                (M["cloth_blue"], M["cloth_red"], M["cloth_gold"], M["cloth_white"])[k],
                M["stone_trim"])
        _lathe("ci_sth%d" % k, [(0.0, 0.0), (0.36, 0.0), (0.30, 0.16), (0.0, 0.30)],
               M["gold"], 12, Ts(x, y, 3.42))


def _tomb_chest(M):
    """唱诗席两侧的墓葬石棺（2 座，贴墙）。"""
    for k, (sx, y) in enumerate(((1, 22.6), (-1, 22.6))):
        x = sx * (N_HW - 0.72)
        _box("ci_tc%d" % k, Ts(x, y, 0.45), (1.16, 2.20, 0.90), M["stone_warm"], bev=0.02)
        _box("ci_tct%d" % k, Ts(x, y, 0.94), (1.30, 2.34, 0.12), M["stone_trim"], bev=0.02)
        _box("ci_tcl%d" % k, Ts(x - sx * 0.10, y, 1.02), (0.86, 1.90, 0.08), M["stone_dark"])
        _lathe("ci_tcf%d" % k, [(0.0, 0.0), (0.30, 0.0), (0.24, 0.34), (0.0, 0.46)],
               M["stone_dark"], 10, Ts(x - sx * 0.10, y, 1.04), False, True)
        _sph("ci_tch%d" % k, Ts(x - sx * 0.10, y + 0.62, 1.14), 0.17, M["stone_dark"], 10, 6)


def _furniture(M):
    _pews(M)
    _choir_stalls(M)
    _rood_screen(M)
    _high_altar(M)
    _lectern(M)
    _aisle_shrines(M)
    _confessional(M)
    _font(M)
    _chandeliers(M)
    _banners(M)
    _floor_candles(M)
    _thurible(M)
    _statues(M)
    _tomb_chest(M)


# ===========================================================================
# 14. 灯光
# ===========================================================================
def _light(name, kind, loc, look, energy, color=(1, 1, 1), size=4.0, size_y=None):
    lt = bpy.data.lights.new(name, kind)
    lt.energy = energy
    lt.color = color
    if kind == "AREA":
        lt.shape = "RECTANGLE"
        lt.size = size
        lt.size_y = size_y or size
    ob = bpy.data.objects.new(name, lt)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


def interior_lights():
    """室内补光：2 盏高侧窗区域光（一暖一冷，模拟彩窗透光）+ 玫瑰窗 +
    唱诗席 + 交叉部 + 祭坛烛光。全部离开墙面 2 m 以上，避免把墙打爆。"""
    out = []
    # ---- 西端玫瑰窗：冷蓝，退到 3.2 m 外，别把窗棂打爆 -----------------
    out.append(_light("ci_L_rose", "AREA", (0.0, Y_W + 3.2, ROSE_Z - 0.8), (0.0, 14.0, 10.0),
                      1900.0, (0.72, 0.82, 1.0), 6.4))
    # 南侧高侧窗（暖金）：斜照对侧，擦过拱顶
    out.append(_light("ci_L_clerS", "AREA", (5.6, -15.0, 25.4), (-6.4, -13.0, 2.0),
                      2600.0, (1.0, 0.80, 0.50), 10.5, 4.2))
    # 北侧高侧窗（冷蓝）
    out.append(_light("ci_L_clerN", "AREA", (-5.6, -9.0, 25.0), (6.4, -11.0, 2.0),
                      1400.0, (0.60, 0.75, 1.0), 10.5, 4.2))
    # 唱诗席
    out.append(_light("ci_L_choir", "AREA", (0.0, 20.5, 24.6), (0.0, 25.5, 2.5),
                      1600.0, (1.0, 0.80, 0.55), 8.0, 3.6))
    # 交叉部 / 采光塔
    out.append(_light("ci_L_cross", "AREA", (0.0, 7.5, 28.6), (0.0, 7.5, 2.0),
                      900.0, (0.88, 0.92, 1.0), 6.0, 6.0))
    # 拱顶泛光（从下往上擦，让肋和曲面有层次）
    out.append(_light("ci_L_up1", "AREA", (0.0, -22.0, 19.5), (0.0, -14.0, 36.0),
                      2100.0, (1.0, 0.90, 0.74), 10.0, 5.5))
    out.append(_light("ci_L_up2", "AREA", (0.0, -6.0, 19.5), (0.0, 0.0, 36.0),
                      1500.0, (1.0, 0.90, 0.74), 9.0, 5.0))
    out.append(_light("ci_L_up3", "AREA", (0.0, 18.0, 19.5), (0.0, 23.0, 35.0),
                      1200.0, (1.0, 0.88, 0.70), 8.0, 4.5))
    # 祭坛烛光
    out.append(_light("ci_L_altar", "POINT", (0.0, 30.6, 2.9), (0.0, 30.6, 0.0),
                      300.0, (1.0, 0.56, 0.24)))
    # 半圆室半穹顶泛光
    out.append(_light("ci_L_apse", "AREA", (0.0, 28.6, 20.0), (0.0, 31.5, 35.0),
                      1100.0, (1.0, 0.86, 0.66), 7.0, 4.0))
    # 横厅两臂
    for s in (-1, 1):
        out.append(_light("ci_L_tr%d" % s, "AREA",
                          (s * 13.5, 7.5, 15.0), (s * 20.0, 7.5, 6.0),
                          900.0, (0.92, 0.94, 1.0), 6.0, 4.0))
    return out


def _roof_cap(M):
    """仅预览用顶盖：室内模块本身不封顶（正式场景外壳有屋面），
    不加这层，太阳会从拱顶上方整片漏进来，画面一片惨白。

    原来这里是 4 块拼的盖板，交叉部正上方（y 3.0..12.7、|x|<6.7）留了一块空白，
    东端也只盖到 y=40.1；斜向上的长射线从这两处钻出去就看见天空（ci_cross
    那道品红光带、ci_entry 右上那 3 px 的缝）。现在改成一块盖满整个模型的大板。"""
    _box("ci_cap0", Ts(0.0, -3.0, 40.9), (78.0, 94.0, 0.6), M["stone_dark"])


# ===========================================================================
# 15. 入口
# ===========================================================================
def footprint():
    return (34.0, 90.0)


def height():
    return Z_LANT_DOME


def build(MAT=None, rng=None):
    global PARTS, RNG
    PARTS = []
    RNG = rng if rng is not None else random.Random(7)
    M = _ensure(MAT)
    build_floor(M)
    _nave_walls(M)
    _aisle_walls(M)
    _west_wall(M)
    build_rose(M)
    build_apse(M)
    build_transept(M)
    build_structure(M)
    build_vaults(M)
    build_crossing(M)
    _furniture(M)
    return PARTS


CAMS = (
    ("entry", (0.0, -35.0, 1.70), (0.0, 8.0, 12.0), 20.0),
    ("mid", (0.0, -14.0, 1.70), (0.0, 22.0, 11.0), 20.0),
    ("choir", (0.0, 4.0, 1.70), (0.0, 30.0, 9.0), 22.0),
    ("vault", (0.0, -19.60, 1.70), (0.0, -7.0, 34.0), 17.0),
    ("rose", (0.0, -24.0, 1.70), (0.0, Y_W, ROSE_Z), 20.0),
    ("cross", (0.0, -2.0, 1.70), (0.0, 7.5, 30.0), 18.0),
)


def preview(samples=128, res=(1600, 900), only=None):
    H._clear()
    try:
        K._MAT_CACHE.clear()
    except Exception:
        pass
    M = _ensure({})
    build(M, random.Random(11))
    H.diorama_floor(M["floor"], 420.0)
    H.setup_world(sun_energy=2.4, sky="#8ba6c6", fill=0.0)
    H.setup_engine(samples=samples, res=res, gpu=True)
    _roof_cap(M)
    interior_lights()
    out = []
    if not os.path.isdir(H.OUT_DIR):
        os.makedirs(H.OUT_DIR, exist_ok=True)
    for (name, loc, look, lens) in CAMS:
        if only and name not in only:
            continue
        cam = H.camera("ci_cam_" + name, loc, look, lens)
        p = os.path.join(H.OUT_DIR, "ci_%s.png" % name)
        H.render_to(p, cam)
        out.append(p)
    return out


if __name__ == "__main__":
    preview()
