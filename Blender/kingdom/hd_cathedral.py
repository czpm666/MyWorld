"""hd_cathedral.py - the Gothic cathedral of the Asura capital.

The second hero landmark: a 90 m long, seven-bay cathedral with twin west
towers, flying buttresses, a polygonal chevet and a flèche.  Everything is
parametric; `build(MAT, rng)` regenerates the model from the constants at the
top of this file.

Local frame:  origin at the centre of the footprint, ground at z=0,
              local +Y = WEST FRONT (the twin-tower facade), -Y = apse.

Run:
    blender -b --factory-startup --python hd_cathedral.py
    blender -b --factory-startup --python hd_cathedral.py -- --quick
"""
import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy
from mathutils import Matrix, Vector

import hd_common as H
import medkit as K
from medkit import T_at as Ts, box, cyl, cone, sphere

TAU = math.tau
D2R = math.radians


# ==========================================================================
# plan constants (metres)
# ==========================================================================
NAVE_HW = 8.5                   # inner half-width of the central vessel
WALL_T = 1.6
CLER_C = NAVE_HW + WALL_T * 0.5   # 9.30  clerestory wall centreline
CLER_OUT = 10.10                  # clerestory wall outer face
AISLE_OUT = 18.10                 # aisle wall outer face
AISLE_C = AISLE_OUT - WALL_T * 0.5   # 17.30

Y_EAST = -27.0                  # straight wall ends, apse begins
Y_TOWER_E = 31.5                # aisle / flyer bay run ends at the towers
Y_FACADE = 41.90                # nave west wall centre (outer face 42.70)
Y_TOWER_W = 45.40               # tower / porch west face
Y_STEP = 45.90                  # bottom of the west steps
PORCH_FRONT = 45.30             # projecting central porch

NBAY = 9
BAY = (Y_TOWER_E - Y_EAST) / NBAY          # 6.50

APSE_N = 5                      # faces in the 180 degree chevet
APSE_RV = 10.10                 # clerestory apse: vertex radius (matches nave)
_HALF = math.pi / (2.0 * APSE_N)
APSE_RF = APSE_RV * math.cos(_HALF)                 # 9.61 flat-face radius
APSE_SPAN = 2.0 * APSE_RF * math.tan(_HALF)         # 6.24
AMB_RV = AISLE_OUT + 0.55       # 18.65 ambulatory vertex radius
AMB_RF = AMB_RV * math.cos(_HALF)                   # 17.74
AMB_SPAN = 2.0 * AMB_RF * math.tan(_HALF)           # 11.53
APSE_CY = Y_EAST

Z_FLOOR = 1.10
Z_AISLE_TOP = 15.20
Z_CLER_BASE = 20.00
Z_CLER_TOP = 30.00
Z_EAVE = 30.00
PITCH = 55.0
ROOF_HW = CLER_OUT + 1.10       # 11.20
Z_RIDGE = Z_EAVE + ROOF_HW * math.tan(D2R(PITCH))

Z_TOWER_TOP = 44.00
Z_BELFRY_TOP = 53.00
Z_SPIRE_TOP = 67.00
TW_W = 13.40                    # tower width  (x)
TW_D = 13.90                    # tower depth  (y)
TW_CX = CLER_OUT + TW_W * 0.5   # 16.80
TW_CY = Y_TOWER_E + TW_D * 0.5  # 38.45

ROSE_R = 6.0
ROSE_Z = 33.40
Z_KINGS0, Z_KINGS1 = 21.6, 27.0
Z_GALLERY0, Z_GALLERY1 = 39.6, 43.4
Z_FACADE_TOP = 43.4
Z_GABLE_TOP = 51.8

M = {}
RNG = random.Random(11)
G = []          # glass materials


# ==========================================================================
# small geometry helpers
# ==========================================================================
def Rz(deg):
    return Matrix.Rotation(D2R(deg), 4, "Z")


def WT(x, y, z, nrm):
    """Wall frame: local +Y is the outward normal, yaw `nrm` degrees from +Y."""
    return Ts(x, y, z) @ Rz(-nrm)


def arch_z(x, w, apex):
    """Height above the springing line of a two-centred pointed arch."""
    if w <= 1e-6:
        return 0.0
    R = apex * apex / w + w * 0.25
    c = R - w * 0.5
    v = R * R - (abs(x) + c) ** 2
    return math.sqrt(v) if v > 0.0 else 0.0


def arch_curve(w, apex, n=14):
    """Points along a pointed arch from the left springing to the right one."""
    pts = []
    for i in range(n + 1):
        t = i / n
        x = -w * 0.5 + w * t
        pts.append((x, arch_z(x, w, apex)))
    return pts


def arch_ring(name, T, w, apex, y, mat, n=14, thick=0.40, depth=0.55, seg=1.06):
    """Ring of voussoirs following a pointed arch, centred on local y."""
    out = []
    pts = arch_curve(w, apex, n)
    for i in range(n):
        (x0, z0), (x1, z1) = pts[i], pts[i + 1]
        dx, dz = x1 - x0, z1 - z0
        L = math.hypot(dx, dz)
        a = math.atan2(dz, dx)
        out.append(box(name + "_v%d" % i,
                       T @ Ts((x0 + x1) * 0.5, y, (z0 + z1) * 0.5, ry=-a),
                       (L * seg, depth, thick), mat, bev=0.015))
    return out


def slab_quads(name, T, quads, thick, mat):
    """Extrude a list of CCW (u,v) quads along local Y by `thick`."""
    verts, faces = [], []
    h = thick * 0.5
    for q in quads:
        b = len(verts)
        for (u, v) in q:
            verts.append((u, -h, v))
        for (u, v) in q:
            verts.append((u, h, v))
        faces += [(b, b + 1, b + 2, b + 3), (b + 7, b + 6, b + 5, b + 4),
                  (b + 4, b + 5, b + 1, b + 0), (b + 5, b + 6, b + 2, b + 1),
                  (b + 6, b + 7, b + 3, b + 2), (b + 7, b + 4, b + 0, b + 3)]
    return H.poly(name, verts, faces, mat, T)


def quad_slab(name, pts, thick, mat):
    """Slab through four world-space corners, offset along its own normal."""
    p = [Vector(v) for v in pts]
    n = (p[1] - p[0]).cross(p[3] - p[0])
    if n.length < 1e-6:
        n = (p[2] - p[0]).cross(p[1] - p[0])
    n.normalize()
    h = n * (thick * 0.5)
    lo = [tuple(x - h) for x in p]
    hi = [tuple(x + h) for x in p]
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (4, 5, 1, 0), (5, 6, 2, 1),
             (6, 7, 3, 2), (7, 4, 0, 3)]
    return H.poly(name, lo + hi, faces, mat)


def plate(name, T, quad, thick, mat):
    """A single planar quad (list of 4 local points) given thickness."""
    return slab_quads(name, T, [quad], thick, mat)


def strip_top_arch(name, T, w, apex, zs, z_top, thick, mat, n=12):
    """Wall above an arched opening: quads from the arch curve up to z_top."""
    qs = []
    for i in range(n):
        x0 = -w * 0.5 + w * i / n
        x1 = -w * 0.5 + w * (i + 1) / n
        qs.append([(x0, zs + arch_z(x0, w, apex)), (x1, zs + arch_z(x1, w, apex)),
                   (x1, z_top), (x0, z_top)])
    return slab_quads(name, T, qs, thick, mat)


def band(name, T, span, z, h, tk, mat, out=0.16):
    """Proud horizontal string course on a wall face (local +Y outward)."""
    return box(name, T @ Ts(0, tk * 0.5 + out * 0.5, z), (span, tk + out, h), mat, bev=0.015)


def quatrefoil(name, T, r, y, mat, bar=0.16):
    """Four small lobes + cross - reads as pierced tracery at 20 m."""
    out = [cyl(name + "_c", T @ Ts(0, y, 0, rx=D2R(90)), r * 0.30, bar, mat, seg=10)]
    for i in range(4):
        a = TAU * i / 4 + math.pi * 0.25
        out.append(cyl(name + "_l%d" % i,
                       T @ Ts(math.cos(a) * r * 0.52, y, math.sin(a) * r * 0.52,
                              rx=D2R(90)),
                       r * 0.34, bar, mat, seg=9))
    return out


def circle_tracery(name, T, r, y, mat, lobes=6, bar=0.16):
    """Ring + inner lobes in the arch head of a window."""
    out = [cyl(name + "_r", T @ Ts(0, y, 0, rx=D2R(90)), r * 0.34, bar, mat, seg=8)]
    for i in range(lobes):
        a = TAU * i / lobes
        out.append(cyl(name + "_l%d" % i,
                       T @ Ts(math.cos(a) * r * 0.62, y, math.sin(a) * r * 0.62,
                              rx=D2R(90)),
                       r * 0.22, bar, mat, seg=7))
    return out


def blind_lancets(name, T, span, z0, z1, n, mat, dark=0.30, gap=0.34, cheap=True, y0=0.0):
    """Row of blind (filled) lancets with arch heads carved into a wall face."""
    out = []
    bay = span / float(n)
    w = bay - gap
    bw = 0.0 if cheap else 0.01
    nn = 4 if cheap else 6
    for i in range(n):
        x = -span * 0.5 + bay * (i + 0.5)
        tag = "%s_%d" % (name, i)
        out.append(box(tag + "_r", T @ Ts(x, y0 + 0.02, (z0 + z1) * 0.5),
                       (w - 0.04, 0.06, z1 - z0 - 0.06), _void()))
        for s in (-1, 1):
            out.append(box(tag + "_j%d" % s,
                           T @ Ts(x + s * (w * 0.5 + 0.10), y0 + 0.09,
                                  (z0 + z1) * 0.5 - 0.12),
                           (0.22, 0.26, z1 - z0 - 0.24), mat, bev=bw))
        out += arch_ring(tag + "_a", T @ Ts(x, y0 + 0.11, z1 - w * 0.62), w,
                         w * 0.55, 0.0, mat, n=nn, thick=0.20, depth=0.30)
        out.append(box(tag + "_s", T @ Ts(x, y0 + 0.08, z0 + 0.06),
                       (w + 0.34, 0.32, 0.14), mat, bev=bw))
    return out


def figure(name, T, h, mat):
    """Robed standing figure: gown, shoulders, head, crown and two arms."""
    out = []
    out.append(H.lathe(name + "_bd",
                       [(h * 0.205, h * 0.02), (h * 0.190, h * 0.26),
                        (h * 0.130, h * 0.56), (h * 0.118, h * 0.63),
                        (h * 0.150, h * 0.71), (h * 0.115, h * 0.755)],
                       mat, seg=12, T=T, smooth=True))
    out.append(box(name + "_sh", T @ Ts(0, 0, h * 0.765),
                   (h * 0.305, h * 0.195, h * 0.065), mat, bev=0.014))
    out.append(sphere(name + "_hd", T @ Ts(0, 0, h * 0.845), h * 0.062, mat,
                      seg=10, ring=7))
    out.append(box(name + "_cr", T @ Ts(0, 0, h * 0.900),
                   (h * 0.125, h * 0.125, h * 0.045), mat, bev=0.010))
    for s in (-1, 1):
        out.append(box(name + "_ar%d" % s,
                       T @ Ts(s * h * 0.158, 0, h * 0.625, ry=D2R(s * 7)),
                       (h * 0.072, h * 0.088, h * 0.285), mat, bev=0.012))
    return out


def niche_row(name, T, span, z0, z1, n, st, st2, statues=True, sc=0.80, y0=0.0):
    """Row of statue niches: corbel, twin colonettes, canopy, statue."""
    out = []
    bay = span / float(n)
    for i in range(n):
        x = -span * 0.5 + bay * (i + 0.5)
        tag = "%s_%d" % (name, i)
        out.append(box(tag + "_bk", T @ Ts(x, y0 + 0.04, (z0 + z1) * 0.52),
                       (bay * 0.58, 0.16, (z1 - z0) - 0.30), _void()))
        out.append(box(tag + "_co", T @ Ts(x, y0 + 0.26, z0 - 0.08),
                       (bay * 0.62, 0.70, 0.28), st2, bev=0.02))
        for s in (-1, 1):
            out.append(cyl(tag + "_c%d" % s,
                           T @ Ts(x + s * bay * 0.27, y0 + 0.26, (z0 + z1) * 0.5),
                           0.085, z1 - z0, st2, seg=8))
            out.append(box(tag + "_cp%d" % s, T @ Ts(x + s * bay * 0.27, y0 + 0.26, z1 - 0.06),
                           (0.28, 0.28, 0.18), st2, bev=0.012))
        out.append(box(tag + "_cn", T @ Ts(x, y0 + 0.24, z1 + 0.10),
                       (bay * 0.78, 0.72, 0.22), st2, bev=0.02))
        out += arch_ring(tag + "_ca", T @ Ts(x, y0 + 0.30, z1 - 0.42), bay * 0.56,
                         0.40, 0.0, st2, n=6, thick=0.17, depth=0.36)
        out.append(H.wedge(tag + "_cw", T @ Ts(x, y0 + 0.22, z1 + 0.20),
                           bay * 0.66, 0.44, 0.62, st2))
        if statues:
            out += [o for o in figure(tag + "_st",
                                        T @ Ts(x, y0 + 0.24, z0 + 0.06) @
                                        Matrix.Scale(sc, 4), 2.9, st)
                    if "_pl" not in o.name]
    return out


def corbel_row(name, T, span, z, n, mat, y0=0.0, w=0.28, d=0.46, h=0.40):
    """Corbel table hanging under a cornice; tops sit at z."""
    out = []
    for i in range(n):
        x = -span * 0.5 + span * (i + 0.5) / float(n)
        out.append(box("%s_%d" % (name, i),
                       T @ Ts(x, y0 + d * 0.5 - 0.10, z - h * 0.5),
                       (w, d, h), mat, bev=0.012))
    return out


