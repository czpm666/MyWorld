"""hd_castle_int.py - the throne hall inside the royal castle.

Ariel's coronation hall: one long aisled hall, entered at -Y through a vaulted
porch, throne under a chancel arch at +Y.  The module is built at its final
world position with identity object transforms, floor at z = 0, so the caller
can drop the returned objects straight into the castle shell (the exterior in
hd_castle.py is 97.8 x 94.2 m and 61 m tall).

    footprint() -> (30.0, 52.0)     outer walls x +-15, y +-26
    height()    -> 21.4             ridge of the timber roof
    build(MAT, rng) -> [bpy objects]

Axes
    +X  east aisle      -X  west aisle      (the model is built once and
    +Y  throne end      -Y  entrance         mirrored, so the two halves are
    +Z  up, floor = 0                        identical by construction)

Vertical section (design numbers, metres)
    0.00  floor                7.60  arcade capitals / vault springing
    1.30  dado top             9.80  arcade arch apex (rise 2.2 on hs 2.03)
    2.55  aisle window sill   10.20  aisle vault crown
    6.00  aisle window apex   12.30  clerestory sill
    7.60  aisle vault spring  16.05  clerestory window apex
                              16.40  wall plate, tie beams seat here
                              21.20  ridge

Every beam, banner, chandelier and tapestry has a named bearing: tie beams sit
on the wall plates, banners hang from the tie beams, chandeliers hang from the
tie beams on chains, tapestries from rails let into the walls, flags from
brackets bolted to the wall.  Nothing floats.
"""

import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import bmesh
import bpy
from mathutils import Matrix, Vector

import hd_common as H
import medkit as K
from medkit import T_at as Ts

OUT = os.path.join(H.OUT_DIR, "cint")
TAU = math.pi * 2.0

# ---------------------------------------------------------------------------
# master dimensions
# ---------------------------------------------------------------------------
HALL_W = 30.0                 # outer footprint, x +-15
HALL_L = 52.0                 # outer footprint, y +-26
WALL_T = 1.6                  # outer wall thickness
X_IN = HALL_W * 0.5 - WALL_T  # 13.40 inner face of the aisle wall
XARC = 9.35                   # centre of the arcade wall
T_ARC = 1.10                  # arcade wall thickness
XNAVE = XARC - T_ARC * 0.5    # 8.80 nave face
XAIS = XARC + T_ARC * 0.5     # 9.90 aisle face
AISLE_W = X_IN - XAIS         # 3.50 clear aisle width

Y_S, Y_N = -26.0, 26.0
Y_BACK = 24.40                # inner face of the north (throne) wall
Y_CHOR = 16.40                # chancel arch
Y_SCREEN = -17.20             # narthex screen arch
BAY = 5.60
NBAY = 6
PIERS = [Y_SCREEN + i * BAY for i in range(NBAY + 1)]

Z_DADO = 1.30                 # 勒脚 / dado top
Z_AIS_SILL = 2.55
Z_AIS_TOP = 6.00
Z_VAULT_SPRING = 7.60
Z_CAP = 7.60                  # abacus top = arch springing
Z_ARC_APEX = 9.80
Z_VAULT_CROWN = 10.20
Z_CLER_SILL = 12.30
Z_CLER_TOP = 16.05
Z_PLATE = 16.40
Z_RIDGE = 21.20
Z_TIE = 16.55                 # underside of the tie beams
HS_ARC = (BAY - 1.55) * 0.5   # 2.025 clear half span of an arcade arch
RISE_ARC = 2.20

# dais / throne
Z_DAIS = 1.12
N_STEP = 7
Y_DAIS = 18.40                # top of the last step / front of the platform
Y_STEP0 = Y_DAIS - N_STEP * 0.32
DAIS_HW = 5.00                # platform half width (10 m)
STEP_HW = 4.20                # stair half width (8.4 m)

MAT_KEYS = (
    "stone", "stone_light", "stone_dark", "stone_floor", "stone_shadow",
    "wood", "wood_dark", "wood_beam", "plaster",
    "iron", "gold", "brass",
    "glass_gold", "glass_blue", "glass_red", "glass_pale",
    "carpet_red", "carpet_blue", "tapestry", "tapestry_blue",
    "cloth_red", "cloth_blue", "cloth_gold", "cloth_white",
    "candle", "fire", "coal",
)

