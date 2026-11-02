"""hd_gate.py - the royal city gate of the capital (Asura).

The player walks through it; the camera flies over it.  Local frame:

    origin  = centre of the threshold (the middle of the gate passage, ground)
    +Y      = OUT of the city (the road side, where the barbican and moat are)
    -Y      = INTO the city (wall-walk, stairs, guardhouse)
    +Z      = up, ground at z = 0

Everything is parametric; `build(MAT, rng)` returns the object list and
`preview()` renders a fixed set of views to Blender/renders/kingdom/.

Run:
    blender -b --factory-startup --python hd_gate.py
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import bpy
from mathutils import Matrix, Vector

import hd_common as H
import medkit as K
from medkit import T_at as Ts, box, cyl, cone, sphere

OUT_DIR = r"E:\My World\Blender\renders\kingdom"
PI = math.pi
TAU = math.tau

# --------------------------------------------------------------------------
#  master dimensions (metres)
# --------------------------------------------------------------------------
R_PASS = 2.75          # half width of the passage  (5.50 m wide)
Z_SPRING = 4.25        # springing of the barrel vault
Z_CROWN = Z_SPRING + R_PASS          # 7.00 m to the crown
GH_W = 13.2            # gatehouse half width
GH_D = 6.6             # gatehouse half depth  (13.2 m thick)
GH_H = 19.6            # gatehouse wall head / wall-walk floor
FP_W = 6.50            # forebuilding (porch block) half width
FP_Y0 = 6.35           # where the forebuilding starts, inside the gatehouse face
FP_Y1 = 9.25           # its front face: the arch stands 1.25 m proud of the drums
FP_H = 12.20           # its height (corbelled brattice on top)
TOW_X = 14.2           # tower centres
TOW_R = 8.0            # tower radius
TOW_TOP = 26.4         # top of the tower shaft (before the machicolation)
WALK = TOW_TOP + 0.55  # tower wall-walk level
WALL_H = 12.6          # curtain wall height
WALL_T = 1.7           # curtain wall half thickness
CURT_END = 28.2        # outer end of the curtain wall stub
MOAT_Y0, MOAT_Y1 = 15.0, 26.0
MOAT_Z = -1.25
MOAT_BOT = -2.75
BR_Y0, BR_Y1 = 13.0, 26.8
BR_HW = 3.7
BARB_X = 8.9
BARB_Y = 26.6          # barbican tower centres (the D's chord plane)
BARB_R = 4.1
BARB_H = 11.6
ROAD_HW = 3.5


def RotX(a):
    return Matrix.Rotation(a, 4, "X")


def RotY(a):
    return Matrix.Rotation(a, 4, "Y")


def RotZ(a):
    return Matrix.Rotation(a, 4, "Z")


def basis_T(x, y, z, p):
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0] = x[i]
        m[i][1] = y[i]
        m[i][2] = z[i]
        m[i][3] = p[i]
    return m


def lerp(a, b, t):
    return a + (b - a) * t


# --------------------------------------------------------------------------
#  materials
# --------------------------------------------------------------------------
def _glow(name, base, emis, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = K.c(base, 1.0)
            n.inputs["Roughness"].default_value = 0.5
            if "Emission Color" in n.inputs:
                n.inputs["Emission Color"].default_value = K.c(emis, 1.0)
                n.inputs["Emission Strength"].default_value = strength
    return m


def materials():
    M = {}
    M["stone"] = K.mat_stone()
    M["stone_warm"] = K.mat_stone("stone_sand", base="#8d8168", dark="#5b5342",
                                  light="#a89b7f", scale=2.0)
    M["stone_dark"] = K.mat_stone("stone_dark", base="#5c554a", dark="#332f28",
                                  light="#726a5c", scale=2.7)
    M["stone_pale"] = K.mat_stone("stone_pale", base="#a49a86", dark="#6f6758",
                                  light="#c0b7a2", scale=2.2)
    M["wood"] = K.mat_wood()
    M["wood_dark"] = K.mat_wood("timber_dark", base="#3a2517", light="#543823", scale=12)
    M["tile"] = K.mat_tile()
    M["tile_blue"] = K.mat_tile("roof_blue", base="#3f5570", dark="#28374b",
                                light="#55708f")
    M["slate"] = K.mat_tile("roof_slate", base="#4a5560", dark="#333c46",
                            light="#5f6d7a")
    M["glass"] = K.mat_glass("glass_window", "#7d97a8")
    M["iron"] = K.mat_metal()
    M["iron_dark"] = K.mat_metal("iron_dark", "#2a292e", 0.55)
    M["gold"] = K.mat_gold()
    M["plaster"] = K.mat_plaster()
    M["banner_red"] = K.mat_cloth("banner_red", "#8e2b26")
    M["banner_blue"] = K.mat_cloth("banner_blue", "#263a63")
    M["flag"] = K.mat_flag()
    M["cobble"] = K.mat_cobble()
    M["water"] = K.mat_water("water_moat", "#33503f")
    M["grass"] = K.mat_earth("grass", base="#5f6a48", dark="#414b32", scale=3.5, patch=0.55)
    M["glow"] = _glow("torch_glow", "#ffb257", "#ff9a3c", 12.0)
    M["lamp"] = _glow("lamp_glow", "#ffe0a8", "#ffd27a", 4.0)
    return M


def make_materials():
    """Palette factory for the capital integrator: every key used by build()."""
    return materials()


MAT_KEYS = ("stone", "stone_warm", "stone_dark", "stone_pale", "wood", "wood_dark",
            "tile", "tile_blue", "slate", "glass", "iron", "iron_dark", "gold",
            "plaster", "banner_red", "banner_blue", "flag", "cobble", "water",
            "grass", "glow", "lamp")


def _palette(MAT):
    """Fill in any key the caller's palette is missing, never override one it has."""
    if not MAT:
        return materials()
    out = materials()
    out.update(dict(MAT))
    return out