def gargoyle(name, T, mat, s=1.0):
    """Small corbelled spout at the cornice; +Y points away from the wall."""
    out = [box(name + "_b", T @ Ts(0, 0.18 * s, 0), (0.44 * s, 0.80 * s, 0.44 * s),
               mat, bev=0.02)]
    out.append(box(name + "_c", T @ Ts(0, 0.72 * s, -0.24 * s, ry=D2R(-16)),
                   (0.32 * s, 0.95 * s, 0.30 * s), mat, bev=0.015))
    out.append(cone(name + "_h", T @ Ts(0, 1.24 * s, -0.40 * s, rx=D2R(-90)),
                    0.17 * s, 0.52 * s, mat, seg=8))
    return out


def balustrade(name, T, span, mat, h=1.15, deep=0.42):
    """Pierced parapet: bottom rail, top rail and little posts (z from T)."""
    out = [box(name + "_b", T @ Ts(0, 0, 0.10), (span, deep, 0.22), mat, bev=0.02)]
    out.append(box(name + "_t", T @ Ts(0, 0, h), (span, deep + 0.06, 0.16), mat, bev=0.02))
    n = max(2, int(span / 0.62))
    for i in range(n):
        x = -span * 0.5 + span * (i + 0.5) / n
        out.append(box(name + "_p%d" % i, T @ Ts(x, 0, h * 0.5),
                       (0.24, deep * 0.72, h * 0.72), mat))
    return out


# ==========================================================================
# wall bay: real opening, real reveal, glass, tracery, hood mould
# ==========================================================================
def wall_bay(name, T, span, z0, z1, tk, mat, win=None, rng=None,
             bands=(), hood=True, sill=True, gl_depth=1.02):
    out = []
    if win is None:
        out.append(box(name + "_w", T @ Ts(0, 0, (z0 + z1) * 0.5),
                       (span, tk, z1 - z0), mat, bev=0.02))
    else:
        w = win["w"]
        zb = win.get("zb", z0)
        zs = win.get("zs")
        apex = win.get("apex", w * 0.9)
        lights = win.get("lights", 2)
        has_glass = win.get("glass", True)
        if zb - z0 > 0.02:
            out.append(box(name + "_lo", T @ Ts(0, 0, (z0 + zb) * 0.5),
                           (span, tk, zb - z0), mat, bev=0.02))
        pw = (span - w) * 0.5
        for s in (-1, 1):
            out.append(box(name + "_p%d" % s,
                           T @ Ts(s * (w * 0.5 + pw * 0.5), 0, (zb + z1) * 0.5),
                           (pw, tk, z1 - zb), mat, bev=0.02))
        out.append(strip_top_arch(name + "_ah", T, w, apex, zs, z1, tk, mat))
        gy = -tk * 0.5 + gl_depth
        if has_glass:
            # glazing built from cells so every window gets its own colour
            # rhythm; a dark lead sheet behind stops the interior showing
            out.append(box(name + "_lead", T @ Ts(0, gy - 0.10, (zb + zs) * 0.5),
                           (w - 0.03, 0.06, zs - zb), G[0]))
            rows = win.get("rows", max(4, min(9, int((zs - zb) / 1.42))))
            cols = win.get("cols", max(3, min(7, int(w / 1.00))))
            seed = len(win) * 7 + int(w * 10) % 13
            cw = (w - 0.10) / cols
            ch = (zs - zb - 0.10) / rows
            for i in range(cols):
                for j in range(rows):
                    # blue-dominant field with scattered medallions (Chartres, not a
                    # checkerboard): hand weighted toward the blue lights G[1..3]
                    gp = (1, 2, 3, 4, 11, 2, 1, 5, 3, 13, 2, 7, 1, 4, 11, 3,
                          2, 9, 13, 5, 1, 2, 11, 3, 6, 1, 2, 12, 3, 4, 1, 2)
                    gm = G[gp[(i * 3 + j * 5 + seed) % len(gp)]]
                    out.append(box("%s_g%d_%d" % (name, i, j),
                                   T @ Ts(-w * 0.5 + 0.05 + cw * (i + 0.5), gy,
                                          zb + 0.05 + ch * (j + 0.5)),
                                   (cw - 0.04, 0.05, ch - 0.04), gm))
            qs = []
            for i in range(10):
                x0 = -w * 0.5 + w * i / 10
                x1 = -w * 0.5 + w * (i + 1) / 10
                qs.append([(x0, zs), (x1, zs), (x1, zs + arch_z(x1, w, apex)),
                           (x0, zs + arch_z(x0, w, apex))])
            out.append(slab_quads(name + "_ga", T @ Ts(0, gy, 0), qs, 0.05,
                                  rng.choice(G[1:]) if rng else G[1]))
            # tracery
            ty = gy + 0.13
            for i in range(lights - 1):
                x = (i + 1) * w / lights - w * 0.5
                out.append(box(name + "_m%d" % i, T @ Ts(x, ty, (zb + zs) * 0.5),
                               (0.16, 0.20, zs - zb), mat, bev=0.01))
            tz = zb + (zs - zb) * 0.62
            out.append(box(name + "_tr", T @ Ts(0, ty, tz), (w - 0.06, 0.20, 0.15),
                           mat, bev=0.01))
            out += circle_tracery(name + "_ct", T @ Ts(0, ty + 0.02, zs + apex * 0.42),
                                  min(w * 0.34, apex * 0.55), 0.0, mat)
        elif win.get("dark", True):
            # doorway / belfry opening: a real hole, only a shadowed backstop
            out.append(box(name + "_void", T @ Ts(0, gy, (zb + zs) * 0.5),
                           (w - 0.05, 0.06, zs - zb), _void()))
        if sill:
            out.append(box(name + "_sill", T @ Ts(0, tk * 0.5 + 0.06, zb - 0.02),
                           (w + 1.0, 0.42, 0.20), mat, bev=0.02))
        if hood:
            out += arch_ring(name + "_hood", T, w + 1.05, apex + 0.52, tk * 0.5 + 0.14,
                             mat, n=10, thick=0.26, depth=0.34)
            for s in (-1, 1):
                out.append(box(name + "_hc%d" % s,
                               T @ Ts(s * (w * 0.5 + 0.52), tk * 0.5 + 0.14, zs - 0.35),
                               (0.28, 0.34, 1.1), mat, bev=0.015))
    for (bz, bh) in bands:
        out.append(band(name + "_b%d" % int(bz * 10), T, span, bz, bh, tk, mat))
    return out


_voidm = [None]


def _void():
    if _voidm[0] is None:
        _voidm[0] = K.mat_metal("void_dark", "#0a0a0d", 0.95)
    return _voidm[0]


# ==========================================================================
# ground, plinth, steps
# ==========================================================================
def plinth():
    out = []
    st = M["stone_warm"]
    # main platform under nave + aisles + towers
    out.append(box("plinth_a", Ts(0, 8.0, 0.34), (47.4, 72.0, 0.68), st, bev=0.03))
    out.append(box("plinth_b", Ts(0, 8.0, 0.85), (45.6, 70.4, 0.34), st, bev=0.03))
    # apse platform (half round, built as a shallow 9-gon)
    poly = [(0.0, -0.02)]
    n = 9
    for i in range(n + 1):
        a = math.pi + math.pi * i / n
        poly.append((math.cos(a) * 19.6, math.sin(a) * 19.6))
    ob = H.lathe("plinth_apse", [(19.6, 0.0), (19.6, 0.68), (0.0, 0.68)], st,
                 seg=36, T=Ts(0, APSE_CY, 0.0), close_top=True, close_bottom=False)
    out.append(ob)
    # west steps
    for i in range(4):
        out.append(box("wstep_%d" % i,
                       Ts(0, Y_FACADE + 0.9 + i * 0.42, 0.14 + (3 - i) * 0.24),
                       (34.0 - i * 0.6, 0.44, 0.28 + (3 - i) * 0.10), st, bev=0.02))
    return out


# ==========================================================================
# nave: aisle wall, aisle roof, clerestory, flyers, piers, cornice
# ==========================================================================
def nave_side(side):
    """side = +1 (east/+X) or -1 (west/-X)."""
    out = []
    st, st2 = M["stone"], M["stone_warm"]
    slate = M["slate"]
    nrm = 90.0 * side
    x_aisle = AISLE_C * side
    x_cler = CLER_C * side
    x_pier = (AISLE_OUT + 2.05) * side

    for i in range(NBAY):
        if i in SKIP_BAYS:
            continue
        yc = Y_EAST + BAY * (i + 0.5)
        tag = "nb%d_%d" % (side, i)
        # ---------------- aisle wall ----------------
        T = WT(x_aisle, yc, 0, nrm)
        # blind arcade at the foot of the aisle wall
        out += blind_lancets(tag + "_abbl", T, BAY, 0.80, Z_FLOOR + 2.95, 5, st2, dark=0.16,
                             y0=WALL_T * 0.5, gap=0.20)
        out += wall_bay(tag + "_aisle", T, BAY, Z_FLOOR, Z_AISLE_TOP, WALL_T, st,
                        win=dict(w=3.35, zb=4.30, zs=10.70, apex=3.30, lights=3),
                        rng=RNG, bands=((4.05, 0.20), (13.55, 0.24)))
        # small buttress between bays
        Tb = WT(AISLE_OUT, yc + BAY * 0.5, 0, nrm)
        out.append(box(tag + "_ab", Tb @ Ts(0, 0.42, 7.4), (1.15, 0.95, 14.8),
                       st2, bev=0.02))
        out.append(box(tag + "_abc", Tb @ Ts(0, 0.46, 15.0), (1.35, 1.10, 0.34),
                       st2, bev=0.03))
        out += H.pinnacle(tag + "_abp", Tb @ Ts(0, 0.40, 15.1), 0.95, 2.6, st2)
        # ---------------- aisle lean-to roof ----------------
        x0, x1 = AISLE_OUT + 0.55, CLER_OUT + 0.05
        z0, z1 = Z_AISLE_TOP + 0.12, Z_CLER_BASE - 0.32
        out.append(_aisle_roof(tag + "_ar", side, yc, x0, x1, z0, z1, slate, BAY))
        # ---------------- clerestory ----------------
        Tc = WT(x_cler, yc, 0, nrm)
        out += wall_bay(tag + "_cler", Tc, BAY, Z_CLER_BASE - 0.35, Z_CLER_TOP, WALL_T, st,
                        win=dict(w=3.72, zb=21.55, zs=25.70, apex=4.05, lights=2),
                        rng=RNG, bands=((20.55, 0.30),))
        # little gablet over each clerestory window
        Tg = WT(CLER_OUT + 0.86, yc, 0, nrm)
        out.append(H.wedge(tag + "_gab", Tg @ Ts(0, 0, 29.9), 4.1, 0.55, 1.15, st))
        for s in (-1, 1):
            out.append(box(tag + "_gbr%d" % s,
                           Tg @ Ts(s * 1.02, 0.02, 30.35, ry=-s * D2R(31)),
                           (2.35, 0.36, 0.20), st, bev=0.012))
        # ---------------- cornice + parapet ----------------
        out.append(box(tag + "_cor", T @ Ts(0, WALL_T * 0.5 + 0.18, Z_CLER_TOP - 0.15),
                       (BAY, 0.55, 0.40), st2, bev=0.03))
        out += corbel_row(tag + "_cbl", T, BAY, Z_CLER_TOP - 0.36,
                          max(4, int(BAY / 0.55)), st2, y0=WALL_T * 0.5 + 0.10)
        out += balustrade(tag + "_bal", T @ Ts(0, WALL_T * 0.30, Z_CLER_TOP + 0.02),
                          BAY, st2, h=1.05, deep=0.34)
        # gargoyle at the bay division
        if i % 1 == 0:
            out += gargoyle(tag + "_garg", WT(CLER_OUT + 0.80, yc + BAY * 0.5, 29.5, nrm), st2)
    # ---------------- clerestory continuation west of the last bay -------------
    T = WT(x_cler, (Y_TOWER_E + Y_FACADE) * 0.5, 0, nrm)
    out += wall_bay("nbw%d" % side, T, Y_FACADE - Y_TOWER_E, Z_CLER_BASE - 0.35,
                    Z_CLER_TOP, WALL_T, st, bands=((20.55, 0.30), (24.0, 0.26)))

    # ---------------- pier + flyers ----------------
    for i in range(NBAY + 1):
        if i in SKIP_PIERS:
            continue
        y = Y_EAST + BAY * i
        tag = "np%d_%d" % (side, i)
        if y > Y_TOWER_E - 0.01:
            y = Y_TOWER_E - 0.9
        Tp = WT(x_pier, y, 0, nrm)
        # stepped pier
        out.append(box(tag + "_a", Tp @ Ts(0, 0.10, 4.2), (1.85, 2.55, 8.4), st2, bev=0.03))
        out.append(box(tag + "_b", Tp @ Ts(0, -0.05, 11.6), (1.55, 2.25, 6.4), st2, bev=0.03))
        out.append(box(tag + "_c", Tp @ Ts(0, -0.22, 16.8), (1.28, 1.95, 4.8), st2, bev=0.03))
        out.append(box(tag + "_cap", Tp @ Ts(0, -0.20, 19.55), (1.65, 2.25, 0.45),
                       st2, bev=0.03))
        # pinnacle on the pier
        out += H.pinnacle(tag + "_pin", Tp @ Ts(0, -0.18, 19.7), 1.25, 4.6, st2)
        for s in (-1, 1):
            out.append(box(tag + "_pinb%d" % s, Tp @ Ts(s * 0.62, -0.18, 20.0),
                           (0.30, 0.34, 3.2), st2))
        # upper flyer (to the clerestory) and lower one (aisle wall)
        Tf = Ts(x_pier * 1.0, y, 0) @ Rz(-nrm + 180)
        _sx = 1.0 if x_pier > 0 else -1.0
        out += flyer(tag + "_fly", (x_pier, y, 12.8),
                     (_sx * (CLER_OUT + 0.35), y, 21.3), 2.30, 0.62, st2)
        # wall-passage arch over the aisle roof
        out.append(box(tag + "_f2", Tf @ Ts(0, 1.9, Z_AISLE_TOP + 0.95),
                       (0.62, 3.0, 0.9), st2, bev=0.02))
    return out


