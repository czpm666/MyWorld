# -*- coding: utf-8 -*-
u"""王都布局自检：统计 / 冲突检测 / 出图。

用法（PowerShell，注意先设编码）：
    $env:PYTHONIOENCODING="utf-8"
    & "E:\\GameProject\\Python313\\python.exe" "_layout_test.py"          全部
    & "E:\\GameProject\\Python313\\python.exe" "_layout_test.py" quick    只统计
"""
from __future__ import annotations

import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hd_layout as L

JSON_PATH = "E:/My World/Blender/kingdom/layout.json"
PNG_PATH = "E:/My World/Blender/renders/kingdom/layout_schematic.png"
TOL = 0.05
R_BUILD = 636.0


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def all_buildings(layout):
    u"""返回 [(source, rec)]，只含真正有占地尺寸的记录。"""
    out = [("plot", r) for r in layout["plots"]]
    for r in layout.get("landmarks", []):
        if r.get("w") and r.get("d"):
            out.append(("landmark", r))
    return out


def box_of(rec):
    w = rec.get("w", 8.0)
    d = rec.get("d", 8.0)
    pts = L.rect_pts(rec["pos"][0], rec["pos"][1], w, d, rec["rz"])
    return L.aabb_of(pts)


def closest_on_seg(p, a, b):
    ex = b[0] - a[0]
    ey = b[1] - a[1]
    l2 = ex * ex + ey * ey
    if l2 < 1e-12:
        return a[0], a[1], math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / l2
    t = max(0.0, min(1.0, t))
    qx = a[0] + ex * t
    qy = a[1] + ey * t
    return qx, qy, math.hypot(p[0] - qx, p[1] - qy)


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------
def check_overlap(layout):
    u"""任意两栋建筑 AABB 不重叠（容差 0.05 m）。返回违规列表。"""
    items = all_buildings(layout)
    boxes = []
    for src, r in items:
        boxes.append((box_of(r), src, r))
    cell = 30.0
    grid = {}
    for i, (b, _s, _r) in enumerate(boxes):
        for ci in range(int(b[0] // cell), int(b[2] // cell) + 1):
            for cj in range(int(b[1] // cell), int(b[3] // cell) + 1):
                grid.setdefault((ci, cj), []).append(i)
    bad = []
    seen = set()
    for i, (b, src, r) in enumerate(boxes):
        for ci in range(int(b[0] // cell), int(b[2] // cell) + 1):
            for cj in range(int(b[1] // cell), int(b[3] // cell) + 1):
                for j in grid.get((ci, cj), ()):
                    if j <= i:
                        continue
                    key = (i, j)
                    if key in seen:
                        continue
                    seen.add(key)
                    o, osrc, orr = boxes[j]
                    ox = min(b[2], o[2]) - max(b[0], o[0])
                    oy = min(b[3], o[3]) - max(b[1], o[1])
                    if ox > TOL and oy > TOL:
                        bad.append((i, j, src, r, osrc, orr, ox, oy))
    return bad


def check_wall(layout, radius=R_BUILD):
    u"""没有任何建筑越出 r = radius。"""
    bad = []
    for src, r in all_buildings(layout):
        pts = L.rect_pts(r["pos"][0], r["pos"][1], r.get("w", 8.0),
                         r.get("d", 8.0), r["rz"])
        rr = max(math.hypot(p[0], p[1]) for p in pts)
        if rr > radius:
            bad.append((src, r, rr))
    return bad


def check_facing(layout, own_only=False):
    u"""门面朝向与最近街道夹角 < 35°。

    距离按街道中心线的"垂足"量（垂足落在段外时允许 ±8 m），这样街尽头的
    房子不会被判成背街；夹角 = 门面法线 与 中心->垂足 方向 的夹角。
    """
    segs = []
    for s in layout["streets"]:
        pieces = s.get("segs") or []
        if not pieces and s.get("a") and s.get("b"):
            pieces = [[s["a"][0], s["a"][1], s["b"][0], s["b"][1]]]
        for x0, y0, x1, y1 in pieces:
            segs.append(((x0, y0), (x1, y1), s["kind"], s.get("name"), s["id"]))
    n = len(segs)
    bad = []
    worst = (0.0, None)
    for src, r in all_buildings(layout):
        c = (r["pos"][0], r["pos"][1])
        fx = math.cos(r["rz"])
        fy = math.sin(r["rz"])
        best = (1e18, None)
        for i in range(n):
            a, b = segs[i][0], segs[i][1]
            ex, ey = b[0] - a[0], b[1] - a[1]
            L2 = ex * ex + ey * ey
            if L2 < 1e-12:
                continue
            t = ((c[0] - a[0]) * ex + (c[1] - a[1]) * ey) / L2
            Ls = math.sqrt(L2)
            if t * Ls < -8.0 or (t - 1.0) * Ls > 8.0:
                continue                     # not on this street's stretch
            qx = a[0] + ex * t
            qy = a[1] + ey * t
            d = math.hypot(c[0] - qx, c[1] - qy)
            if own_only:
                if r.get("street") != segs[i][4]:
                    continue
            if d < best[0]:
                best = (d, (qx, qy, i))
        if best[1] is None or best[0] < 1e-6:
            continue
        qx, qy, i = best[1]
        vx, vy = qx - c[0], qy - c[1]
        vl = math.hypot(vx, vy)
        if vl < 1e-6:
            continue
        ca = max(-1.0, min(1.0, (fx * vx + fy * vy) / vl))
        ang = math.degrees(math.acos(ca))
        if ang > worst[0]:
            worst = (ang, (src, r))
        if ang >= 35.0:
            bad.append((src, r, ang, best[0], segs[i][2]))
    return bad, worst


def check_fill(layout):
    u"""地块建筑占地率 >= 55%。"""
    bad = []
    for r in layout["plots"]:
        if r.get("fill", 1.0) < L.MIN_FILL - 1e-9:
            bad.append(r)
    return bad


def check_variety(layout):
    u"""同街区同类 <= 2。"""
    per = {}
    for r in layout["plots"]:
        key = (r["block_id"], r["kind"])
        per[key] = per.get(key, 0) + 1
    bad = [(k, v) for k, v in per.items() if v > 2]
    worst = max(per.values()) if per else 0
    return bad, worst


def check_bounds_of_blocks(layout):
    u"""街区多边形是否在地块范围内，且面积合理。"""
    lo, hi = 1e18, 0.0
    for b in layout["blocks"]:
        if b["open"]:
            continue
        lo = min(lo, b["area"])
        hi = max(hi, b["area"])
    return lo, hi


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv):
    t0 = time.time()
    layout = L.generate(radius=636.0, seed=7)
    t_gen = time.time() - t0

    print(u"\n[生成] %.2f s  (radius 636 m, seed 7)" % t_gen)
    L.report(layout)

    bl = [b for b in layout["blocks"] if not b["open"] and b["area"] > 0]
    if bl:
        areas = sorted(b["area"] for b in bl)
        print(u"\n街区面积 m2: min %.0f  p25 %.0f  median %.0f  p75 %.0f  max %.0f"
              % (areas[0], areas[len(areas) // 4], areas[len(areas) // 2],
                 areas[3 * len(areas) // 4], areas[-1]))
        print(u"街区边数: %.1f 平均" % (sum(len(b["poly"]) for b in bl) / len(bl)))

    over = check_overlap(layout)
    wall = check_wall(layout)
    faces, worst = check_facing(layout)
    own, own_worst = check_facing(layout, own_only=True)
    fills = check_fill(layout)
    var, vmax = check_variety(layout)

    print(u"\n" + "=" * 74)
    print(u"[A] AABB 重叠  (容差 %.2f m) : %s  %d 对"
          % (TOL, u"通过" if not over else u"失败", len(over)))
    for i, j, s1, r1, s2, r2, ox, oy in over[:8]:
        print(u"    #%d %-14s (%.1f,%.1f)  <->  #%d %-14s (%.1f,%.1f)  重叠 %.2f x %.2f m"
              % (i, r1["kind"], r1["pos"][0], r1["pos"][1],
                 j, r2["kind"], r2["pos"][0], r2["pos"][1], ox, oy))

    print(u"[B] 越界 r < %.0f m      : %s  %d 栋"
          % (R_BUILD, u"通过" if not wall else u"失败", len(wall)))
    for src, r, rr in wall[:8]:
        print(u"    %-14s (%.1f,%.1f)  r=%.2f" %
              (r["kind"], r["pos"][0], r["pos"][1], rr))

    plot_faces = [f for f in faces if f[0] == "plot"]
    print(u"[C] 门面/最近街道 > 35°  : %s  %d 栋地块建筑   (最大 %.1f°)"
          % (u"通过" if not plot_faces else u"失败", len(plot_faces), worst[0]))
    for src, r, ang, dist, sk in faces[:10]:
        print(u"    %-14s %-12s (%.1f,%.1f)  %.1f°  最近 %.1f m (%s)"
              % (src, r["kind"], r["pos"][0], r["pos"][1], ang, dist, sk))
    lm = [(src, r, ang) for src, r, ang, _d, _k in faces if src == "landmark"]
    if lm:
        print(u"    其中地标 %d 处（按广场/轴线定向，不计入门面检查）：%s"
              % (len(lm), u", ".join("%s %.0f°" % (r["kind"], a)
                                     for _s, r, a in lm)))
    print(u"[C2] 门面/自身临街街 > 35°: %s  %d 栋   (最大 %.1f°)"
          % (u"通过" if not own else u"失败", len(own), own_worst[0]))

    print(u"[D] 地块填充率 >= 55%%    : %s  %d 个"
          % (u"通过" if not fills else u"失败", len(fills)))
    print(u"[E] 同街区同类 <= 2      : %s  最多同街区同类 %d 个, %d 处超标"
          % (u"通过" if not var else u"失败", vmax, len(var)))
    for (bid, kd), v in var[:8]:
        print(u"    block #%d  %-14s x%d" % (bid, kd, v))

    n = layout["city"]["stats"]["buildings"]
    print(u"[F] 建筑总数 1500-2500   : %s  %d 栋"
          % (u"通过" if 1500 <= n <= 2500 else u"失败", n))

    ok = (not over and not wall and not plot_faces and not fills and not var
          and 1500 <= n <= 2500)
    print(u"=" * 74)
    print(u"总判定: %s" % (u"全部通过" if ok else u"有问题，见上"))

    if len(argv) > 1 and argv[1] == "quick":
        return 0 if ok else 1

    t1 = time.time()
    L.save(layout, JSON_PATH)
    print(u"[存盘] %s  (%.0f KB, %.2f s)"
          % (JSON_PATH, os.path.getsize(JSON_PATH) / 1024.0, time.time() - t1))
    t2 = time.time()
    L.schematic(layout, PNG_PATH)
    print(u"[出图] %s  (%.0f KB, %.2f s)"
          % (PNG_PATH, os.path.getsize(PNG_PATH) / 1024.0, time.time() - t2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