RZF = {"+y": 0.0, "-y": math.pi, "+x": -math.pi * 0.5, "-x": math.pi * 0.5}


def WF(x, y, z, n="+y"):
    """Frame on a wall face: local +X runs along the wall, local +Y is OUTWARD."""
    return Ts(x, y, z, rz=RZF[n])


# ---------------------------------------------------------------------------
# tiny local toolkit
# ---------------------------------------------------------------------------
def bx(name, T, size, mat, bev=0.0):
    return K.box(name, T, size, mat, bev=bev)


def cyl(name, T, r, h, mat, seg=20, r2=None, bev=0.0):
    ob = K.cyl(name, T, r, h, mat, seg=seg, r2=r2)
    if bev:
        K.bevel(ob, bev, 2, 40.0)
    return ob


def _recalc(ob):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return ob


def prism(name, pts, mat, a0, a1, axis="y", bev=0.0, T=None):
    """Extrude a 2D polygon along `axis` between a0 and a1.

    pts are (u, v) in the plane perpendicular to `axis`:
        axis 'x' -> (y, z)   axis 'y' -> (x, z)   axis 'z' -> (x, y)
    Normals are recalculated, so the winding of `pts` does not matter.
    """
    n = len(pts)
    verts = []
    for d in (a0, a1):
        for (u, v) in pts:
            if axis == "x":
                verts.append((d, u, v))
            elif axis == "y":
                verts.append((u, d, v))
            else:
                verts.append((u, v, d))
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    ob = K.mesh_obj(name, verts, faces)
    if mat is not None:
        K.assign(ob, mat)
    _recalc(ob)
    if T is not None:
        ob.data.transform(T)
    if bev:
        K.bevel(ob, bev, 2, 40.0)
    return ob


def quad_strip(name, rows, mat, closed=False, smooth=False):
    """Mesh from `rows` of equal-length point lists (each row a list of xyz)."""
    nr, nc = len(rows), len(rows[0])
    verts = [tuple(p) for row in rows for p in row]
    faces = []
    for i in range(nr - 1):
        for j in range(nc - 1 + (1 if closed else 0)):
            j2 = (j + 1) % nc
            faces.append((i * nc + j, i * nc + j2,
                          (i + 1) * nc + j2, (i + 1) * nc + j))
    ob = K.mesh_obj(name, verts, faces)
    if mat is not None:
        K.assign(ob, mat)
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def torus(name, T, R, r, mat, seg=24, ring=6):
    rows = []
    for i in range(seg + 1):
        a = TAU * i / seg
        row = []
        for j in range(ring + 1):
            b = TAU * j / ring
            rr = R + r * math.cos(b)
            row.append((rr * math.cos(a), rr * math.sin(a), r * math.sin(b)))
        rows.append(row)
    ob = quad_strip(name, rows, mat, smooth=True, closed=False)
    _recalc(ob)
    ob.data.transform(T)
    return ob