def flyer(name, p0, p1, thick=2.2, wid=0.60, mat=None, n=9, taper=0.52):
    """Solid curved flying buttress: a thin wall whose intrados is a quarter
    arc rising from the pier to the clerestory wall."""
    mat = mat or M["stone"]
    out = []
    a, b = Vector(p0), Vector(p1)
    d = b - a
    d.z = 0.0
    if d.length < 0.1:
        return out
    lat = Vector((-d.y, d.x, 0.0)).normalized() * (wid * 0.5)
    vs, fs = [], []
    for i in range(n + 1):
        t = i / float(n)
        c = a + (b - a) * t
        zb = p0[2] + (p1[2] - p0[2]) * math.sin(t * math.pi * 0.5)
        th = thick * (1.0 - taper * t)
        zt = zb + th
        vs += [(c.x - lat.x, c.y - lat.y, zb), (c.x + lat.x, c.y + lat.y, zb),
               (c.x + lat.x, c.y + lat.y, zt), (c.x - lat.x, c.y - lat.y, zt)]
    for i in range(n):
        o, q = i * 4, (i + 1) * 4
        fs.append((o + 0, o + 1, q + 1, q + 0))
        fs.append((o + 2, o + 3, q + 3, q + 2))
        fs.append((o + 0, o + 3, q + 3, q + 0))
        fs.append((o + 1, o + 2, q + 2, q + 1))
    fs.append((0, 1, 2, 3))
    e = n * 4
    fs.append((e + 3, e + 2, e + 1, e + 0))
    out.append(H.poly(name, vs, fs, mat))
    return out


def _aisle_roof(name, side, yc, x0, x1, z0, z1, mat, length):
    """Sloping aisle roof plate between the aisle wall and the clerestory."""
    return quad_slab(name,
                     [(side * (AISLE_OUT + 0.55), yc - length * 0.5, z0),
                      (side * (AISLE_OUT + 0.55), yc + length * 0.5, z0),
                      (side * (CLER_OUT + 0.05), yc + length * 0.5, z1),
                      (side * (CLER_OUT + 0.05), yc - length * 0.5, z1)],
                     0.30, mat)


def nave_roof():
    out = []
    slate, wood = M["slate"], M["wood_dark"]
    d = Y_FACADE - Y_EAST
    yc = (Y_FACADE + Y_EAST) * 0.5
    out += H.roof("nroof", Ts(0, yc, 0), ROOF_HW * 2.0, d, Z_EAVE, PITCH, slate, wood,
                  courses=True, course_h=0.42, verge=0.0, ridge=True, gable_ends=False)
    # stone gable closing the roof against the chevet
    out.append(H.wedge("ngable", Ts(0, Y_EAST + 0.9, Z_EAVE), ROOF_HW * 2.0,
                       Z_RIDGE - Z_EAVE, 1.8, M["stone_warm"]))
    out.append(box("ngab_c", Ts(0, Y_EAST + 0.9, Z_RIDGE + 0.35),
                   (0.42, 1.5, 0.7), M["stone"], bev=0.02))
    # ---- dormers on both slopes ----
    _tn = math.tan(D2R(PITCH))
    for _s in (-1, 1):
        for _k in range(3):
            _y = Y_EAST + 10.0 + _k * (d - 21.0) / 2.0
            _xo = _s * 5.35
            _zl = Z_EAVE + (ROOF_HW - 5.35) * _tn - 1.60
            out.append(box("luc%d_%d" % (_s, _k), Ts(_xo, _y, _zl + 1.55),
                           (2.30, 2.55, 3.10), M["stone"], bev=0.03))
            out.append(box("luc%d_%dg" % (_s, _k), Ts(_s * 6.52, _y, _zl + 1.45),
                           (0.14, 1.32, 1.85), _void()))
            out.append(box("luc%d_%ds" % (_s, _k), Ts(_s * 6.44, _y, _zl - 0.18),
                           (0.36, 2.08, 0.30), M["stone"], bev=0.02))
            out.append(H.wedge("luc%d_%dw" % (_s, _k),
                               Ts(_xo, _y, _zl + 3.10) @ Rz(90),
                               2.55, 1.55, 2.34, M["stone"]))
    # ridge cresting
    for i in range(18):
        y = Y_EAST + 2.2 + i * (d - 3.0) / 17.0
        out.append(box("ncrest_%d" % i, Ts(0, y, Z_RIDGE + 0.30),
                       (0.30, 0.55, 0.55), slate, bev=0.02))
    return out


# ==========================================================================
# chevet / apse
# ==========================================================================
def _chevet(rv):
    """(cx, cy, nrm_deg, span) for the APSE_N faces of the -Y half-polygon."""
    rf = rv * math.cos(_HALF)
    span = 2.0 * rf * math.tan(_HALF)
    out = []
    for k in range(APSE_N):
        mid = math.pi + (2 * k + 1) * _HALF
        out.append((rf * math.cos(mid), APSE_CY + rf * math.sin(mid),
                    90.0 - math.degrees(mid), span))
    return out


def _chevet_verts(rv):
    out = []
    for k in range(APSE_N + 1):
        a = math.pi + 2.0 * k * _HALF
        out.append((rv * math.cos(a), APSE_CY + rv * math.sin(a)))
    return out


def apse():
    out = []
    st, st2 = M["stone_warm"], M["stone"]
    # ---- clerestory chevet ----
    for k, (cx, cy, nrm, span) in enumerate(_chevet(APSE_RV)):
        tag = "ap_c%d" % k
        T = WT(cx, cy, 0, nrm)
        out += wall_bay(tag, T, span, Z_CLER_BASE - 0.35, Z_CLER_TOP, WALL_T, st,
                        win=dict(w=3.9, zb=21.9, zs=25.20, apex=4.20, lights=3),
                        rng=RNG, bands=((20.55, 0.30),))
        out.append(box(tag + "_cor", T @ Ts(0, WALL_T * 0.5 + 0.18, Z_CLER_TOP - 0.15),
                       (span, 0.55, 0.40), st2, bev=0.03))
        out += corbel_row(tag + "_cbl", T, span, Z_CLER_TOP - 0.36,
                          max(4, int(span / 0.55)), st2, y0=WALL_T * 0.5 + 0.10)
        out += balustrade(tag + "_bal", T @ Ts(0, WALL_T * 0.30, Z_CLER_TOP + 0.02),
                          span, st2, h=1.0, deep=0.32)
        _nx, _ny = math.sin(D2R(nrm)), math.cos(D2R(nrm))
        out += gargoyle(tag + "_garg", WT(cx + _nx * 0.80, cy + _ny * 0.80, 29.4, nrm),
                        st2, s=0.9)
        out.append(H.wedge(tag + "_gab", WT(cx, cy, Z_CLER_TOP - 0.1, nrm),
                           span * 0.55, 0.45, 0.95, st))
    # ---- ambulatory wall: two windows per face ----
    for k, (cx, cy, nrm, span) in enumerate(_chevet(AMB_RV)):
        tag = "ap_a%d" % k
        T = WT(cx, cy, 0, nrm)
        for j in (-1, 1):
            out += wall_bay(tag + "_w%d" % j, T @ Ts(j * span * 0.26, 0, 0),
                            span * 0.44, Z_FLOOR, Z_AISLE_TOP, WALL_T, st,
                            win=dict(w=3.0, zb=4.30, zs=10.60, apex=3.20, lights=2),
                            rng=RNG, bands=((4.05, 0.20), (13.55, 0.24)))
        out.append(box(tag + "_mid", T @ Ts(0, 0, (Z_FLOOR + Z_AISLE_TOP) * 0.5),
                       (span - 2 * span * 0.44, WALL_T, Z_AISLE_TOP - Z_FLOOR),
                       st, bev=0.02))
        for s in (-1, 1):
            out.append(box(tag + "_e%d" % s, T @ Ts(s * (span * 0.5 + 0.35), 0,
                                                    (Z_FLOOR + Z_AISLE_TOP) * 0.5),
                           (1.05, 1.25, Z_AISLE_TOP - Z_FLOOR), st2, bev=0.03))
        out.append(box(tag + "_cor", T @ Ts(0, WALL_T * 0.5 + 0.16, Z_AISLE_TOP - 0.10),
                       (span, 0.5, 0.36), st2, bev=0.03))
        # ambulatory lean-to roof, a trapezoid from the ambulatory wall up to
        # the clerestory chevet
        nx, ny = math.sin(D2R(nrm)), math.cos(D2R(nrm))
        tx, ty = math.cos(D2R(nrm)), -math.sin(D2R(nrm))
        ho, hi = span * 0.5 + 0.55, APSE_SPAN * 0.5
        d = AMB_RF - APSE_RF
        out.append(quad_slab(tag + "_roof",
                             [(cx + tx * ho + nx * 0.25, cy + ty * ho + ny * 0.25,
                               Z_AISLE_TOP + 0.06),
                              (cx - tx * ho + nx * 0.25, cy - ty * ho + ny * 0.25,
                               Z_AISLE_TOP + 0.06),
                              (cx - tx * hi - nx * d, cy - ty * hi - ny * d,
                               Z_CLER_BASE - 0.42),
                              (cx + tx * hi - nx * d, cy + ty * hi - ny * d,
                               Z_CLER_BASE - 0.42)], 0.30, M["slate"]))
    # ---- radial piers + flyers at the polygon vertices ----
    for k, (px, py) in enumerate(_chevet_verts(AMB_RV)):
        ang = math.degrees(math.pi + 2.0 * k * _HALF)
        nrm = 90.0 - ang
        tag = "ap_p%d" % k
        Tp = WT(px, py, 0, nrm)
        out.append(box(tag + "_a", Tp @ Ts(0, 0.00, 4.2), (1.7, 2.7, 8.4), st2, bev=0.03))
        out.append(box(tag + "_b", Tp @ Ts(0, -0.15, 11.6), (1.45, 2.3, 6.4), st2, bev=0.03))
        out.append(box(tag + "_c", Tp @ Ts(0, -0.30, 17.6), (1.20, 1.95, 5.6), st2, bev=0.03))
        out.append(box(tag + "_cap", Tp @ Ts(0, -0.28, 20.55), (1.55, 2.2, 0.42), st2, bev=0.03))
        out += H.pinnacle(tag + "_pin", Tp @ Ts(0, -0.26, 20.7), 1.18, 4.2, st2)
        _dx, _dy = -px, (APSE_CY - py)
        _L = math.hypot(_dx, _dy) or 1.0
        _rr = APSE_RV + 0.45
        out += flyer(tag + "_fly", (px, py, 15.4),
                     (_dx / _L * _rr, APSE_CY + _dy / _L * _rr, 21.8),
                     1.90, 0.55, st2)
    return out


def apse_roof():
    """Half-cone hipped roof over the chevet, apex on the ridge line."""
    mat = M["slate"]
    seg = 16
    r = ROOF_HW
    Z_E, Z_R = Z_EAVE, Z_RIDGE
    out = []
    # ---- cone shell -------------------------------------------------------
    verts = [(0.0, APSE_CY, Z_R)]
    ring = []
    for i in range(seg + 1):
        a = math.pi + math.pi * i / seg
        ring.append((math.cos(a) * r, APSE_CY + math.sin(a) * r, Z_E))
    verts += ring
    faces = [(0, 1 + i, 2 + i) for i in range(seg)]
    verts.append((0.0, APSE_CY, Z_E - 0.4))
    cb = len(verts) - 1
    for i in range(seg):
        faces.append((cb, 2 + i, 1 + i))
    out.append(H.poly("ap_roof", verts, faces, mat))
    # ---- eave cornice -----------------------------------------------------
    out.append(H.lathe("ap_eave", [(r, Z_E - 0.40), (r, Z_E + 0.10),
                                   (r * 1.045, Z_E + 0.10), (r * 1.045, Z_E - 0.40)],
                       M["stone"], seg=32, T=Ts(0, APSE_CY, 0),
                       close_bottom=False, close_top=False))
    # ---- sloped tile courses: ribbons laid on the cone --------------------
    n = 11
    for i in range(n):
        t0 = i / float(n)
        t1 = (i + 1) / float(n) - 0.012
        rr0, zz0 = r * (1.0 - t0) + 0.10, Z_E + (Z_R - Z_E) * t0
        rr1, zz1 = r * (1.0 - t1) + 0.10, Z_E + (Z_R - Z_E) * t1
        vs, fs = [], []
        for k in range(seg + 1):
            a = math.pi + math.pi * k / seg
            vs.append((math.cos(a) * rr0, APSE_CY + math.sin(a) * rr0, zz0))
        for k in range(seg + 1):
            a = math.pi + math.pi * k / seg
            vs.append((math.cos(a) * rr1, APSE_CY + math.sin(a) * rr1, zz1))
        for k in range(seg):
            fs.append((k, k + 1, seg + 2 + k, seg + 1 + k))
        out.append(H.poly("ap_tc%d" % i, vs, fs, mat))
    # ---- radial rib arcs --------------------------------------------------
    for i in range(seg + 1):
        a = math.pi + math.pi * i / seg
        p0 = Vector((math.cos(a) * (r + 0.06), APSE_CY + math.sin(a) * (r + 0.06),
                     Z_E + 0.12))
        p1 = Vector((0.0, APSE_CY, Z_R + 0.05))
        d = p1 - p0
        L = d.length
        Mx = Ts((p0.x + p1.x) * 0.5, (p0.y + p1.y) * 0.5, (p0.z + p1.z) * 0.5) @ \
            d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        out.append(box("ap_rib%d" % i, Mx, (0.34, 0.46, L), M["stone"], bev=0.012))
    # ---- apex finial ------------------------------------------------------
    out.append(cyl("ap_fin", Ts(0, APSE_CY, Z_R + 1.0), 0.16, 2.0, M["stone"], seg=8))
    out.append(sphere("ap_ball", Ts(0, APSE_CY, Z_R + 2.1), 0.28, M["gold"], seg=12))
    out.append(box("ap_cr1", Ts(0, APSE_CY, Z_R + 3.0), (0.16, 0.16, 1.4), M["gold"]))
    out.append(box("ap_cr2", Ts(0, APSE_CY, Z_R + 3.2), (0.9, 0.16, 0.16), M["gold"]))
    return out


