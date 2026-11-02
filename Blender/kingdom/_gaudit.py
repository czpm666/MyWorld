"""Geometric audit of the gate complex.

    blender -b --factory-startup --python _gaudit.py

Builds the module exactly as the preview does and then measures, instead of
guessing:

  1. water surface inside a tower or wall          (穿模)
  2. every solid standing in the moat sealed below the waterline
  3. portcullis bar tips housed in the stone chase  (悬空, gate)
  4. lifting-chain ends sitting in a visible fitting (链条连接)
  5. parts neither supported from below nor close to any other part
     (the "hanging in nothing" class)
"""
import math
import random
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_common as H                                          # noqa: E402
import hd_gate as G                                            # noqa: E402

H._clear()
MAT = G.materials()
rng = random.Random(20261030)
OBS = [o for o in G.build(MAT, rng) if o is not None and o.type == "MESH"]
BY = {o.name: o for o in OBS}
dg = bpy.context.evaluated_depsgraph_get()
scene = bpy.context.scene


def bb(o):
    m = o.matrix_world
    pts = [m @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


BOX = {o.name: bb(o) for o in OBS}
ok = True
fails = []


def say(tag, msg, bad=False):
    global ok
    print("[audit] %-10s %s" % (tag, msg), flush=True)
    if bad:
        ok = False
        fails.append(msg)


# ---------------------------------------------------------------- 1. water ---
def in_footprint(x, y):
    """Name of the solid occupying (x, y) at water level, else None."""
    for s in (-1, 1):
        if (x - s * G.BARB_X) ** 2 + (y - 22.60) ** 2 < (G.BTOW_R + 0.42) ** 2:
            return "barbican tower %+d" % s
    for s in (-1, 1):
        if abs(x - s * G.BARB_X) <= G.BARB_T * 0.5 and 6.45 <= y <= G.BARB_FRONT:
            return "barbican wall %+d" % s
        if (x - s * G.TOW_X) ** 2 + y * y < (G.TOW_R + 0.48) ** 2:
            return "drum tower %+d" % s
    if G.MOAT_A - 0.42 <= y <= G.MOAT_A + 0.02:
        return "near revetment"
    if G.MOAT_B - 0.02 <= y <= G.MOAT_B + 0.42:
        return "far revetment"
    return None


bad_water = []
n_samp = 0
water = BY.get("gd_water")
if water is None:
    say("WATER", "gd_water MISSING", bad=True)
else:
    lo, hi = BOX["gd_water"]

    def wet(x, y):
        """True if the water prism actually covers (x, y)."""
        hit = scene.ray_cast(dg, Vector((x, y, G.WATER_Z - 2.0)),
                             Vector((0, 0, 1)), distance=1.2)
        return bool(hit[0]) and hit[4] is not None and hit[4].name == "gd_water"

    step = 0.25
    y = lo.y
    while y <= hi.y:
        x = lo.x
        while x <= hi.x:
            hit = in_footprint(x, y)
            if hit:
                n_samp += 1
                if wet(x, y):
                    bad_water.append((round(x, 2), round(y, 2), hit))
            x += step
        y += step
    me = water.evaluated_get(dg).to_mesh()
    for v in me.vertices:
        n_samp += 1
        p = water.matrix_world @ v.co
        hit = in_footprint(p.x, p.y)
        if hit:
            bad_water.append((round(p.x, 2), round(p.y, 2), hit))
    water.evaluated_get(dg).to_mesh_clear()
    uniq = sorted(set(bad_water))
    say("WATER", "%d wet surface points lie inside a solid (%d samples "
        "checked against tower and wall footprints)" % (len(bad_water), n_samp),
        bad=bool(uniq))
    for u in uniq[:8]:
        say("WATER", "   x=%.2f y=%.2f inside %s" % u)

# ------------------------------------------------- 2. sealed below water ----
names = ["bt_pl-1", "bt_pl1", "gd_rvn", "gd_rvf", "gd_rvw", "gd_bed"]
sealed = [n for n in names if n in BOX and BOX[n][0].z <= G.WATER_Z - 1.0]
miss = [n for n in names if n in BOX and BOX[n][0].z > G.WATER_Z - 1.0]
say("SEALED", "%d/%d solids in the moat reach >1 m below the waterline"
    % (len(sealed), len(sealed) + len(miss)), bad=bool(miss))
for m in miss:
    say("SEALED", "   %s bottoms at z=%.2f" % (m, BOX[m][0].z))

# ------------------------------------------------ 3. portcullis housing ------
free = []
total = 0
for pre in ("ps_pc", "bb_pc"):
    for o in OBS:
        if not o.name.startswith(pre + "_b"):
            continue
        tail = o.name[len(pre) + 2:]
        if not tail.isdigit():
            continue
        total += 1
        lo, hi = BOX[o.name]
        p = Vector(((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5, hi.z))
        hit = scene.ray_cast(dg, p + Vector((0, 0, 0.004)), Vector((0, 0, 1)),
                             distance=0.45)
        if not hit[0]:
            free.append((o.name, round(p.z, 2)))
say("PORTCUL", "%d/%d grille bar tips are covered by chase stone within 0.45 m"
    % (total - len(free), total), bad=bool(free))
for f in free:
    print("[audit] PORTCUL      %s tip at z=%.2f ends in open air" % f, flush=True)

# ------------------------------------------------------ 4. chain endings -----
def centre(name):
    lo, hi = BOX[name]
    return (lo + hi) * 0.5


def verts_of(o):
    me = o.evaluated_get(dg).to_mesh()
    out = [o.matrix_world @ v.co for v in me.vertices]
    o.evaluated_get(dg).to_mesh_clear()
    return out


for s in (-1, 1):
    links = [o for o in OBS if o.name.startswith("db_ch%d_l" % s)]
    eye, ring = BY.get("db_ar%d" % s), BY.get("db_tr%d" % s)
    if not links or eye is None or ring is None:
        say("CHAIN", "side %+d: %d links, eye=%s ring=%s"
            % (s, len(links), bool(eye), bool(ring)), bad=True)
        continue
    pts = []
    for o in links:
        pts += verts_of(o)
    ce, cr = centre("db_ar%d" % s), centre("db_tr%d" % s)
    d0 = min((p - ce).length for p in pts)
    d1 = min((p - cr).length for p in pts)
    say("CHAIN", "side %+d: %d links, lower end %.3f m from the hinge eye, "
        "upper end %.3f m from the winch ring" % (s, len(links), d0, d1),
        bad=(d0 > 0.14 or d1 > 0.14))

# --------------------------------------------------- 5. floating parts -------
exempt = ("gd_", "cx_", "rd_", "bb_floor", "bb_tun", "ps_floor", "bb_gr", "bb_gf")
loose = []
for o in OBS:
    if o.name.startswith(exempt):
        continue
    lo, hi = BOX[o.name]
    if lo.z <= 0.03:
        continue
    cx, cy = (lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5
    if scene.ray_cast(dg, Vector((cx, cy, lo.z - 0.006)), Vector((0, 0, -1)),
                      distance=0.75)[0]:
        continue
    loose.append(o)

# precise: how far is a part from the nearest *other* part?
say("FLOAT", "%d parts are not resting on anything within 0.75 m below" % len(loose))
worst = []
for o in loose:
    lo, hi = BOX[o.name]
    pad = 0.60
    nb = []
    for q in OBS:
        if q is o:
            continue
        ql, qh = BOX[q.name]
        if (ql.x > hi.x + pad or qh.x < lo.x - pad
                or ql.y > hi.y + pad or qh.y < lo.y - pad
                or ql.z > hi.z + pad or qh.z < lo.z - pad):
            continue
        nb.append(q)
    if not nb:
        worst.append((o.name, 99.0))
        continue
    vs, fs = [], []
    for q in nb:
        me = q.evaluated_get(dg).to_mesh()
        base = len(vs)
        m = q.matrix_world
        vs += [m @ v.co for v in me.vertices]
        fs += [[base + i for i in p.vertices] for p in me.polygons]
        q.evaluated_get(dg).to_mesh_clear()
    try:
        tree = BVHTree.FromPolygons(vs, fs, all_triangles=False, epsilon=0.0)
    except Exception as exc:                      # noqa: BLE001
        say("FLOAT", "   BVH failed for %s: %s" % (o.name, exc), bad=True)
        continue
    mine = verts_of(o)
    stride = max(1, len(mine) // 200)
    # probe only points that are really on the part's own surface: its vertices
    # plus its polygon centres.  (Bounding-box probe points are not surface
    # points for a thin or concave part and would report a false gap.)
    probe = mine[::stride]
    me = o.evaluated_get(dg).to_mesh()
    polys = list(me.polygons)
    pstride = max(1, len(polys) // 200)
    for poly in polys[::pstride]:
        probe.append(o.matrix_world @ poly.center)
    o.evaluated_get(dg).to_mesh_clear()
    best = 99.0
    for p in probe:
        r = tree.find_nearest(p)
        if r and r[3] is not None and r[3] < best:
            best = r[3]
    if best > 0.06:
        worst.append((o.name, best))
worst.sort(key=lambda t: -t[1])
say("FLOAT", "%d parts sit more than 0.06 m from every other part"
    % len(worst), bad=bool(worst))
for n, d in worst:
    print("[audit] FLOAT      %-16s %.3f m from its nearest neighbour" % (n, d),
          flush=True)

say("RESULT", "PASS" if ok else "REVIEW")
print("[audit] parts=%d" % len(OBS), flush=True)