# ---------------------------------------------------------------------------
# arches
# ---------------------------------------------------------------------------
def arch_pts(hs, rise, n=14):
    """From (-hs, 0) over the apex (0, rise) back to (hs, 0): two-centred arch."""
    hs = max(1e-4, float(hs))
    rise = max(1e-4, float(rise))
    c = (rise * rise - hs * hs) / (2.0 * hs)          # centre offset
    R = c + hs                                        # radius
    ta = math.acos(max(-1.0, min(1.0, -c / R)))       # angle at the apex
    m = max(2, n // 2)
    half = []
    for i in range(m + 1):
        th = math.pi + (ta - math.pi) * (i / float(m))
        half.append((c + R * math.cos(th), R * math.sin(th)))
    half[-1] = (0.0, rise)
    out = list(half)
    for (x, z) in reversed(half[:-1]):
        out.append((-x, z))
    return out


def hole_pts(hs, z_bot, z_spring, z_apex, n=14):
    """Polygon of a doorway shaped opening: sill, two jambs, pointed head."""
    rise = max(1e-3, z_apex - z_spring)
    pts = [(-hs, z_bot)]
    for (x, z) in arch_pts(hs, rise, n):
        pts.append((x, z_spring + z))
    pts.append((hs, z_bot))
    return pts


def spandrel_pts(hw, z0, z1, hs, z_spring, rise, n=14):
    """Rectangle hw wide from z0 to z1 with an arched bite out of its base."""
    pts = [(-hw, z0), (-hs, z0)]
    for (x, z) in arch_pts(hs, rise, n):
        pts.append((x, z_spring + z))
    pts += [(hs, z0), (hw, z0), (hw, z1), (-hw, z1)]
    return pts


def arch_normals(pts):
    seg = []
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dz = pts[i + 1][1] - pts[i][1]
        L = math.hypot(dx, dz) or 1.0
        seg.append((-dz / L, dx / L))
    nrm = []
    for i in range(len(pts)):
        if i == 0:
            nrm.append(seg[0])
        elif i == len(pts) - 1:
            nrm.append(seg[-1])
        else:
            vx = seg[i - 1][0] + seg[i][0]
            vz = seg[i - 1][1] + seg[i][1]
            L = math.hypot(vx, vz) or 1.0
            nrm.append((vx / L, vz / L))
    return nrm


def voussoirs(name, T, hs, z_spring, rise, ring, a0, a1, mat, n=14, bev=0.012,
              keystone=True, key_mat=None):
    """Voussoir blocks on the intrados of a two-centred arch.

    T is the bay frame (local +X along the wall, +Y through it, +Z up).
    a0..a1 is the extrusion range along local Y.
    """
    pts = [(x, z_spring + z) for (x, z) in arch_pts(hs, rise, n)]
    nrm = arch_normals(pts)
    out = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        q0 = (p0[0] + nrm[i][0] * ring, p0[1] + nrm[i][1] * ring)
        q1 = (p1[0] + nrm[i + 1][0] * ring, p1[1] + nrm[i + 1][1] * ring)
        out.append(prism("%s_vs%02d" % (name, i), [p0, p1, q1, q0], mat,
                         a0, a1, axis="y", bev=bev, T=T))
    if keystone:
        km = key_mat or mat
        # a keystone is taller than the ring and slightly wider than one voussoir
        w = (pts[len(pts) // 2 + 1][0] - pts[len(pts) // 2 - 1][0]) * 0.75
        zc = z_spring + rise
        out.append(bx("%s_key" % name, T @ Ts(0.0, (a0 + a1) * 0.5, zc - 0.10),
                      (max(0.34, w), (a1 - a0) + 0.10, ring * 1.55), km, bev=0.02))
        out.append(bx("%s_keycap" % name, T @ Ts(0.0, (a0 + a1) * 0.5,
                                                 zc - 0.10 + ring * 0.78),
                      (max(0.26, w * 0.62), (a1 - a0) + 0.16, 0.10), km, bev=0.02))
    return out


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------
_DEF = {}


def _lit_glass(key, hexcol, glow, strength, trans):
    if key in K._MAT_CACHE:
        return K._MAT_CACHE[key]
    m, b = K._new_mat(key)
    K._put(b, ["Base Color"], K.c(hexcol))
    K._put(b, ["Roughness"], 0.22)
    K._put(b, ["Metallic"], 0.0)
    K._put(b, ["Emission Color"], K.c(glow))
    K._put(b, ["Emission Strength"], strength)
    if trans > 0.0:
        nt = m.node_tree
        out = None
        for nd in nt.nodes:
            if nd.type == "OUTPUT_MATERIAL":
                out = nd
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs[0].default_value = trans
        nt.links.new(b.outputs[0], mx.inputs[1])
        nt.links.new(tr.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs["Surface"])
    K._MAT_CACHE[key] = m
    return m


def _clay(key, hexcol, rough=0.9, sheen=0.0, bump=0.0):
    if key in K._MAT_CACHE:
        return K._MAT_CACHE[key]
    m, b = K._new_mat(key)
    K._put(b, ["Base Color"], K.c(hexcol))
    K._put(b, ["Roughness"], rough)
    K._put(b, ["Metallic"], 0.0)
    if sheen:
        K._put(b, ["Sheen Weight"], sheen)
    K._MAT_CACHE[key] = m
    return m


def _emissive(key, hexcol, strength):
    if key in K._MAT_CACHE:
        return K._MAT_CACHE[key]
    m, b = K._new_mat(key)
    K._put(b, ["Base Color"], K.c(hexcol))
    K._put(b, ["Emission Color"], K.c(hexcol))
    K._put(b, ["Emission Strength"], strength)
    K._put(b, ["Roughness"], 0.5)
    K._MAT_CACHE[key] = m
    return m


def make_mats():
    """Preview materials.  build() falls back to these for any missing key."""
    M = {}
    M["stone"] = K.mat_stone("cint_stone", base="#9b8f76", dark="#4f4839",
                             light="#bcab8b", scale=1.9)
    M["stone_light"] = K.mat_stone("cint_stone_l", base="#b3a689", dark="#6d6453",
                                   light="#cdc0a0", scale=2.4)
    M["stone_dark"] = K.mat_stone("cint_stone_d", base="#6a6254", dark="#37322a",
                                  light="#8a8170", scale=3.0)
    M["stone_floor"] = K.mat_flag("cint_floor", base="#8e8676", dark="#4b463c",
                                  light="#b0a795")
    M["stone_shadow"] = K.mat_stone("cint_shadow", base="#1c1915", dark="#0c0b09",
                                    light="#2a251f", scale=6.0)
    M["wood"] = K.mat_wood("cint_oak", base="#4e3524", light="#77522f", scale=16.0)
    M["wood_beam"] = K.mat_wood("cint_beam", base="#5d4028", light="#8a6035",
                                scale=9.0)
    M["wood_dark"] = K.mat_wood("cint_timber_dark", base="#33210f", light="#4b3119",
                                scale=12.0)
    M["plaster"] = K.mat_plaster("cint_plaster", base="#d8cbb0", dirt="#b9a98c",
                                 scale=4.0)
    M["iron"] = K.mat_metal("cint_iron", base="#2f2e33", rough=0.46)
    M["gold"] = K.mat_gold("cint_gold", base="#cb9f34")
    M["brass"] = K.mat_gold("cint_brass", base="#a8781f")
    M["glass_gold"] = _lit_glass("cint_glass_g", "#4a3410", "#f0b64a", 2.0, 0.26)
    M["glass_blue"] = _lit_glass("cint_glass_b", "#101c40", "#2f4f9e", 1.5, 0.24)
    M["glass_red"] = _lit_glass("cint_glass_r", "#3a0a0d", "#9e2b25", 1.5, 0.24)
    M["glass_pale"] = _lit_glass("cint_glass_p", "#4a5560", "#b9cfe4", 2.2, 0.34)
    M["carpet_red"] = K.mat_cloth("cint_carpet_r", "#6e1a24", rough=0.92)
    M["carpet_blue"] = K.mat_cloth("cint_carpet_b", "#1d2a55", rough=0.92)
    M["tapestry"] = K.mat_cloth("cint_tap", "#6d2a33", rough=0.95)
    M["tapestry_blue"] = K.mat_cloth("cint_tap_b", "#25315c", rough=0.95)
    M["cloth_red"] = K.mat_cloth("cint_cloth_r", "#8e2229")
    M["cloth_blue"] = K.mat_cloth("cint_cloth_b", "#20305c")
    M["cloth_gold"] = K.mat_cloth("cint_cloth_g", "#c39a2c")
    M["cloth_white"] = K.mat_cloth("cint_cloth_w", "#d8cfba")
    M["candle"] = _clay("cint_candle", "#e6d9b8", rough=0.62)
    M["fire"] = _emissive("cint_fire", "#ff8a2a", 9.0)
    M["coal"] = _clay("cint_coal", "#2a1a12", rough=0.95)
    return M


def _m(MAT, key):
    """Material lookup that survives a caller MAT lacking one of our keys."""
    if MAT is not None:
        got = MAT.get(key)
        if got is not None:
            return got
    if not _DEF:
        _DEF.update(make_mats())
    return _DEF[key]