# ==========================================================================
# west facade
# ==========================================================================
def portal(name, T, w, h_s, n_orders, wstep=0.62, dstep=0.74, k=1.12, open_doors=False,
           stone=None, statues=False):
    """Receding portal: nested arch panels stepping back into the wall,
    tympanum, double doors with ironwork and jamb figures.

    T sits on the outermost order's front face with local +Y outward; the whole
    assembly retreats along -Y.  Order 0 keeps the widest opening, order n-1
    the door opening `w`.
    """
    out = []
    stone = stone or M["stone_warm"]
    wood, iron = M["wood_dark"], M["iron"]
    th = 0.74
    z_top = h_s + k * (w + 2.0 * wstep * (n_orders - 1)) + 0.75
    for i in range(n_orders):
        wi = w + 2.0 * wstep * (n_orders - 1 - i)
        yi = -th * 0.5 - i * dstep
        apex = k * wi
        tag = "%s_o%d" % (name, i)
        Tp = T @ Ts(0, yi, 0)
        hw = wi * 0.5
        jw = wstep + 0.34
        for s in (-1, 1):
            out.append(box(tag + "_j%d" % s,
                           Tp @ Ts(s * (hw + jw * 0.5), 0, z_top * 0.5),
                           (jw, th, z_top), stone, bev=0.02))
        qs = []
        for j in range(12):
            x0 = -hw + wi * j / 12
            x1 = -hw + wi * (j + 1) / 12
            qs.append([(x0, h_s + arch_z(x0, wi, apex)),
                       (x1, h_s + arch_z(x1, wi, apex)), (x1, z_top), (x0, z_top)])
        out.append(slab_quads(tag + "_ah", Tp, qs, th, stone))
        # archivolt roll on the front face of the order
        out += arch_ring(tag + "_av", Tp @ Ts(0, th * 0.5 + 0.13, 0), wi + 0.30,
                         apex + 0.14, 0.0, stone, n=16, thick=0.30, depth=0.28)
        for s in (-1, 1):
            out.append(box(tag + "_vj%d" % s,
                           Tp @ Ts(s * (hw + 0.15), th * 0.5 + 0.13, h_s * 0.5),
                           (0.30, 0.28, h_s), stone, bev=0.015))
            out.append(box(tag + "_ct%d" % s,
                           Tp @ Ts(s * (hw + 0.15), th * 0.5 + 0.13, h_s + 0.16),
                           (0.52, 0.44, 0.32), stone, bev=0.02))
    # ---- door plane at the back of the tunnel ----
    yd = -th - (n_orders - 1) * dstep - 0.12
    Td = T @ Ts(0, yd, 0)
    if not open_doors:
        out.append(box(name + "_back", Td @ Ts(0, -0.45, z_top * 0.5),
                       (w + 0.8, 0.30, z_top), _void()))
    # tympanum fills the innermost arch head
    qs = []
    for j in range(10):
        x0 = -w * 0.5 + w * j / 10.0
        x1 = -w * 0.5 + w * (j + 1) / 10.0
        qs.append([(x0, h_s), (x1, h_s), (x1, h_s + arch_z(x1, w, k * w)),
                   (x0, h_s + arch_z(x0, w, k * w))])
    out.append(slab_quads(name + "_tymp", Td, qs, 0.42, stone))
    for j in range(3):
        out.append(box(name + "_tyb%d" % j,
                       Td @ Ts(0, 0.26, h_s + 0.35 + j * 1.05),
                       (w - 0.35, 0.16, 0.16), stone, bev=0.01))
    for j in range(7):
        x = -w * 0.33 + w * 0.66 * j / 6.0
        hh = 0.9 + 0.25 * math.sin(j * 1.7)
        out.append(cyl(name + "_tyf%d" % j, Td @ Ts(x, 0.24, h_s + 0.42 + hh * 0.5),
                       0.15, hh, stone, seg=7))
        out.append(sphere(name + "_tyh%d" % j, Td @ Ts(x, 0.24, h_s + 0.42 + hh + 0.09),
                          0.115, stone, seg=7, ring=5))
    # lintel + trumeau
    out.append(box(name + "_lint", Td @ Ts(0, 0.12, h_s - 0.18),
                   (w + 0.05, 0.34, 0.36), stone, bev=0.02))
    out.append(box(name + "_trum", Td @ Ts(0, 0.02, (h_s - 0.4) * 0.5),
                   (0.55, 0.55, h_s - 0.4), stone, bev=0.02))
    # doors, two leaves with ironwork
    dw = (w * 0.5 - 0.34)
    for s in (-1, 1):
        xc = s * (dw * 0.5 + 0.16)
        if open_doors:
            Th = (Td @ Ts(xc + s * dw * 0.5, 0.10, 0) @
                  Matrix.Rotation(D2R(s * 68.0), 4, "Z") @
                  Ts(-s * dw * 0.5, 0, h_s * 0.5))
        else:
            Th = Td @ Ts(xc, 0.04, h_s * 0.5)
        out.append(box(name + "_dr%d" % s, Th, (dw, 0.14, h_s - 0.42), wood, bev=0.012))
        for j in range(3):
            out.append(box(name + "_bd%d_%d" % (s, j),
                           Th @ Ts(0, 0.09, -h_s * 0.5 + 0.55 + j * (h_s - 1.1) * 0.45),
                           (dw * 0.94, 0.08, 0.14), iron, bev=0.008))
        for j in range(4):
            out.append(box(name + "_pl%d_%d" % (s, j),
                           Th @ Ts(-dw * 0.36 + dw * 0.72 * j / 3.0, 0.08, 0),
                           (0.04, 0.06, h_s - 0.6), iron))
        out.append(box(name + "_hn%d" % s, Th @ Ts(0, 0.11, h_s * 0.05),
                       (0.5, 0.10, h_s * 0.6), iron, bev=0.008))
    out.append(cyl(name + "_knob", Td @ Ts(0.55, 0.16, h_s * 0.45), 0.08, 0.16,
                   M["gold"], seg=10))
    # steps up to the door
    for i in range(3):
        out.append(box(name + "_st%d" % i,
                       T @ Ts(0, 0.55 + i * 0.42, 1.02 - i * 0.05 + 0.05),
                       (w + 5.2 - i * 0.6, 0.44, 0.24 + (2 - i) * 0.16), stone, bev=0.02))
    if statues:
        for s in (-1, 1):
            hwo = (w + 2.0 * wstep * (n_orders - 1)) * 0.5 + wstep * 0.55
            out += [o for o in figure(name + "_js%d" % s,
                                        T @ Ts(s * hwo, 0.1, 0.02) @
                                        Matrix.Scale(0.82, 4), 3.1, stone)
                    if "_pl" not in o.name]
    return out


def west_front():
    out = []
    st, st2 = M["stone_warm"], M["stone"]
    P0 = WT(0, Y_FACADE, 0, 0)          # wall centre, local +Y outward
    W = 20.2

    # ---------------- ground storey with the portal opening ----------------
    out += wall_bay("wf_lo", P0, W, Z_FLOOR, Z_KINGS0, WALL_T, st,
                    win=dict(w=6.6, zb=Z_FLOOR, zs=Z_FLOOR + 7.6, apex=7.3,
                             glass=False, dark=False, lights=1),
                    sill=False, hood=False)

    # ---------------- kings band, rose storey, gallery ----------------
    out.append(box("wf_kings", P0 @ Ts(0, 0, (Z_KINGS0 + Z_KINGS1) * 0.5),
                   (W, WALL_T, Z_KINGS1 - Z_KINGS0), st, bev=0.02))
    for s in (-1, 1):
        out.append(box("wf_r%d" % s,
                       P0 @ Ts(s * (ROSE_R + (10.1 - ROSE_R) * 0.5), 0,
                               (Z_KINGS1 + Z_GALLERY0) * 0.5),
                       (10.1 - ROSE_R, WALL_T, Z_GALLERY0 - Z_KINGS1), st, bev=0.02))
    n = 16
    qs_lo, qs_hi = [], []
    for i in range(n):
        x0 = -ROSE_R + 2 * ROSE_R * i / n
        x1 = -ROSE_R + 2 * ROSE_R * (i + 1) / n
        z0 = ROSE_Z - math.sqrt(max(0.0, ROSE_R ** 2 - x0 ** 2))
        z1 = ROSE_Z - math.sqrt(max(0.0, ROSE_R ** 2 - x1 ** 2))
        qs_lo.append([(x0, Z_KINGS1), (x1, Z_KINGS1), (x1, z1), (x0, z0)])
        za = ROSE_Z + math.sqrt(max(0.0, ROSE_R ** 2 - x0 ** 2))
        zb = ROSE_Z + math.sqrt(max(0.0, ROSE_R ** 2 - x1 ** 2))
        qs_hi.append([(x0, za), (x1, zb), (x1, Z_GALLERY0), (x0, Z_GALLERY0)])
    out.append(slab_quads("wf_rlo", P0, qs_lo, WALL_T, st))
    out.append(slab_quads("wf_rhi", P0, qs_hi, WALL_T, st))
    out.append(box("wf_gal", P0 @ Ts(0, 0, (Z_GALLERY0 + Z_FACADE_TOP) * 0.5),
                   (W, WALL_T, Z_FACADE_TOP - Z_GALLERY0), st, bev=0.02))

    # ---------------- string courses ----------------
    for z, h in ((Z_KINGS0, 0.34), (Z_KINGS1 - 0.06, 0.28), (Z_GALLERY0, 0.30),
                 (Z_FACADE_TOP - 0.30, 0.46)):
        out.append(box("wf_sc%d" % int(z * 10), P0 @ Ts(0, WALL_T * 0.5 + 0.10, z),
                       (W + 0.2, 0.38, h), st2, bev=0.02))

    # ---------------- projecting porch ----------------
    dep = PORCH_FRONT - (Y_FACADE + WALL_T * 0.5)
    yc = (Y_FACADE + WALL_T * 0.5 + PORCH_FRONT) * 0.5
    Tp = WT(0, yc, 0, 0)
    hp = 21.0
    for s in (-1, 1):
        out.append(box("wf_pw%d" % s, Tp @ Ts(s * (6.40 - 0.65), 0, (Z_FLOOR + hp) * 0.5),
                       (1.30, dep, hp - Z_FLOOR), st, bev=0.02))
        # pilaster on the porch corner
        out.append(box("wf_pp%d" % s, Tp @ Ts(s * 5.55, dep * 0.5 - 0.25,
                                              (Z_FLOOR + hp) * 0.5),
                       (0.9, 0.5, hp - Z_FLOOR), st2, bev=0.02))
        out += H.pinnacle("wf_ppp%d" % s, Tp @ Ts(s * 5.55, dep * 0.5 - 0.25, hp - 0.1),
                          0.95, 3.0, st2)
    # porch front face: jambs + arch head around a 9.5 m opening
    Tw = WT(0, PORCH_FRONT, 0, 0)
    out += wall_bay("wf_pf", Tw, 12.8, Z_FLOOR, hp, 0.80, st,
                    win=dict(w=9.5, zb=Z_FLOOR, zs=Z_FLOOR + 7.3, apex=10.6,
                             glass=False, dark=False, lights=1),
                    sill=False, hood=False)
    out.append(box("wf_pcb", Tw @ Ts(0, 0.26, hp - 0.12), (13.2, 1.05, 0.36), st2, bev=0.03))
    out += balustrade("wf_pbal", Tw @ Ts(0, 0.40, hp + 0.05), 12.8, st2, h=1.0, deep=0.34)
    # carved frieze over the portal, under the parapet
    out += blind_lancets("wf_pfr", Tw, 11.4, hp - 2.05, hp - 0.55, 9, st2, y0=0.40,
                         gap=0.26)
    # porch jamb figures standing either side of the entry
    for s in (-1, 1):
        for j in (0, 1):
            out += [o for o in figure("wf_pjs%d_%d" % (s, j),
                                        Tw @ Ts(s * 5.55, 0.62,
                                                Z_FLOOR + 0.10 + 3.30 * j) @
                                        Matrix.Scale(0.72, 4), 2.9, st)
                    if "_pl" not in o.name]
            out.append(box("wf_pjc%d_%d" % (s, j),
                           Tw @ Ts(s * 5.55, 0.55, Z_FLOOR + 3.18 * j + 0.02),
                           (1.15, 0.85, 0.30), st2, bev=0.02))

    # ---------------- facade buttresses / corner pilasters ----------------
    for s in (-1, 1):
        Tb = WT(s * 8.05, Y_FACADE, 0, 0)
        out.append(box("wf_bt%d" % s, Tb @ Ts(0, WALL_T * 0.5 + 0.45,
                                              (Z_FLOOR + Z_FACADE_TOP) * 0.5),
                       (1.15, 0.95, Z_FACADE_TOP - Z_FLOOR), st2, bev=0.03))
        for k in range(6):
            out.append(box("wf_btc%d_%d" % (s, k),
                           Tb @ Ts(0, WALL_T * 0.5 + 0.52, Z_FLOOR + 5.4 + k * 6.6),
                           (1.35, 1.12, 0.30), st2, bev=0.02))
            # a prophet standing on every corbel of the facade buttresses
            out += [o for o in figure("wf_bts%d_%d" % (s, k),
                                        Tb @ Ts(0, WALL_T * 0.5 + 0.62,
                                                Z_FLOOR + 5.62 + k * 6.6) @
                                        Matrix.Scale(0.86, 4), 2.9, st)
                    if "_pl" not in o.name]
        out += H.pinnacle("wf_btp%d" % s,
                          Tb @ Ts(0, WALL_T * 0.5 + 0.45, Z_FACADE_TOP - 0.2),
                          1.05, 3.2, st2)
        Tc = WT(s * 9.72, Y_FACADE, 0, 0)
        out.append(box("wf_cp%d" % s, Tc @ Ts(0, WALL_T * 0.5 + 0.22,
                                              (Z_FLOOR + Z_FACADE_TOP) * 0.5),
                       (0.55, 0.55, Z_FACADE_TOP - Z_FLOOR), st2, bev=0.02))

    # ---------------- gable ----------------
    Gw = 22.2
    Gh = Z_GABLE_TOP - Z_FACADE_TOP
    out.append(H.wedge("wf_gable", P0 @ Ts(0, 0.55, Z_FACADE_TOP), Gw, Gh, WALL_T, st))
    rake = math.atan2(Gh, Gw * 0.5)
    rl = math.hypot(Gw * 0.5, Gh)
    for s in (-1, 1):
        out.append(box("wf_gr%d" % s, P0 @ Ts(s * Gw * 0.25, 1.42,
                                              Z_FACADE_TOP + Gh * 0.5,
                                              ry=-s * rake),
                       (rl, 0.40, 0.42), st2, bev=0.02))
        for i in range(9):
            t = (i + 0.5) / 9.0
            out.append(box("wf_gc%d_%d" % (i, s),
                           P0 @ Ts(s * (Gw * 0.5) * (1 - t), 1.56,
                                   Z_FACADE_TOP + Gh * t + 0.30),
                           (0.40, 0.40, 0.40), st2, bev=0.012))
    out.append(box("wf_cross1", P0 @ Ts(0, 1.10, Z_GABLE_TOP + 0.75),
                   (0.34, 0.40, 2.1), st2, bev=0.02))
    out.append(box("wf_cross2", P0 @ Ts(0, 1.10, Z_GABLE_TOP + 1.25),
                   (1.45, 0.40, 0.30), st2, bev=0.02))
    # gable oculus
    zoc = Z_FACADE_TOP + 2.55
    out.append(H.lathe("wf_oc", [(1.45, -0.35), (1.45, 0.35), (1.62, 0.35), (1.62, -0.35)],
                       st, seg=24, T=Ts(0, Y_FACADE + 1.35, zoc, rx=D2R(-90)),
                       close_bottom=False, close_top=False))
    out.append(cyl("wf_ocg", Ts(0, Y_FACADE + 1.28, zoc, rx=D2R(90)), 1.42, 0.10,
                   rng_choice(), seg=24))
    for i in range(6):
        a = TAU * i / 6
        out.append(box("wf_ocs%d" % i,
                       Ts(math.cos(a) * 0.72, Y_FACADE + 1.46,
                          zoc + math.sin(a) * 0.72, ry=-a),
                       (1.44, 0.24, 0.13), st2))
    # gable field: flanking quatrefoils + Christ in Majesty above the oculus
    for s in (-1, 1):
        out += quatrefoil("wf_gq%d" % s, P0 @ Ts(s * 2.75, 1.45,
                                                  Z_FACADE_TOP + 2.55), 0.98, 0.0, st2, bar=0.26)
    out += [o for o in figure("wf_gst", P0 @ Ts(0, 1.30, Z_GABLE_TOP - 3.3) @
                                Matrix.Scale(0.62, 4), 2.9, st2)
            if "_pl" not in o.name]
    out.append(box("wf_gbp", P0 @ Ts(0, 1.30, Z_GABLE_TOP - 3.42),
                   (1.5, 1.0, 0.34), st2, bev=0.02))
    # ---------------- central portal ----------------
    out += portal("por_c", Ts(0, PORCH_FRONT - 0.10, 0), 5.9, Z_FLOOR + 6.4, 4,
                  dstep=0.58, open_doors=True, statues=True)
    return out


