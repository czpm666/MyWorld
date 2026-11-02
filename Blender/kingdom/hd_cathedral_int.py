# -*- coding: utf-8 -*-
"""hd_cathedral_int.py -- the INTERIOR of the great cathedral (Latin cross).

Authored by CATHEDRAL_INT.  Everything is built at its final size, floor at
z = 0, in a "church frame" whose origin is the crossing centre projected on the
floor.  The caller moves the whole thing with one matrix (see build()).

CHURCH FRAME
    +Y  -> the high altar / apse (east)
    -Y  -> the west front and the main door
    +X  -> the south transept arm
    z   -> up, floor at 0

SHELL FRAME (hd_cathedral.py, read-only for us)
    the shell's own +Y is its WEST FRONT, so the shell itself is placed with
    rot = pi (capital_hd_glue.cathedral passes math.pi); its apse therefore
    ends up on +Y as well.  Matching the interiors is therefore

        build(origin = CATH_C, rot = 0.0, scale = 1.0)

    CATH_C = (-224.96, 85.84); the church-frame origin is the crossing centre,
    which the shell also has at CATH_C + (0, +7.5) -- measured, see
    look/cath_align.py.  rot = 0, NOT pi: pi would put our apse on the west.
    Z_LIFT = 1.10 lifts everything onto the shell's floor slab.

CLEARANCES inside the shell that we must not exceed
    nave half width from the shell's piers ........ 8.50
    aisle inner face (from centre line) ........... 16.50
    straight walls end / apse mouth (local y) ..... -27.0 = our +27.0
    apse inscription radius inside the shell ...... ~8.50
    transept end wall inner face |x| ............... ~35.4
    transept band depth / local y ................. [-14, -1] -> ours [1, 14]
    under-vault headroom at |x| = 8.5 ............. ~33.9

PUBLIC API
    build(K, MAT, origin=(x, y), rot=0.0, scale=1.0, seed=5) -> [objects]
    interior_lights(spec="full")   -> [light objects]  (already parented to nothing)
    atmosphere(scene=None)         -> volumetric haze tuned for the interior
    footprint() / height() / CAMS / preview()
"""

from __future__ import annotations

import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import medkit as MK

TAU = math.pi * 2.0
D2R = math.pi / 180.0
OFF = 0.02          # face offset, keeps coplanar sheets from z-fighting


def L(msg):
    print("[hd] ci: %s" % msg)


# ---------------------------------------------------------------------------
# 1. dimensions  (metres, church frame)
# ---------------------------------------------------------------------------
# --- longitudinal, already verified against the shell ---------------------
Y_W = -40.90                 # inner face of the west wall
NBAY = 8
BAY = 5.2375                 # (41.90 / 8) so the last bay hits the crossing
Y_X0 = 1.00                  # crossing, west edge
CROSS_D = 13.00
Y_X1 = Y_X0 + CROSS_D        # 14.00
CH_BAY = 6.50
NCH = 2                      # choir bays
Y_APSE = Y_X1 + NCH * CH_BAY  # 27.00  apse mouth
APSE_R = 7.95                # APOTHEM of the inner apse half-decagon (room side)
                             # (shell's apse inside face: vertex r 8.50 / apothem 8.09)
TR_BAY = 5.36
NTRB = 5
TR_X = 33.30                 # transept end wall inner face

# --- lateral (user spec: nave 12-14, aisles 5-6) --------------------------
N_HW = 6.50                  # nave half width  -> 13.0 m clear
AISLE_IN = 12.10             # aisle wall inner face -> 5.60 m clear
WALL_T = 0.95                # interior skin thickness (real window reveals)
AIS_HW = N_HW + 0.0
AMB_IN = APSE_R + WALL_T     # ambulatory inner face (9.40)
AMB_OUT = AISLE_IN           # ambulatory outer face = 12.10, tangent to aisles

# --- vertical stack -------------------------------------------------------
Z_BASE = 1.10                # plinth / pier base
Z_ARC_SPR = 7.20             # arcade springing
Z_ARC_RISE = 4.05            # apex 11.25, strongly pointed
Z_ARC_APEX = Z_ARC_SPR + Z_ARC_RISE
Z_AIS_SPR = 11.55            # aisle vault springing (above the arcade apex)
Z_AIS_RISE = 1.95
Z_AIS_CROWN = Z_AIS_SPR + Z_AIS_RISE
Z_TRIF_S = 13.30             # triforium sill
Z_TRIF_T = 14.85
Z_TRIF_SPR = 13.55
Z_TRIF_RISE = 1.05
Z_TRIF_B = 15.10
Z_CLER_S = 15.60
Z_CLER_SPR = 18.30
Z_CLER_RISE = 1.25           # apex 19.55
Z_CORN = 19.75
Z_VAULT = 20.05
NAVE_HT = 5.55               # transverse rib rise over 13 m
NAVE_HR = 1.15               # wall rib rise over one bay
NAVE_HC = 5.80               # crown 25.85 -> 22-26 m clear height  OK
Z_CROWN = Z_VAULT + NAVE_HC
X_HC = 6.25                  # crossing crown 26.30
Z_APSE_CROWN = 25.80
Z_AMB_SPR = 11.55
Z_AMB_RISE = 1.95

# --- aisle vault ----------------------------------------------------------
AIS_HALF = (AISLE_IN - N_HW) * 0.5      # 2.80
AIS_HT = 1.95                           # transverse rib across the aisle
AIS_HR = 0.85                           # wall rib along the aisle

# --- roses ----------------------------------------------------------------
ROSE_W_R = 4.55              # west rose
ROSE_W_Z = 15.05             # centre height (hole top 19.76 < Z_VAULT 20.05)
ROSE_T_R = 4.20              # transept roses
ROSE_T_Z = 15.10

# --- furniture anchors ----------------------------------------------------
ROOD_Y = 14.30               # rood screen, at the choir's west end
ALTAR_Y = 31.20
CH_STALL_Y0 = 15.60
CH_STALL_Y1 = 26.10
PEW_Y0 = -39.20
PEW_N = 20

# --- materials that the caller may override -------------------------------
MAT_KEYS = (
    "stone", "stone_light", "stone_dark", "stone_warm", "plaster",
    "marble", "floor1", "floor2", "floor3", "floor4",
    "wood", "wood_light", "iron", "brass", "gold", "lead",
    "cloth_red", "cloth_blue", "cloth_gold", "linen", "wax",
    "glass_blue", "glass_red", "glass_gold", "glass_green",
    "glass_violet", "glass_pale", "glass_amber", "glass_teal",
    "flame", "bronze_dark", "gilt",
)


# ---------------------------------------------------------------------------
# 2. scene bookkeeping
# ---------------------------------------------------------------------------
PARTS = []
RNG = random.Random(5)
MAT = {}
_OWN = set()          # objects created by this module (for lights / cleanup)
WINDOWS = []          # (F, a0, a1, zsill, zspr, rise, th, seed) -- every lancet
ROSES = []            # (F, ca, cz, R, th, seed)                   -- every rose
LIGHTS = []
_XFORM = Matrix.Identity(4)
_ORIGIN = Vector((0.0, 0.0, 0.0))


def _reset(seed=5):
    global PARTS, RNG, MAT, _XFORM
    PARTS = []
    RNG = random.Random(seed)
    MAT = {}
    _OWN.clear()
    del WINDOWS[:]
    del ROSES[:]
    del LIGHTS[:]
    _XFORM = Matrix.Identity(4)


class MB(object):
    """Tiny mesh accumulator with vertex sharing by rounded position."""

    __slots__ = ("v", "f", "map")

    def __init__(self):
        self.v = []
        self.f = []
        self.map = {}

    def add(self, pts):
        idx = []
        for p in pts:
            if not isinstance(p, (Vector, tuple)):
                p = Vector(p)
            elif not isinstance(p, Vector):
                p = Vector(p)
            k = (round(p.x, 4), round(p.y, 4), round(p.z, 4))
            i = self.map.get(k)
            if i is None:
                i = len(self.v)
                self.v.append((p.x, p.y, p.z))
                self.map[k] = i
            idx.append(i)
        if len(idx) >= 3:
            self.f.append(tuple(idx))
        return idx

    def quad(self, a, b, c, d):
        self.add((a, b, c, d))

    def strip(self, row0, row1, closed=False):
        n = len(row0)
        m = n if closed else n - 1
        for i in range(m):
            j = (i + 1) % n
            self.quad(row0[i], row0[j], row1[j], row1[i])

    def fan(self, pts, centre):
        n = len(pts)
        for i in range(n):
            self.add((pts[i], pts[(i + 1) % n], centre))


def _mk(name, mb, mat, smooth=False):
    ob = MK.mesh_obj(name, mb.v, mb.f, smooth)
    if mat is None:
        mat = MAT["stone"]
    if isinstance(mat, (list, tuple)):
        MK.assign(ob, *mat)
    else:
        MK.assign(ob, mat)
    PARTS.append(ob)
    _OWN.add(ob.name)
    return ob


def _merge(obs, name):
    """Join a list of objects into one (keeps all material slots)."""
    obs = [o for o in obs if o is not None]
    if not obs:
        return None
    if len(obs) == 1:
        return obs[0]
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


# ---------------------------------------------------------------------------
# 3. arch maths
# ---------------------------------------------------------------------------
def arch_z(a, a0, a1, zspr, rise):
    """Height of a two-centred (pointed) or single-centred (segmental) arch.

    z(a0) = z(a1) = zspr,  z(mid) = zspr + rise.  rise/half > 1 gives a pointed
    arch with a real cusp at the apex (the gothic profile); rise/half <= 1 gives
    a smooth segmental arc.
    """
    h = (a1 - a0) * 0.5
    if h < 1e-7:
        return zspr + rise
    if rise <= 1e-5:
        return zspr
    x = a - (a0 + a1) * 0.5
    if abs(x) >= h:
        return zspr
    R = rise
    if R <= h:
        rho = (R * R + h * h) / (2.0 * R)
        y0 = (R * R - h * h) / (2.0 * R)
        v = rho * rho - x * x
        return zspr + (math.sqrt(v) if v > 0.0 else 0.0) + y0
    c = (R * R - h * h) / (2.0 * h)
    rho = (R * R + h * h) / (2.0 * h)
    u = abs(x) + c
    v = rho * rho - u * u
    return zspr + (math.sqrt(v) if v > 0.0 else 0.0)


def arch_contour(a0, a1, zsill, zspr, rise, n=12):
    """Closed loop in the (a, z) plane: up, over the arch, down, back."""
    pts = [(a0, zsill), (a0, zspr)]
    for i in range(1, n + 1):
        a = a0 + (a1 - a0) * i / n
        pts.append((a, arch_z(a, a0, a1, zspr, rise)))
    pts.append((a1, zsill))
    return pts


def offset_poly(pts, d):
    """Shrink a closed convex-ish loop inwards by d (bisector offset)."""
    n = len(pts)
    # signed area -> orientation
    ar = 0.0
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        ar += x0 * y1 - x1 * y0
    sgn = 1.0 if ar > 0 else -1.0
    out = []
    for i in range(n):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        e0 = Vector((x1 - x0, y1 - y0))
        e1 = Vector((x2 - x1, y2 - y1))
        if e0.length < 1e-9:
            e0 = e1.copy()
        if e1.length < 1e-9:
            e1 = e0.copy()
        e0.normalize()
        e1.normalize()
        n0 = Vector((-e0.y, e0.x)) * sgn
        n1 = Vector((-e1.y, e1.x)) * sgn
        m = n0 + n1
        if m.length < 1e-6:
            m = n0
        m.normalize()
        k = d / max(0.35, m.dot(n0))
        out.append((x1 + m.x * k, y1 + m.y * k))
    return out


def lancet(a0, a1, zsill, zspr, rise, inset=0.0, n=12):
    """Arch contour with an optional uniform inset (used for reveals)."""
    c = arch_contour(a0 + inset, a1 - inset, zsill + inset, zspr, rise - inset * 0.55, n)
    return c


# ---------------------------------------------------------------------------
# 4. sweep / rib profiles
# ---------------------------------------------------------------------------
def sweep(name, pts, prof, mat, up=(0.0, 0.0, 1.0), closed=False, smooth=True,
          caps=True):
    """Sweep a closed 2-D profile along a polyline.

    prof points are (side, up) in the frame perpendicular to the path.
    """
    upv = Vector(up)
    n = len(pts)
    if n < 2:
        return None
    rows = []
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
        s = t.cross(upv)
        if s.length < 1e-7:
            s = t.cross(Vector((1.0, 0.0, 0.0)))
            if s.length < 1e-7:
                s = t.cross(Vector((0.0, 1.0, 0.0)))
        s.normalize()
        u2 = s.cross(t)
        u2.normalize()
        rows.append([pts[i] + s * p[0] + u2 * p[1] for p in prof])
    mb = MB()
    np = len(prof)
    if closed:
        for i in range(n - 1):
            mb.strip(rows[i], rows[i + 1], closed=True)
        if caps:
            mb.fan(rows[0], Vector((0, 0, 0)) if False else pts[0])
            mb.fan(list(reversed(rows[-1])), pts[-1])
    else:
        for i in range(n - 1):
            for j in range(np - 1):
                mb.quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])
        if caps:
            mb.add(tuple(rows[0]))
            mb.add(tuple(reversed(rows[-1])))
    return _mk(name, mb, mat, smooth)


def ribprof(w=0.34, d=0.30, n=7):
    """A roll/torus rib section hanging below the path (up = -d)."""
    p = [(-w * 0.5, 0.14), (-w * 0.5, -0.02)]
    for i in range(1, 5):
        ang = math.pi * i / 5.0
        p.append((-w * 0.5 * math.cos(ang), -d * 0.52 - d * 0.48 * math.sin(ang)))
    p.append((w * 0.5, -0.02))
    p.append((w * 0.5, 0.14))
    return p


def arch_rib(name, a0, a1, zspr, rise, plane, w=0.34, d=0.30, mat=None, n=16):
    """A rib following an arch.  plane( point2d ) -> Vector."""
    pts = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        pts.append(plane((a, arch_z(a, a0, a1, zspr, rise))))
    if len(pts) < 2:
        return None
    return sweep(name, pts, ribprof(w, d), mat or MAT["stone_light"], smooth=True)


# ---------------------------------------------------------------------------
# 5. places / frames
# ---------------------------------------------------------------------------
class Frame(object):
    """O + U*a + V*z + N*d  with N pointing OUT of the room."""

    __slots__ = ("O", "U", "V", "N")

    def __init__(self, O, U, V, N):
        self.O = Vector(O)
        self.U = Vector(U).normalized()
        self.V = Vector(V).normalized()
        self.N = Vector(N).normalized()

    def p(self, a, z, d=0.0):
        return self.O + self.U * a + self.V * z + self.N * d

    def p2(self, az, d=0.0):
        return self.p(az[0], az[1], d)