# --------------------------------------------------------------------------
#  low level mesh helpers
# --------------------------------------------------------------------------
def _blk(v, f, x0, x1, y0, y1, z0, z1):
    i = len(v)
    v.extend([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
              (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
    f.extend([(i, i + 3, i + 2, i + 1), (i + 4, i + 5, i + 6, i + 7),
              (i, i + 1, i + 5, i + 4), (i + 1, i + 2, i + 6, i + 5),
              (i + 2, i + 3, i + 7, i + 6), (i + 3, i, i + 4, i + 7)])


def _mk(name, verts, faces, mat, T=None, smooth=False):
    if T is not None:
        verts = [T @ Vector(v) for v in verts]
    ob = K.mesh_obj(name, [tuple(v) for v in verts], faces, smooth=smooth)
    if mat is not None:
        K.assign(ob, mat)
    return ob


def ashlar(name, T, w, h, mat, rng, bw=1.42, bh=0.64, gap=0.045, proud=0.05,
           z0=0.0, y_in=-0.07):
    """Proud dressed stones over a w x h face lying in the local XZ plane.

    Local +Y is the outward normal; stones stand `proud` out of the wall and
    the joints between them show the (darker) wall behind.  One mesh object.
    """
    v, f = [], []
    z = 0.0
    row = 0
    while z < h - 0.06:
        hh = min(bh, h - z)
        x = -w * 0.5 - (bw * 0.45 if row % 2 else 0.0) - rng.uniform(0.0, 0.3)
        while x < w * 0.5 - 0.05:
            ww = bw * rng.uniform(0.78, 1.28)
            a = max(x, -w * 0.5)
            b = min(x + ww, w * 0.5)
            if b - a > 0.16:
                pr = proud * rng.uniform(0.75, 1.15)
                _blk(v, f, a + gap * 0.5, b - gap * 0.5, y_in, pr,
                     z0 + z + gap * 0.5, z0 + z + hh - gap * 0.5)
            x += ww
        z += hh
        row += 1
    return [_mk(name, v, f, mat, T)]


def ring_stones(name, T, r, z, n, h, mat_a, mat_b, rng, thick=0.055, gap=0.028,
                a0=0.0, a1=TAU):
    """One course of proud stones around a cylinder -> two mesh objects."""
    va, fa, vb, fb = [], [], [], []
    seg = (a1 - a0) / n
    # stagger alternate courses by half a stone so the vertical joints do not
    # line up into continuous seams down the drum
    ph = gap * 0.5 / r + (seg * 0.5 if int(round(z / 0.64)) % 2 else 0.0)
    for i in range(n):
        off = ph + rng.uniform(-0.002, 0.002)
        s0 = a0 + i * seg + off
        s1 = a0 + (i + 1) * seg - gap * 0.5 / r + off
        zz = z + rng.uniform(-0.006, 0.006)
        th = thick * rng.uniform(0.8, 1.2)
        vv = []
        for (rr, aa) in ((r, s0), (r + th, s0), (r + th, s1), (r, s1)):
            for zs in (zz, zz + h):
                vv.append((math.cos(aa) * rr, math.sin(aa) * rr, zs))
        vv = [T @ Vector(p) for p in vv]
        if i % 2 == 0:
            base = len(va)
            va.extend(vv)
            fa.extend([(base + 1, base + 2, base + 6, base + 5),
                       (base + 0, base + 4, base + 7, base + 3),
                       (base + 0, base + 1, base + 5, base + 4),
                       (base + 3, base + 7, base + 6, base + 2),
                       (base + 4, base + 5, base + 6, base + 7),
                       (base + 0, base + 3, base + 2, base + 1)])
        else:
            base = len(vb)
            vb.extend(vv)
            fb.extend([(base + 1, base + 2, base + 6, base + 5),
                       (base + 0, base + 4, base + 7, base + 3),
                       (base + 0, base + 1, base + 5, base + 4),
                       (base + 3, base + 7, base + 6, base + 2),
                       (base + 4, base + 5, base + 6, base + 7),
                       (base + 0, base + 3, base + 2, base + 1)])
    out = []
    if fa:
        out.append(_mk(name + "_a", va, fa, mat_a))
    if fb:
        out.append(_mk(name + "_b", vb, fb, mat_b))
    return out


def ring_wall(name, T, r_in, r_out, z0, z1, mat, seg=64, batter=0.0):
    """Solid annulus wall (outer, inner, top, bottom).  `batter` widens the top."""
    prof = [(r_in, z0), (r_out, z0), (r_out + batter, z1), (r_in, z1)]
    return H.lathe(name, prof, mat, seg=seg, T=T, close_bottom=False, close_top=False)


def arch_tube(name, T, r, zc, y0, y1, thick, mat, seg=26, a0=0.0, a1=PI):
    """Solid half-tube: an arch soffit of radius r centred on (0, zc) in local XZ,
    extruded along local Y from y0 to y1."""
    v, f = [], []
    n = seg + 1
    for y in (y0, y1):
        for i in range(n):
            a = lerp(a0, a1, i / seg)
            v.append((math.cos(a) * r, y, zc + math.sin(a) * r))
    for y in (y0, y1):
        for i in range(n):
            a = lerp(a0, a1, i / seg)
            v.append((math.cos(a) * (r + thick), y, zc + math.sin(a) * (r + thick)))
    base = 2 * n
    for i in range(seg):
        f.append((i, i + 1, n + i + 1, n + i))                       # inner
        f.append((base + i, base + n + i, base + n + i + 1, base + i + 1))  # outer
    for o in (0, n):
        for i in range(seg):
            f.append((o + i, base + o + i, base + o + i + 1, o + i + 1))
    return _mk(name, v, f, mat, T)


def arch_notch_poly(w, h, r, zs, seg=26):
    """Rectangle with a round-headed doorway bitten out of the bottom centre."""
    pts = [(w, 0.0), (w, h), (-w, h), (-w, 0.0), (-r, 0.0), (-r, zs)]
    for i in range(1, seg):
        a = PI - PI * i / seg
        pts.append((math.cos(a) * r, zs + math.sin(a) * r))
    pts += [(r, zs), (r, 0.0)]
    return pts


def bridge_notch_poly(y0, y1, ztop, zbot, r, zc, half_span, seg=22):
    """Bridge body: a slab with a segmental arch bitten out of its underside."""
    a_spring = math.asin(max(-1.0, min(1.0, (zbot - zc) / r)))
    pts = [(y1, ztop), (y0, ztop), (y0, zbot)]
    for i in range(seg + 1):
        a = lerp(PI - a_spring, a_spring, i / seg)
        pts.append((math.cos(a) * r, zc + math.sin(a) * r))
    pts.append((y1, zbot))
    return pts


def arch_band(name, T, r_in, r_out, y0, y1, mat, seg=28, a0=0.0, a1=PI, zc=0.0):
    """Solid half-annulus band in the local XZ plane, extruded along Y.

    Used behind arch orders so the joints between voussoirs show stone, not
    the black inside of the vault tube."""
    pts = []
    for i in range(seg + 1):
        a = lerp(a0, a1, i / seg)
        pts.append((math.cos(a) * r_out, zc + math.sin(a) * r_out))
    for i in range(seg + 1):
        a = lerp(a1, a0, i / seg)
        pts.append((math.cos(a) * r_in, zc + math.sin(a) * r_in))
    return H.prism(name, T @ Ts(0, (y0 + y1) * 0.5, 0), pts, abs(y1 - y0), mat, axis="y")


def voussoir_ring(name, T, r_in, depth_ring, n, mat, y=0.0, zc=0.0,
                  a0=0.0, a1=PI, thick=0.10, gap=0.0):
    """Radial arch stones around a half circle in the local XZ plane."""
    v, f = [], []
    g = (gap / max(r_in, 0.2)) * 0.5
    for i in range(n):
        aa = lerp(a0, a1, i / n) + g
        ab = lerp(a0, a1, (i + 1) / n) - g
        rr = r_in
        for (ang, rad) in ((aa, rr), (aa, rr + depth_ring), (ab, rr + depth_ring), (ab, rr)):
            for yy in (-thick * 0.5, thick * 0.5):
                v.append((math.cos(ang) * rad, y + yy, zc + math.sin(ang) * rad))
    for i in range(n):
        b = i * 8
        f.extend([(b + 0, b + 1, b + 5, b + 4),
                  (b + 2, b + 6, b + 7, b + 3),
                  (b + 0, b + 4, b + 6, b + 2),
                  (b + 1, b + 3, b + 7, b + 5),
                  (b + 4, b + 5, b + 7, b + 6),
                  (b + 0, b + 2, b + 3, b + 1)])
    return _mk(name, v, f, mat, T)


def radial_T(x0, y0, z0, ang, r, y=0.0, zc=0.0):
    """Matrix whose local X is radial and local Z tangential, at angle `ang`."""
    ca, sa = math.cos(ang), math.sin(ang)
    R = Matrix(((ca, 0.0, -sa, 0.0), (0.0, 1.0, 0.0, 0.0),
                (sa, 0.0, ca, 0.0), (0.0, 0.0, 0.0, 1.0)))
    return Ts(x0 + ca * r, y0 + y, z0 + zc + sa * r) @ R


def face_T(x0, y0, z0, ang, r, lift=0.0):
    """Matrix whose local +Y points outward at angle `ang` on a drum."""
    return Ts(x0 + math.cos(ang) * (r + lift), y0 + math.sin(ang) * (r + lift), z0) \
        @ RotZ(ang - PI * 0.5)


def rcrenel(name, T, r, z, n, merlon=1.05, gap=0.55, h=1.25, depth=0.62,
            mat=None, a0=0.0, a1=TAU):
    """Battlement merlons around a circle as real rectangular blocks (one mesh)."""
    v, f = [], []
    step = (a1 - a0) / n
    for i in range(n):
        a = a0 + step * (i + 0.5)
        ca, sa = math.cos(a), math.sin(a)
        ux, uy = ca, sa          # radial
        tx, ty = -sa, ca         # tangential
        rr = r - depth * 0.5
        cx, cy = ux * rr, uy * rr
        hw, hd = merlon * 0.5, depth * 0.5
        b = len(v)
        for (dt, du) in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)):
            for zz in (z, z + h):
                v.append((cx + tx * dt + ux * du, cy + ty * dt + uy * du, zz))
        f.extend([(b + 1, b + 2, b + 6, b + 5), (b + 0, b + 4, b + 7, b + 3),
                  (b + 0, b + 1, b + 5, b + 4), (b + 3, b + 7, b + 6, b + 2),
                  (b + 4, b + 5, b + 6, b + 7), (b + 0, b + 3, b + 2, b + 1)])
    if not f:
        return []
    return [_mk(name, v, f, mat, T)]


def corbel_ring(name, T, r, z, n, mat, out=1.45, h=1.2, w=0.44, a0=0.0, a1=TAU,
                taper=0.35):
    """Ring of tapered corbels carrying a machicolation gallery (one mesh)."""
    v, f = [], []
    step = TAU / n
    for i in range(n):
        a = a0 + step * (i + 0.5)
        if a > a1:
            continue
        for (aa, rr) in ((a - w * 0.5 / r, r - 0.05), (a - w * 0.5 / r, r + out),
                         (a + w * 0.5 / r, r + out), (a + w * 0.5 / r, r - 0.05)):
            v.append((math.cos(aa) * rr, math.sin(aa) * rr, z))
        for (aa, rr) in ((a - w * 0.5 / r, r - 0.05), (a - w * 0.5 / r, r + out * taper),
                         (a + w * 0.5 / r, r + out * taper), (a + w * 0.5 / r, r - 0.05)):
            v.append((math.cos(aa) * rr, math.sin(aa) * rr, z + h))
        b = len(v) - 8
        f.extend([(b + 1, b + 2, b + 6, b + 5), (b + 0, b + 4, b + 7, b + 3),
                  (b + 0, b + 1, b + 5, b + 4), (b + 3, b + 7, b + 6, b + 2),
                  (b + 4, b + 5, b + 6, b + 7), (b + 0, b + 3, b + 2, b + 1)])
    if not f:
        return []
    return [_mk(name, v, f, mat, T)]


def torus(name, T, R, r, mat, seg=10, ring=5):
    v, f = [], []
    for i in range(seg):
        a = TAU * i / seg
        for j in range(ring):
            b = TAU * j / ring
            v.append(((R + r * math.cos(b)) * math.cos(a),
                      (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
    for i in range(seg):
        for j in range(ring):
            a0 = i * ring + j
            a1 = i * ring + (j + 1) % ring
            b0 = ((i + 1) % seg) * ring + j
            b1 = ((i + 1) % seg) * ring + (j + 1) % ring
            f.append((a0, b0, b1, a1))
    return _mk(name, v, f, mat, T, smooth=True)


def chain(name, p0, p1, sag, mat, links=11, R=0.075, r=0.026, up=Vector((0, 0, 1))):
    """A sagging chain of alternating torus links between two points."""
    p0, p1 = Vector(p0), Vector(p1)
    out = []

    def at(t):
        p = p0.lerp(p1, t)
        p.z -= sag * math.sin(PI * t)
        return p

    for i in range(links):
        t = (i + 0.5) / links
        p = at(t)
        d = (at(min(1.0, t + 0.02)) - at(max(0.0, t - 0.02)))
        if d.length < 1e-6:
            d = (p1 - p0)
        d.normalize()
        n1 = d.cross(up)
        if n1.length < 1e-4:
            n1 = d.cross(Vector((1.0, 0.0, 0.0)))
        n1.normalize()
        n2 = d.cross(n1).normalized()
        zax = n1 if i % 2 == 0 else n2
        xax = d
        yax = zax.cross(xax).normalized()
        T = basis_T(xax, yax, zax, p)
        out.append(torus(name + "_l%d" % i, T, R, r, mat, seg=8, ring=4))
    return out


def slit(name, T, h, mat, dark, w=0.30, sh=0.46):
    """Arrow loop: a dark slot sunk in a proud dressed surround."""
    p = [box(name + "_s", T @ Ts(0, 0.045, h * 0.5), (w, 0.10, h + 0.20), mat, bev=0.012),
         box(name + "_d", T @ Ts(0, 0.10, h * 0.5), (w * 0.42, 0.04, h), dark)]
    p.append(box(name + "_l", T @ Ts(0, 0.10, h * 0.5 + h * 0.18), (w * 0.16, 0.05, sh * 0.6), dark))
    return p


def flagstones(name, T, w, y0, y1, mat, rng, cw=1.15, cl=0.85, gap=0.03, h=0.12,
               rough=0.012, y_axis=True):
    """Coursed flagstone paving in the local XY plane, top at z=0 (one mesh)."""
    v, f = [], []
    y = y0
    row = 0
    while y < y1 - 0.05:
        ll = min(cl, y1 - y)
        x = -w * 0.5 - (cw * 0.5 if row % 2 else 0.0) - rng.uniform(0, 0.2)
        while x < w * 0.5 - 0.05:
            ww = cw * rng.uniform(0.75, 1.3)
            a = max(x, -w * 0.5)
            b = min(x + ww, w * 0.5)
            if b - a > 0.12:
                zz = -h + rng.uniform(-rough, rough)
                _blk(v, f, a + gap * 0.5, b - gap * 0.5, y + gap * 0.5, y + ll - gap * 0.5,
                     zz, 0.0)
            x += ww
        y += ll
        row += 1
    return [_mk(name, v, f, mat, T)]


def crenel_line(name, T, length, mat, merlon=1.0, gap=0.55, h=1.25, depth=0.62,
                z=0.0, axis="x"):
    """Straight battlement row (one mesh)."""
    v, f = [], []
    pitch = merlon + gap
    n = max(1, int(length / pitch))
    total = n * pitch - gap
    x0 = -total * 0.5 + merlon * 0.5
    for i in range(n):
        x = x0 + i * pitch
        if axis == "x":
            _blk(v, f, x - merlon * 0.5, x + merlon * 0.5, -depth * 0.5, depth * 0.5, z, z + h)
        else:
            _blk(v, f, -depth * 0.5, depth * 0.5, x - merlon * 0.5, x + merlon * 0.5, z, z + h)
    return [_mk(name, v, f, mat, T)]


# --------------------------------------------------------------------------
#  ornament
# --------------------------------------------------------------------------
def coat_of_arms(name, T, r, MAT):
    """Carved heraldic roundel in relief (local +Y is out of the wall)."""
    p = []
    sw, pale, blue, gold = MAT["stone_warm"], MAT["stone_pale"], MAT["banner_blue"], MAT["gold"]
    # moulded stone frame (lathe, axis turned to +Y)
    prof = [(r * 1.02, -0.05), (r * 1.21, -0.05), (r * 1.21, 0.09), (r * 1.13, 0.19),
            (r * 1.02, 0.19), (r * 1.02, 0.11), (r * 1.09, 0.09), (r * 1.09, 0.01),
            (r * 1.02, 0.01)]
    p.append(H.lathe(name + "_fr", prof, sw, seg=44, T=T @ RotX(-PI * 0.5),
                     close_bottom=False, close_top=False))
    # recessed field
    p.append(cyl(name + "_fd", T @ Ts(0, 0.05, 0) @ RotX(PI * 0.5), r * 1.02, 0.14, pale, seg=44))
    # four quarters, blue on the diagonals
    for i in range(4):
        a0 = i * PI * 0.5 + 0.02
        a1 = a0 + PI * 0.5 - 0.04
        pts = [(0.0, 0.0)]
        for k in range(9):
            a = lerp(a0, a1, k / 8.0)
            pts.append((math.cos(a) * r * 0.99, math.sin(a) * r * 0.99))
        p.append(H.prism(name + "_q%d" % i, T @ Ts(0, 0.13, 0), pts, 0.08,
                         blue if i % 2 == 0 else pale, axis="y"))
    # raised cross over the quarters
    p.append(box(name + "_cx", T @ Ts(0, 0.18, 0), (r * 1.98, 0.07, 0.26), sw, bev=0.012))
    p.append(box(name + "_cz", T @ Ts(0, 0.18, 0), (0.26, 0.07, r * 1.98), sw, bev=0.012))
    p.append(cyl(name + "_hub", T @ Ts(0, 0.23, 0) @ RotX(PI * 0.5), 0.23, 0.09, gold, seg=18))
    # crown resting on the frame
    cz = r * 1.23
    p.append(torus(name + "_crb", T @ Ts(0, 0.10, cz) @ RotX(PI * 0.5), 0.29, 0.065, gold,
                   seg=18, ring=5))
    for i in range(3):
        a = -0.62 + 0.62 * i
        p.append(cone(name + "_crp%d" % i, T @ Ts(math.sin(a) * 0.30, 0.10, cz + 0.30),
                      0.085, 0.26, gold, seg=6))
        p.append(sphere(name + "_crj%d" % i, T @ Ts(math.sin(a) * 0.30, 0.10, cz + 0.46),
                        0.052, gold, seg=8, ring=5))
    return p


def wall_banner(name, T, w, h, cloth, gold, iron):
    """Vertical banner hanging flat on a wall; T origin at the top centre."""
    p = []
    p.append(cyl(name + "_rod", T @ Ts(0, 0.19, 0) @ RotY(PI * 0.5), 0.05, w + 0.62, iron, seg=10))
    for s in (-1, 1):
        p.append(sphere(name + "_fin%d" % s, T @ Ts(s * (w * 0.5 + 0.34), 0.19, 0), 0.10,
                        gold, seg=10, ring=6))
        p.append(box(name + "_brk%d" % s, T @ Ts(s * w * 0.34, 0.10, 0.02), (0.10, 0.22, 0.12), iron))
    pts = [(-w * 0.5, 0.0), (w * 0.5, 0.0), (w * 0.5, -h), (0.0, -h * 0.80), (-w * 0.5, -h)]
    p.append(H.prism(name + "_cl", T @ Ts(0, 0.13, 0), pts, 0.05, cloth, axis="y"))
    for s in (-1, 1):
        p.append(box(name + "_bd%d" % s, T @ Ts(s * (w * 0.5 - 0.07), 0.155, -h * 0.5),
                     (0.13, 0.02, h * 0.98), gold))
    p.append(box(name + "_bdt", T @ Ts(0, 0.155, -0.07), (w, 0.02, 0.14), gold))
    p.append(cyl(name + "_em", T @ Ts(0, 0.165, -h * 0.46) @ RotX(PI * 0.5), w * 0.27, 0.03,
                 gold, seg=22))
    p.append(cyl(name + "_em2", T @ Ts(0, 0.175, -h * 0.46) @ RotX(PI * 0.5), w * 0.13, 0.03,
                 cloth, seg=18))
    for i in range(3):
        p.append(box(name + "_emb%d" % i, T @ Ts(0, 0.17, -h * 0.70 - i * 0.18),
                     (w * 0.46 - i * 0.06, 0.02, 0.09), gold))
    for i in range(5):
        x = -w * 0.5 + w * (i + 0.5) / 5.0
        p.append(torus(name + "_rg%d" % i, T @ Ts(x, 0.19, -0.02) @ RotY(PI * 0.5), 0.045, 0.012,
                       iron, seg=8, ring=4))
    return p


def flag(name, T, pole_h, w, h, cloth, gold, iron):
    """Vertical flagpole with a flag flying to +X."""
    p = [cyl(name + "_pole", T @ Ts(0, 0, pole_h * 0.5), 0.075, pole_h, iron, seg=10),
         sphere(name + "_knob", T @ Ts(0, 0, pole_h + 0.10), 0.13, gold, seg=10, ring=6),
         cyl(name + "_base", T @ Ts(0, 0, 0.16), 0.26, 0.32, iron, seg=12)]
    p.append(box(name + "_cl", T @ Ts(w * 0.5 + 0.08, 0, pole_h - h * 0.5 - 0.2),
                 (w, 0.05, h), cloth, bev=0.01))
    p.append(box(name + "_bd", T @ Ts(w * 0.5 + 0.08, 0.035, pole_h - h * 0.5 - 0.2),
                 (w * 0.94, 0.02, h * 0.9), gold))
    p.append(box(name + "_bd2", T @ Ts(w * 0.5 + 0.08, 0.045, pole_h - h * 0.5 - 0.2),
                 (w * 0.62, 0.02, h * 0.5), cloth))
    return p


def guardian(name, T, h, MAT, spear=True):
    """Guardian figure for a niche: plinth, robe, mail, helm, spear, shield."""
    st = MAT["stone_warm"]
    p = []
    p.append(cyl(name + "_base", T @ Ts(0, 0, 0.12), 0.46, 0.24, st, seg=14))
    p.append(H.lathe(name + "_robe", [(0.40, 0.24), (0.33, h * 0.42), (0.30, h * 0.52),
                                      (0.26, h * 0.60)], st, seg=14, T=T,
                     close_bottom=False, close_top=False))
    p.append(H.lathe(name + "_mail", [(0.29, h * 0.55), (0.31, h * 0.66), (0.25, h * 0.74)],
                     st, seg=14, T=T, close_bottom=False, close_top=False))
    p.append(sphere(name + "_hd", T @ Ts(0, 0, h * 0.80), 0.155, st, seg=14, ring=9))
    p.append(H.lathe(name + "_helm", [(0.19, h * 0.80), (0.17, h * 0.87), (0.05, h * 0.90)],
                     st, seg=12, T=T, close_bottom=False, close_top=True))
    p.append(box(name + "_nas", T @ Ts(0, 0.15, h * 0.80), (0.05, 0.06, 0.16), st))
    for s in (-1, 1):
        p.append(box(name + "_arm%d" % s, T @ Ts(s * 0.30, 0.02, h * 0.64, ry=s * 0.12),
                     (0.11, 0.12, 0.42), st, bev=0.01))
        p.append(box(name + "_leg%d" % s, T @ Ts(s * 0.13, 0.02, 0.20), (0.14, 0.16, 0.34), st))
    # cloak
    p.append(H.prism(name + "_clk", T @ Ts(0, -0.12, 0),
                     [(-0.30, 0.24), (0.30, 0.24), (0.26, h * 0.66), (0.0, h * 0.72),
                      (-0.26, h * 0.66)], 0.09, st, axis="y"))
    if spear:
        p.append(cyl(name + "_sp", T @ Ts(0.40, 0.10, h * 0.46), 0.032, h * 0.98, st, seg=8))
        p.append(cone(name + "_tip", T @ Ts(0.40, 0.10, h * 0.97), 0.06, 0.26, st, seg=6))
    # shield
    p.append(H.prism(name + "_shd", T @ Ts(-0.34, 0.20, h * 0.52),
                     [(-0.24, 0.28), (0.24, 0.28), (0.24, -0.10), (0.0, -0.34), (-0.24, -0.10)],
                     0.10, st, axis="y"))
    return p


def niche(name, T, w, h, MAT, rng):
    """Projecting statue aedicule on a wall face (local +Y out, y=0 at the face).

    Everything sits at y >= 0 so it never fights the proud ashlar behind it.
    """
    st, sd = MAT["stone_warm"], MAT["stone_dark"]
    p = []
    p.append(box(name + "_back", T @ Ts(0, 0.07, h * 0.5), (w, 0.14, h), sd))
    for s in (-1, 1):
        p.append(box(name + "_j%d" % s, T @ Ts(s * (w * 0.5 + 0.15), 0.17, h * 0.5 + 0.05),
                     (0.30, 0.34, h + 0.30), st, bev=0.015))
    p.append(box(name + "_lin", T @ Ts(0, 0.20, h + 0.16), (w + 0.9, 0.16, 0.26), st, bev=0.02))
    p.append(voussoir_ring(name + "_arch", T @ Ts(0, 0.26, 0), w * 0.5, 0.24, 9, st,
                           y=0.0, zc=h, thick=0.34))
    p.append(box(name + "_hood", T @ Ts(0, 0.26, h + w * 0.5 + 0.34), (w + 1.0, 0.42, 0.22),
                 st, bev=0.02))
    for s in (-1, 1):
        p.append(box(name + "_cor%d" % s, T @ Ts(s * (w * 0.5 + 0.10), 0.24, 0.18),
                     (0.42, 0.46, 0.36), st, bev=0.025))
        p.append(cone(name + "_cod%d" % s, T @ Ts(s * (w * 0.5 + 0.10), 0.24, 0.02) @ RotX(PI),
                      0.26, 0.36, st, seg=4))
    p.append(box(name + "_sill", T @ Ts(0, 0.24, 0.36), (w + 0.56, 0.50, 0.18), st, bev=0.025))
    return p


def machic_line(name, T, length, MAT, n=None, out=1.0, wall_z=0.0, walk=0.42):
    """Corbelled machicolation gallery running along local X (one or few meshes).

    T is at the wall face, z=wall_z is the walk level.  Returns corbels, the
    overhanging floor, the parapet with a batter and the merlons.
    """
    sw, pale = MAT["stone_warm"], MAT["stone_pale"]
    p = []
    v, f = [], []
    if n is None:
        n = max(2, int(length / 0.95))
    pitch = length / n
    for i in range(n):
        x = -length * 0.5 + pitch * (i + 0.5)
        w = min(pitch * 0.52, 0.42)
        _blk(v, f, x - w * 0.5, x + w * 0.5, -0.10, out * 0.86, wall_z - 1.55, wall_z - 0.30)
        _blk(v, f, x - w * 0.62, x + w * 0.62, -0.10, out, wall_z - 0.44, wall_z - 0.22)
    p.append(_mk(name + "_corb", v, f, sw, T))
    # overhanging floor slab
    p.append(box(name + "_gal", T @ Ts(0, (out - 0.55) * 0.5, wall_z - 0.10),
                 (length, out + 0.55, 0.34), pale, bev=0.02))
    # parapet with a batter (a trapezoid prism along X)
    pp = [(-0.52, 0.0), (out + 0.16, 0.0), (out - 0.02, 1.02), (-0.52, 1.02)]
    p.append(H.prism(name + "_par", T @ Ts(0, 0, wall_z + 0.07), pp, length, sw, axis="x"))
    p.append(box(name + "_cap", T @ Ts(0, (out - 0.36) * 0.5, wall_z + 1.09),
                 (length, out + 0.68, 0.13), pale, bev=0.015))
    p += crenel_line(name + "_mer", T @ Ts(0, out - 0.15, wall_z + 1.20), length - 0.2,
                     MAT["stone"], merlon=0.96, gap=0.50, h=1.20, depth=0.62)
    return p


# --------------------------------------------------------------------------
#  pointed windows (local primitive: H.window_arched hides its own glass)
# --------------------------------------------------------------------------
def pointed_loop(w, h, seg=10, k=0.30):
    """Opening outline (x, z) of a two-centred pointed arch: jambs + head."""
    hw = w * 0.5
    c = w * k
    R = hw + c
    hz = math.sqrt(max(R * R - c * c, 1e-6))
    aL = math.atan2(hz, -c)
    aR = math.atan2(hz, c)
    pts = [(-hw, 0.0), (-hw, h)]
    for i in range(1, seg + 1):
        a = PI + (aL - PI) * i / seg
        pts.append((c + R * math.cos(a), h + R * math.sin(a)))
    for i in range(1, seg + 1):
        a = aR * (1.0 - i / seg)
        pts.append((-c + R * math.cos(a), h + R * math.sin(a)))
    pts.append((hw, 0.0))
    return pts


def _tube(name, T, loop, y0, y1, mat):
    """Open tube: a closed 2D loop (x, z) swept along local Y (window reveal)."""
    n = len(loop)
    v, f = [], []
    for (x, z) in loop:
        v.append((x, y0, z))
        v.append((x, y1, z))
    for i in range(n):
        j = (i + 1) % n
        f.append((i * 2, j * 2, j * 2 + 1, i * 2 + 1))
    return _mk(name, v, f, mat, T)


def pointed_band(name, T, w, h, thick, y0, y1, mat, seg=10, k=0.30):
    """A moulded band following a pointed arch (architrave / hood mould)."""
    inner = pointed_loop(w, h, seg=seg, k=k)
    hw = w * 0.5
    c = w * k
    R = hw + c
    hz = math.sqrt(max(R * R - c * c, 1e-6))
    aL = math.atan2(hz, -c)
    aR = math.atan2(hz, c)
    Ro = R + thick
    outer = [(-hw - thick, h)]
    for i in range(1, seg + 1):
        a = PI + (aL - PI) * i / seg
        outer.append((c + Ro * math.cos(a), h + Ro * math.sin(a)))
    for i in range(1, seg + 1):
        a = aR * (1.0 - i / seg)
        outer.append((-c + Ro * math.cos(a), h + Ro * math.sin(a)))
    outer.append((hw + thick, h))
    pts = list(outer) + [(x, z) for (x, z) in reversed(inner[1:-1])]
    return H.prism(name, T @ Ts(0, (y0 + y1) * 0.5, 0), pts, y1 - y0, mat, axis="y")


def gothic_window(name, T, w, h, MAT, tracery=2, transom=0, hood=True, depth=0.46,
                  dark=None, glass=None, sill=True, seg=10, k=0.30):
    """Recessed pointed window: reveal, glass, mullions, architrave, hood.

    T sits at the SILL centre, local +Y points out of the wall.
    Total height = h + sqrt((w/2 + w*k)^2 - (w*k)^2).
    """
    sw, pale = MAT["stone_warm"], MAT["stone_pale"]
    dk = dark or MAT["stone_dark"]
    gl = glass or MAT["glass"]
    hw = w * 0.5
    loop = pointed_loop(w, h, seg=seg, k=k)
    # the wall skin (ashlar) stands up to 0.05 proud of the wall plane, so the
    # whole window assembly is built proud of that skin: glazed panel first,
    # then the architrave, then the hood.  Works on any solid wall.
    fr = 0.115
    dep = max(0.22, depth)
    p = []
    p.append(_tube(name + "_rev", T, loop, fr, fr - dep, dk))
    p.append(H.prism(name + "_bk", T @ Ts(0, fr - dep, 0), loop, 0.05, dk, axis="y"))
    p.append(H.prism(name + "_gl", T @ Ts(0, fr - 0.035, 0), loop, 0.05, gl, axis="y"))
    n = max(1, int(tracery))
    for i in range(1, n):
        x = -hw + w * i / n
        p.append(box(name + "_m%d" % i, T @ Ts(x, fr + 0.045, h * 0.5),
                     (0.10, 0.13, h), pale, bev=0.01))
    for i in range(int(transom)):
        z = h * (0.40 + 0.30 * i)
        p.append(box(name + "_t%d" % i, T @ Ts(0, fr + 0.045, z),
                     (w, 0.13, 0.10), pale, bev=0.01))
    for s in (-1, 1):
        p.append(box(name + "_j%d" % s, T @ Ts(s * (hw + 0.15), 0.13, h * 0.5),
                     (0.30, 0.22, h + 0.02), sw, bev=0.015))
    p.append(pointed_band(name + "_ar", T, w, h, 0.30, 0.10, 0.24, sw, seg=seg, k=k))
    if sill:
        p.append(box(name + "_sl", T @ Ts(0, 0.17, -0.12), (w + 0.80, 0.40, 0.18), pale,
                     bev=0.02))
        p.append(box(name + "_sd", T @ Ts(0, 0.26, -0.24), (w + 0.58, 0.16, 0.06), dk))
    if hood:
        p.append(pointed_band(name + "_hd", T, w + 0.56, h, 0.36, 0.20, 0.40, pale,
                              seg=seg, k=k))
        for s in (-1, 1):
            p.append(box(name + "_hs%d" % s, T @ Ts(s * (hw + 0.46), 0.30, h - 0.16),
                         (0.30, 0.30, 0.34), pale, bev=0.02))
    return p