def rng_choice():
    return G[1 + RNG.randrange(len(G) - 1)]


def rose():
    """Rose window: dark backing, two rings of coloured lights, stone tracery
    wheel in front, then the outer frame and hood mould."""
    out = []
    st = M["stone_warm"]
    yf = Y_FACADE + WALL_T * 0.5        # outer wall face
    R = ROSE_R
    out.append(cyl("rose_back", Ts(0, yf - 0.16, ROSE_Z, rx=D2R(90)), R * 0.995, 0.06,
                   G[0], seg=44))
    # ---- stained glass: a continuous colour field, then medallions on it ----
    for (r0, r1, gi) in ((0.155, 0.400, 2), (0.400, 0.720, 5), (0.720, 0.950, 2)):
        out.append(H.lathe("rose_fd%d" % int(r0 * 100),
                           [(R * r0, -0.03), (R * r1, -0.03),
                            (R * r1, 0.03), (R * r0, 0.03)], G[gi], seg=44,
                           T=Ts(0, yf, ROSE_Z, rx=D2R(90)),
                           close_bottom=False, close_top=False))
    n = 12
    for (rr, siz, st_) in ((0.560, 0.084, 3), (0.835, 0.098, 5)):
        for i in range(n):
            a = TAU * (i + 0.5) / float(n)
            out.append(cyl("rose_g%d_%d" % (int(rr * 1000), i),
                           Ts(math.cos(a) * R * rr, yf + 0.05,
                              ROSE_Z + math.sin(a) * R * rr, rx=D2R(90)),
                           R * siz, 0.06,
                           G[1 + (i * st_ + int(rr * 100)) % (len(G) - 1)],
                           seg=14))
    out.append(cyl("rose_gc", Ts(0, yf + 0.05, ROSE_Z, rx=D2R(90)), R * 0.155, 0.06,
                   G[3], seg=18))
    # ---- stone tracery in front of the glass ----
    yt = yf + 0.16
    for i in range(n):
        a = TAU * i / n
        out.append(box("rose_spk%d" % i,
                       Ts(math.cos(a) * R * 0.58, yt,
                          ROSE_Z + math.sin(a) * R * 0.58, ry=-a),
                       (R * 0.80, 0.34, 0.40), st, bev=0.012))
    for i in range(24):
        a = TAU * (i + 0.5) / 24
        out.append(box("rose_lace%d" % i,
                       Ts(math.cos(a) * R * 0.545, yt,
                          ROSE_Z + math.sin(a) * R * 0.545, ry=-a),
                       (R * 0.15, 0.30, 0.22), st, bev=0.008))
    for rr, ww in ((0.40, 0.30), (0.72, 0.32)):
        out.append(H.lathe("rose_ring%d" % int(rr * 100),
                           [(rr * R - ww, -0.13), (rr * R - ww, 0.13),
                            (rr * R + ww, 0.13), (rr * R + ww, -0.13),
                            (rr * R - ww, -0.13)], st, seg=36,
                           T=Ts(0, yt, ROSE_Z, rx=D2R(-90)),
                           close_bottom=False, close_top=False))
    out.append(cyl("rose_hub", Ts(0, yt, ROSE_Z, rx=D2R(90)), R * 0.135, 0.30, st, seg=16))
    out.append(cyl("rose_hub2", Ts(0, yt + 0.10, ROSE_Z, rx=D2R(90)), R * 0.075, 0.22,
                   st, seg=12))
    # ---- outer frame + hood ----
    out.append(H.lathe("rose_frame",
                       [(R, -0.55), (R, 0.30), (R * 1.10, 0.30), (R * 1.10, -0.55),
                        (R, -0.55)], st, seg=44, T=Ts(0, yf, ROSE_Z, rx=D2R(-90)),
                       close_bottom=False, close_top=False))
    out.append(H.lathe("rose_hm",
                       [(R * 1.10, 0.10), (R * 1.10, 0.52), (R * 1.22, 0.52),
                        (R * 1.22, 0.10), (R * 1.10, 0.10)], st, seg=44,
                       T=Ts(0, yf, ROSE_Z, rx=D2R(-90)),
                       close_bottom=False, close_top=False))
    # crockets around the hood
    for i in range(16):
        a = TAU * i / 16
        out.append(box("rose_cr%d" % i,
                       Ts(math.cos(a) * R * 1.16, yf + 0.50,
                          ROSE_Z + math.sin(a) * R * 1.16, ry=-a),
                       (0.30, 0.34, 0.26), st, bev=0.01))
    return out

# ==========================================================================
# towers
# ==========================================================================
def tower(side):
    """side = +1 / -1 ; centred on (TW_CX*side, TW_CY)."""
    out = []
    st, st2 = M["stone_warm"], M["stone"]
    cx = TW_CX * side
    T0 = Ts(cx, TW_CY, 0)
    W, D = TW_W, TW_D
    nrm_out = 90.0 * side
    # ---- corner buttresses ----
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx, by = sx * (W * 0.5 - 0.10), sy * (D * 0.5 - 0.10)
            tag = "tw%d_c%d%d" % (side, sx, sy)
            out.append(box(tag + "_a", T0 @ Ts(bx, by, 5.6), (2.5, 2.5, 11.2), st2, bev=0.03))
            out.append(box(tag + "_b", T0 @ Ts(bx, by, 17.0), (2.1, 2.1, 11.6), st2, bev=0.03))
            out.append(box(tag + "_c", T0 @ Ts(bx, by, 30.0), (1.8, 1.8, 14.4), st2, bev=0.03))
            out.append(box(tag + "_d", T0 @ Ts(bx, by, 40.4), (1.9, 1.9, 6.6), st2, bev=0.03))
            out += H.pinnacle(tag + "_pin", T0 @ Ts(bx, by, 43.7), 1.75, 5.6, st2)
            for s in (-1, 1):
                out.append(box(tag + "_pinb%d" % s, T0 @ Ts(bx + s * 0.55, by, 44.6),
                               (0.30, 0.36, 4.2), st2))
    # ---- shaft faces ----
    faces = []
    faces.append((T0 @ Ts(0, D * 0.5, 0), 0.0, W, "w"))          # west
    faces.append((T0 @ Ts(0, -D * 0.5, 0), 180.0, W, "e"))       # east
    faces.append((T0 @ Ts(side * W * 0.5, 0, 0), nrm_out, D, "o"))   # outer
    faces.append((T0 @ Ts(-side * W * 0.5, 0, 0), -nrm_out, D, "i"))  # inner
    for (Tface, nrm, span, tag) in faces:
        Tf = Tface @ Rz(-nrm)
        win_lo = dict(w=4.0, zb=6.0, zs=15.0, apex=3.2, lights=2)
        if tag == "w":
            win_lo = dict(w=4.5, zb=Z_FLOOR, zs=Z_FLOOR + 5.4, apex=4.6,
                          glass=False, dark=False, lights=1)
        out += wall_bay("tw%d_%s_lo" % (side, tag), Tf, span, Z_FLOOR, 22.0, 1.15, st,
                        win=win_lo, rng=RNG, bands=((5.4, 0.24), (11.2, 0.26), (17.8, 0.26)))
        # upper stage: paired tall lancets under a round oculus
        for s_ in (-1, 1):
            out += wall_bay("tw%d_%s_h%d" % (side, tag, s_),
                            Tf @ Ts(s_ * span * 0.245, 0, 0), span * 0.46,
                            22.0, Z_TOWER_TOP, 1.15, st,
                            win=dict(w=span * 0.20, zb=26.0, zs=36.6, apex=3.1,
                                     lights=2),
                            rng=RNG, bands=((22.6, 0.30),))
        for (bz, bh) in ((29.2, 0.26), (34.2, 0.26), (41.6, 0.40)):
            out.append(band("tw%d_%s_b%d" % (side, tag, int(bz * 10)), Tf, span, bz, bh,
                            1.15, st))
        # blind lancet fields filling the blank stages
        out += blind_lancets("tw%d_%s_bb" % (side, tag), Tf, span * 0.86, 22.95, 25.65,
                             6, st2, y0=0.575)
        if tag == "w":
            # tall blind arcade over the portal, fills the blank lower stage
            out += niche_row("tw%d_w_nr" % side, Tf, span * 0.90, 11.80, 17.30,
                             5, st, st2, statues=True, sc=1.35, y0=0.575)
            out += blind_lancets("tw%d_w_ub" % side, Tf, span * 0.90, 18.40, 24.30,
                                 6, st2, dark=0.22, y0=0.575, gap=0.22)
            for jn, jx in ((0, -4.15), (1, 4.15)):
                out += niche_row("tw%d_w_lo%d" % (side, jn), Tf @ Ts(jx, 0, 0),
                                 2.9, 3.30, 8.60, 1, st, st2, statues=True, sc=1.45, y0=0.575)

        out.append(box("tw%d_%s_pil" % (side, tag), Tf @ Ts(0, 0.90, 33.0),
                       (0.80, 0.62, 22.0), st2, bev=0.02))
        # oculus in the gable-like head of the stage
        Tv = Tf @ Ts(0, 0.0, 39.9)
        out.append(H.lathe("tw%d_%s_oc" % (side, tag),
                           [(1.02, -0.30), (1.02, 0.26), (1.20, 0.26), (1.20, -0.30),
                            (1.02, -0.30)], st2, seg=20,
                           T=Tv @ Ts(0, 0.86, 0, rx=D2R(-90)),
                           close_bottom=False, close_top=False))
        out.append(cyl("tw%d_%s_ocg" % (side, tag),
                       Tv @ Ts(0, 0.92, 0, rx=D2R(90)), 0.98, 0.06, rng_choice(), seg=20))
        for k in range(6):
            a = TAU * k / 6
            out.append(box("tw%d_%s_ocs%d" % (side, tag, k),
                           Tv @ Ts(math.cos(a) * 0.50, 1.00, math.sin(a) * 0.50,
                                   ry=-a),
                           (1.0, 0.16, 0.12), st2))
    # interior block (so nothing shows through the glass reveals)
    out.append(box("tw%d_in" % side, T0 @ Ts(0, 0, (Z_FLOOR + 43.0) * 0.5),
                   (W - 2.3, D - 2.3, 43.0 - Z_FLOOR), _void()))
    # ---- belfry stage: openwork ----
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(box("tw%d_bp%d%d" % (side, sx, sy),
                           T0 @ Ts(sx * (W * 0.5 - 1.15), sy * (D * 0.5 - 1.15),
                                   (Z_TOWER_TOP + Z_BELFRY_TOP) * 0.5),
                           (2.3, 2.3, Z_BELFRY_TOP - Z_TOWER_TOP), st2, bev=0.03))
    out.append(box("tw%d_bin" % side, T0 @ Ts(0, 0, (Z_TOWER_TOP + Z_BELFRY_TOP) * 0.5),
                   (W - 3.4, D - 3.4, Z_BELFRY_TOP - Z_TOWER_TOP), _void()))
    for (Tface, nrm, span, tag) in faces:
        Tf = Tface @ Rz(-nrm)
        for k in range(3):
            xc = (k - 1) * span * 0.305
            Tw = Tf @ Ts(xc, 0, 0)
            wdt = span * 0.225
            zt = Z_TOWER_TOP + 0.55
            zsp = Z_TOWER_TOP + 3.85
            ap = 3.05
            for s_ in (-1, 1):
                out.append(box("tw%d_%s_bp%d_%d" % (side, tag, k, s_),
                               Tw @ Ts(s_ * (wdt * 0.5 + 0.34), 0,
                                       (zt + zsp + ap) * 0.5),
                               (0.68, 1.15, zsp + ap - zt), st, bev=0.02))
            out += arch_ring("tw%d_%s_ba%d" % (side, tag, k), Tw @ Ts(0, 0, zsp),
                             wdt + 0.68, ap + 0.30, 0.0, st, n=8, thick=0.58, depth=1.15)
            out.append(box("tw%d_%s_bs%d" % (side, tag, k), Tw @ Ts(0, 0.02, zt - 0.24),
                           (wdt + 1.5, 1.32, 0.52), st, bev=0.02))
            for j in range(6):
                out.append(box("tw%d_%s_bl%d_%d" % (side, tag, k, j),
                               Tw @ Ts(0, -0.16, zt + 0.42 + j * 0.62, rx=D2R(-30)),
                               (wdt * 0.98, 0.80, 0.13), M["wood_dark"]))
    out += balustrade("tw%d_btop" % side, T0 @ Ts(0, D * 0.5 - 0.3, Z_BELFRY_TOP - 0.1),
                      W - 0.6, st2, h=1.0, deep=0.34)
    out.append(box("tw%d_corn" % side, T0 @ Ts(0, 0, Z_BELFRY_TOP + 0.12),
                   (W - 0.2, D - 0.2, 0.5), st2, bev=0.03))
    # ---- spire ----
    out += openwork_spire("tw%d_sp" % side, T0 @ Ts(0, 0, Z_BELFRY_TOP + 0.35),
                          W * 0.47, Z_SPIRE_TOP - Z_BELFRY_TOP - 0.35, st2, seg=8)
    # corner pinnacles flanking the spire
    for sx in (-1, 1):
        for sy in (-1, 1):
            out += H.pinnacle("tw%d_sp%d%d" % (side, sx, sy),
                              T0 @ Ts(sx * (W * 0.5 - 0.7), sy * (D * 0.5 - 0.7),
                                      Z_BELFRY_TOP + 0.2), 1.55, 6.2, st2)
    # ---- stair turret on the inner-west corner ----
    out.append(cyl("tw%d_tur" % side, T0 @ Ts(-side * (W * 0.5 + 0.35), D * 0.5 - 2.2,
                                              23.0),
                   1.55, 46.0, st2, seg=16))
    out.append(cyl("tw%d_turb" % side, T0 @ Ts(-side * (W * 0.5 + 0.35), D * 0.5 - 2.2,
                                               30.0), 1.75, 0.3, st, seg=16))
    out += H.spire("tw%d_turs" % side,
                   T0 @ Ts(-side * (W * 0.5 + 0.35), D * 0.5 - 2.2, 0),
                   1.9, 9.0, M["slate"], seg=8, base_z=46.0)
    return out