def f_wall(x, y0, side, th=WALL_T):
    """A wall whose room face runs along Y at x = side * x, normal outward.

    O.y is always 0, so the caller passes ABSOLUTE y as the a coordinate.
    """
    return Frame((side * x, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
                 (side, 0.0, 0.0))


def f_xwall(y, x0):
    """A wall whose room face runs along X at y = y, normal outward (+/-Y)."""
    return Frame((x0, y, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
                 (0.0, 1.0 if y > 0 else -1.0, 0.0))


# ---------------------------------------------------------------------------
# 6. walls with real openings
# ---------------------------------------------------------------------------
def wall_slab(name, F, a0, a1, z0, z1, holes, th=WALL_T, mat=None,
              n_arch=10, band=True):
    """A wall panel with pointed-arch holes.

    holes = [(ha0, ha1, zsill, zspr, rise), ...]
    Builds the room face (d=0), the back face (d=th) and the perimeter band.
    The holes stay open -- see window_dress().
    """
    if mat is None:
        mat = MAT["stone"]
    holes = [h for h in holes if h[1] > a0 and h[0] < a1]
    zs_min = min([h[2] for h in holes] or [z1])
    za_max = max([h[3] + h[4] for h in holes] or [z0])
    cuts = {a0, a1}
    for (h0, h1, zs, zp, rr) in holes:
        h0c = max(a0, h0)
        h1c = min(a1, h1)
        cuts.add(round(h0c, 5))
        cuts.add(round(h1c, 5))
        for i in range(1, n_arch):
            cuts.add(round(h0c + (h1c - h0c) * i / n_arch, 5))
    cuts = sorted(cuts)
    mb = MB()

    def quad_at(d, pts):
        mb.add([F.p(p[0], p[1], d) for p in pts])

    def face(d):
        for i in range(len(cuts) - 1):
            c0, c1 = cuts[i], cuts[i + 1]
            if c1 - c0 < 1e-6:
                continue
            mid = (c0 + c1) * 0.5
            hole = None
            for h in holes:
                if h[0] - 1e-6 <= mid <= h[1] + 1e-6:
                    hole = h
                    break
            if hole is None:
                if z1 - z0 > 1e-6:
                    quad_at(d, [(c0, z0), (c1, z0), (c1, z1), (c0, z1)])
            else:
                h0, h1, zs, zp, rr = hole
                if zs - z0 > 1e-6:
                    quad_at(d, [(c0, z0), (c1, z0), (c1, zs), (c0, zs)])
                za = zp + rr
                zl = arch_z(c0, h0, h1, zp, rr)
                zr = arch_z(c1, h0, h1, zp, rr)
                if za - max(zl, zr) > 1e-6:
                    quad_at(d, [(c0, zl), (c1, zr), (c1, za), (c0, za)])
                if z1 - za > 1e-6:
                    quad_at(d, [(c0, za), (c1, za), (c1, z1), (c0, z1)])

    face(0.0)
    if band:
        face(th)
        # perimeter band
        ring = [(a0, z0), (a1, z0), (a1, z1), (a0, z1)]
        r0 = [F.p(p[0], p[1], 0.0) for p in ring]
        r1 = [F.p(p[0], p[1], th) for p in ring]
        mb.strip(r0, r1, closed=True)
    return _mk(name, mb, mat, smooth=False)


def window_dress(F, a0, a1, zsill, zspr, rise, th=WALL_T, inset=0.10,
                 glass=None, frame_mat=None, sill=True, tracery=0,
                 mosaic_cell=0.135, seed=0, back=False, emit=1.9,
                 transom=(), mullion=False, name="win"):
    """Real window: splayed reveal, outer embrasure, glazing, stone frame.

    Returns the list of created objects.  The wall slab must have been built
    with the same (a0,a1,zsill,zspr,rise) hole.
    """
    out = []
    inner = arch_contour(a0, a1, zsill, zspr, rise, 14)
    outer = offset_poly(inner, inset)
    # --- reveal: inner contour at d=0 -> offset contour at d=th -------------
    mb = MB()
    r0 = [F.p(p[0], p[1], 0.0) for p in inner]
    r1 = [F.p(p[0], p[1], th) for p in outer]
    mb.strip(r1, r0, closed=True)
    out.append(_mk(name + "_rev", mb, MAT["stone_light"]))
    # --- outer embrasure face (annulus at d=th) ----------------------------
    mb = MB()
    mb.strip(r1, [F.p(p[0], p[1], th) for p in inner], closed=True)
    out.append(_mk(name + "_emb", mb, MAT["stone_dark"]))
    # --- glazing ----------------------------------------------------------
    gc = F.p(0.0, 0.0, 0.0)  # unused
    # dark backing pane, slightly behind the tiles
    mb = MB()
    ring = [F.p(p[0], p[1], th - 0.10) for p in outer]
    mb.add(tuple(ring))
    out.append(_mk(name + "_bk", mb, glass or MAT["glass_blue"]))
    gl = _mosaic(name + "_gl", F, outer, th - 0.055, mosaic_cell, seed,
                 mats=None, emit=emit)
    out.extend(gl)
    # --- stone frame (moulding on the room face) ---------------------------
    if frame_mat is None:
        frame_mat = MAT["stone_light"]
    pts = [F.p(p[0], p[1], -0.03) for p in inner]
    pts.append(pts[0])
    out.append(sweep(name + "_frm", pts, _frame_prof(), frame_mat,
                     closed=False, caps=False))
    if sill:
        mb = MB()
        zz = zsill - 0.07
        w = 0.16
        p0 = F.p(a0 - 0.12, zz, 0.0)
        p1 = F.p(a1 + 0.12, zz, 0.0)
        p2 = F.p(a1 + 0.12, zz - 0.10, -w)
        p3 = F.p(a0 - 0.12, zz - 0.10, -w)
        mb.add((p0, p1, p2, p3))
        mb.add((p0 + F.N * 0.0, p3, p2, p1))
        out.append(_mk(name + "_sill", mb, frame_mat))
    # --- mullion / transoms ----------------------------------------------
    if mullion:
        am = (a0 + a1) * 0.5
        out.append(_bar(name + "_mul", F, am - 0.045, am + 0.045, zsill,
                        zspr + rise * 0.55, th))
    for zt in transom:
        out.append(_bar(name + "_tra", F, a0, a1, zt - 0.04, zt + 0.04, th,
                        horiz=True))
    for ob in out:                      # glazing must not stop the light
        if "_gl" in ob.name or ob.name.endswith("_bk"):
            ob.visible_shadow = False
    WINDOWS.append((F, a0, a1, zsill, zspr, rise, th, seed))
    return out


def _frame_prof():
    """Wide flat-ish moulding for a window surround (side, up)."""
    return [(-0.115, 0.0), (-0.115, 0.055), (-0.075, 0.105),
            (0.06, 0.105), (0.10, 0.055), (0.10, -0.02)]


def _bar(name, F, a0, a1, z0, z1, th, horiz=False):
    """A slim stone bar inside a window opening."""
    mb = MB()
    d0 = th - 0.16
    d1 = th - 0.02
    r0 = [F.p(a0, z0, d0), F.p(a1, z0, d0), F.p(a1, z1, d0), F.p(a0, z1, d0)]
    r1 = [F.p(a0, z0, d1), F.p(a1, z0, d1), F.p(a1, z1, d1), F.p(a0, z1, d1)]
    mb.add(tuple(r0))
    mb.add(tuple(reversed(r1)))
    mb.strip(r0, r1, closed=True)
    return _mk(name, mb, MAT["stone_light"])


def _in_poly(x, y, poly):
    c = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if ((y0 > y) != (y1 > y)):
            xin = (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0
            if x < xin:
                c = not c
    return c


GLASS_SETS = (
    ("#123a8f", "#8d1f2b", "#c9a13a", "#1d6a4c", "#52307a", "#cfd8e8", "#c86a1c", "#2d8a8a"),
    ("#0f2f74", "#7c1c2a", "#d0a83c", "#1a5c46", "#452a6b", "#e2e6ee", "#b3541a", "#207070"),
    ("#1a4494", "#96222c", "#bf9330", "#22704f", "#5a3682", "#d8dee9", "#d07c22", "#2f9490"),
)


def _mosaic(name, F, contour, d, cell, seed, mats=None, emit=1.9, gap=0.013):
    """Leaded glass: a fine patchwork of emissive quads on a polygon."""
    rng = random.Random(1000 + seed)
    xs = [p[0] for p in contour]
    ys = [p[1] for p in contour]
    a0, a1 = min(xs), max(xs)
    z0, z1 = min(ys), max(ys)
    pal = GLASS_SETS[seed % len(GLASS_SETS)]
    ncol = [[] for _ in pal]
    na = max(1, int(math.ceil((a1 - a0) / cell)))
    nz = max(1, int(math.ceil((z1 - z0) / cell)))
    ca = (a1 - a0) / na
    cz = (z1 - z0) / nz
    for ia in range(na):
        for iz in range(nz):
            pa = a0 + (ia + 0.5) * ca
            pz = z0 + (iz + 0.5) * cz
            if not _in_poly(pa, pz, contour):
                continue
            # colour blobs: 3x3 cells share a hue, with noise
            key = (int(ia / 3.0), int(iz / 3.0))
            r = (key[0] * 73856093) ^ (key[1] * 19349663) ^ (seed * 83492791)
            ci = (r >> 5) % len(pal)
            if rng.random() < 0.22:
                ci = rng.randrange(len(pal))
            aa = a0 + ia * ca + gap * 0.5
            bb = aa + ca - gap
            cc = z0 + iz * cz + gap * 0.5
            dd = cc + cz - gap
            if not (_in_poly(aa + 0.01, cc + 0.01, contour)
                    and _in_poly(bb - 0.01, dd - 0.01, contour)):
                # clip the cell to the contour by shrinking it a little
                e = 0.02
                aa += e
                bb -= e
                cc += e
                dd -= e
                if bb - aa < 0.01 or dd - cc < 0.01:
                    continue
            ncol[ci].append((aa, cc, bb, dd))
    out = []
    for ci, lst in enumerate(ncol):
        if not lst:
            continue
        mb = MB()
        for (aa, cc, bb, dd) in lst:
            mb.add((F.p(aa, cc, d), F.p(bb, cc, d), F.p(bb, dd, d), F.p(aa, dd, d)))
        m = glass_mat("s%d_%d" % (seed % 3, ci), pal[ci], emit)
        out.append(_mk("%s_g%d" % (name, ci), mb, m))
    return out


# ---------------------------------------------------------------------------
# 7. materials
# ---------------------------------------------------------------------------
def _mnew(key):
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    return m, MK._bsdf(m), m.node_tree


GLASS_GAIN = 1.7


def glass_mat(name, hexcol, emit=1.9, alpha=0.60):
    key = "ci_gl_" + name
    if key in MK._MAT_CACHE:
        return MK._MAT_CACHE[key]
    m, b, nt = _mnew(key)
    col = MK.c("#" + hexcol.lstrip("#"))
    dark = tuple(v * 0.35 for v in col[:3]) + (1.0,)
    MK._put(b, ["Base Color"], dark)
    MK._put(b, ["Roughness"], 0.16)
    MK._put(b, ["Metallic"], 0.0)
    MK._put(b, ["Emission Color", "Emission"], col)
    MK._put(b, ["Emission Strength"], GLASS_GAIN * emit / max(0.2, alpha))
    MK._put(b, ["Alpha"], alpha)
    MK._MAT_CACHE[key] = m
    return m


def flat_mat(name, hexcol, rough=0.7, metallic=0.0, emit=0.0, noise=None):
    key = "ci_m_" + name
    if key in MK._MAT_CACHE:
        return MK._MAT_CACHE[key]
    m, b, nt = _mnew(key)
    col = MK.c("#" + hexcol.lstrip("#"))
    MK._put(b, ["Base Color"], col)
    MK._put(b, ["Roughness"], rough)
    MK._put(b, ["Metallic"], metallic)
    if emit > 0:
        MK._put(b, ["Emission Color", "Emission"], col)
        MK._put(b, ["Emission Strength"], emit)
    if noise is not None:
        n = MK._noise(nt, scale=noise[0], detail=7.0, rough=0.55)
        ramp = MK._ramp(nt, [(0.35, tuple(v * 0.72 for v in col[:3]) + (1.0,)),
                             (0.65, tuple(min(1.0, v * 1.18) for v in col[:3]) + (1.0,))])
        nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
        MK._bump(nt, b, n.outputs["Fac"], 0.22, 0.05)
    MK._MAT_CACHE[key] = m
    return m


def _build_mats():
    """Interior material table.  Caller-supplied entries win."""
    d = {}
    d["stone"] = MK.mat_stone("ci_stone", base="#8d8375", dark="#5d564b",
                              light="#b0a692", scale=1.9)
    d["stone_light"] = MK.mat_stone("ci_stone_l", base="#a89d89", dark="#7a7264",
                                    light="#c9bfa9", scale=2.6)
    d["stone_dark"] = MK.mat_stone("ci_stone_d", base="#6f6659", dark="#443f37",
                                   light="#8d8474", scale=3.4)
    d["stone_warm"] = MK.mat_stone("ci_stone_w", base="#9a8b73", dark="#6b5f4c",
                                   light="#c0b096", scale=2.2)
    d["plaster"] = MK.mat_plaster("ci_plaster", base="#d8d0bd", dirt="#bdb29a")
    d["marble"] = MK.mat_stone("ci_marble", base="#c8c3b4", dark="#9b958a",
                               light="#e2ded1", scale=1.4)
    for i, (b, dk, lt) in enumerate((
            ("#8b8274", "#5a5349", "#a9a08f"),
            ("#958a79", "#645b4d", "#b2a897"),
            ("#827a6d", "#4f4a41", "#9e9587"),
            ("#9d9182", "#6a6253", "#bbb19c"))):
        d["floor%d" % (i + 1)] = MK.mat_stone("ci_floor%d" % (i + 1), base=b,
                                              dark=dk, light=lt, scale=1.3)
    d["wood"] = MK.mat_wood("ci_oak", base="#3b2718", light="#5c4028", scale=18.0)
    d["wood_light"] = MK.mat_wood("ci_ash", base="#6a4c31", light="#8a6a48", scale=16.0)
    d["iron"] = MK.mat_metal("ci_iron", base="#2f2e33", rough=0.44)
    d["brass"] = MK.mat_metal("ci_brass", base="#8a6a2c", rough=0.34)
    d["bronze_dark"] = MK.mat_metal("ci_bronze", base="#4a3a26", rough=0.52)
    d["gold"] = MK.mat_gold("ci_gold", base="#c9a227")
    d["gilt"] = MK.mat_gold("ci_gilt", base="#e0b53c")
    d["lead"] = flat_mat("lead", "#3a3a3d", rough=0.5, metallic=0.55)
    d["cloth_red"] = MK.mat_cloth("ci_crev", "#7a1c20", 0.86)
    d["cloth_blue"] = MK.mat_cloth("ci_cblu", "#1d2f5e", 0.86)
    d["cloth_gold"] = MK.mat_cloth("ci_cgld", "#a8801f", 0.78)
    d["linen"] = MK.mat_cloth("ci_linen", "#ddd6c2", 0.9)
    d["wax"] = flat_mat("wax", "#efe6cf", rough=0.55)
    d["flame"] = flat_mat("flame", "#ffb060", rough=0.5, emit=14.0)
    d["stone_floor"] = d["floor1"]
    for key, hx in (("blue", "2f4f9e"), ("red", "8f1f2c"), ("gold", "c99a2e"),
                    ("green", "2f6b46"), ("violet", "5b3a7e"),
                    ("pale", "cfd8e6"), ("amber", "d9832a"),
                    ("teal", "2b6f72")):
        d["glass_" + key] = glass_mat(key, hx, emit=2.4, alpha=0.26)
    return d


def _ensure(MATIN):
    d = _build_mats()
    if MATIN:
        for k, v in MATIN.items():
            if v is not None:
                d[k] = v
    return d


MAT_DEFAULT = None


# ---------------------------------------------------------------------------
# 8. small parts
# ---------------------------------------------------------------------------
def boss(name, x, y, z, r=0.30, mat=None):
    mb = MB()
    seg = 12
    ring = [(x + r * math.cos(TAU * i / seg), y + r * math.sin(TAU * i / seg), z)
            for i in range(seg)]
    lo = [(x + r * 0.45 * math.cos(TAU * i / seg),
           y + r * 0.45 * math.sin(TAU * i / seg), z - 0.34) for i in range(seg)]
    mb.strip(ring, lo, closed=True)
    mb.fan(lo, Vector((x, y, z - 0.52)))
    mb.fan(list(reversed(ring)), Vector((x, y, z + 0.06)))
    return _mk(name, mb, mat or MAT["stone_light"], smooth=True)


def candle(name, x, y, z, r=0.035, h=0.26, mat=None):
    mb = MB()
    seg = 7
    ring0 = [(x + r * math.cos(TAU * i / seg), y + r * math.sin(TAU * i / seg), z)
             for i in range(seg)]
    ring1 = [(p[0], p[1], z + h) for p in ring0]
    mb.strip(ring0, ring1, closed=True)
    mb.fan(ring1, Vector((x, y, z + h)))
    _mk(name + "_w", mb, mat or MAT["wax"], smooth=True)
    mb = MB()
    z2 = z + h
    mid = [(x + r * 0.55 * math.cos(TAU * i / seg), y + r * 0.55 * math.sin(TAU * i / seg),
            z2 + h * 0.5) for i in range(seg)]
    tip = Vector((x, y, z2 + h * 0.85))
    mb.strip(mid, [(p[0], p[1], z2) for p in mid], closed=True)
    mb.fan(mid, tip)
    return _mk(name + "_f", mb, MAT["flame"], smooth=True)


def stick(name, x, y, z, h=1.6, mat=None):
    """A floor candlestick with a fat candle."""
    m = mat or MAT["brass"]
    MK.cyl(name + "_b", MK.T_at(x, y, z), 0.19, 0.05, m, seg=12)
    MK.cone(name + "_s", MK.T_at(x, y, z + 0.05), 0.11, 0.18, m, seg=12)
    MK.cyl(name + "_st", MK.T_at(x, y, z + 0.23), 0.038, h * 0.55, m, seg=10)
    MK.sphere(name + "_k", MK.T_at(x, y, z + h * 0.62), 0.075, m, seg=12, ring=8)
    MK.cone(name + "_c", MK.T_at(x, y, z + h * 0.66), 0.13, 0.06, m, seg=12)
    ob = candle(name + "_ca", x, y, z + h * 0.70, 0.045, 0.30)
    return ob


def trefoil(name, F, a, z, r=0.16, mat=None):
    mb = MB()
    seg = 10
    for k in range(3):
        cx = a + r * 0.92 * math.cos(TAU * k / 3.0 + math.pi * 0.5)
        cz = z + r * 0.92 * math.sin(TAU * k / 3.0 + math.pi * 0.5)
        pts = [F.p(cx + r * 0.58 * math.cos(TAU * i / seg),
                   cz + r * 0.58 * math.sin(TAU * i / seg), -0.05) for i in range(seg)]
        mb.fan(pts, F.p(cx, cz, -0.05))
    return _mk(name, mb, mat or MAT["stone_dark"])


def quatrefoil(name, F, a, z, r=0.28, d=0.0, mat=None):
    mb = MB()
    seg = 9
    for k in range(4):
        cx = a + r * 0.55 * math.cos(TAU * k / 4.0)
        cz = z + r * 0.55 * math.sin(TAU * k / 4.0)
        for i in range(seg):
            p0 = F.p(cx + r * 0.55 * math.cos(TAU * i / seg),
                     cz + r * 0.55 * math.sin(TAU * i / seg), d)
            p1 = F.p(cx + r * 0.55 * math.cos(TAU * (i + 1) / seg),
                     cz + r * 0.55 * math.sin(TAU * (i + 1) / seg), d)
            mb.add((p0, p1, F.p(cx, cz, d)))
    return _mk(name, mb, mat or MAT["stone_dark"])


def course(name, F, a0, a1, z, h=0.14, d0=-0.13, d1=0.06, mat=None):
    """A horizontal moulding course along a wall."""
    mb = MB()
    r0 = [F.p(a0, z, d0), F.p(a1, z, d0), F.p(a1, z, d1), F.p(a0, z, d1)]
    r1 = [F.p(a0, z + h, d0), F.p(a1, z + h, d0), F.p(a1, z + h, d1),
          F.p(a0, z + h, d1)]
    mb.add(tuple(r0))
    mb.add(tuple(reversed(r1)))
    mb.strip(r0, r1, closed=True)
    return _mk(name, mb, mat or MAT["stone_light"])


def plinth(name, F, a0, a1, z0=0.0, z1=Z_BASE, mat=None):
    mb = MB()
    r0 = [F.p(a0, z0, -0.16), F.p(a1, z0, -0.16), F.p(a1, z0, 0.04),
          F.p(a0, z0, 0.04)]
    r1 = [F.p(a0, z1, -0.11), F.p(a1, z1, -0.11), F.p(a1, z1, 0.04),
          F.p(a0, z1, 0.04)]
    mb.add(tuple(r0))
    mb.add(tuple(reversed(r1)))
    mb.strip(r0, r1, closed=True)
    return _mk(name, mb, mat or MAT["stone_dark"])


# ---------------------------------------------------------------------------
# 9. vaults
# ---------------------------------------------------------------------------
def vault_z(x, y, x0, x1, y0, y1, zs, ht, hr, hc):
    ax, bx = (x0 + x1) * 0.5, (x1 - x0) * 0.5
    ay, by = (y0 + y1) * 0.5, (y1 - y0) * 0.5
    if bx < 1e-6 or by < 1e-6:
        return zs + hc
    A = arch_z(x, x0, x1, 0.0, ht)
    B = arch_z(y, y0, y1, 0.0, hr)
    return zs + A + B + (hc - ht - hr) * (A / max(1e-6, ht)) * (B / max(1e-6, hr))


def vault_sheet(name, x0, x1, y0, y1, zs, ht, hr, hc, mat=None, nx=14, ny=6,
                oculus=None, flip=False):
    mb = MB()
    rows = []
    for j in range(ny + 1):
        y = y0 + (y1 - y0) * j / ny
        row = []
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            row.append(Vector((x, y, vault_z(x, y, x0, x1, y0, y1, zs, ht, hr, hc))))
        rows.append(row)
    for j in range(ny):
        for i in range(nx):
            if oculus is not None:
                cx = (rows[j][i].x + rows[j + 1][i + 1].x) * 0.5
                cy = (rows[j][i].y + rows[j + 1][i + 1].y) * 0.5
                if (cx - oculus[0]) ** 2 + (cy - oculus[1]) ** 2 < oculus[2] ** 2:
                    continue
            mb.quad(rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i])
    ob = _mk(name, mb, mat or MAT["plaster"], smooth=True)
    return ob


def vault_rib_curve(x0, x1, y0, y1, zs, ht, hr, hc, p0, p1, n=20, inset=0.004):
    """3-D points along a line in plan, lifted onto the vault surface."""
    pts = []
    for i in range(n + 1):
        t = inset + (1.0 - 2.0 * inset) * i / n
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t
        pts.append(Vector((x, y, vault_z(x, y, x0, x1, y0, y1, zs, ht, hr, hc))))
    return pts


def vault_bay(name, x0, x1, y0, y1, zs, ht, hr, hc, mat=None,
              nx=13, ny=6, ribs=True, wall_ribs=True, boss_it=True, oculus=None):
    """One quadripartite bay: web + diagonal ribs + transverse/wall ribs."""
    out = []
    out.append(vault_sheet(name + "_web", x0, x1, y0, y1, zs, ht, hr, hc,
                           mat or MAT["plaster"], nx, ny, oculus))
    if ribs:
        m = MAT["stone_light"]
        for (p0, p1) in (((x0, y0), (x1, y1)), ((x0, y1), (x1, y0))):
            pts = vault_rib_curve(x0, x1, y0, y1, zs, ht, hr, hc, p0, p1, 22)
            out.append(sweep(name + "_dr", pts, ribprof(0.42, 0.34), m))
    if wall_ribs:
        m = MAT["stone_light"]
        # transverse ribs on the x = const edges
        for x in (x0, x1):
            pts = []
            for i in range(19):
                y = y0 + (y1 - y0) * (0.03 + 0.94 * i / 18)
                pts.append(Vector((x, y, vault_z(x, y, x0, x1, y0, y1, zs, ht, hr, hc))))
            out.append(sweep(name + "_tr", pts, ribprof(0.40, 0.30), m))
        # wall ribs on the y = const edges
        for y in (y0, y1):
            pts = []
            for i in range(17):
                x = x0 + (x1 - x0) * (0.04 + 0.92 * i / 16)
                pts.append(Vector((x, y, vault_z(x, y, x0, x1, y0, y1, zs, ht, hr, hc))))
            out.append(sweep(name + "_wr", pts, ribprof(0.30, 0.22), m))
    if boss_it:
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        out.append(boss(name + "_boss", cx, cy, vault_z(cx, cy, x0, x1, y0, y1, zs, ht, hr, hc),
                        0.36))
    return out


def dome_conch(name, cx, cy, r_poly, zs, zc, nseg=11, nring=5, mat=None,
               ribs=7, off=0.0):
    """Semi-dome (conch) over a half-decagon, pole above (cx, cy)."""
    out = []
    mb = MB()
    rings = []
    for k in range(nring + 1):
        u = k / float(nring)
        row = []
        for i in range(nseg + 1):
            th = -math.pi * 0.5 + math.pi * i / nseg
            rr = r_poly / max(0.30, math.cos(th - _face_th(th)))
            r = rr * u
            z = zs + (zc - zs) * (1.0 - u * u) ** 0.62
            row.append(Vector((cx + r * math.sin(th), cy + r * math.cos(th), z)))
        rings.append(row)
    for k in range(nring):
        for i in range(nseg):
            mb.quad(rings[k][i], rings[k][i + 1], rings[k + 1][i + 1], rings[k + 1][i])
    _mk(name + "_web", mb, mat or MAT["plaster"], smooth=True)
    # ribs
    if ribs:
        for i in range(ribs + 1):
            th = -math.pi * 0.5 + math.pi * i / ribs
            pts = []
            for k in range(nring + 1):
                u = 0.04 + 0.92 * k / float(nring)
                rr = r_poly / max(0.30, math.cos(th - _face_th(th)))
                r = rr * u
                z = zs + (zc - zs) * (1.0 - u * u) ** 0.62
                pts.append(Vector((cx + r * math.sin(th), cy + r * math.cos(th), z + off)))
            out.append(sweep(name + "_rib", pts, ribprof(0.30, 0.22),
                             MAT["stone_light"]))
    out.append(boss(name + "_boss", cx, cy, zc, 0.34))
    return out


def _face_th(th):
    """Angle of the facet centre nearest to a plan angle (half-decagon)."""
    step = math.pi / 5.0
    k = round((th + math.pi * 0.5 - step * 0.5) / step)
    return -math.pi * 0.5 + step * (k + 0.5)


# ---------------------------------------------------------------------------
# 10. piers and shafts
# ---------------------------------------------------------------------------
Z_LIFT = 1.10                     # the shell floor sits at this height
PIER_R = 0.46
PIER_SHAFTS = 8


def pier(name, x, y, z0, z1, core=PIER_R, mat=None, cap=True, big=1.0):
    """A compound pier: octagonal base, core, engaged shafts, capital."""
    m = mat or MAT["stone"]
    ml = MAT["stone_light"]
    out = []

    def P(r, a, z):
        return Vector((x + r * math.cos(a), y + r * math.sin(a), z))

    # two-step octagonal base
    mb = MB()
    for (r, za, zb) in ((core * 1.58 * big, z0, z0 + 0.16),
                        (core * 1.30 * big, z0 + 0.16, z0 + 0.30)):
        lo = [P(r, TAU * i / 8 + math.pi / 8, za) for i in range(8)]
        hi = [P(r, TAU * i / 8 + math.pi / 8, zb) for i in range(8)]
        mb.strip(lo, hi, closed=True)
        mb.fan(hi, Vector((x, y, zb)))
    out.append(_mk(name + "_base", mb, ml, smooth=False))
    # core
    seg = 16
    mb = MB()
    lo = [P(core, TAU * i / seg, z0 + 0.30) for i in range(seg)]
    hi = [P(core, TAU * i / seg, z1 - 0.42) for i in range(seg)]
    mb.strip(lo, hi, closed=True)
    out.append(_mk(name + "_core", mb, m, smooth=True))
    # engaged shafts
    rs = core * 0.30
    for k in range(PIER_SHAFTS):
        ang = TAU * k / PIER_SHAFTS + math.pi / PIER_SHAFTS
        sx = x + (core + rs * 0.55) * math.cos(ang)
        sy = y + (core + rs * 0.55) * math.sin(ang)
        mb = MB()
        lo = [Vector((sx + rs * math.cos(TAU * i / 8), sy + rs * math.sin(TAU * i / 8),
                      z0 + 0.30)) for i in range(8)]
        hi = [Vector((p.x, p.y, z1 - 0.42)) for p in lo]
        mb.strip(lo, hi, closed=True)
        out.append(_mk(name + "_sh%d" % k, mb, m, smooth=True))
    # capital
    mb = MB()
    r0 = core * 1.10 * big
    r1 = core * 1.42 * big
    zc = z1 - 0.42
    lo = [P(r0, TAU * i / seg, zc) for i in range(seg)]
    hi = [P(r1, TAU * i / seg, zc + 0.26) for i in range(seg)]
    mb.strip(lo, hi, closed=True)
    mb.fan(hi, Vector((x, y, zc + 0.26)))
    out.append(_mk(name + "_cap", mb, ml, smooth=True))
    if cap:
        ob = MK.box(name + "_ab", MK.T_at(x, y, z1 - 0.09),
                    (core * 3.0 * big, core * 3.0 * big, 0.18), ml)
        PARTS.append(ob)
        out.append(ob)
        for k in range(6):
            ang = TAU * k / 6.0
            ob = MK.sphere(name + "_lf%d" % k,
                           MK.T_at(x + r1 * 0.80 * math.cos(ang),
                                   y + r1 * 0.80 * math.sin(ang), zc + 0.12),
                           0.075, ml, seg=10, ring=6)
            PARTS.append(ob)
            out.append(ob)
    return out


def shaft(name, P0, P1, r=0.115, mat=None, base=True):
    """A slim vertical shaft (vaulting shaft) standing off a wall."""
    d = (Vector(P1) - Vector(P0))
    if d.length < 0.02:
        return None
    m = mat or MAT["stone_light"]
    return sweep(name, [Vector(P0), Vector(P1)], [
        (r * math.cos(TAU * i / 8), r * math.sin(TAU * i / 8)) for i in range(8)
    ], m, smooth=True)


# ---------------------------------------------------------------------------
# 11. the main vessel elevation (nave / choir / transept side walls)
# ---------------------------------------------------------------------------
def elev_bay(name, F, a0, a1, wins, arc=True, trif=True, corn=True,
             z_top=Z_VAULT, z_floor=0.0, plinth_it=True, seed=0,
             clere=True, vault_shafts=True, ceil_corn=True):
    """One bay of the high wall: arcade, triforium, clerestory, cornice."""
    out = []
    holes = []
    ac0, ac1 = a0 + PIER_R, a1 - PIER_R
    if arc and ac1 - ac0 > 1.4:
        holes.append((ac0, ac1, 0.0, Z_ARC_SPR, Z_ARC_RISE))
    for (w0, w1) in wins:
        holes.append((w0, w1, Z_CLER_S, Z_CLER_SPR, Z_CLER_RISE))
    out.append(wall_slab(name + "_wall", F, a0, a1, z_floor, z_top, holes,
                         WALL_T, MAT["stone"]))
    # --- arcade: soffit + roll mouldings ----------------------------------
    if arc and ac1 - ac0 > 1.4:
        inner = arch_contour(ac0, ac1, 0.0, Z_ARC_SPR, Z_ARC_RISE, 16)
        mb = MB()
        mb.strip([F.p(p[0], p[1], WALL_T) for p in inner],
                 [F.p(p[0], p[1], 0.0) for p in inner], closed=True)
        out.append(_mk(name + "_sof", mb, MAT["stone_light"]))
        out.append(arch_rib(name + "_arib", ac0, ac1, Z_ARC_SPR, Z_ARC_RISE,
                            lambda az, F=F: F.p(az[0], az[1], -0.02),
                            0.30, 0.20, MAT["stone_light"]))
    # --- triforium --------------------------------------------------------
    if trif:
        out.extend(triforium(name + "_tri", F, a0 + 0.30, a1 - 0.30, seed))
    # --- clerestory windows ----------------------------------------------
    if clere:
        for i, (w0, w1) in enumerate(wins):
            out.extend(window_dress(F, w0, w1, Z_CLER_S, Z_CLER_SPR, Z_CLER_RISE,
                                    th=WALL_T, inset=0.08, emit=2.0,
                                    transom=(Z_CLER_SPR + 0.55,), mullion=False,
                                    seed=seed * 7 + i, name=name + "_cw%d" % i,
                                    back=True))
    # --- cornice / string courses ----------------------------------------
    if corn:
        out.append(course(name + "_cor1", F, a0, a1, Z_CORN, 0.16, -0.22, 0.05))
        out.append(course(name + "_cor2", F, a0, a1, Z_CORN + 0.16, 0.14, -0.30, 0.05))
    if ceil_corn:
        out.append(course(name + "_cor3", F, a0, a1, Z_TRIF_B - 0.20, 0.10, -0.16, 0.04))
    if plinth_it:
        out.append(plinth(name + "_pl", F, a0, a1))
    # --- vaulting shafts at the bay boundaries ---------------------------
    if vault_shafts:
        for a, tag in ((a0, "L"), (a1, "R")):
            P0 = F.p(a, Z_ARC_SPR + 0.12, -0.16)
            P1 = F.p(a, Z_VAULT - 0.05, -0.16)
            out.append(shaft(name + "_vs" + tag, P0, P1, 0.115))
            out.append(course(name + "_vcap" + tag, F, a - 0.20, a + 0.20,
                              Z_VAULT - 0.26, 0.20, -0.24, 0.02))
    return out


def triforium(name, F, a0, a1, seed=0):
    """Blind arcading: a recessed dark panel with 4 pointed sub-arches."""
    out = []
    n = 4
    span = (a1 - a0) / n
    # recessed back panel
    mb = MB()
    d = -0.16
    r0 = [F.p(a0, Z_TRIF_S, d), F.p(a1, Z_TRIF_S, d), F.p(a1, Z_TRIF_T, d),
          F.p(a0, Z_TRIF_T, d)]
    mb.add(tuple(r0))
    out.append(_mk(name + "_bk", mb, MAT["stone_dark"]))
    # frame
    for i in range(n):
        s0 = a0 + span * i + 0.06
        s1 = s0 + span - 0.12
        zs = Z_TRIF_SPR
        rr = Z_TRIF_RISE
        c = arch_contour(s0, s1, Z_TRIF_S + 0.10, zs, rr, 10)
        mb = MB()
        mb.strip([F.p(p[0], p[1], d) for p in c], [F.p(p[0], p[1], -0.02) for p in c],
                 closed=True)
        out.append(_mk(name + "_r%d" % i, mb, MAT["stone_light"]))
        out.append(arch_rib(name + "_rb%d" % i, s0, s1, zs, rr,
                            lambda az, F=F: F.p(az[0], az[1], -0.03), 0.16, 0.10,
                            MAT["stone_light"], 10))
    # colonnettes between the arches
    for i in range(n + 1):
        a = a0 + span * i
        out.append(shaft(name + "_col%d" % i, F.p(a, Z_TRIF_S, -0.10),
                         F.p(a, Z_TRIF_T - 0.05, -0.10), 0.055, MAT["stone_light"]))
    return out


# ---------------------------------------------------------------------------
# 12. plates, bands, rings
# ---------------------------------------------------------------------------
def plate(name, F, poly, d0, d1, mat, smooth=False):
    """Extrude a closed 2-D polygon (a, z) from d0 to d1."""
    mb = MB()
    r0 = [F.p(p[0], p[1], d0) for p in poly]
    r1 = [F.p(p[0], p[1], d1) for p in poly]
    mb.add(tuple(r0))
    mb.add(tuple(reversed(r1)))
    mb.strip(r0, r1, closed=True)
    return _mk(name, mb, mat, smooth)


def disc_contour(ca, cz, r, n=32):
    return [(ca + r * math.cos(TAU * i / n), cz + r * math.sin(TAU * i / n))
            for i in range(n)]


def ring_band(name, F, ca, cz, r, w, d0, d1, mat, n=36):
    """A flat annulus band (tracery ring) standing in the wall plane."""
    mb = MB()
    ri, ro = r - w * 0.5, r + w * 0.5
    lo = [(ca + ri * math.cos(TAU * i / n), cz + ri * math.sin(TAU * i / n)) for i in range(n)]
    hi = [(ca + ro * math.cos(TAU * i / n), cz + ro * math.sin(TAU * i / n)) for i in range(n)]
    mb.strip([F.p(p[0], p[1], d0) for p in lo], [F.p(p[0], p[1], d0) for p in hi], closed=True)
    mb.strip([F.p(p[0], p[1], d1) for p in lo], [F.p(p[0], p[1], d1) for p in hi], closed=True)
    mb.strip([F.p(p[0], p[1], d0) for p in lo], [F.p(p[0], p[1], d1) for p in lo], closed=True)
    mb.strip([F.p(p[0], p[1], d0) for p in hi], [F.p(p[0], p[1], d1) for p in hi], closed=True)
    return _mk(name, mb, mat, smooth=True)


def spoke(name, F, ca, cz, th, r0, r1, w, d0, d1, mat):
    """A radial tracery bar."""
    c, s = math.cos(th), math.sin(th)
    nx, nz = -s, c
    poly = []
    for (r, k) in ((r0, -1), (r1, -1), (r1, 1), (r0, 1)):
        poly.append((ca + c * r + nx * w * 0.5 * k, cz + s * r + nz * w * 0.5 * k))
    return plate(name, F, poly, d0, d1, mat)


def sq_edge(cx, cz, sq, th):
    c, s = math.cos(th), math.sin(th)
    if abs(c) < 1e-9:
        return (cx, cz + sq if s > 0 else cz - sq)
    if abs(s) < 1e-9:
        return (cx + sq if c > 0 else cx - sq, cz)
    t = min(sq / abs(c), sq / abs(s))
    return (cx + c * t, cz + s * t)


def corner_spandrels(name, F, ca, cz, R, sq, d0, d1, mat, n=8):
    """Fill the 4 corners between a circle of radius R and a square half-side sq."""
    out = []
    for q in range(4):
        th0 = q * math.pi * 0.5 + math.pi * 0.25
        mb = MB()
        rowc = []
        rows = []
        for i in range(n + 1):
            th = th0 + (math.pi * 0.5) * i / n
            cp = (ca + R * math.cos(th), cz + R * math.sin(th))
            ep = sq_edge(ca, cz, sq, th)
            rows.append((cp, ep))
        for i in range(n):
            (c0, e0), (c1, e1) = rows[i], rows[i + 1]
            mb.add((F.p(c0[0], c0[1], d0), F.p(c1[0], c1[1], d0),
                    F.p(e1[0], e1[1], d0), F.p(e0[0], e0[1], d0)))
            mb.add((F.p(c0[0], c0[1], d1), F.p(c1[0], c1[1], d1),
                    F.p(e1[0], e1[1], d1), F.p(e0[0], e0[1], d1)))
            # outer side wall of the reveal
            mb.add((F.p(c0[0], c0[1], d0), F.p(e0[0], e0[1], d0),
                    F.p(e0[0], e0[1], d1), F.p(c0[0], c0[1], d1)))
        out.append(_mk(name + "_sp%d" % q, mb, mat))
    return out


# ---------------------------------------------------------------------------
# 13. rose window (real geometry: reveal, tracery, leaded glass)
# ---------------------------------------------------------------------------
def rose(name, F, ca, cz, R, th=WALL_T, sq=None, seed=0, emit=2.2,
         spokes=12, mat=None, mat2=None, r_trac=None):
    """A rose window cut into a wall built with a square hole of half-side sq.

    F is the wall frame; (ca, cz) the centre in the wall plane.
    """
    out = []
    m1 = mat or MAT["stone_light"]
    m2 = mat2 or MAT["stone_dark"]
    if sq is None:
        sq = R + 0.14
    Rg = R - 0.06            # glass radius
    # --- splayed cylindrical reveal ---------------------------------------
    steps = ((0.0, R), (0.42 * th, R - 0.14), (th, R - 0.30))
    n = 40
    for k in range(2):
        d0, r0 = steps[k]
        d1, r1 = steps[k + 1]
        mb = MB()
        lo = [F.p(ca + r0 * math.cos(TAU * i / n), cz + r0 * math.sin(TAU * i / n), d0)
              for i in range(n)]
        hi = [F.p(ca + r1 * math.cos(TAU * i / n), cz + r1 * math.sin(TAU * i / n), d1)
              for i in range(n)]
        mb.strip(lo, hi, closed=True)
        out.append(_mk(name + "_rev%d" % k, mb, m1 if k == 0 else m2, smooth=True))
    # --- glass disc + mosaic ---------------------------------------------
    mb = MB()
    mb.add(tuple([F.p(ca + (Rg + 0.02) * math.cos(TAU * i / n),
                       cz + (Rg + 0.02) * math.sin(TAU * i / n), th - 0.16)
                  for i in range(n)]))
    out.append(_mk(name + "_bk", mb, MAT["lead"]))
    out.extend(_mosaic(name + "_gl", F, disc_contour(ca, cz, Rg, 64), th - 0.13, 0.115,
                       seed + 3, emit=emit, gap=0.010))
    # --- tracery ----------------------------------------------------------
    d0, d1 = th - 0.34, th - 0.20
    out.append(ring_band(name + "_r0", F, ca, cz, R - 0.24, 0.42, th - 0.60, th - 0.16, m1))
    r1 = (Rg) * 0.66
    out.append(ring_band(name + "_r1", F, ca, cz, r1, 0.20, d0, d1, m1))
    r2 = (Rg) * 0.30
    out.append(ring_band(name + "_r2", F, ca, cz, r2, 0.18, d0, d1, m1))
    out.append(ring_band(name + "_r3", F, ca, cz, Rg * 0.12, 0.16, d0, d1, m2))
    for k in range(spokes):
        th1 = TAU * k / spokes + math.pi / spokes * 0.0
        out.append(spoke(name + "_sp%d" % k, F, ca, cz, th1, r2 - 0.02, Rg - 0.02,
                         0.13, d0, d1, m1))
        out.append(spoke(name + "_s2%d" % k, F, ca, cz, th1 + math.pi / spokes,
                         r1 + 0.02, Rg - 0.02, 0.085, d0, d1, m2))
    # little cusps at the inner ring
    for k in range(spokes * 2):
        th1 = TAU * k / (spokes * 2) + math.pi / (spokes * 2)
        out.append(spoke(name + "_cs%d" % k, F, ca, cz, th1, r2 + 0.02, r1 - 0.02,
                         0.05, d0, d1, m2))
    # --- outer hood mould ------------------------------------------------
    out.append(ring_band(name + "_hood", F, ca, cz, R + 0.09, 0.20, -0.10, 0.10, m1))
    for ob in out:                      # glazing must not stop the light
        if "_gl" in ob.name or ob.name.endswith("_bk"):
            ob.visible_shadow = False
    ROSES.append((F, ca, cz, R, th, seed))
    return out


# ---------------------------------------------------------------------------
# 14. lunettes (the wall above a bay, following the vault's edge curve)
# ---------------------------------------------------------------------------
def lunette(name, F, a0, a1, z0, ztop, th=WALL_T, mat=None, n=16, curve="wall",
            rise=None):
    """Fill from a flat top edge (z0) up to a curve (vault web edge)."""
    if mat is None:
        mat = MAT["stone"]
    mb = MB()
    for i in range(n):
        u0 = i / float(n)
        u1 = (i + 1) / float(n)
        a_0 = a0 + (a1 - a0) * u0
        a_1 = a0 + (a1 - a0) * u1
        z_0 = ztop(a_0)
        z_1 = ztop(a_1)
        if z_0 < z0 + 1e-3 and z_1 < z0 + 1e-3:
            continue
        mb.add((F.p(a_0, z0, 0.0), F.p(a_1, z0, 0.0), F.p(a_1, z_1, 0.0),
                F.p(a_0, z_0, 0.0)))
        mb.add((F.p(a_0, z0, th), F.p(a_1, z0, th), F.p(a_1, z_1, th),
                F.p(a_0, z_0, th)))
    # close the two ends and the top edge
    return _mk(name, mb, mat)


def cler_wins(a0, a1, n=2, w=1.80, gap=0.38):
    total = n * w + (n - 1) * gap
    m = (a1 - a0 - total) * 0.5
    out = []
    for i in range(n):
        s = a0 + m + i * (w + gap)
        out.append((s, s + w))
    return out


# ---------------------------------------------------------------------------
# 15. nave / choir aisles
# ---------------------------------------------------------------------------
def build_aisle(side, y0, y1, bays, tag, top_vault=True):
    """One aisle: outer wall with windows + vaults + the aisle bay ribs."""
    out = []
    Fa = f_wall(AISLE_IN, y0, side)          # outer wall, room face inward
    n = max(1, int(round((y1 - y0) / BAY)))
    bw = (y1 - y0) / n
    for k in range(n):
        yb0 = y0 + k * bw
        yb1 = yb0 + bw
        wins = cler_wins(yb0, yb1, 2, 1.34, 0.34)
        holes = [(w0, w1, 3.60, 8.30, 1.25) for (w0, w1) in wins]
        out.append(wall_slab("%s_aw%d" % (tag, k), Fa, yb0, yb1, 0.0, Z_AIS_SPR,
                             holes, WALL_T, MAT["stone"]))
        for i, (w0, w1) in enumerate(wins):
            out.extend(window_dress(Fa, w0, w1, 3.60, 8.30, 1.25, th=WALL_T,
                                    inset=0.08, emit=1.7, transom=(6.35,),
                                    seed=40 + k * 3 + i, name="%s_aww%d_%d" % (tag, k, i)))
        out.append(plinth("%s_apl%d" % (tag, k), Fa, yb0, yb1))
        out.append(course("%s_ac1_%d" % (tag, k), Fa, yb0, yb1, 1.55, 0.12, -0.14, 0.04))
        out.append(course("%s_ac2_%d" % (tag, k), Fa, yb0, yb1, 3.42, 0.14, -0.18, 0.04))
        out.append(course("%s_ac3_%d" % (tag, k), Fa, yb0, yb1, 9.66, 0.14, -0.16, 0.04))
        # wall shafts
        for a in (yb0, yb1):
            out.append(shaft("%s_as%d_%0.1f" % (tag, k, a),
                             Fa.p(a, 1.30, -0.12), Fa.p(a, Z_AIS_SPR - 0.10, -0.12),
                             0.075))
        if top_vault:
            # lunette above the wall to meet the aisle vault
            out.append(lunette("%s_alun%d" % (tag, k), Fa, yb0, yb1, Z_AIS_SPR,
                               lambda a, yb0=yb0, yb1=yb1: Z_AIS_SPR + arch_z(
                                   a, yb0, yb1, 0.0, AIS_HR) * 1.0,
                               WALL_T, MAT["stone"], 10))
    return out


def build_aisle_vaults(side, y0, y1, tag, bays=None):
    out = []
    n = max(1, int(round((y1 - y0) / BAY)))
    bw = (y1 - y0) / n
    xa, xb = sorted((N_HW, AISLE_IN))
    for k in range(n):
        yb0 = y0 + k * bw
        yb1 = yb0 + bw
        out.extend(vault_bay("%s_av%d" % (tag, k), xa, xb, yb0, yb1,
                             Z_AIS_SPR, AIS_HT, AIS_HR, 2.10,
                             MAT["plaster"], 7, 4, True, True, True))
    return out


# ---------------------------------------------------------------------------
# 16. blind arcading (used by the triforium and the low dado arcades)
# ---------------------------------------------------------------------------
def blind_arcade(name, F, a0, a1, z0, z1, n=4, depth=0.16, mat=None,
                 spring=None, rise=None, seed=0):
    out = []
    if z1 - z0 < 0.3 or a1 - a0 < 0.4:
        return out
    span = (a1 - a0) / n
    zs = spring if spring is not None else z0 + (z1 - z0) * 0.28
    rr = rise if rise is not None else (z1 - z0) * 0.66
    mb = MB()
    d = -depth
    mb.add(tuple([F.p(a0, z0, d), F.p(a1, z0, d), F.p(a1, z1, d), F.p(a0, z1, d)]))
    out.append(_mk(name + "_bk", mb, mat or MAT["stone_dark"]))
    for i in range(n):
        s0 = a0 + span * i + 0.05
        s1 = s0 + span - 0.10
        c = arch_contour(s0, s1, z0 + 0.08, zs, rr, 9)
        mb = MB()
        mb.strip([F.p(p[0], p[1], d) for p in c], [F.p(p[0], p[1], -0.015) for p in c],
                 closed=True)
        out.append(_mk(name + "_rh%d" % i, mb, mat or MAT["stone_light"]))
        out.append(arch_rib(name + "_rb%d" % i, s0, s1, zs, rr,
                            lambda az, F=F: F.p(az[0], az[1], -0.025), 0.13, 0.09,
                            MAT["stone_light"], 9))
    for i in range(n + 1):
        a = a0 + span * i
        out.append(shaft(name + "_cl%d" % i, F.p(a, z0 + 0.04, -0.09),
                         F.p(a, z1 - 0.04, -0.09), 0.048, MAT["stone_light"]))
    return out


# ---------------------------------------------------------------------------
# 17. the high vessel: nave or choir, walls + piers + vaults
# ---------------------------------------------------------------------------
def build_vessel(y0, y1, nb, tag, aisle=True, vault=True):
    out = []
    bw = (y1 - y0) / nb
    for sy in (-1, 1):
        F = f_wall(N_HW, y0, sy)
        for k in range(nb):
            a0 = y0 + k * bw
            a1 = a0 + bw
            wins = cler_wins(a0, a1)
            out.append(elev_bay("%s_w%s_%d" % (tag, "p" if sy > 0 else "n", k),
                                F, a0, a1, wins, seed=k + (60 if sy < 0 else 0)))
            out.append(lunette("%s_lun%s_%d" % (tag, "p" if sy > 0 else "n", k),
                               F, a0, a1, Z_VAULT,
                               lambda a, a0=a0, a1=a1: Z_VAULT + arch_z(
                                   a, a0, a1, 0.0, NAVE_HR) + 0.02,
                               WALL_T, MAT["stone"], 12))
    # bay piers
    for k in range(0, nb + 1):
        y = y0 + k * bw
        if k == 0 or k == nb:
            continue
        for sy in (-1, 1):
            out.append(pier("%s_pier%s_%d" % (tag, "p" if sy > 0 else "n", k),
                            sy * N_HW, y, Z_BASE, Z_ARC_SPR, PIER_R))
    # vaults
    if vault:
        for k in range(nb):
            a0 = y0 + k * bw
            a1 = a0 + bw
            out.extend(vault_bay("%s_vb_%d" % (tag, k), -N_HW, N_HW, a0, a1,
                                 Z_VAULT, NAVE_HT, NAVE_HR, NAVE_HC,
                                 MAT["stone"], 15, 6))
    # aisle
    if aisle:
        for sy in (-1, 1):
            t = "%s_a%s" % (tag, "p" if sy > 0 else "n")
            out.extend(build_aisle(sy, y0, y1, nb, t))
            out.extend(build_aisle_vaults(sy, y0, y1, t))
    return out


# ---------------------------------------------------------------------------
# 18. crossing: four great arches, the vault, and the lantern
# ---------------------------------------------------------------------------
X_PIER = 0.80


def build_crossing():
    out = []
    x0, x1 = -N_HW, N_HW
    y0, y1 = Y_X0, Y_X1
    # --- the four corner piers -------------------------------------------
    for sx in (-1, 1):
        for y in (y0, y1):
            out.append(pier("cx_pier%s_%d" % ("p" if sx > 0 else "n", int(y)),
                            sx * N_HW, y, Z_BASE, Z_VAULT, X_PIER, big=1.35))
    # --- great arches -----------------------------------------------------
    for sx in (-1, 1):
        pl = lambda az, sx=sx: Vector((sx * N_HW, az[0], az[1]))
        out.append(arch_rib("cx_ga%s" % ("p" if sx > 0 else "n"), y0 + 0.62,
                            y1 - 0.62, Z_VAULT, NAVE_HT, pl, 0.62, 0.42))
        out.append(sweep("cx_ga2%s" % ("p" if sx > 0 else "n"),
                         [pl((y0 + 0.62 + (y1 - y0 - 1.24) * i / 200.0,
                              arch_z(y0 + 0.62 + (y1 - y0 - 1.24) * i / 200.0,
                                     y0 + 0.62, y1 - 0.62, Z_VAULT, NAVE_HT)))
                          for i in range(19)][1:-1],
                         ribprof(0.34, 0.26), MAT["stone_light"]))
    for y in (y0, y1):
        pl = lambda az, y=y: Vector((az[0], y, az[1]))
        out.append(arch_rib("cx_gb%d" % int(y), x0 + 0.62, x1 - 0.62, Z_VAULT,
                            NAVE_HT, pl, 0.62, 0.42))
        out.append(sweep("cx_gb2%d" % int(y),
                         [pl((x0 + 0.62 + (x1 - x0 - 1.24) * i / 200.0,
                              arch_z(x0 + 0.62 + (x1 - x0 - 1.24) * i / 200.0,
                                     x0 + 0.62, x1 - 0.62, Z_VAULT, NAVE_HT)))
                          for i in range(19)][1:-1],
                         ribprof(0.34, 0.26), MAT["stone_light"]))
    # --- vault with an oculus --------------------------------------------
    cy = (y0 + y1) * 0.5
    oc = (0.0, cy, 1.42)
    out.append(vault_sheet("cx_web", x0, x1, y0, y1, Z_VAULT, NAVE_HT, NAVE_HT, X_HC,
                           MAT["stone"], 17, 17, oc))
    for (p0, p1) in (((x0, y0), (x1, y1)), ((x0, y1), (x1, y0))):
        pts = vault_rib_curve(x0, x1, y0, y1, Z_VAULT, NAVE_HT, NAVE_HT, X_HC, p0, p1, 22)
        out.append(sweep("cx_dr", pts, ribprof(0.50, 0.40), MAT["stone_light"]))
    # oculus ring
    zc = vault_z(0.0, cy, x0, x1, y0, y1, Z_VAULT, NAVE_HT, NAVE_HT, X_HC)
    out.append(_oculus_ring(0.0, cy, zc, 1.42))
    out.extend(_lantern(0.0, cy, zc))
    return out


def _oculus_ring(cx, cy, z, r, mat=None):
    m = mat or MAT["stone_light"]
    n = 28
    mb = MB()
    lo = [(cx + r * math.cos(TAU * i / n), cy + r * math.sin(TAU * i / n), z - 0.02)
          for i in range(n)]
    hi = [(cx + (r + 0.30) * math.cos(TAU * i / n), cy + (r + 0.30) * math.sin(TAU * i / n),
           z + 0.30) for i in range(n)]
    mb.strip(lo, hi, closed=True)
    # underside roll
    lo2 = [(cx + r * 0.94 * math.cos(TAU * i / n), cy + r * 0.94 * math.sin(TAU * i / n),
            z - 0.24) for i in range(n)]
    mb.strip(lo2, lo, closed=True)
    mb.strip([(cx + (r + 0.30) * math.cos(TAU * i / n), cy + (r + 0.30) * math.sin(TAU * i / n),
               z + 0.30) for i in range(n)],
             [(cx + (r + 0.52) * math.cos(TAU * i / n), cy + (r + 0.52) * math.sin(TAU * i / n),
               z + 0.30) for i in range(n)], closed=True)
    return _mk("cx_ocring", mb, m, smooth=True)


def _lantern(cx, cy, z0, r=1.72, n=8):
    """A little glazed drum above the oculus: the light source of the crossing."""
    out = []
    z1 = z0 + 1.55
    z2 = z0 + 2.05
    # drum wall with 8 arch openings
    for k in range(n):
        th0 = TAU * k / n
        th1 = TAU * (k + 1) / n
        if k % 2 == 0:
            continue
        # pier between the openings
        for j in range(2):
            th = th0 + (th1 - th0) * (j * 0.5 + 0.1)
            p0 = Vector((cx + r * math.cos(th), cy + r * math.sin(th), z0))
            p1 = Vector((cx + r * math.cos(th), cy + r * math.sin(th), z1))
            out.append(sweep("lan_col", [p0, p1], [
                (0.10 * math.cos(TAU * i / 6), 0.10 * math.sin(TAU * i / 6)) for i in range(6)
            ], MAT["stone_light"], smooth=True))
    # glazing ring (a cone of emissive glass)
    mb = MB()
    n2 = 24
    lo = [(cx + r * 0.98 * math.cos(TAU * i / n2), cy + r * 0.98 * math.sin(TAU * i / n2), z0 + 0.35)
          for i in range(n2)]
    hi = [(cx + r * 0.98 * math.cos(TAU * i / n2), cy + r * 0.98 * math.sin(TAU * i / n2), z1 - 0.10)
          for i in range(n2)]
    mb.strip(lo, hi, closed=True)
    out.append(_mk("lan_gl", mb, glass_mat("lantern", "#ffe3b0", 3.2, 0.85), smooth=True))
    # top cone + apex, and a bright cap
    mb = MB()
    top = [(cx + r * 0.98 * math.cos(TAU * i / n2), cy + r * 0.98 * math.sin(TAU * i / n2), z1)
           for i in range(n2)]
    mb.strip(top, [(cx + r * 0.42 * math.cos(TAU * i / n2),
                    cy + r * 0.42 * math.sin(TAU * i / n2), z2) for i in range(n2)],
             closed=True)
    out.append(_mk("lan_cone", mb, glass_mat("lantern2", "#fff0cc", 4.0, 0.9), smooth=True))
    mb = MB()
    mb.add(tuple([(cx + r * 0.42 * math.cos(TAU * i / n2),
                   cy + r * 0.42 * math.sin(TAU * i / n2), z2) for i in range(n2)]))
    out.append(_mk("lan_cap", mb, flat_mat("lan_cap", "#fff6e0", rough=0.6, emit=6.0)))
    # outer hood so no daylight leaks around the drum
    mb = MB()
    for i in range(n2):
        a0 = TAU * i / n2
        a1 = TAU * (i + 1) / n2
        p0 = Vector((cx + (r + 0.34) * math.cos(a0), cy + (r + 0.34) * math.sin(a0), z0 - 0.20))
        p1 = Vector((cx + (r + 0.34) * math.cos(a1), cy + (r + 0.34) * math.sin(a1), z0 - 0.20))
        p2 = Vector((cx + (r + 0.34) * math.cos(a1), cy + (r + 0.34) * math.sin(a1), z2 + 0.30))
        p3 = Vector((cx + (r + 0.34) * math.cos(a0), cy + (r + 0.34) * math.sin(a0), z2 + 0.22))
        mb.add((p0, p1, p2, p3))
    out.append(_mk("lan_hood", mb, MAT["lead"]))
    return out


# ---------------------------------------------------------------------------
# 19. a wall pierced by a rose window (square hole + corner spandrels)
# ---------------------------------------------------------------------------
def wall_around_rose(name, F, a0, a1, z0, z1, ca, cz, R, th=WALL_T, mat=None,
                     holes=(), seed=0, spokes=12, emit=2.2):
    out = []
    m = mat or MAT["stone"]
    sq = R + 0.16
    if cz - sq > z0 + 0.08:
        out.append(wall_slab(name + "_lo", F, a0, a1, z0, cz - sq,
                             [h for h in holes if h[2] < cz - sq], th, m))
    if z1 > cz + sq + 0.08:
        out.append(wall_slab(name + "_hi", F, a0, a1, cz + sq, z1, (), th, m))
    if ca - sq > a0 + 0.08:
        out.append(wall_slab(name + "_l", F, a0, ca - sq, cz - sq, cz + sq, (), th, m))
    if a1 > ca + sq + 0.08:
        out.append(wall_slab(name + "_r", F, ca + sq, a1, cz - sq, cz + sq, (), th, m))
    out.extend(corner_spandrels(name + "_sp", F, ca, cz, R, sq, 0.0, th, m))
    out.extend(rose(name + "_r", F, ca, cz, R, th, sq, seed, emit, spokes))
    return out


# ---------------------------------------------------------------------------
# 20. transept
# ---------------------------------------------------------------------------
TR_WIN = dict(sill=4.55, spr=13.40, rise=2.30, w=1.52, gap=0.52)


def build_transept():
    out = []
    for sx in (-1, 1):
        xa, xb = (N_HW, TR_X) if sx > 0 else (-TR_X, -N_HW)
        tag = "tr%s" % ("p" if sx > 0 else "n")
        # ---- the two long walls ------------------------------------------
        for ywall, nrm in ((Y_X0, -1), (Y_X1, 1)):
            F = Frame((0.0, ywall, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
                      (0.0, nrm, 0.0))
            t2 = "%s_%s" % (tag, "s" if ywall == Y_X0 else "n")
            for k in range(NTRB):
                a0 = xa + k * TR_BAY
                a1 = a0 + TR_BAY
                wins = cler_wins(a0, a1, 2, TR_WIN["w"], TR_WIN["gap"])
                holes = [(w0, w1, TR_WIN["sill"], TR_WIN["spr"], TR_WIN["rise"])
                         for (w0, w1) in wins]
                out.append(wall_slab("%s_w%d" % (t2, k), F, a0, a1, 0.0, Z_VAULT,
                                     holes, WALL_T, MAT["stone"]))
                for i, (w0, w1) in enumerate(wins):
                    out.extend(window_dress(F, w0, w1, TR_WIN["sill"], TR_WIN["spr"],
                                            TR_WIN["rise"], th=WALL_T, inset=0.10,
                                            emit=2.0, transom=(9.0, 11.4),
                                            seed=70 + k * 4 + i + (0 if sx > 0 else 40),
                                            name="%s_w%d_%d" % (t2, k, i)))
                out.extend(blind_arcade("%s_ba%d" % (t2, k), F, a0 + 0.30, a1 - 0.30,
                                        1.35, 4.05, 3, 0.15, MAT["stone_dark"],
                                        spring=3.05, rise=1.05, seed=k))
                out.append(plinth("%s_pl%d" % (t2, k), F, a0, a1))
                for zz in (1.30, 4.12, 14.20, 19.35):
                    out.append(course("%s_c%d_%0.1f" % (t2, k, zz), F, a0, a1, zz,
                                      0.12, -0.13, 0.04))
                for a in (a0, a1):
                    out.append(shaft("%s_sh%d_%0.2f" % (t2, k, a),
                                     F.p(a, 1.35, -0.12), F.p(a, Z_VAULT - 0.10, -0.12),
                                     0.085 if abs(a) > N_HW + 0.1 else 0.10))
                out.append(lunette("%s_lu%d" % (t2, k), F, a0, a1, Z_VAULT,
                                   lambda a, a0=a0, a1=a1: Z_VAULT + arch_z(
                                       a, a0, a1, 0.0, TRANSEPT_HT) + 0.02,
                                   WALL_T, MAT["stone"], 8))
        # ---- the arm's vaults --------------------------------------------
        for k in range(NTRB):
            a0 = xa + k * TR_BAY
            a1 = a0 + TR_BAY
            out.extend(vault_bay("%s_vb%d" % (tag, k), a0, a1, Y_X0, Y_X1,
                                 Z_VAULT, TRANSEPT_HT, NAVE_HT, NAVE_HC,
                                 MAT["stone"], 8, 18))
        # ---- the end wall ------------------------------------------------
        Fe = Frame((sx * TR_X, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
                   (float(sx), 0.0, 0.0))
        ca = (Y_X0 + Y_X1) * 0.5
        portal = [(ca - 1.95, ca + 1.95, 0.0, 5.60, 2.20)]
        out.extend(wall_around_rose("%s_end" % tag, Fe, Y_X0, Y_X1, 0.0, Z_VAULT,
                                    ca, ROSE_T_Z, ROSE_T_R, WALL_T, MAT["stone"],
                                    portal, seed=8 + (0 if sx > 0 else 5),
                                    spokes=12, emit=6.0))
        out.append(plinth("%s_epl" % tag, Fe, Y_X0, Y_X1))
        for zz in (1.30, 3.10, 9.30, 19.55):
            out.append(course("%s_ec%d" % (tag, int(zz * 10)), Fe, Y_X0, Y_X1,
                              zz, 0.13, -0.14, 0.05))
        out.append(lunette("%s_elu" % tag, Fe, Y_X0, Y_X1, Z_VAULT,
                           lambda a: Z_VAULT + arch_z(a, Y_X0, Y_X1, 0.0, NAVE_HT) + 0.02,
                           WALL_T, MAT["stone"], 14))
        # portal surround + steps + the door itself
        out.extend(_portal_trim("%s_ep" % tag, Fe, ca - 1.95, ca + 1.95, 5.60, 2.20,
                                WALL_T))
        out.extend(_doors("%s_ed" % tag, Fe, ca - 1.90, ca + 1.90, 5.55, 2.15,
                          WALL_T, height=4.9))
        # ---- the corner piers of the arm --------------------------------
        for y in (Y_X0, Y_X1):
            out.append(pier("%s_cp%d" % (tag, int(y)), sx * N_HW, y, Z_BASE, Z_VAULT,
                            X_PIER, big=1.1))
    return out


TRANSEPT_HT = 1.15


def _portal_trim(name, F, a0, a1, zspr, rise, th):
    """Two receding mouldings around an arched doorway."""
    out = []
    for k, (dw, dz) in enumerate(((0.26, 0.0), (0.52, 0.10))):
        c = arch_contour(a0 - dw, a1 + dw, -0.10, zspr + dz, rise + dz * 0.6, 14)
        pts = [F.p(p[0], p[1], 0.06) for p in c]
        pts.append(pts[0])
        out.append(sweep(name + "_%d" % k, pts, _frame_prof(), MAT["stone_light"]))
    return out


def _doors(name, F, a0, a1, zspr, rise, th, height=5.0):
    """A pair of oak leaves set back in the reveal, the right one ajar."""
    out = []
    ca = (a0 + a1) * 0.5
    d = th - 0.34
    for k, (b0, b1, ang) in enumerate(((a0, ca, 0.0), (ca, a1, 0.40))):
        n = 7
        hinge = F.p(b0, 0.02, d)
        R = Matrix.Rotation(-ang, 4, F.V)

        def put(p):
            return hinge + (R @ (p - hinge)) if ang else p

        for i in range(n):
            aa = b0 + (b1 - b0) * (i / float(n))
            ab = b0 + (b1 - b0) * ((i + 1) / float(n))
            t0 = zspr + arch_z(aa, a0, a1, 0.0, rise) - 0.03
            t1 = zspr + arch_z(ab, a0, a1, 0.0, rise) - 0.03
            mb = MB()
            mb.add((put(F.p(aa, 0.04, d)), put(F.p(ab, 0.04, d)),
                    put(F.p(ab, t1, d)), put(F.p(aa, t0, d))))
            mb.add((put(F.p(aa, 0.04, d - 0.09)), put(F.p(ab, 0.04, d - 0.09)),
                    put(F.p(ab, t1, d - 0.09)), put(F.p(aa, t0, d - 0.09))))
            out.append(_mk("%s_b%d_%d" % (name, k, i), mb, MAT["wood"]))
        # iron straps
        for zz in (0.55, 1.75, 3.05):
            if zz > zspr:
                continue
            mb = MB()
            mb.add((put(F.p(b0 + 0.10, zz, d - 0.10)), put(F.p(b1 - 0.06, zz, d - 0.10)),
                    put(F.p(b1 - 0.06, zz + 0.11, d - 0.10)),
                    put(F.p(b0 + 0.10, zz + 0.11, d - 0.10))))
            out.append(_mk("%s_st%d_%d" % (name, k, int(zz * 10)), mb, MAT["iron"]))
        # ring handle
        aa = (b1 - 0.24) if k == 0 else (b0 + 0.24)
        cz = 2.30
        out.append(sweep("%s_h%d" % (name, k),
                         [put(F.p(aa + 0.15 * math.cos(TAU * i / 12),
                                  cz + 0.15 * math.sin(TAU * i / 12), d - 0.13))
                          for i in range(13)],
                         [(0.021 * math.cos(TAU * j / 6), 0.021 * math.sin(TAU * j / 6))
                          for j in range(6)], MAT["brass"], smooth=True))
    return out


# ---------------------------------------------------------------------------
# 21. apse + ambulatory (the chevet)
# ---------------------------------------------------------------------------
APSE_V = APSE_R / math.cos(math.pi / 10.0)     # vertex radius of the half-decagon
APSE_CH = 2.0 * APSE_V * math.sin(math.pi / 10.0)


def _apse_pts(k):
    th = math.pi * k / 5.0
    return Vector((APSE_V * math.cos(th), Y_APSE + APSE_V * math.sin(th), 0.0))


def _facet_frame(k):
    p0 = _apse_pts(k)
    p1 = _apse_pts(k + 1)
    U = (p1 - p0).normalized()
    th = math.pi * (k + 0.5) / 5.0
    N = Vector((math.cos(th), math.sin(th), 0.0))
    return Frame(p0, U, Vector((0.0, 0.0, 1.0)), N)


def arch_soffit(name, F, a0, a1, zsill, zspr, rise, th=WALL_T, mat=None, n=14):
    """The intrados + jambs of an *open* arch through a wall (no glass)."""
    c = arch_contour(a0, a1, zsill, zspr, rise, n)
    mb = MB()
    mb.strip([F.p(p[0], p[1], 0.0) for p in c],
             [F.p(p[0], p[1], th) for p in c], closed=True)
    return _mk(name, mb, mat or MAT["stone_light"], smooth=True)


def build_apse():
    out = []
    L("apse: %d facets, apothem %.2f, chord %.2f" % (5, APSE_R, APSE_CH))
    for k in range(5):
        F = _facet_frame(k)
        t = "apse%d" % k
        wins = cler_wins(0.0, APSE_CH, 2, 1.28, 0.46)
        holes = [(w0, w1, 4.20, 10.30, 2.05) for (w0, w1) in wins]
        holes += [(w0, w1, 14.95, 18.40, 1.05) for (w0, w1) in
                  cler_wins(0.0, APSE_CH, 2, 1.02, 1.16)]
        out.append(wall_slab(t + "_w", F, 0.0, APSE_CH, 0.0, Z_VAULT, holes,
                             WALL_T, MAT["stone"]))
        for i, (w0, w1) in enumerate(wins):
            out.extend(window_dress(F, w0, w1, 4.20, 10.30, 2.05, th=WALL_T,
                                    inset=0.10, emit=2.1, transom=(7.55,),
                                    seed=90 + k * 4 + i, name="%s_ww%d" % (t, i)))
        for i, (w0, w1) in enumerate(cler_wins(0.0, APSE_CH, 2, 1.02, 1.16)):
            out.extend(window_dress(F, w0, w1, 14.95, 18.40, 1.05, th=WALL_T,
                                    inset=0.10, emit=1.9, seed=120 + k * 3 + i,
                                    name="%s_uw%d" % (t, i)))
        out.extend(blind_arcade(t + "_ba", F, 0.35, APSE_CH - 0.35, 1.30, 3.95, 3,
                                0.15, MAT["stone_dark"], spring=2.95, rise=1.00,
                                seed=k))
        out.append(plinth(t + "_pl", F, 0.0, APSE_CH))
        for zz in (1.28, 4.05, 12.55, 14.60, 19.30):
            out.append(course(t + "_c%0.1f" % zz, F, 0.0, APSE_CH, zz, 0.13, -0.14, 0.05))
        out.extend(blind_arcade(t + "_tf", F, 0.30, APSE_CH - 0.30, 12.75, 14.45, 4,
                                0.17, MAT["stone_dark"], spring=13.55, rise=0.85,
                                seed=k + 3))
        # engaged vaulting shafts at the joints
        out.append(shaft(t + "_s0", F.p(0.0, 1.30, -0.14), F.p(0.0, Z_VAULT - 0.15, -0.14),
                         0.10, MAT["stone_light"]))
    # ---- the six joint piers (engaged clusters standing in the room) -----
    for k in range(6):
        th = math.pi * k / 5.0
        cx = APSE_V * math.cos(th)
        cy = Y_APSE + APSE_V * math.sin(th)
        nx, ny = -math.cos(th), -math.sin(th)
        tx, ty = -math.sin(th), math.cos(th)
        for j, (off, dep, rr) in enumerate(((0.00, 0.40, 0.150),
                                            (-0.30, 0.22, 0.085),
                                            (0.30, 0.22, 0.085))):
            bx = cx + nx * dep + tx * off
            by = cy + ny * dep + ty * off
            out.append(shaft("apse_jp%d_%d" % (k, j), Vector((bx, by, Z_BASE)),
                             Vector((bx, by, Z_VAULT - 0.10)), rr,
                             MAT["stone_light"], base=(j == 0)))
        out.append(course("apse_jc%d" % k, Frame(Vector((cx + nx * 0.30, cy + ny * 0.30, 0.0)),
                                                 Vector((tx, ty, 0.0)),
                                                 Vector((0.0, 0.0, 1.0)),
                                                 Vector((nx, ny, 0.0))),
                          -0.45, 0.45, 1.16, 0.16, -0.20, 0.02))
    out.extend(dome_conch("apse_conch", 0.0, Y_APSE, APSE_R, Z_VAULT, Z_APSE_CROWN,
                          11, 6, MAT["plaster"], 11))
    # ---- the walls that close the chevet's straight bay -----------------
    for sx in (-1, 1):
        F = Frame((0.0, Y_APSE, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
                  (0.0, 1.0, 0.0))
        tg = "p" if sx > 0 else "n"
        a0, a1 = sort_pair(sx * APSE_V, sx * AISLE_IN)
        oa0, oa1 = a0 + 0.62, a1 - 0.62
        out.append(wall_slab("chevet_%s" % tg, F, a0, a1, 0.0, Z_VAULT,
                             [(oa0, oa1, 0.0, 8.20, 1.55)], WALL_T, MAT["stone"]))
        out.append(arch_soffit("chevet_%s_ar" % tg, F, oa0, oa1, 0.0, 8.20, 1.55,
                               WALL_T, MAT["stone_light"]))
        out.extend(_portal_trim("chevet_%s_pm" % tg, F, oa0, oa1, 8.20, 1.55, WALL_T))
        out.append(plinth("chevet_pl%s" % tg, F, a0, a1))
        out.append(course("chevet_c%s" % tg, F, a0, a1, 9.95, 0.14, -0.14, 0.05))
        out.append(course("chevet_c2%s" % tg, F, a0, a1, 1.32, 0.13, -0.14, 0.04))
    return out


def sort_pair(a, b):
    return (a, b) if a < b else (b, a)


# ---------------------------------------------------------------------------
# 22. ambulatory (the ring behind the apse)
# ---------------------------------------------------------------------------
AMB_SEG = 10


def build_ambulatory():
    out = []
    r0, r1 = APSE_R + WALL_T, AMB_OUT
    for k in range(AMB_SEG):
        th0 = math.pi * k / AMB_SEG
        th1 = math.pi * (k + 1) / AMB_SEG
        p0 = Vector((r1 * math.cos(th0), Y_APSE + r1 * math.sin(th0), 0.0))
        p1 = Vector((r1 * math.cos(th1), Y_APSE + r1 * math.sin(th1), 0.0))
        F = Frame(p0, (p1 - p0).normalized(), Vector((0.0, 0.0, 1.0)), Vector(
            (math.cos(0.5 * (th0 + th1)), math.sin(0.5 * (th0 + th1)), 0.0)))
        cl = (p1 - p0).length
        t = "amb%d" % k
        wins = cler_wins(0.0, cl, 1, 1.30, 0.0)
        holes = [(w0, w1, 3.70, 9.30, 1.55) for (w0, w1) in wins]
        out.append(wall_slab(t + "_w", F, 0.0, cl, 0.0, Z_AMB_SPR, holes, WALL_T,
                             MAT["stone"]))
        for i, (w0, w1) in enumerate(wins):
            out.extend(window_dress(F, w0, w1, 3.70, 9.30, 1.55, th=WALL_T,
                                    inset=0.10, emit=1.9, transom=(6.70,),
                                    seed=150 + k * 3 + i, name="%s_ww%d" % (t, i)))
        out.append(plinth(t + "_pl", F, 0.0, cl))
        for zz in (1.42, 3.52, 10.85):
            out.append(course(t + "_c%0.1f" % zz, F, 0.0, cl, zz, 0.12, -0.13, 0.04))
        out.append(shaft(t + "_s0", F.p(0.0, 1.30, -0.13), F.p(0.0, Z_AMB_SPR - 0.10, -0.13),
                         0.09, MAT["stone_light"]))
    # annular barrel vault over the ring
    zs, rise = Z_AMB_SPR, Z_AMB_RISE
    nr, nt = 5, 3

    def _av(kk, ii, jj):
        u = ii / float(nr)
        rr = r0 + (r1 - r0) * u
        zz = zs + rise * math.sqrt(max(0.0, 1.0 - (2.0 * u - 1.0) ** 2))
        th = math.pi * (kk + jj / float(nt)) / AMB_SEG
        return Vector((rr * math.cos(th), Y_APSE + rr * math.sin(th), zz))

    mb = MB()
    for k in range(AMB_SEG):
        for j in range(nt):
            for i in range(nr):
                mb.quad(_av(k, i, j), _av(k, i + 1, j), _av(k, i + 1, j + 1),
                        _av(k, i, j + 1))
    out.append(_mk("amb_vault", mb, MAT["plaster"], smooth=True))
    # radial ribs
    for k in range(AMB_SEG + 1):
        th = math.pi * k / AMB_SEG
        pts = []
        for i in range(nr + 1):
            u = i / float(nr)
            rr = r0 + (r1 - r0) * u
            zz = zs + rise * math.sqrt(max(0.0, 1.0 - (2.0 * u - 1.0) ** 2))
            pts.append(Vector((rr * math.cos(th), Y_APSE + rr * math.sin(th), zz - 0.03)))
        out.append(sweep("amb_rib%d" % k, pts, ribprof(0.26, 0.22), MAT["stone_light"]))
    # bosses on the rib crowns?  (nothing in the middle of a barrel)
    return out


# ---------------------------------------------------------------------------
# 23. the west front, from the inside
# ---------------------------------------------------------------------------
def build_west():
    out = []
    F = Frame((-AISLE_IN, Y_W, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
              (0.0, -1.0, 0.0))
    a_mid = AISLE_IN                      # a of the centre line
    c0, c1 = a_mid - N_HW, a_mid + N_HW   # 5.60 .. 18.60
    door_a0, door_a1 = a_mid - 2.55, a_mid + 2.55
    door_spr, door_rise = 6.60, 1.85
    # --- central bay -----------------------------------------------------
    out.extend(wall_around_rose("west_c", F, c0, c1, 0.0, Z_VAULT, a_mid, ROSE_W_Z,
                                ROSE_W_R, WALL_T, MAT["stone"],
                                [(door_a0, door_a1, 0.0, door_spr, door_rise)],
                                seed=11, spokes=12, emit=7.0))
    out.extend(_portal_trim("west_dt", F, door_a0, door_a1, door_spr, door_rise, WALL_T))
    out.extend(_doors("west_dd", F, door_a0, door_a1, door_spr, door_rise, WALL_T))
    out.append(plinth("west_pl", F, c0, c1))
    for zz in (1.34, 3.20, 9.55, 20.30):
        out.append(course("west_c%0.1f" % zz, F, c0, c1, zz, 0.14, -0.15, 0.05))
    out.append(lunette("west_lun", F, c0, c1, Z_VAULT,
                       lambda a: Z_VAULT + arch_z(a, c0, c1, 0.0, NAVE_HT) + 0.02,
                       WALL_T, MAT["stone"], 16))
    # tympanum band of blind arcading between the door and the rose
    out.extend(blind_arcade("west_ty", F, c0 + 0.35, c1 - 0.35, 8.75, 10.20, 5,
                            0.13, MAT["stone_dark"], spring=9.55, rise=0.75, seed=2))
    # --- the two aisle ends ----------------------------------------------
    for sx in (-1, 1):
        a0, a1 = (0.0, c0) if sx < 0 else (c1, 2.0 * AISLE_IN)
        t = "west_a%s" % ("n" if sx < 0 else "p")
        wins = cler_wins(a0, a1, 1, 1.36, 0.0)
        holes = [(w0, w1, 3.60, 8.55, 1.45) for (w0, w1) in wins]
        out.append(wall_slab(t, F, a0, a1, 0.0, Z_AIS_SPR, holes, WALL_T, MAT["stone"]))
        for i, (w0, w1) in enumerate(wins):
            out.extend(window_dress(F, w0, w1, 3.60, 8.55, 1.45, th=WALL_T, inset=0.10,
                                    emit=1.8, transom=(6.30,), seed=180 + i + (0 if sx > 0 else 7),
                                    name="%s_w%d" % (t, i)))
        out.append(plinth(t + "_pl", F, a0, a1))
        for zz in (1.40, 3.45, 9.05):
            out.append(course("%s_c%0.1f" % (t, zz), F, a0, a1, zz, 0.12, -0.13, 0.04))
        out.append(lunette(t + "_lun", F, a0, a1, Z_AIS_SPR,
                           lambda a, a0=a0, a1=a1: Z_AIS_SPR + arch_z(
                               a, a0, a1, 0.0, AIS_HT) + 0.02,
                           WALL_T, MAT["stone"], 8))
    # --- a marble threshold inside the door ------------------------------
    mb = MB()
    mb.add((F.p(door_a0 - 0.55, 0.02, -1.60), F.p(door_a1 + 0.55, 0.02, -1.60),
            F.p(door_a1 + 0.55, 0.02, -0.10), F.p(door_a0 - 0.55, 0.02, -0.10)))
    out.append(_mk("west_thr", mb, MAT["marble"]))
    for i in range(2):
        mb = MB()
        zz = 0.06 * (i + 1)
        mb.add((F.p(door_a0 - 0.55 + 0.3 * i, zz, -1.60), F.p(door_a1 + 0.55 - 0.3 * i, zz, -1.60),
                F.p(door_a1 + 0.55 - 0.3 * i, zz, -0.10), F.p(door_a0 - 0.55 + 0.3 * i, zz, -0.10)))
        out.append(_mk("west_thr%d" % i, mb, MAT["marble"]))
    return out


def _step(name, F, d0, d1, z0, a0, a1, h):
    mb = MB()
    mb.add((F.p(a0, z0, -d0), F.p(a1, z0, -d0), F.p(a1, z0, -d1), F.p(a0, z0, -d1)))
    mb.add((F.p(a0, z0 + h, -d0), F.p(a1, z0 + h, -d0),
            F.p(a1, z0 + h, -d1), F.p(a0, z0 + h, -d1)))
    mb.add((F.p(a0, z0, -d1), F.p(a1, z0, -d1), F.p(a1, z0 + h, -d1),
            F.p(a0, z0 + h, -d1)))
    return _mk(name, mb, MAT["marble"])


# ---------------------------------------------------------------------------
# 24. floors
# ---------------------------------------------------------------------------
def _slab_rect(name, x0, x1, y0, y1, z=0.0, seed=0, gap=0.011, wlo=0.95, whi=1.55):
    rng = random.Random(seed)
    mb = MB()
    mi = []
    mats = [MAT["floor1"], MAT["floor2"], MAT["floor3"], MAT["floor4"]]
    y = y0
    while y < y1 - 1e-5:
        h = min(rng.uniform(wlo * 0.9, whi * 0.9), y1 - y)
        x = x0
        while x < x1 - 1e-5:
            w = min(rng.uniform(wlo, whi), x1 - x)
            mb.add((Vector((x + gap, y + gap, z)), Vector((x + w - gap, y + gap, z)),
                    Vector((x + w - gap, y + h - gap, z)),
                    Vector((x + gap, y + h - gap, z))))
            mi.append(rng.randrange(4))
            x += w
        y += h
    ob = _mk(name, mb, mats)
    for i, p in enumerate(ob.data.polygons):
        if i < len(mi):
            p.material_index = mi[i]
    return ob


def _slab_ring(name, cy, r0, r1, z=0.0, seed=0, gap=0.011, nth=30):
    rng = random.Random(seed)
    mb = MB()
    mi = []
    mats = [MAT["floor1"], MAT["floor2"], MAT["floor3"], MAT["floor4"]]
    for k in range(nth):
        t0 = math.pi * k / nth
        t1 = math.pi * (k + 1) / nth
        rr = r0
        while rr < r1 - 1e-5:
            st = min(rng.uniform(0.95, 1.45), r1 - rr)
            ri = rr + gap
            ro = rr + st - gap
            if ri > ro - 1e-4:
                rr += st
                continue
            g0 = gap / max(ri, 0.30)
            g1 = gap / max(ri, 0.30)
            A = Vector((ri * math.cos(t0 + g0), cy + ri * math.sin(t0 + g0), z))
            B = Vector((ro * math.cos(t0 + g0), cy + ro * math.sin(t0 + g0), z))
            C = Vector((ro * math.cos(t1 - g1), cy + ro * math.sin(t1 - g1), z))
            D = Vector((ri * math.cos(t1 - g1), cy + ri * math.sin(t1 - g1), z))
            if ri < 1e-3:
                A = Vector((0.0, cy, z))
                D = Vector((0.0, cy, z))
                mb.add((A, B, C))
            else:
                mb.add((A, B, C, D))
            mi.append(rng.randrange(4))
            rr += st
    ob = _mk(name, mb, mats)
    for i, p in enumerate(ob.data.polygons):
        if i < len(mi):
            p.material_index = mi[i]
    return ob


def build_floor():
    out = []
    L("floor")
    FZ_CH = 0.45        # choir + sanctuary platform
    # --- the main vessel runs unbroken from the west door to the apse ------
    out.append(_slab_rect("fl_nave", -N_HW, N_HW, Y_W, Y_X0, 0.0, 3))
    out.append(_slab_rect("fl_choir", -N_HW, N_HW, Y_X1, Y_APSE, FZ_CH, 5))
    out.append(_slab_rect("fl_cross", -N_HW, N_HW, Y_X0, Y_X1, 0.0, 4))
    for sx in (-1, 1):
        tg = "p" if sx > 0 else "n"
        xa, xb = sort_pair(sx * N_HW, sx * AISLE_IN)
        out.append(_slab_rect("fl_na%s" % tg, xa, xb, Y_W, Y_X0, 0.0, 7 + (sx > 0)))
        out.append(_slab_rect("fl_ca%s" % tg, xa, xb, Y_X1, Y_APSE, FZ_CH, 15 + (sx > 0)))
        ta, tb = sort_pair(sx * N_HW, sx * TR_X)
        out.append(_slab_rect("fl_tr%s" % tg, ta, tb, Y_X0, Y_X1, 0.0, 9 + (sx > 0)))
    # --- the choir platform (a raised box with a stepped front) ------------
    mb = MB()
    for i in range(3):
        zt = FZ_CH * (i + 1) / 3.0
        yb = Y_X1 - 0.40 * (3 - i)
        mb.add((Vector((-N_HW, yb, 0.0)), Vector((N_HW, yb, 0.0)),
                Vector((N_HW, yb, zt)), Vector((-N_HW, yb, zt))))
        mb.add((Vector((-N_HW, yb, zt)), Vector((N_HW, yb, zt)),
                Vector((N_HW, Y_X1 + 0.02, FZ_CH)), Vector((-N_HW, Y_X1 + 0.02, FZ_CH))))
    out.append(_mk("fl_pl_st", mb, MAT["marble"]))
    mb = MB()
    mb.add((Vector((-N_HW, Y_X1, FZ_CH)), Vector((N_HW, Y_X1, FZ_CH)),
            Vector((N_HW, Y_X1, FZ_CH + 0.10)), Vector((-N_HW, Y_X1, FZ_CH + 0.10))))
    out.append(_mk("fl_pl_nose", mb, MAT["marble"]))
    # --- sanctuary platform, flush with the choir -------------------------
    out.append(_slab_ring("fl_apse", Y_APSE, 0.0, APSE_R, FZ_CH, 12, nth=26))
    out.append(_slab_ring("fl_amb", Y_APSE, APSE_R + WALL_T, AMB_OUT, FZ_CH, 13, nth=26))
    mb = MB()
    mb.add(tuple([Vector((APSE_V * math.cos(math.pi * k / 5.0),
                          Y_APSE + APSE_V * math.sin(math.pi * k / 5.0), FZ_CH))
                  for k in range(6)]))
    out.append(_mk("fl_apse_edge", mb, MAT["marble"]))
    # mortared under-layer so the joints read dark
    for (nm, x0, x1, y0, y1, z) in (("fl_um_n", -N_HW, N_HW, Y_W, Y_APSE, -0.03),
                                    ("fl_um_a", -AISLE_IN, AISLE_IN, Y_W, Y_APSE, -0.03),
                                    ("fl_um_t", -TR_X, TR_X, Y_X0, Y_X1, -0.03)):
        mb = MB()
        mb.add((Vector((x0, y0, z)), Vector((x1, y0, z)), Vector((x1, y1, z)),
                Vector((x0, y1, z))))
        out.append(_mk(nm, mb, MAT["stone_dark"]))
    out.extend(_tomb_slabs())
    return out


def F_axis():
    return Frame((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))


TOMB_SPOTS = ((-4.30, -33.0, 1.9, 1.0), (4.30, -31.0, 1.9, 1.0),
              (-4.30, -24.5, 1.9, 1.0), (4.30, -22.5, 1.9, 1.0),
              (-4.30, -16.5, 1.9, 1.0), (4.30, -14.0, 1.9, 1.0),
              (-3.90, 3.60, 2.2, 1.15), (3.90, 3.60, 2.2, 1.15))


def _tomb_slabs():
    out = []
    for i, (x, y, w, d) in enumerate(TOMB_SPOTS):
        z = 0.012 if y < Y_X1 else 0.46
        mb = MB()
        mb.add((Vector((x - w * 0.5, y - d * 0.5, z + 0.05)),
                Vector((x + w * 0.5, y - d * 0.5, z + 0.05)),
                Vector((x + w * 0.5, y + d * 0.5, z + 0.05)),
                Vector((x - w * 0.5, y + d * 0.5, z + 0.05))))
        out.append(_mk("tomb_pl%d" % i, mb, MAT["bronze_dark"]))
        # raised border
        for (dx, dy, sw, sd) in ((0, d * 0.5 - 0.045, w, 0.09),
                                 (0, -d * 0.5 + 0.045, w, 0.09),
                                 (w * 0.5 - 0.045, 0, 0.09, d),
                                 (-w * 0.5 + 0.045, 0, 0.09, d)):
            mb = MB()
            mb.add((Vector((x + dx - sw * 0.5, y + dy - sd * 0.5, z + 0.075)),
                    Vector((x + dx + sw * 0.5, y + dy - sd * 0.5, z + 0.075)),
                    Vector((x + dx + sw * 0.5, y + dy + sd * 0.5, z + 0.075)),
                    Vector((x + dx - sw * 0.5, y + dy + sd * 0.5, z + 0.075))))
            out.append(_mk("tomb_bd%d" % i, mb, MAT["brass"]))
        # the effigy: a recumbent figure on the slab
        out.extend(_effigy("tomb_ef%d" % i, x, y, z + 0.055, min(w * 0.82, 1.75),
                           w * 0.34, 0.26))
        # inscription lines
        for k in range(3):
            mb = MB()
            ww = w * (0.42 - 0.08 * k)
            yy = y + d * 0.32 + k * 0.13
            mb.add((Vector((x - ww * 0.5, yy, z + 0.062)),
                    Vector((x + ww * 0.5, yy, z + 0.062)),
                    Vector((x + ww * 0.5, yy + 0.045, z + 0.062)),
                    Vector((x - ww * 0.5, yy + 0.045, z + 0.062))))
            out.append(_mk("tomb_in%d_%d" % (i, k), mb, MAT["gilt"]))
    return out


def _effigy(name, x, y, z, ln=1.6, wd=0.44, ht=0.26):
    """A recumbent figure, head to +y, lying on a tomb slab."""
    out = []
    prof = [(-1.00, 0.00), (-0.92, 0.55), (-0.45, 0.90), (0.00, 1.00),
            (0.45, 0.90), (0.92, 0.55), (1.00, 0.00)]
    n = 10
    rows = []
    for i in range(n + 1):
        u = i / float(n)
        yy = y - ln * 0.5 + ln * u
        r = wd * 0.5 * (0.55 + 0.45 * math.sin(math.pi * min(1.0, u * 1.02)))
        if u > 0.86:
            r *= 0.80
        rows.append([Vector((x + px * r, yy, z + pz * ht)) for (px, pz) in prof])
    mb = MB()
    for i in range(n):
        mb.strip(rows[i], rows[i + 1], closed=False)
    out.append(_mk(name + "_body", mb, MAT["marble"], smooth=True))
    hz = z + ht * 0.80
    ob = MK.sphere(name + "_hd", MK.T_at(x, y + ln * 0.5 + 0.10, hz), 0.135,
                   MAT["marble"], seg=14, ring=8)
    PARTS.append(ob)
    out.append(ob)
    # a book and folded hands
    mb = MB()
    mb.add((Vector((x - 0.09, y + 0.10, hz + 0.02)), Vector((x + 0.09, y + 0.10, hz + 0.02)),
            Vector((x + 0.09, y + 0.30, hz + 0.02)), Vector((x - 0.09, y + 0.30, hz + 0.02))))
    out.append(_mk(name + "_bk", mb, MAT["gilt"]))
    return out


# ---------------------------------------------------------------------------
# 25. furniture
# ---------------------------------------------------------------------------
def _bx(mb, x0, x1, y0, y1, z0, z1, top=True, bot=False):
    P = Vector
    mb.add((P((x0, y0, z1)), P((x1, y0, z1)), P((x1, y1, z1)), P((x0, y1, z1))))
    if bot:
        mb.add((P((x0, y0, z0)), P((x1, y0, z0)), P((x1, y1, z0)), P((x0, y1, z0))))
    mb.add((P((x0, y0, z0)), P((x1, y0, z0)), P((x1, y0, z1)), P((x0, y0, z1))))
    mb.add((P((x0, y1, z0)), P((x1, y1, z0)), P((x1, y1, z1)), P((x0, y1, z1))))
    mb.add((P((x0, y0, z0)), P((x0, y1, z0)), P((x0, y1, z1)), P((x0, y0, z1))))
    mb.add((P((x1, y0, z0)), P((x1, y1, z0)), P((x1, y1, z1)), P((x1, y0, z1))))


def _pew_into(mb, x0, x1, y, z0):
    """One bench: seat, back, book ledge, kneeler and two shaped ends."""
    d = 0.46
    _bx(mb, x0 + 0.06, x1 - 0.06, y, y + 0.40, z0 + 0.42, z0 + 0.48)
    _bx(mb, x0 + 0.06, x1 - 0.06, y + 0.36, y + 0.42, z0 + 0.46, z0 + 1.02)
    _bx(mb, x0 + 0.06, x1 - 0.06, y + 0.18, y + 0.24, z0 + 0.66, z0 + 1.06)
    _bx(mb, x0 + 0.06, x1 - 0.06, y - 0.30, y - 0.24, z0 + 0.10, z0 + 0.16)
    for xx in (x0, x1 - 0.055):
        _bx(mb, xx, xx + 0.055, y - 0.34, y + 0.44, z0, z0 + 0.50)
        _bx(mb, xx, xx + 0.055, y + 0.30, y + 0.44, z0 + 0.50, z0 + 0.94)
        _bx(mb, xx, xx + 0.055, y + 0.10, y + 0.30, z0 + 0.50, z0 + 0.62)


def build_pews():
    out = []
    z = 0.0
    n = PEW_N
    pitch = 1.78
    for s in (-1, 1):
        mb = MB()
        for k in range(n):
            y = PEW_Y0 + k * pitch
            x0, x1 = (1.35, 5.60) if s > 0 else (-5.60, -1.35)
            _pew_into(mb, x0, x1, y, z)
        out.append(_mk("pews_%s" % ("p" if s > 0 else "n"), mb, MAT["wood"]))
        # a low iron rail on the alley side
        mb = MB()
        for k in range(n + 1):
            y = PEW_Y0 - 0.42 + k * pitch
            _bx(mb, s * 1.26, s * 1.30, y - 0.02, y + 0.02, z, z + 0.78)
        _bx(mb, s * 1.255, s * 1.305, PEW_Y0 - 0.45, PEW_Y0 + n * pitch, z + 0.74,
            z + 0.78)
        out.append(_mk("pew_rail_%s" % ("p" if s > 0 else "n"), mb, MAT["iron"]))
    return out


def _stall_into(mb, x0, x1, y, z0, s):
    """One choir stall seat, facing the centre line."""
    xin = x0 if s > 0 else x1
    _bx(mb, x0, x1, y, y + 0.56, z0, z0 + 0.48)                 # dais
    _bx(mb, x0, x1, y + 0.10, y + 0.52, z0 + 0.48, z0 + 0.54)    # seat
    _bx(mb, x0, x1, y + 0.44, y + 0.56, z0 + 0.54, z0 + 1.30)    # back
    _bx(mb, x0, x1, y + 0.50, y + 0.58, z0 + 1.30, z0 + 1.44)    # capping
    _bx(mb, x0, x1, y - 0.34, y - 0.26, z0 + 0.10, z0 + 0.46)    # kneeler
    # end boards with a finial
    for xx in (x0, x1 - 0.07):
        _bx(mb, xx, xx + 0.07, y - 0.36, y + 0.60, z0, z0 + 1.44)
        _bx(mb, xx - 0.01, xx + 0.08, y + 0.10, y + 0.50, z0 + 1.44, z0 + 1.58)
    # canopy: a slab over the seat on two little posts
    _bx(mb, x0 + 0.02, x1 - 0.02, y - 0.10, y + 0.62, z0 + 2.06, z0 + 2.16)
    for xx in (x0 + 0.05, x1 - 0.12):
        _bx(mb, xx, xx + 0.07, y + 0.50, y + 0.58, z0 + 1.44, z0 + 2.06)


def build_stalls():
    out = []
    z0 = 0.45
    for s in (-1, 1):
        mb = MB()
        n = 13
        pitch = 0.82
        for k in range(n):
            y = CH_STALL_Y0 + k * pitch
            x0, x1 = (2.15, 4.35) if s > 0 else (-4.35, -2.15)
            _stall_into(mb, x0, x1, y, z0, s)
        out.append(_mk("stalls_%s" % ("p" if s > 0 else "n"), mb, MAT["wood"]))
    return out


def _spandrel_fill(mb, y, x0, x1, z, mat_pts):
    pass


def build_rood_screen():
    out = []
    z0 = 0.45
    y = ROOD_Y
    pl = lambda az: Vector((az[0], y, az[1]))
    # parapet wings with a moulded cap
    for s in (-1, 1):
        xa, xb = (2.95, N_HW) if s > 0 else (-N_HW, -2.95)
        mb = MB()
        _bx(mb, xa, xb, y, y + 0.52, z0, z0 + 1.85)
        _bx(mb, xa - 0.06, xb + 0.06, y - 0.06, y + 0.58, z0 + 1.85, z0 + 1.98, bot=True)
        out.append(_mk("rood_par%s" % ("p" if s > 0 else "n"), mb, MAT["stone_dark"]))
        # three open arches above the parapet, under the cornice
        for i in range(3):
            a0 = xa + (xb - xa) * i / 3.0 + 0.14
            a1 = xa + (xb - xa) * (i + 1) / 3.0 - 0.14
            out.append(arch_rib("rood_a%d%s" % (i, "p" if s > 0 else "n"), a0, a1,
                                z0 + 1.98, 1.35, pl, 0.20, 0.18, MAT["stone_light"], 10))
            # little columns between the arches
            out.append(shaft("rood_c%d%s" % (i, "p" if s > 0 else "n"),
                             Vector((a0, y + 0.26, z0 + 1.98)),
                             Vector((a0, y + 0.26, z0 + 3.30)), 0.075, MAT["stone_light"]))
    # the great opening frame
    for s in (-1, 1):
        out.append(shaft("rood_j%s" % ("p" if s > 0 else "n"),
                         Vector((s * 2.95, y + 0.26, z0)),
                         Vector((s * 2.95, y + 0.26, z0 + 5.10)), 0.19, MAT["stone_light"]))
    out.append(arch_rib("rood_big", -2.95, 2.95, z0 + 5.10, 1.10, pl, 0.26, 0.22,
                        MAT["stone_light"], 16))
    # cornice across everything
    mb = MB()
    _bx(mb, -N_HW, N_HW, y - 0.08, y + 0.60, z0 + 3.42, z0 + 3.62, bot=True)
    _bx(mb, -N_HW, N_HW, y + 0.02, y + 0.50, z0 + 3.62, z0 + 3.78, bot=True)
    out.append(_mk("rood_corn", mb, MAT["stone"]))
    # the rood beam + the cross
    mb = MB()
    _bx(mb, -N_HW, N_HW, y + 0.10, y + 0.38, z0 + 6.10, z0 + 6.36)
    out.append(_mk("rood_beam", mb, MAT["wood"]))
    mb = MB()
    _bx(mb, -0.09, 0.09, y + 0.20, y + 0.30, z0 + 6.36, z0 + 9.30)
    _bx(mb, -1.05, 1.05, y + 0.20, y + 0.30, z0 + 7.85, z0 + 8.03)
    out.append(_mk("rood_cross", mb, MAT["wood_light"]))
    out.append(boss("rood_nim", 0.0, y + 0.25, z0 + 7.95, 0.16))
    return out


def build_high_altar():
    out = []
    z0 = 0.45
    y = ALTAR_Y
    # predella: three steps
    for i in range(3):
        zz = z0 + 0.30 * (i + 1)
        mb = MB()
        _bx(mb, -3.70 + 0.30 * i, 3.70 - 0.30 * i, y - 1.55 + 0.28 * i,
            y + 1.30 - 0.22 * i, z0, zz, bot=True)
        out.append(_mk("alt_st%d" % i, mb, MAT["marble"]))
    zt = z0 + 0.90
    # the altar itself
    mb = MB()
    _bx(mb, -1.72, 1.72, y - 0.48, y + 0.52, zt, zt + 1.02, bot=True)
    _bx(mb, -1.86, 1.86, y - 0.58, y + 0.62, zt + 1.02, zt + 1.14, bot=True)
    out.append(_mk("alt_body", mb, MAT["marble"]))
    mb = MB()
    _bx(mb, -1.80, 1.80, y - 0.56, y + 0.60, zt + 1.14, zt + 1.20, bot=True)
    out.append(_mk("alt_mensa", mb, MAT["stone_light"]))
    # linen runner, front fall and a gold frontal panel
    mb = MB()
    _bx(mb, -1.60, 1.60, y - 0.62, y + 0.56, zt + 1.20, zt + 1.235, bot=True)
    _bx(mb, -1.60, 1.60, y - 0.64, y - 0.60, zt + 0.66, zt + 1.235)
    out.append(_mk("alt_cloth", mb, MAT["linen"]))
    mb = MB()
    _bx(mb, -1.45, 1.45, y - 0.50, y - 0.46, zt + 0.18, zt + 0.62)
    out.append(_mk("alt_front", mb, MAT["cloth_red"]))
    out.append(boss("alt_orn", 0.0, y - 0.60, zt + 0.40, 0.13, MAT["gold"]))
    # reredos: three blind arches + a gold cross
    yr = y + 0.68
    mb = MB()
    _bx(mb, -2.15, 2.15, yr, yr + 0.42, zt, zt + 3.55, bot=True)
    _bx(mb, -2.30, 2.30, yr - 0.08, yr + 0.50, zt + 3.55, zt + 3.75, bot=True)
    out.append(_mk("alt_rer", mb, MAT["stone"]))
    for i, (a0, a1) in enumerate(((-1.95, -0.72), (-0.62, 0.62), (0.72, 1.95))):
        out.extend(blind_arcade("alt_ra%d" % i, Frame(Vector((0.0, yr, 0.0)),
                                                      Vector((1.0, 0.0, 0.0)),
                                                      Vector((0.0, 0.0, 1.0)),
                                                      Vector((0.0, -1.0, 0.0))),
                                a0, a1, zt + 0.55, zt + 2.95, 1, 0.10,
                                MAT["stone_dark"], spring=zt + 2.05, rise=0.60, seed=i))
    mb = MB()
    _bx(mb, -0.07, 0.07, yr - 0.14, yr - 0.08, zt + 1.62, zt + 3.20, bot=True)
    _bx(mb, -0.45, 0.45, yr - 0.14, yr - 0.08, zt + 2.55, zt + 2.69, bot=True)
    out.append(_mk("alt_gcross", mb, MAT["gold"]))
    # six candlesticks on the mensa + the altar cross
    for i, xx in enumerate((-1.42, -0.94, -0.48, 0.48, 0.94, 1.42)):
        out.append(stick("alt_cs%d" % i, xx, y + 0.14, zt + 1.235, 0.52 + 0.10 * (i % 3),
                         MAT["brass"]))
        out.append(candle("alt_cd%d" % i, xx, y + 0.14, zt + 1.235 + 0.52 + 0.10 * (i % 3),
                          0.042, 0.34))
    mb = MB()
    _bx(mb, -0.045, 0.045, y + 0.18, y + 0.24, zt + 1.235, zt + 2.05, bot=True)
    _bx(mb, -0.30, 0.30, y + 0.18, y + 0.24, zt + 1.72, zt + 1.81, bot=True)
    _bx(mb, -0.20, 0.20, y + 0.12, y + 0.30, zt + 1.235, zt + 1.30, bot=True)
    out.append(_mk("alt_cross", mb, MAT["gold"]))
    # the sanctuary lamps: three hanging bowls
    for i, xx in enumerate((-1.1, 0.0, 1.1)):
        out.extend(_lamp("alt_lamp%d" % i, xx, y - 1.9, 9.4, 1.9))
    return out


def _lamp(name, x, y, z_high, z_low, r=0.16):
    out = []
    mb = MB()
    for j in range(3):
        a = TAU * j / 3.0
        mb.add((Vector((x + 0.02 * math.cos(a), y + 0.02 * math.sin(a), z_high)),
                Vector((x, y, z_low + r)),
                Vector((x + 0.02 * math.cos(a + 0.4), y + 0.02 * math.sin(a + 0.4),
                        z_high))))
    out.append(_mk(name + "_ch", mb, MAT["iron"]))
    mb = MB()
    n = 12
    out.append(_mk(name + "_bowl", MB_cone(x, y, z_low - 0.10, r, 0.22, n),
                   MAT["brass"], smooth=True))
    out.append(_mk(name + "_gl", MB_cone(x, y, z_low + 0.02, r * 0.7, 0.10, n),
                   MAT["flame"], smooth=True))
    return out


def MB_cone(x, y, z, r, h, n=12, up=True):
    mb = MB()
    lo = [Vector((x + r * math.cos(TAU * i / n), y + r * math.sin(TAU * i / n), z))
          for i in range(n)]
    hi = [Vector((x + r * 0.6 * math.cos(TAU * i / n), y + r * 0.6 * math.sin(TAU * i / n),
                  z + h)) for i in range(n)]
    if up:
        mb.strip(lo, hi, closed=True)
        mb.fan(lo, Vector((x, y, z - 0.02)))
    else:
        mb.strip(hi, lo, closed=True)
        mb.fan(hi, Vector((x, y, z + h + 0.02)))
    return mb


def build_side_shrines():
    out = []
    for i, (s, y) in enumerate(((1, -36.4), (-1, -35.2), (1, -26.2), (-1, -25.0),
                                (1, -16.0), (-1, -14.8))):
        x = s * (AISLE_IN - 0.30)
        F = Frame((x, y, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
        # the shrine faces into the aisle (-s * x)
        F = Frame(Vector((x, y, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0)),
                  Vector((-float(s), 0.0, 0.0)))
        t = "sh%d" % i
        mb = MB()
        ex = float(s) * 0.55
        _bx(mb, min(x, x + ex), max(x, x + ex), y - 0.95, y + 0.95, 0.0, 0.95, bot=True)
        _bx(mb, min(x, x + ex * 0.8), max(x, x + ex * 0.8), y - 0.80, y + 0.80, 0.95,
            1.02, bot=True)
        out.append(_mk(t + "_mensa", mb, MAT["stone"]))
        mb = MB()
        _bx(mb, min(x, x + ex * 0.5), max(x, x + ex * 0.5), y - 0.92, y + 0.92, 0.0, 2.85,
            bot=True)
        _bx(mb, min(x, x + ex * 0.62), max(x, x + ex * 0.62), y - 1.00, y + 1.00, 2.85,
            3.02, bot=True)
        out.append(_mk(t + "_ret", mb, MAT["stone_light"]))
        # a niche + a gilded figure
        out.extend(blind_arcade(t + "_nc", F, -0.62, 0.62, 1.25, 2.70, 1, 0.12,
                                MAT["stone_dark"], spring=2.25, rise=0.38, seed=i))
        out.extend(_figure(t + "_fg", x - float(s) * 0.26, y, 1.02, 1.30,
                           MAT["stone_light"]))
        # candles
        for j, yy in enumerate((y - 0.55, y + 0.55)):
            out.append(candle(t + "_c%d" % j, x - float(s) * 0.30, yy, 1.02, 0.035, 0.30))
            out.append(stick(t + "_s%d" % j, x - float(s) * 0.30, yy, 1.02, 0.16,
                             MAT["brass"]))
        # a kneeler facing the shrine
        mb = MB()
        _bx(mb, min(x - float(s) * 1.5, x - float(s) * 2.0),
            max(x - float(s) * 1.5, x - float(s) * 2.0), y - 0.70, y + 0.70, 0.0, 0.14,
            bot=True)
        out.append(_mk(t + "_kn", mb, MAT["wood"]))
        # a canopy over the shrine
        mb = MB()
        _bx(mb, min(x - float(s) * 0.1, x + float(s) * 0.62),
            max(x - float(s) * 0.1, x + float(s) * 0.62), y - 1.05, y + 1.05, 3.02, 3.16,
            bot=True)
        out.append(_mk(t + "_cn", mb, MAT["stone"]))
    return out


def _figure(name, x, y, z, h, mat=None):
    """A small standing figure: a tapered robe, shoulders, head."""
    out = []
    prof = [(-0.16, 0.00), (-0.15, 0.16), (-0.10, 0.42), (-0.075, 0.62),
            (-0.10, 0.76), (-0.055, 0.86), (0.0, 0.90)]
    n = 10
    rows = []
    for (rr, hh) in prof:
        rows.append([Vector((x + rr * math.cos(TAU * i / n) * 1.0,
                             y + rr * math.sin(TAU * i / n) * 0.8,
                             z + hh * h)) for i in range(n)])
    mb = MB()
    for i in range(len(rows) - 1):
        mb.strip(rows[i], rows[i + 1], closed=True)
    mb.fan(rows[-1], Vector((x, y, z + h * 0.92)))
    mb.fan(list(reversed(rows[0])), Vector((x, y, z)))
    out.append(_mk(name, mb, mat or MAT["stone_light"], smooth=True))
    ob = MK.sphere(name + "_h", MK.T_at(x, y, z + h * 0.95), h * 0.075,
                   mat or MAT["stone_light"], seg=10, ring=6)
    PARTS.append(ob)
    out.append(ob)
    return out


def build_font():
    out = []
    x, y = 8.55, -37.60
    for i, (r, z0, z1) in enumerate(((0.62, 0.0, 0.16), (0.44, 0.16, 0.30),
                                     (0.20, 0.30, 0.92), (0.34, 0.92, 1.02),
                                     (0.56, 1.02, 1.22))):
        out.append(_mk("font_%d" % i, MB_cone(x, y, z0, r, z1 - z0, 8,
                                              up=(i != 2)), MAT["stone"] if i != 2
                       else MAT["stone_light"], smooth=True))
    # water
    mb = MB()
    mb.add(tuple([Vector((x + 0.50 * math.cos(TAU * i / 20),
                          y + 0.50 * math.sin(TAU * i / 20), 1.14)) for i in range(20)]))
    out.append(_mk("font_w", mb, MAT["brass"]))
    # cover
    out.append(_mk("font_cv", MB_cone(x, y, 1.24, 0.56, 0.62, 8, up=True),
                   MAT["wood"], smooth=True))
    for i in range(8):
        out.append(boss("font_cb%d" % i, x + 0.50 * math.cos(TAU * i / 8),
                        y + 0.50 * math.sin(TAU * i / 8), 1.28, 0.055, MAT["iron"]))
    return out


def _ring(name, x, y, z, r, w, n=28, mat=None):
    mb = MB()
    lo = [Vector((x + (r - w * 0.5) * math.cos(TAU * i / n),
                  y + (r - w * 0.5) * math.sin(TAU * i / n), z)) for i in range(n)]
    hi = [Vector((x + (r + w * 0.5) * math.cos(TAU * i / n),
                  y + (r + w * 0.5) * math.sin(TAU * i / n), z)) for i in range(n)]
    lo2 = [Vector((p.x, p.y, z - 0.10)) for p in lo]
    hi2 = [Vector((p.x, p.y, z - 0.10)) for p in hi]
    mb.strip(lo, hi, closed=True)
    mb.strip(lo2, hi2, closed=True)
    mb.strip(lo, lo2, closed=True)
    mb.strip(hi, hi2, closed=True)
    return _mk(name, mb, mat or MAT["iron"], smooth=True)


def build_chandeliers():
    out = []
    for i, y in enumerate((-33.0, -25.0, -17.0, -9.0)):
        for s in (-1, 1):
            x = s * 3.62
            zt = 25.45
            zr = 15.30
            t = "chd%d%s" % (i, "p" if s > 0 else "n")
            mb = MB()
            mb.add((Vector((x, y, zt)), Vector((x + 0.05, y + 0.05, zt - 1.2)),
                    Vector((x - 0.05, y - 0.05, zt - 1.2))))
            out.append(_mk(t + "_rod", mb, MAT["iron"]))
            out.append(_mk(t + "_rod2", MB_cone(x, y, zr + 0.18, 0.035, zt - zr - 1.2, 6),
                           MAT["iron"], smooth=True))
            out.append(_ring(t + "_ring", x, y, zr, 0.86, 0.05))
            out.append(_ring(t + "_ring2", x, y, zr - 0.14, 0.66, 0.035))
            for j in range(12):
                a = TAU * j / 12.0
                cx = x + 0.86 * math.cos(a)
                cy = y + 0.86 * math.sin(a)
                out.append(stick(t + "_c%d" % j, cx, cy, zr + 0.02, 0.10, MAT["brass"]))
                out.append(candle(t + "_cd%d" % j, cx, cy, zr + 0.12, 0.032, 0.26))
            out.append(boss(t + "_fin", x, y, zr - 0.26, 0.11, MAT["brass"]))
    return out


def build_corona():
    out = []
    x, y = 0.0, (Y_X0 + Y_X1) * 0.5
    zt, zr = 25.30, 17.20
    out.append(_mk("cor_rod", MB_cone(x, y, zr + 0.20, 0.04, zt - zr - 0.2, 6),
                   MAT["iron"], smooth=True))
    out.append(_ring("cor_r1", x, y, zr, 1.30, 0.06))
    out.append(_ring("cor_r2", x, y, zr + 0.30, 1.02, 0.035))
    for j in range(16):
        a = TAU * j / 16.0
        cx = x + 1.30 * math.cos(a)
        cy = y + 1.30 * math.sin(a)
        out.append(stick("cor_cs%d" % j, cx, cy, zr + 0.03, 0.11, MAT["brass"]))
        out.append(candle("cor_cd%d" % j, cx, cy, zr + 0.14, 0.030, 0.24))
    out.append(boss("cor_fin", x, y, zr - 0.30, 0.14, MAT["gold"]))
    # four chains up to the lantern
    mb = MB()
    for j in range(4):
        a = TAU * j / 4.0 + math.pi / 4.0
        mb.add((Vector((x + 1.30 * math.cos(a), y + 1.30 * math.sin(a), zr + 0.10)),
                Vector((x + 0.10 * math.cos(a), y + 0.10 * math.sin(a), zt))))
    out.append(_mk("cor_ch", mb, MAT["iron"]))
    return out


def build_thurible():
    out = []
    x, y = 2.60, 16.20
    zt, zl = 24.20, 14.60
    mb = MB()
    for j in range(4):
        a = TAU * j / 4.0
        mb.add((Vector((x + 0.09 * math.cos(a), y + 0.09 * math.sin(a), zt)),
                Vector((x + 0.02 * math.cos(a), y + 0.02 * math.sin(a), zl + 0.12))))
    out.append(_mk("thu_ch", mb, MAT["iron"]))
    out.append(_mk("thu_body", MB_cone(x, y, zl, 0.13, 0.26, 10, up=False), MAT["brass"],
                   smooth=True))
    out.append(_mk("thu_top", MB_cone(x, y, zl + 0.26, 0.11, 0.16, 10), MAT["brass"],
                   smooth=True))
    mb = MB()
    mb.add((Vector((x - 0.05, y, zl + 0.02)), Vector((x + 0.05, y, zl + 0.02)),
            Vector((x + 0.05, y + 0.02, zl + 0.10)), Vector((x - 0.05, y + 0.02, zl + 0.10))))
    out.append(_mk("thu_ember", mb, MAT["flame"]))
    return out


def build_pulpit():
    out = []
    x, y = -5.35, 4.20
    for i in range(4):
        mb = MB()
        _bx(mb, x - 0.55 + 0.10 * i, x + 0.55 - 0.10 * i, y - 0.55 + 0.10 * i,
            y + 0.55 + 0.16 * i, 0.0, 0.16 * (i + 1), bot=True)
        out.append(_mk("pul_st%d" % i, mb, MAT["marble"]))
    out.append(_mk("pul_body", MB_cone(x, y + 0.10, 0.64, 0.62, 1.30, 8, up=False),
                   MAT["stone_light"], smooth=True))
    out.append(_ring("pul_top", x, y + 0.10, 1.94, 0.68, 0.10, 8, MAT["stone_light"]))
    mb = MB()
    for j in range(8):
        a = TAU * j / 8.0 + math.pi / 8.0
        mb.add((Vector((x + 0.64 * math.cos(a), y + 0.10 + 0.64 * math.sin(a), 1.99)),
                Vector((x + 0.20 * math.cos(a), y + 0.10 + 0.20 * math.sin(a), 3.10))))
    out.append(_mk("pul_rib", mb, MAT["stone_light"]))
    out.append(_mk("pul_snd", MB_cone(x, y + 0.10, 3.10, 0.86, 0.10, 8, up=False),
                   MAT["wood"], smooth=True))
    return out


def build_lectern():
    out = []
    x, y = 2.55, 8.40
    out.append(_mk("lec_base", MB_cone(x, y, 0.0, 0.42, 0.16, 8), MAT["marble"], smooth=True))
    out.append(_mk("lec_col", MB_cone(x, y, 0.16, 0.11, 1.10, 8), MAT["brass"], smooth=True))
    out.append(_mk("lec_eagle", MB_cone(x, y, 1.26, 0.30, 0.30, 8), MAT["brass"], smooth=True))
    mb = MB()
    mb.add((Vector((x - 0.34, y - 0.22, 1.60)), Vector((x + 0.34, y - 0.22, 1.60)),
            Vector((x + 0.34, y + 0.20, 1.74)), Vector((x - 0.34, y + 0.20, 1.74))))
    out.append(_mk("lec_desk", mb, MAT["wood"]))
    return out


def build_candles_floor():
    out = []
    spots = ((-3.05, 28.30), (3.05, 28.30), (-3.05, 24.20), (3.05, 24.20),
             (-2.20, -4.60), (2.20, -4.60))
    for i, (x, y) in enumerate(spots):
        z = 0.45 if y > Y_X1 else 0.0
        out.append(_mk("fcst_%d" % i, MB_cone(x, y, z, 0.24, 0.10, 8), MAT["brass"],
                       smooth=True))
        out.append(stick("fcst_s%d" % i, x, y, z + 0.10, 1.35, MAT["brass"]))
        out.append(candle("fcst_c%d" % i, x, y, z + 1.45, 0.05, 0.42))
    return out


def build_furniture():
    out = []
    out.extend(build_pews())
    out.extend(build_stalls())
    out.extend(build_rood_screen())
    out.extend(build_high_altar())
    out.extend(build_side_shrines())
    out.extend(build_font())
    out.extend(build_chandeliers())
    out.extend(build_corona())
    out.extend(build_thurible())
    out.extend(build_pulpit())
    out.extend(build_lectern())
    out.extend(build_candles_floor())
    return out


# ---------------------------------------------------------------------------
# 26. light
# ---------------------------------------------------------------------------
# The shell around us is opaque, so no sun beam can reach the interior: every
# shaft is made here by a rectangular area light sitting just OUTSIDE a real
# window, aimed along the "sun" direction.  The 0.95 m wall with its splayed
# reveal cuts the light into a hard-edged beam, and the haze in the air makes
# it visible.  That is the whole trick.
SUN_TO = Vector((0.74, 0.14, 0.66)).normalized()   # direction towards the sun
SUN_E = 700.0                                       # sun irradiance, W/m^2
DIR_TRAVEL = (-SUN_TO).normalized()                # direction light travels

WARM = "#ffe0b4"
COOL = "#cfe0ff"
GOLD = "#ffd070"


def _area(name, loc, aim, energy, color, sx, sy, spread=None, cam=False,
          vol=False):
    li = bpy.data.lights.new(name, "AREA")
    li.shape = "RECTANGLE"
    li.size = max(0.05, sx)
    li.size_y = max(0.05, sy)
    li.energy = energy
    li.color = tuple(color)[:3]
    if spread is not None:
        li.spread = spread
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat(
        "-Z", "Y").to_euler()
    ob.visible_camera = cam
    try:
        ob.visible_volume_scatter = vol      # only the sun may light the haze
    except Exception:
        pass
    LIGHTS.append(ob)
    _OWN.add(ob.name)
    return ob


def _point(name, loc, energy, color, radius=0.05, vol=False):
    li = bpy.data.lights.new(name, "POINT")
    li.energy = energy
    li.color = tuple(color)[:3]
    li.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    LIGHTS.append(ob)
    _OWN.add(ob.name)
    return ob


# ---------------------------------------------------------------------------
# 26b. light shafts -- soft additive air so the beams READ
# ---------------------------------------------------------------------------
# Cycles' haze does scatter for real (the sun is shadow-linked so only the
# lancets let it in), but in a sunlit room the single-scatter radiance of a
# 2 m wide beam is about a tenth of the wall behind it, so a side view of the
# beam shows nothing.  Every shaft photograph is helped by dust; here the dust
# is a very faint emission tube that follows the same DIR_TRAVEL as the sun, so
# the glow always sits exactly where the real light is.  A fade along the
# length plus a Fresnel fall-off at the silhouette keep it from reading as
# glass.
SHAFTS_ON = False   # experimental volume wedges; the linked sun + haze is the real thing
SHAFT_DENS = 0.062
SHAFT_FLAT = True           # constant density (the fade attribute is unreliable)          # extra density inside a beam
SHAFT_STRENGTH = 1.45
_SHAFT_MATS = {}
_SHAFT_COLS = ("#ffe4bd", "#ffdcaa", "#ffe9cc", "#ffe1b8", "#f6e7d2")


def _inp(node, names, val):
    for nm in names:
        sck = node.inputs.get(nm)
        if sck is not None:
            try:
                sck.default_value = val
                return True
            except Exception:
                pass
    return False


def shaft_mat(color, strength=None, alpha=None):
    """Volume shader: the tube is a wedge of denser air, not a glass sheet.

    A surface shader (emission + alpha) always shows its silhouette as a hard
    edged pane.  A Principled Volume integrates along the ray instead, so the
    beam has soft ends, breathes with the distance and scatters towards the
    camera exactly like the real haze it is standing in for.
    """
    density = SHAFT_DENS if strength is None else strength
    key = "%s_%.3f" % (color, density)
    if key in _SHAFT_MATS:
        return _SHAFT_MATS[key]
    mat = bpy.data.materials.new("ci_shaft_" + key)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (620, 0)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.location = (320, 120)
    nt.links.new(tr.outputs[0], out.inputs["Surface"])
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.location = (320, -140)
    col = tuple(MK.c(color))[:3]
    _inp(vol, ("Color",), (col[0], col[1], col[2], 1.0))
    _inp(vol, ("Anisotropy",), 0.55)
    _inp(vol, ("Absorption Color",), (0.0, 0.0, 0.0, 1.0))
    _inp(vol, ("Absorption Density",), 0.0)
    _inp(vol, ("Emission Strength",), 0.0)
    at = nt.nodes.new("ShaderNodeAttribute")
    at.location = (-120, -260)
    at.attribute_name = "fade"
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    m1.location = (60, -240)
    m1.use_clamp = True
    m1.inputs[1].default_value = density
    nt.links.new(at.outputs["Fac"], m1.inputs[0])
    if SHAFT_FLAT:
        _inp(vol, ("Density",), density)
    else:
        nt.links.new(m1.outputs[0], vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    mat.use_backface_culling = False
    _SHAFT_MATS[key] = mat
    return mat


def _one_shaft(name, F, a0, a1, zsill, zspr, rise, seed, d0=0.07, flare=1.22):
    cont = arch_contour(a0, a1, zsill, zspr, rise, 10)
    ring0 = [F.p2(p, d0) for p in cont]
    n = len(ring0)
    if n < 4:
        return None
    cen = Vector((0.0, 0.0, 0.0))
    for p in ring0:
        cen = cen + p
    cen = cen / n
    L = (cen.z - 0.10) / max(0.22, abs(DIR_TRAVEL.z))
    L = max(2.5, min(L, 34.0))
    ring1 = []
    for p in ring0:
        q = cen + (p - cen) * flare + DIR_TRAVEL * L
        if q.z < 0.06:                  # never sink through the floor
            q = Vector((q.x, q.y, 0.06))
        ring1.append(q)
    verts = [tuple(p) for p in ring0] + [tuple(p) for p in ring1]
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    # the volume needs a closed box, so cap both ends
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range(n, 2 * n)))
    ob = MK.mesh_obj(name, verts, faces, False)
    try:
        ca = ob.data.color_attributes.new(name="fade", type="FLOAT_COLOR",
                                          domain="POINT")
        for i in range(len(verts)):
            f = 1.0 if i < n else 0.0
            ca.data[i].color = (f, f, f, 1.0)
    except Exception as exc:
        L("shaft fade attr failed: %s" % exc)
    MK.assign(ob, shaft_mat(_SHAFT_COLS[seed % len(_SHAFT_COLS)]))
    ob.visible_shadow = False
    PARTS.append(ob)
    return ob


def light_shafts(gain=1.0):
    """Faint additive tubes that follow the sun through the lancets."""
    if not SHAFTS_ON:
        return []
    if gain != 1.0:
        global SHAFT_DENS
        SHAFT_DENS = SHAFT_DENS * gain
        _SHAFT_MATS.clear()
    objs = []
    k = 0
    for (F, a0, a1, zsill, zspr, rise, th, seed) in list(WINDOWS):
        if zsill < 12.0:
            continue
        d = F.N.normalized().dot(SUN_TO)
        if d < 0.05:
            continue
        if abs(F.N.x) > 0.6:
            k += 1
            if k % 2 == 0:
                continue
        ob = _one_shaft("ci_beam%02d" % k, F, a0, a1, zsill, zspr, rise, seed)
        if ob is not None:
            objs.append(ob)
        if k >= 26:
            break
    L("shafts: %d" % len(objs))
    return objs


def _sun_linked(receivers_extra=(), energy=None, angle=0.9, color="#fff3dc"):
    """A real (parallel) sun whose light is confined to the interior.

    A distant source is the only way to get a sharp, window-shaped shaft: a big
    area light 0.3 m behind a lancet is a floodlight, never a beam.  The shell
    around us would swallow every ray, so the sun is shadow-linked (blockers =
    our walls) and receiver-linked (our geometry only): the shell neither blocks
    it nor is lit by it.
    """
    energy = SUN_E if energy is None else energy
    li = bpy.data.lights.new("ci_sun", "SUN")
    li.energy = energy
    li.angle = math.radians(angle)
    li.color = tuple(MK.c(color))[:3]
    ob = bpy.data.objects.new("ci_sun", li)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = DIR_TRAVEL.to_track_quat("-Z", "Y").to_euler()
    LIGHTS.append(ob)
    _OWN.add(ob.name)
    try:
        rec = bpy.data.collections.new("CI_SUN_RECEIVERS")
        blk = bpy.data.collections.new("CI_SUN_BLOCKERS")
        for c in (rec, blk):
            bpy.context.scene.collection.children.link(c)
        for o in list(PARTS) + [e for e in receivers_extra if e is not None]:
            try:
                rec.objects.link(o)
            except Exception:
                pass
        n = 0
        for o in PARTS:
            nm = o.name
            if "_gl" in nm or nm.endswith("_bk") or nm.endswith("_gc"):
                continue                     # glazing never blocks
            try:
                blk.objects.link(o)
                n += 1
            except Exception:
                pass
        lk = ob.light_linking
        lk.receiver_collection = rec
        lk.blocker_collection = blk
        L("sun %.0f linked: %d receivers, %d blockers" % (energy, len(rec.objects), n))
    except Exception as exc:                 # pragma: no cover
        L("sun linking unavailable (%s)" % exc)
    return ob


def _shaft(F, name, a0, a1, zsill, zspr, rise, th, energy, color,
           out=0.26, inflate=0.88):
    """One beam through one lancet."""
    zh = zspr + rise
    am = 0.5 * (a0 + a1)
    zc = zsill + 0.56 * (zh - zsill)
    loc = F.p(am, zc, th + out)
    aim = loc + DIR_TRAVEL * 10.0
    return _area(name, loc, aim, energy, color,
                 (a1 - a0) * inflate, (zh - zsill) * inflate)


def _rose_shaft(F, name, ca, cz, R, th, energy, color, out=0.24):
    loc = F.p(ca, cz, th + out)
    aim = loc + DIR_TRAVEL * 10.0
    return _area(name, loc, aim, energy, color, R * 1.50, R * 1.50)


def interior_lights(spec="full", air=True, sun=True):
    """All interior lighting.  Returns the light objects.

    spec="full"  everything (the default)
    spec="shaft" only the beams
    spec="none"  nothing
    """
    out = []
    if spec == "none":
        return out
    atm = atmosphere() if air else None
    # ---- 1. the beams through the clerestory (both sides, sun side wins) --
    k = 0
    for (F, a0, a1, zsill, zspr, rise, th, seed) in list(WINDOWS):
        if zsill < 12.0:                    # aisle / ambulatory glazing: no beam
            continue
        d = F.N.normalized().dot(SUN_TO)
        if d < 0.05:
            continue                        # facing away: it only glows
        if abs(F.N.x) > 0.6 and zsill > 12.0:
            k += 1                          # one strong beam per clerestory bay
            if k % 2 == 0:
                continue
        e = (15000.0 if d > 0.4 else 6000.0) * (0.55 + 0.45 * d)
        col = MK.c(WARM) if (seed % 3) else MK.c(GOLD)
        out.append(_shaft(F, "ci_shaft%02d" % k, a0, a1, zsill, zspr, rise, th,
                          e, col))
        if k >= 26:
            break
    # ---- 2. the three roses ----------------------------------------------
    for i, (F, ca, cz, R, th, seed) in enumerate(list(ROSES)):
        col = MK.c("#ffd9c0") if i == 0 else MK.c("#e8d0ff")
        out.append(_rose_shaft(F, "ci_rosesh%d" % i, ca, cz, R, th, 26000.0, col))
    # ---- 3. soft bounce fill, keeps the shade readable -------------------
    fills = (
        ("ci_fill0", (0.0, -30.0, 22.6), (0.0, -30.0, 0.0), 2000.0, 8.0, COOL),
        ("ci_fill1", (0.0, -10.0, 22.8), (0.0, -10.0, 0.0), 1900.0, 8.0, WARM),
        ("ci_fill2", (0.0, 16.0, 22.8), (0.0, 16.0, 0.0), 1950.0, 7.5, WARM),
        ("ci_fill3", (0.0, 30.0, 21.6), (0.0, 30.0, 2.0), 2200.0, 6.0, GOLD),
        ("ci_fill4", (-9.6, -24.0, 10.4), (-9.6, -24.0, 0.0), 230.0, 5.0, COOL),
        ("ci_fill5", (9.6, -24.0, 10.4), (9.6, -24.0, 0.0), 900.0, 5.0, COOL),
        ("ci_fill6", (-9.6, -8.0, 10.4), (-9.6, -8.0, 0.0), 200.0, 5.0, COOL),
        ("ci_fill7", (9.6, -8.0, 10.4), (9.6, -8.0, 0.0), 800.0, 5.0, COOL),
        # bounce off the floor, aimed up: this is what grades the vault webs
        ("ci_bnc0", (-3.4, -26.0, 1.1), (-3.4, -26.0, 24.0), 1100.0, 4.0, WARM),
        ("ci_bnc1", (3.4, -26.0, 1.1), (3.4, -26.0, 24.0), 1100.0, 4.0, COOL),
        ("ci_bnc2", (-3.4, -8.0, 1.1), (-3.4, -8.0, 24.0), 1100.0, 4.0, WARM),
        ("ci_bnc3", (3.4, -8.0, 1.1), (3.4, -8.0, 24.0), 1100.0, 4.0, COOL),
    )
    for (nm, loc, aim, e, sz, col) in fills:
        out.append(_area(nm, loc, aim, e, MK.c(col), sz, sz))
    # ---- 4. candles: the warm heart -------------------------------------
    zt = 0.45 + 0.90 + 1.235
    for i, xx in enumerate((-1.42, -0.94, -0.48, 0.48, 0.94, 1.42)):
        out.append(_point("ci_cnd%d" % i, (xx, 31.34, zt + 0.62), 700.0,
                          MK.c("#ffa552"), 0.05))
    out.append(_point("ci_altar_glow", (0.0, 31.0, 3.0), 160.0, MK.c("#ff9a40"),
                      0.6))
    for i, (s, y) in enumerate(((1, -36.4), (-1, -35.2), (1, -26.2), (-1, -25.0),
                                (1, -16.0), (-1, -14.8))):
        out.append(_point("ci_shc%d" % i, (s * 11.4, y, 1.55), 200.0,
                          MK.c("#ffa552"), 0.05))
    out.append(_point("ci_corona", (0.0, 7.5, 17.4), 520.0, MK.c("#ffb066"), 0.4))
    # ---- 5. the sun: the only source that makes a real shaft --------------
    if sun:
        out.append(_sun_linked([atm]))
    # ---- 6. apply the same transform the geometry got ----------------------
    if _XFORM != Matrix.Identity(4):
        for ob in out:
            ob.matrix_world = _XFORM @ ob.matrix_world
    L("lights: %d" % len(out))
    return out


# ---------------------------------------------------------------------------
# 27. atmosphere
# ---------------------------------------------------------------------------
def atmosphere(scene=None, density=0.0055, height=42.0, extent=210.0,
               aniso=0.35, preset="fog"):
    """Volumetric haze that makes the beams visible.  Safe to call twice."""
    try:
        import hd_atmosphere as ATM
    except Exception as exc:                       # pragma: no cover
        L("atmosphere unavailable: %s" % exc)
        return None
    c = _ORIGIN
    try:
        ob = ATM.haze(preset, density=density, height=height, extent=extent,
                      center=(c.x, c.y), aniso=aniso)
    except Exception as exc:                       # pragma: no cover
        L("haze failed: %s" % exc)
        return None
    L("haze d=%.3f h=%.0f" % (density, height))
    return ob


# ---------------------------------------------------------------------------
# 28. cameras
# ---------------------------------------------------------------------------
EYE = 1.72
CAMS = [
    # the walk in: on the axis, through the door, altar at the end
    ("entry", (0.0, Y_W + 1.55, EYE), (0.0, 31.0, 5.2), 19.0),
    ("nave", (0.0, -17.0, EYE), (0.0, 20.0, 7.0), 20.0),
    ("nave_up", (0.0, -11.0, EYE), (0.0, 1.5, 22.0), 15.0),
    ("vault", (0.0, -4.0, EYE), (0.0, -6.0, 24.6), 14.0),
    ("crossing_up", (0.0, 7.5, EYE), (0.0, 7.5, 25.5), 13.0),
    ("altar", (0.0, 5.6, EYE), (0.0, 32.0, 6.6), 30.0),
    ("rose", (0.0, -13.0, 2.35), (0.0, Y_W, ROSE_W_Z + 0.2), 24.0),
    ("rose_close", (0.0, -24.0, 9.0), (0.0, Y_W, ROSE_W_Z), 30.0),
    ("aisle", (-9.30, -24.0, EYE), (-9.30, 6.0, 3.6), 22.0),
    ("aisle_e", (9.30, -26.0, EYE), (9.30, 4.0, 4.4), 22.0),
    ("rose_tr", (0.0, 7.5, EYE), (TR_X, 7.5, ROSE_T_Z), 20.0),
    ("transept", (20.0, 7.5, EYE), (0.0, 7.5, 11.0), 24.0),
    ("cross_s", (0.0, 7.5, EYE), (TR_X, 7.5, 14.0), 26.0),
    ("apse", (0.0, 14.0, EYE), (0.0, 32.0, 12.0), 28.0),
    ("light", (0.0, -4.0, EYE), (0.0, 26.0, 8.0), 20.0),
    # in the shadow of the south aisle, looking up into the beams: near end-on
    ("beam", (-10.55, -22.0, EYE), (2.0, -6.0, 16.0), 24.0),
    ("beam2", (-10.55, -30.0, EYE), (4.0, -18.0, 14.0), 24.0),
    ("beam3", (0.0, -35.0, EYE), (0.0, -12.0, 17.0), 20.0),
    ("beam4", (0.0, -30.0, EYE), (0.0, -2.0, 15.0), 22.0),
    ("light2", (2.30, -14.0, EYE), (-3.0, -38.0, 12.0), 26.0),
    ("floor", (0.0, -34.0, 1.62), (0.0, 6.0, 0.4), 26.0),
]


# ---------------------------------------------------------------------------
# 29. build
# ---------------------------------------------------------------------------
def footprint():
    """(width_x, depth_y) of the interior, church frame, metres."""
    return (2.0 * (TR_X + WALL_T), Y_APSE + AMB_OUT + WALL_T - (Y_W - WALL_T))


def height():
    """Ridge of the interior vaulting (lantern cap)."""
    return X_HC + Z_VAULT + 2.05


def build(K=None, MAT=None, origin=(0.0, 0.0), rot=0.0, scale=1.0, seed=5):
    """Build the whole interior and return the created objects.

    origin : (x, y) of the church-frame origin in the parent scene
    rot    : rotation about Z, radians (exterior needs pi)
    scale  : uniform scale
    """
    global _XFORM, _ORIGIN
    if MAT is not None and not isinstance(MAT, dict):
        MAT = None                      # tolerate the legacy build(MAT, rng) call
    _reset(seed)
    m = _ensure(MAT)
    globals()["MAT"] = m
    t0 = time.time() if "time" in globals() else None
    _XFORM = (Matrix.Translation((origin[0], origin[1], Z_LIFT))
              @ Matrix.Rotation(rot, 4, "Z")
              @ Matrix.Scale(scale, 4))
    _ORIGIN = Vector((origin[0], origin[1], Z_LIFT))

    build_floor()
    build_west()
    build_vessel(Y_W, Y_X0, NBAY, "nave")
    build_vessel(Y_X1, Y_APSE, NCH, "choir")
    build_transept()
    build_apse()
    build_ambulatory()
    build_crossing()
    build_furniture()
    light_shafts()

    if _XFORM != Matrix.Identity(4):
        for ob in PARTS:
            ob.matrix_world = _XFORM @ ob.matrix_world
    L("build: %d objects, %d windows, %d roses"
      % (len(PARTS), len(WINDOWS), len(ROSES)))
    return list(PARTS)


def preview(samples=24, res=(960, 540), only=None):
    """Render this module's cameras (standalone, for the parent's convenience)."""
    import hd_common as H
    sel = [c for c in CAMS if (only is None or c[0] in only)]
    cam_obs = []
    for (nm, loc, look, lens) in sel:
        cam_obs.append((nm, H.camera("ci_" + nm, loc, look, lens)))
    H.setup_engine(samples=samples, res=res, gpu=True)
    files = []
    for (nm, cam) in cam_obs:
        p = os.path.join(H.OUT_DIR, "C_%s.png" % nm)
        H.render_to(p, cam)
        files.append(p)
        L("render %s" % p)
    return files