def openwork_spire(name, T, r, h, mat, seg=8):
    """Pierced octagonal spire: eight ribs, lace bands, crockets, finial."""
    out = []
    steps = 7
    prof = []
    for i in range(steps + 1):
        t = i / steps
        prof.append((max(0.06, r * (1.0 - t) ** 0.90), h * t))
    # solid inner cone so the pierced cage reads as stone, not wirework
    out.append(H.lathe(name + "_core",
                       [(r * 0.72, 0.0), (r * 0.44, h * 0.55), (r * 0.10, h * 1.00)],
                       mat, seg=seg, T=T, close_bottom=False, close_top=False))
    # ribs at the octagon corners
    for k in range(seg):
        a = TAU * k / seg + math.pi / seg
        for i in range(steps):
            (r0, z0), (r1, z1) = prof[i], prof[i + 1]
            x0, y0 = math.cos(a) * r0, math.sin(a) * r0
            x1, y1 = math.cos(a) * r1, math.sin(a) * r1
            L = math.hypot(math.hypot(x1 - x0, y1 - y0), z1 - z0)
            pitch = math.degrees(math.atan2(z1 - z0, math.hypot(x1 - x0, y1 - y0)))
            Mx = T @ Ts((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5) @ \
                Rz(-math.degrees(a)) @ Matrix.Rotation(-D2R(90 - pitch), 4, "Y")
            out.append(box(name + "_rib%d_%d" % (k, i), Mx, (0.34, 0.46, L * 1.10),
                           mat, bev=0.015))
    # lace bands (thin horizontal octagon frames)
    for i in (2, 4, 6):
        rr, zz = prof[i]
        out.append(H.lathe(name + "_band%d" % i,
                           [(rr * 0.98, zz - 0.10), (rr * 0.98, zz + 0.10),
                            (rr * 1.05, zz + 0.10), (rr * 1.05, zz - 0.10),
                            (rr * 0.98, zz - 0.10)], mat, seg=seg,
                           T=T, close_bottom=False, close_top=False))
    # crockets
    for k in range(seg):
        a = TAU * k / seg
        for i, cs in ((1, 0.85), (3, 1.15), (5, 1.60)):
            rr, zz = prof[i]
            out.append(box(name + "_cr%d_%d" % (k, i),
                           T @ Ts(math.cos(a) * rr * 1.05, math.sin(a) * rr * 1.05, zz),
                           (0.24 * cs, 0.24 * cs, 0.36 * cs), mat, bev=0.01))
    out.append(cyl(name + "_fin", T @ Ts(0, 0, h + 0.9), 0.09, 1.8, mat, seg=8))
    out.append(sphere(name + "_ball", T @ Ts(0, 0, h + 1.85), 0.22, M["gold"], seg=10))
    out.append(box(name + "_cross1", T @ Ts(0, 0, h + 2.55), (0.13, 0.13, 1.2), M["gold"]))
    out.append(box(name + "_cross2", T @ Ts(0, 0, h + 2.75), (0.75, 0.13, 0.13), M["gold"]))
    return out


# ==========================================================================
# flèche on the ridge
# ==========================================================================
def fleche(y):
    out = []
    st, slate = M["stone_warm"], M["slate"]
    r = 2.35
    base = Z_RIDGE - 0.6
    out.append(cyl("fl_drum", Ts(0, y, base + 2.4), r, 4.8, st, seg=8))
    for i in range(8):
        a = TAU * i / 8 + math.pi / 8
        Mx = Ts(math.cos(a) * r, y + math.sin(a) * r, base + 2.4) @ Rz(-math.degrees(a))
        out += H.window_slit("fl_sl%d" % i, Mx @ Ts(0, 0.05, 0), 0.5, 2.2, st)
    out.append(cyl("fl_corn", Ts(0, y, base + 4.9), r * 1.12, 0.42, st, seg=8))
    out += H.spire("fl_sp", Ts(0, y, 0), r * 1.02, 11.5, slate, seg=8, base_z=base + 5.0)
    for i in range(6):
        t = (i + 0.5) / 6.0
        for k in range(8):
            a = TAU * k / 8
            rr = r * 1.02 * (1 - t) * 1.0
            out.append(box("fl_cr%d_%d" % (i, k),
                           Ts(math.cos(a) * rr, y + math.sin(a) * rr,
                              base + 5.0 + 11.5 * t), (0.22, 0.22, 0.34), st, bev=0.01))
    out.append(box("fl_cross", Ts(0, y, base + 17.2), (0.12, 0.12, 1.5), M["gold"]))
    out.append(box("fl_cross2", Ts(0, y, base + 17.5), (0.8, 0.12, 0.12), M["gold"]))
    return out


# ==========================================================================
# kings gallery, niche statues, misc facade dressing
# ==========================================================================
def kings_gallery():
    """Gallery of kings: 11 statue niches standing proud of the facade face."""
    out = []
    st, st2 = M["stone_warm"], M["stone"]
    FY = Y_FACADE + WALL_T * 0.5          # the actual outer face
    PF = WT(0, FY, 0, 0)
    n = 11
    span = 19.8 / n
    z0, z1 = Z_KINGS0 + 0.4, Z_KINGS1 - 0.9
    for i in range(n):
        x = -9.9 + span * (i + 0.5)
        tag = "kg%d" % i
        # corbel the statue stands on
        out.append(box(tag + "_co", PF @ Ts(x, 0.30, z0 - 0.10),
                       (span * 0.80, 0.85, 0.34), st2, bev=0.02))
        out.append(box(tag + "_co2", PF @ Ts(x, 0.18, z0 - 0.42),
                       (span * 0.52, 0.62, 0.34), st2, bev=0.02))
        # flanking colonettes
        for s in (-1, 1):
            out.append(cyl(tag + "_c%d" % s, PF @ Ts(x + s * span * 0.40, 0.34,
                                                      (z0 + z1) * 0.5),
                           0.105, z1 - z0, st2, seg=8))
            out.append(box(tag + "_cb%d" % s, PF @ Ts(x + s * span * 0.40, 0.34, z0 + 0.10),
                           (0.34, 0.34, 0.22), st2, bev=0.015))
            out.append(box(tag + "_cc%d" % s, PF @ Ts(x + s * span * 0.40, 0.34, z1 - 0.10),
                           (0.38, 0.38, 0.24), st2, bev=0.015))
        # canopy: slab + arched head + gablet
        out.append(box(tag + "_cp", PF @ Ts(x, 0.30, z1 + 0.12),
                       (span * 0.92, 0.86, 0.26), st2, bev=0.02))
        out += arch_ring(tag + "_ca", PF @ Ts(x, 0.36, z1 - 0.95), span * 0.62,
                         0.62, 0.0, st2, n=6, thick=0.22, depth=0.42)
        out.append(H.wedge(tag + "_cw", PF @ Ts(x, 0.30, z1 + 0.24),
                           span * 0.78, 0.60, 0.72, st2))
        # statue
        out += [o for o in figure(tag + "_st",
                                    PF @ Ts(x, 0.30, z0 + 0.12) @
                                    Matrix.Scale(1.16, 4), 2.9, st)
                if "_pl" not in o.name]
        # divider pilaster between the niches
        out.append(box(tag + "_dv", PF @ Ts(x + span * 0.5, 0.14,
                                            (Z_KINGS0 + Z_KINGS1) * 0.5),
                       (0.30, 0.52, Z_KINGS1 - Z_KINGS0), st, bev=0.012))
    return out


def gallery_blind():
    """Blind arcade band under the facade cornice."""
    out = []
    st = M["stone_warm"]
    FY = Y_FACADE + WALL_T * 0.5
    PF = WT(0, FY, 0, 0)
    n = 9
    span = 19.8 / n
    for i in range(n):
        x = -9.9 + span * (i + 0.5)
        T = PF @ Ts(x, 0.0, Z_GALLERY0)
        w = span * 0.58
        zs = 1.75
        apex = 0.92 * w
        # shadowed recess behind the arcade
        out.append(box("gb%d_v" % i, T @ Ts(0, -0.28, zs * 0.55),
                       (w - 0.04, 0.20, zs * 1.10), _void()))
        for s in (-1, 1):
            out.append(box("gb%d_p%d" % (i, s), T @ Ts(s * (w * 0.5 + 0.20), 0.24,
                                                      zs * 0.52),
                           (0.34, 0.62, zs + apex * 0.22), st, bev=0.012))
            out.append(cyl("gb%d_c%d" % (i, s), T @ Ts(s * (w * 0.5 + 0.20), 0.30,
                                                       zs * 0.50),
                           0.085, zs * 0.94, st, seg=6))
        out += arch_ring("gb%d_a" % i, T @ Ts(0, 0.26, 0), w + 0.74, apex + 0.20, 0.0,
                         st, n=7, thick=0.24, depth=0.50)
        out.append(cyl("gb%d_o" % i, T @ Ts(0, 0.10, zs + apex * 0.42, rx=D2R(90)),
                       w * 0.19, 0.22, rng_choice(), seg=8))
    return out


# ==========================================================================
# build
# ==========================================================================
# ==========================================================================
# transept: the crossing arms that turn the plan into a cross
# ==========================================================================
TR_Y0 = Y_EAST + 2.0 * BAY          # -14.0  choir side edge of the crossing
TR_Y1 = Y_EAST + 4.0 * BAY          #  -1.0  nave side edge
TR_CY = (TR_Y0 + TR_Y1) * 0.5       #  -7.5
TR_D = TR_Y1 - TR_Y0                #  13.0  depth of each arm
TR_XOUT = 37.0                      # outer face of the transept end wall
TR_RIDGE = Z_EAVE + TR_D * 0.5 * math.tan(D2R(PITCH))
SKIP_BAYS = (2, 3)
SKIP_PIERS = (2, 3, 4)                  # aisle bays swallowed by the crossing


def rose_at(name, T, R, st, st2):
    """Blind wheel window applied to a face frame (local +Y outward)."""
    out = []
    out.append(cyl(name + "_bk", T @ Ts(0, -0.12, 0, rx=D2R(90)), R * 0.99, 0.12,
                   _void(), seg=36))
    for (r0, r1, gi) in ((0.15, 0.42, 1), (0.42, 0.74, 3), (0.74, 0.97, 2)):
        prof = [(R * r0, -0.035), (R * r1, -0.035), (R * r1, 0.035), (R * r0, 0.035)]
        out.append(H.lathe(name + "_g%d" % gi, prof, G[gi], seg=36,
                           T=T @ Ts(0, 0.04, 0, rx=D2R(90)),
                           close_bottom=False, close_top=False))
    for i in range(12):
        a = TAU * i / 12.0
        out.append(box(name + "_sp%d" % i,
                       T @ Ts(math.cos(a) * R * 0.50, 0.17, math.sin(a) * R * 0.50, ry=-a),
                       (R * 0.96, 0.42, 0.36), st2, bev=0.012))
    for rr in (0.42, 0.74):
        out.append(H.lathe(name + "_r%d" % int(rr * 100),
                           [(R * rr * 0.97, -0.04), (R * rr * 1.03, -0.04),
                            (R * rr * 1.03, 0.04), (R * rr * 0.97, 0.04)],
                           st2, seg=36, T=T @ Ts(0, 0.18, 0, rx=D2R(90)),
                           close_bottom=False, close_top=False))
    out.append(cyl(name + "_hub", T @ Ts(0, 0.22, 0, rx=D2R(90)), R * 0.16, 0.20, st2, seg=16))
    out.append(cyl(name + "_hg", T @ Ts(0, 0.30, 0, rx=D2R(90)), R * 0.13, 0.06, G[3], seg=16))
    # outer frame + hood
    out.append(H.lathe(name + "_fr",
                       [(R * 1.00, -0.22), (R * 1.10, -0.10), (R * 1.10, 0.34),
                        (R * 1.00, 0.34), (R * 1.00, -0.22)],
                       st, seg=36, T=T @ Ts(0, 0.10, 0, rx=D2R(90)),
                       close_bottom=False, close_top=False))
    for k in range(16):
        a = TAU * k / 16.0
        out.append(box(name + "_ck%d" % k,
                       T @ Ts(math.cos(a) * R * 1.13, 0.26, math.sin(a) * R * 1.13,
                              ry=-a, rz=math.degrees(a)),
                       (0.30, 0.34, 0.46), st2, bev=0.012))
    return out


def transept():
    """Two crossing arms with rose-window facades, plus the crossing tower."""
    out = []
    st, st2 = M["stone"], M["stone_warm"]
    slate = M["slate"]
    x0, x1 = CLER_OUT, TR_XOUT
    L = x1 - x0

    for s in (1, -1):
        tag = "tr%d" % s
        # ---------------- plinth ----------------
        out.append(box(tag + "_pl", Ts(s * (x0 + x1) * 0.5, TR_CY, 0.34),
                       (L + 2.6, TR_D + 2.6, 0.68), st, bev=0.03))
        # ---------------- the two side walls ----------------
        for (yy, nm, wtag) in ((TR_Y0, 180.0, "n"), (TR_Y1, 0.0, "s")):
            nb = 3
            bw = L / nb
            for k in range(nb):
                cx = s * (x0 + bw * (k + 0.5))
                T = WT(cx, yy, 0, nm)
                nm_bay = "%s_%s_%d" % (tag, wtag, k)
                out += blind_lancets(nm_bay + "_ab", T, bw, 0.85, 5.40,
                                     4, st2, dark=0.16, y0=WALL_T * 0.5, gap=0.24)
                if k == 1:
                    # rose bay: solid wall carrying a wheel window
                    out += wall_bay(nm_bay, T, bw, 0.0, Z_EAVE, WALL_T, st,
                                    win=None, rng=RNG,
                                    bands=((6.10, 0.24), (19.60, 0.30), (26.80, 0.26)))
                    out += rose_at(nm_bay + "_rose",
                                   T @ Ts(0, WALL_T * 0.5 + 0.10, 22.90), 2.95, st, st2)
                else:
                    out += wall_bay(nm_bay, T, bw, 0.0, Z_EAVE, WALL_T, st,
                                    win=dict(w=3.30, zb=7.30, zs=17.60, apex=3.70, lights=2),
                                    rng=RNG, bands=((6.10, 0.24), (19.60, 0.30)))
                out += balustrade(nm_bay + "_bal",
                                  T @ Ts(0, WALL_T * 0.30, Z_EAVE + 0.06), bw, st2,
                                  h=1.10, deep=0.36)
                if k < nb - 1:
                    Tb = WT(s * (x0 + bw * (k + 1)), yy + (0.7 if nm == 180.0 else -0.7),
                            0, nm)
                    bt = "%s_%s_bt%d" % (tag, wtag, k)
                    out.append(box(bt, Tb @ Ts(0, 0.55, 6.90), (1.30, 1.10, 13.8),
                                   st2, bev=0.03))
                    out.append(box(bt + "c", Tb @ Ts(0, 0.62, 14.20), (1.55, 1.30, 0.40),
                                   st2, bev=0.03))
                    out += H.pinnacle(bt + "p", Tb @ Ts(0, 0.55, 14.35), 1.05, 3.4, st2)
            out.append(box("%s_%s_cor" % (tag, wtag),
                           WT(s * (x0 + L * 0.5), yy, 0, nm)
                           @ Ts(0, WALL_T * 0.5 + 0.18, Z_EAVE - 0.16),
                           (L, 0.56, 0.44), st2, bev=0.03))
        # ---------------- end wall: portal, rose, gable ----------------
        Te = WT(s * x1, TR_CY, 0, 90.0 * s)
        span_e = TR_D + WALL_T
        out += wall_bay(tag + "_end", Te, span_e, 0.0, Z_EAVE, WALL_T, st,
                        win=dict(w=5.60, zb=Z_FLOOR, zs=8.20, apex=5.90,
                                 glass=False, dark=False, lights=1),
                        rng=RNG, bands=((10.40, 0.34), (20.40, 0.30)))
        out += portal(tag + "_por", WT(s * (x1 + WALL_T * 0.5), TR_CY, 0, 90.0 * s),
                      5.0, Z_FLOOR + 6.0, 3, wstep=0.55, dstep=0.60, k=1.14)
        Tr = Te @ Ts(0, WALL_T * 0.5 + 0.10, 25.30)
        out += rose_at(tag + "_rose", Tr, 4.10, st, st2)
        for (bs, by) in ((-1, TR_Y0 - 1.05), (1, TR_Y1 + 1.05)):
            Tb = WT(s * (x1 - 0.75), by, 0, 90.0 * s)
            out.append(box("%s_ebt%d" % (tag, by > TR_CY),
                           Tb @ Ts(0, 0.35, 8.60), (1.85, 1.85, 17.2), st2, bev=0.03))
            out.append(box("%s_ebt2%d" % (tag, by > TR_CY),
                           Tb @ Ts(0, 0.25, 17.80), (2.15, 2.15, 1.60), st2, bev=0.03))
            out += H.pinnacle("%s_ebtp%d" % (tag, by > TR_CY),
                              Tb @ Ts(0, 0.20, 18.60), 1.45, 5.6, st2)
        Tg = Te @ Ts(0, 0.45, Z_EAVE)
        out.append(H.wedge(tag + "_gab", Tg, span_e + 0.8, TR_RIDGE - Z_EAVE, WALL_T, st))
        out += quatrefoil(tag + "_gq0", Te @ Ts(0, WALL_T * 0.5 + 0.62, TR_RIDGE - 2.95),
                          1.02, 0.24, st2)
        for sd in (-1, 1):
            out += quatrefoil(tag + "_gqs%d" % sd,
                              Te @ Ts(sd * 2.95, WALL_T * 0.5 + 0.58, TR_RIDGE - 4.15),
                              0.58, 0.18, st2)
        for sd in (-1, 1):
            out.append(box("%s_gr%d" % (tag, sd),
                           Te @ Ts(sd * (span_e * 0.25), WALL_T * 0.5 + 0.48,
                                   Z_EAVE + (TR_RIDGE - Z_EAVE) * 0.5),
                           (span_e * 0.5 + 0.3, 0.40, 0.34), st2, bev=0.02))
            out.append(box("%s_grc%d" % (tag, sd),
                           Te @ Ts(sd * (span_e * 0.31), WALL_T * 0.5 + 0.60,
                                   Z_EAVE + (TR_RIDGE - Z_EAVE) * 0.40),
                           (0.34, 0.34, 0.60), st2, bev=0.015))
            out.append(box("%s_grc2%d" % (tag, sd),
                           Te @ Ts(sd * (span_e * 0.40), WALL_T * 0.5 + 0.60,
                                   Z_EAVE + (TR_RIDGE - Z_EAVE) * 0.17),
                           (0.34, 0.34, 0.60), st2, bev=0.015))
        out.append(box(tag + "_cross", Te @ Ts(0, WALL_T * 0.5 + 0.30, TR_RIDGE + 1.0),
                       (0.16, 0.16, 1.7), M["gold"]))
        out.append(box(tag + "_cross2", Te @ Ts(0, WALL_T * 0.5 + 0.30, TR_RIDGE + 1.35),
                       (1.0, 0.16, 0.16), M["gold"]))
        # ---------------- arm roof: two slopes to a ridge along X ----------------
        xe = x1 + 0.75
        out.append(quad_slab(tag + "_rn",
                             [(s * x0, TR_Y0 - 0.75, Z_EAVE + 0.06),
                              (s * xe, TR_Y0 - 0.75, Z_EAVE + 0.06),
                              (s * xe, TR_CY, TR_RIDGE),
                              (s * x0, TR_CY, TR_RIDGE)], 0.34, slate))
        out.append(quad_slab(tag + "_rs",
                             [(s * x0, TR_Y1 + 0.75, Z_EAVE + 0.06),
                              (s * xe, TR_Y1 + 0.75, Z_EAVE + 0.06),
                              (s * xe, TR_CY, TR_RIDGE),
                              (s * x0, TR_CY, TR_RIDGE)], 0.34, slate))
        out.append(box(tag + "_ridge", Ts(s * (x0 + xe) * 0.5, TR_CY, TR_RIDGE + 0.18),
                       (xe - x0, 0.60, 0.36), st2, bev=0.02))
        for (yy, nm) in ((TR_Y0 - 0.78, 180.0), (TR_Y1 + 0.78, 0.0)):
            T = WT(s * (x0 + xe) * 0.5, yy, 0, nm)
            out.append(box("%s_ev%d" % (tag, int(yy)), T @ Ts(0, 0.0, Z_EAVE + 0.22),
                           (xe - x0, 0.30, 0.42), st2, bev=0.02))
            # a lucarne on each slope
            out.append(box("%s_lu%d" % (tag, int(yy)),
                           T @ Ts(s * L * 0.18, 1.05, Z_EAVE + 2.4),
                           (2.20, 2.40, 2.80), st2, bev=0.02))
            out.append(box("%s_luw%d" % (tag, int(yy)),
                           T @ Ts(s * L * 0.18, 2.30, Z_EAVE + 2.5),
                           (1.30, 0.30, 1.70), _void()))
            out.append(H.wedge("%s_lug%d" % (tag, int(yy)),
                               T @ Ts(s * L * 0.18, 2.05, Z_EAVE + 3.8),
                               2.40, 1.50, 1.30, st2))

    out += crossing_tower()
    return out


def crossing_tower():
    """Short, sturdy lantern over the crossing with an eight-rib spire."""
    out = []
    st, st2 = M["stone"], M["stone_warm"]
    W = 9.90
    z0, z1 = 31.0, 50.60
    for (nm, tg) in ((0.0, "s"), (180.0, "n"), (90.0, "e"), (-90.0, "w")):
        T = WT(math.sin(D2R(nm)) * W * 0.5, TR_CY + math.cos(D2R(nm)) * W * 0.5, 0, nm)
        out += wall_bay("xt_" + tg, T, W, z0, z1, 1.35, st,
                        win=dict(w=2.40, zb=38.60, zs=45.30, apex=2.50,
                                 glass=False, dark=True, lights=2),
                        rng=RNG, bands=((36.40, 0.38), (47.10, 0.40)))
        out += balustrade("xt_" + tg + "_bal", T @ Ts(0, 1.35 * 0.30, z1 + 0.06), W, st2,
                          h=1.05, deep=0.34)
        out += blind_lancets("xt_" + tg + "_bl", T, W * 0.86, 32.20, 35.60, 5, st2,
                             dark=0.18, y0=1.35 * 0.5, gap=0.22)
    for sx in (-1, 1):
        for sy in (-1, 1):
            Tb = WT(sx * W * 0.5, TR_CY + sy * W * 0.5, 0, 0)
            out.append(box("xt_cb%d%d" % (sx, sy), Tb @ Ts(0, 0, (z0 + z1) * 0.5),
                           (1.55, 1.55, z1 - z0), st2, bev=0.03))
            out.append(box("xt_cc%d%d" % (sx, sy), Tb @ Ts(0, 0, z1 + 0.22),
                           (1.90, 1.90, 0.44), st2, bev=0.03))
            out += H.pinnacle("xt_cp%d%d" % (sx, sy), Tb @ Ts(0, 0, z1 + 0.46),
                              1.55, 5.40, st2)
    # octagonal drum easing the box into the spire
    out.append(H.lathe("xt_drum", [(5.60, 0.0), (5.45, 1.30), (5.10, 2.60)],
                       st, seg=8, T=Ts(0, TR_CY, z1 + 0.30),
                       close_bottom=False, close_top=False))
    out.append(H.lathe("xt_drumc", [(5.30, 0.0), (5.62, 0.18), (5.30, 0.36)],
                       st2, seg=8, T=Ts(0, TR_CY, z1 + 0.30),
                       close_bottom=False, close_top=False))
    out += openwork_spire("xt_sp", Ts(0, TR_CY, z1 + 2.55), 5.05, 13.20, st2, seg=8)
    return out


def narthex():
    """Vaulted west bays behind the central portal: depth for the eye-level shot."""
    out = []
    st, st2 = M["stone"], M["stone_warm"]
    y0, y1 = Y_EAST + 2.0 * BAY + 4.0, Y_FACADE - 2.0
    # floor
    out.append(box("nx_fl", Ts(0, (y0 + y1) * 0.5, Z_FLOOR - 0.10),
                   (NAVE_HW * 2.0, y1 - y0, 0.30), st2, bev=0.02))
    for (yy, tag) in ((y1 - 6.0, "a"), (y1 - 12.0, "b"), (y1 - 18.0, "c")):
        # two free columns per bay
        for s in (-1, 1):
            xc = s * (NAVE_HW - 1.35)
            Tc = Ts(xc, yy, Z_FLOOR)
            out.append(box("nx_%s%d_b" % (tag, s), Tc @ Ts(0, 0, 0.28),
                           (1.55, 1.55, 0.56), st2, bev=0.03))
            out.append(H.lathe("nx_%s%d_sh" % (tag, s),
                               [(0.62, 0.0), (0.58, 0.35), (0.52, 7.60), (0.62, 8.10)],
                               st2, seg=12, T=Tc @ Ts(0, 0, 0.56),
                               close_bottom=False, close_top=False))
            out.append(box("nx_%s%d_cap" % (tag, s), Tc @ Ts(0, 0, 8.90),
                           (1.45, 1.45, 0.42), st2, bev=0.03))
            # clustered shafts around it
            for k in range(4):
                a = TAU * k / 4.0 + math.pi / 4.0
                out.append(box("nx_%s%d_s%d" % (tag, s, k),
                               Tc @ Ts(math.cos(a) * 0.66, math.sin(a) * 0.66, 4.60),
                               (0.26, 0.26, 7.60), st2))
            # springing rib toward the wall and across
            out.append(box("nx_%s%d_r" % (tag, s), Tc @ Ts(-s * 0.75, 0, 9.30, ry=s * D2R(16)),
                           (1.60, 0.30, 0.34), st2, bev=0.012))
        # transverse rib across the vessel
        out.append(box("nx_%s_arch" % tag, Ts(0, yy, 9.10), (NAVE_HW * 2.0 - 1.4, 0.36, 0.42),
                       st2, bev=0.02))
        out.append(box("nx_%s_arch2" % tag, Ts(0, yy, 19.20), (NAVE_HW * 2.0 - 2.6, 0.34, 0.40),
                       st2, bev=0.02))
    return out


def build(MAT, rng):
    global M, RNG, G
    M = MAT
    RNG = rng
    G = glass_palette()
    P = []
    P += plinth()
    for s in (1, -1):
        P += nave_side(s)
    P += nave_roof()
    P += apse()
    P += apse_roof()
    P += transept()
    P += narthex()
    P += west_front()
    P += rose()
    P += kings_gallery()
    P += gallery_blind()
    P += portal("por_l", WT(-TW_CX, Y_TOWER_W, 0, 0), 4.4, Z_FLOOR + 5.4, 2,
                wstep=0.52, dstep=0.40)
    P += portal("por_r", WT(TW_CX, Y_TOWER_W, 0, 0), 4.4, Z_FLOOR + 5.4, 2,
                wstep=0.52, dstep=0.40)
    for s in (1, -1):
        P += tower(s)

    # small chamfers only need one bevel segment: identical silhouette at 1/3 cost
    for ob in P:
        if ob is None or ob.type != "MESH":
            continue
        for md in ob.modifiers:
            if md.type == "BEVEL" and md.width <= 0.024:
                md.segments = 1
    return P


def glass_palette():
    """Opaque stained-glass sheets: deep colour + a little emission so the
    windows read from a distance instead of turning into black holes."""
    out = []
    for nm, hexc, em in (("glass_lead", "#161d2c", 0.22),
                         ("glass_red", "#6e1622", 0.55),
                         ("glass_blue", "#1d3b6e", 0.70),
                         ("glass_gold", "#8a6414", 0.50),
                         ("glass_green", "#1b3a24", 0.40),
                         ("glass_violet", "#3d1a4e", 0.55),
                         ("glass_rose", "#7d2436", 0.60)):
        m = K.mat_cloth(nm, hexc)
        b = None
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                b = n
                break
        if b is not None:
            for key, val in (("Emission Color", K.c(hexc)),
                             ("Emission Strength", em),
                             ("Roughness", 0.18),
                             ("Metallic", 0.0)):
                inp = b.inputs.get(key)
                if inp is not None:
                    try:
                        inp.default_value = val
                    except Exception:
                        pass
        out.append(m)
    # weight the field the way a French window reads: a blue ground with red
    # and violet accents. G[0] stays the dark lead sheet.
    idx = (2, 2, 2, 1, 1, 6, 5, 5, 3, 4, 2, 5, 2)
    return [out[0]] + [out[i] for i in idx]


def mats():
    MAT = {}
    # trim stone: pale warm limestone, catches the light on every moulding
    MAT["stone"] = K.mat_stone("stone_trim", base="#c0b597", dark="#9a8f72",
                               light="#ded3b4", scale=1.7)
    # wall stone: mid warm grey, a full value below the trim
    MAT["stone_warm"] = K.mat_stone("stone_wall", base="#6f6752", dark="#463f2f",
                                    light="#8d8467", scale=1.5)
    MAT["wood"] = K.mat_wood()
    MAT["wood_dark"] = K.mat_wood("timber_dark", base="#3a2517", light="#543823", scale=12)
    MAT["tile"] = K.mat_tile()
    MAT["tile_blue"] = K.mat_tile("roof_tile_blue", base="#3f4c63", dark="#2b3446",
                                  light="#57687f")
    MAT["slate"] = K.mat_tile("roof_slate", base="#4a5560", dark="#333c46", light="#5f6d7a")
    MAT["glass"] = K.mat_glass()
    MAT["iron"] = K.mat_metal()
    MAT["gold"] = K.mat_gold()
    MAT["plaster"] = K.mat_plaster()
    MAT["banner_red"] = K.mat_cloth("banner_red", "#8e2b26")
    MAT["banner_blue"] = K.mat_cloth("banner_blue", "#243a63")
    MAT["banner_gold"] = K.mat_cloth("banner_gold", "#a8811f")
    return MAT


# ==========================================================================
# preview
# ==========================================================================
def _tris(parts):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        ev.to_mesh_clear()
    return n


def preview(samples=48, res=(1400, 900), full=True, only=None):
    H._clear()
    MAT = mats()
    rng = random.Random(7)
    parts = build(MAT, rng)
    lo, hi = H.bbox(parts)
    raw = H.tri_count(parts)
    print("[cath] parts=%d tris=%d" % (len(parts), raw), flush=True)
    print("[cath] bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f) size=(%.1f,%.1f,%.1f)"
          % (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z,
             hi.x - lo.x, hi.y - lo.y, hi.z - lo.z), flush=True)
    dg = bpy.context.evaluated_depsgraph_get()
    print("[cath] tris_eval=%d" % _tris(parts), flush=True)

    H.diorama_floor(M["stone_warm"], size=420.0)
    H.setup_world()
    # dedicated key on the west facade (the toolkit sun comes from the SE and
    # leaves the hero elevation in shadow)
    fd = bpy.data.lights.new("cath_sun", "SUN")
    fd.energy = 2.3
    fd.angle = math.radians(4.0)
    fd.color = (1.0, 0.97, 0.92)
    fo = bpy.data.objects.new("cath_sun", fd)
    bpy.context.collection.objects.link(fo)
    fo.rotation_euler = (math.radians(56), 0.0, math.radians(203))
    H.setup_engine(samples=samples, res=res)
    if not only:
        H.three_views("cathedral", center=(0, 0, 30), size=(90, 110), dist=105)

    # soft fill on the west front (the key sun leaves it in shadow)
    lt = bpy.data.lights.new("cath_fill", "AREA")
    lt.energy = 88000.0
    lt.size = 70.0
    lt.color = (1.0, 0.96, 0.90)
    lo_ = bpy.data.objects.new("cath_fill", lt)
    bpy.context.collection.objects.link(lo_)
    lo_.location = (34.0, 165.0, 62.0)
    d = Vector((0.0, 30.0, 35.0)) - lo_.location
    lo_.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    # second fill for the +X flank and the chevet
    lt2 = bpy.data.lights.new("cath_fill2", "AREA")
    lt2.energy = 40000.0
    lt2.size = 80.0
    lt2.color = (0.86, 0.91, 1.0)
    lo2 = bpy.data.objects.new("cath_fill2", lt2)
    bpy.context.collection.objects.link(lo2)
    lo2.location = (168.0, -104.0, 96.0)
    d2 = Vector((0.0, 4.0, 26.0)) - lo2.location
    lo2.rotation_euler = d2.to_track_quat("-Z", "Y").to_euler()

    # head-on facade fill: the towers shade the central gable and the portals
    lt3 = bpy.data.lights.new("cath_fill3", "AREA")
    lt3.energy = 42000.0
    lt3.size = 110.0
    lt3.color = (1.0, 0.98, 0.95)
    lo3 = bpy.data.objects.new("cath_fill3", lt3)
    bpy.context.collection.objects.link(lo3)
    lo3.location = (8.0, 150.0, 62.0)
    d3 = Vector((0.0, 43.0, 38.0)) - lo3.location
    lo3.rotation_euler = d3.to_track_quat("-Z", "Y").to_euler()
    # low warm bounce into the portal tunnel + a nave interior light so the
    # open doors reveal the narthex instead of a black hole
    lt4 = bpy.data.lights.new("cath_por", "AREA")
    lt4.energy = 4200.0
    lt4.size = 22.0
    lt4.color = (1.0, 0.9, 0.72)
    lo4 = bpy.data.objects.new("cath_por", lt4)
    bpy.context.collection.objects.link(lo4)
    lo4.location = (0.0, 62.0, 6.0)
    d4 = Vector((0.0, 46.0, 9.5)) - lo4.location
    lo4.rotation_euler = d4.to_track_quat("-Z", "Y").to_euler()
    lt5 = bpy.data.lights.new("cath_nave", "POINT")
    lt5.energy = 220000.0
    lt5.color = (1.0, 0.86, 0.62)
    lt5.shadow_soft_size = 6.0
    lo5 = bpy.data.objects.new("cath_nave", lt5)
    bpy.context.collection.objects.link(lo5)
    lo5.location = (0.0, 14.0, 15.0)

    out_dir = H.OUT_DIR
    cams = []
    cams.append(("front", (0.0, PORCH_FRONT + 27.0, 1.75), (0.0, PORCH_FRONT, 21.0), 17.0))
    cams.append(("west", (0.0, 246.0, 35.0), (0.0, 40.0, 34.0), 60.0))
    cams.append(("rose", (0.0, 96.0, 34.0), (0.0, 43.0, 33.4), 72.0))
    cams.append(("apse", (-138.0, -168.0, 66.0), (0.0, -8.0, 27.0), 55.0))
    cams.append(("flank", (205.0, -104.0, 78.0), (0.0, 2.0, 28.0), 50.0))
    cams.append(("door", (1.0, PORCH_FRONT + 15.0, 4.20), (0.0, PORCH_FRONT, 6.60), 42.0))
    if not full:
        cams = cams[:2]
    if only:
        cams = [c_ for c_ in cams if c_[0] in only]
    for tag, loc, tgt, lens in cams:
        c = H.camera("cam_" + tag, loc, tgt, lens=lens)
        H.render_to(os.path.join(out_dir, "hd_cathedral_%s.png" % tag), c)
    print("[cath] done", flush=True)
    return parts


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    quick = "--quick" in argv
    if "--norender" in argv:
        H._clear()
        MAT = mats()
        parts = build(MAT, random.Random(7))
        lo, hi = H.bbox(parts)
        print("[cath] parts=%d tris=%d" % (len(parts), H.tri_count(parts)), flush=True)
        print("[cath] bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)"
              % (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z), flush=True)
        print("[cath] tris_eval=%d" % _tris(parts), flush=True)
        if "--stats" in argv:
            dg = bpy.context.evaluated_depsgraph_get()
            agg = {}
            for ob in parts:
                if ob is None or ob.type != "MESH":
                    continue
                ev = ob.evaluated_get(dg)
                me = ev.to_mesh()
                me.calc_loop_triangles()
                key = "_".join(ob.name.split("_")[:3])
                agg[key] = agg.get(key, 0) + len(me.loop_triangles)
                ev.to_mesh_clear()
            tot = sum(agg.values()) or 1
            for k, v in sorted(agg.items(), key=lambda kv: -kv[1])[:28]:
                print("[stat] %-14s %8d  %5.1f%%" % (k, v, 100.0 * v / tot), flush=True)
    elif "--all" in argv:
        preview(samples=24, res=(760, 500), full=True)
    else:
        preview(samples=24 if quick else 48,
                res=(760, 500) if quick else (1400, 900), full=not quick)