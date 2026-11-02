"""hd_nature.py -- HD trees for the Asura capital: 7 species, 3 LODs, procedural.

WHY THIS FILE WAS REWRITTEN
===========================
V24's trees are lollipops: one thin pole with one smooth green sphere on top.
Up close it is a plastic toy; from the air it is a field of green dots.  The
cause is structural, not a matter of adding detail: a *single* convex lump can
only ever read as a ball.  A tree reads as a tree when

  * the crown is 8-20 SEPARATE lumps of different size, each sitting at the end
    of a visible branch, so the silhouette is lobed and full of holes;
  * the trunk tapers, forks, and has longitudinal bark grooves that catch the
    light (a cylinder has neither);
  * the leaf mass is broken by hundreds of small OPAQUE leaf boards.  Alpha
    cards are banned here on purpose: EEVEE sorts them per object, so a crown
    of cards shimmers and shows the sky through its own back faces.  Every
    board in this module is opaque geometry, double-wound so it is visible from
    both sides without alpha.

The other half of the problem is placement: 2,596 trees for a walled city of
12,990 houses is one tree per five buildings.  A medieval town has fruit trees
in every courtyard, elms at the corners, lindens round the squares and willows
on the water.  `place()` does that, and refuses any spot that is in a
carriageway, inside a house, inside a landmark or outside the wall.

PUBLIC API
==========
    build(MAT, units=None, res=None, seed=7, cell=64.0, lod=2, **kw) -> dict
        Build the whole city tree layer.  Returns
            {"objects": [bpy.types.Object, ...],
             "records": [rec, ...],
             "info": {...counts, faces, seconds, peak_mb...}}
        `MAT` is capital.py's material dict; two entries are added to it,
        MAT["nat_leaf"] and MAT["nat_bark"].  `units` is hd_dense/hd_pick's
        placement list (needs "quad"); `res` is the plan dict from hd_plan2 /
        hd_layout (needs "blocks", optionally "streets"/"landmarks"/"city").
        `cell` is the mesh batch size in metres (64 -> ~150 objects for the
        whole city).  `lod` is the *maximum* LOD to build: 2 = full 3-band
        LOD, 1 = nothing finer than L1, 0 = every tree at L0 (hero shots only).

    place(units=None, res=None, seed=7, **kw) -> [record]
        Pure python (no bpy, no numpy).  One dict per tree:
            x, y, z, kind, scale, rot, tint, lod, role, seed

    tree(kind, rng, scale=1.0, lod=0) -> (V, F, M, C, L)
        One tree as raw geometry, standing on z=0, `scale` metres tall.
        V  (N,3) float64 verts      F  (M,3) int32 tris
        M  (M,)  int32 material index, 0 = bark, 1 = leaf
        C  (N,3) float64 linear colour (species colour x shading x grooves)
        L  (N,)  uint8 1 where the vertex belongs to leaf mass

    tree_template(kind, lod, seed=0) -> (V, F, shade)
        The *hd_landscape_geo* contract (height-normalised verts, tri faces,
        per-vertex brightness) so the far field can swap its lollipop
        templates for these without touching the instancer.  See the report.

    tint(t, kind=None) -> (r, g, b)
        Season/colour multiplier for a 0..1 tint.  0.5 is neutral green,
        0.80-0.92 yellow, 0.95-1.0 orange.  Applied to leaf vertices only.

    forest(MAT, res=None, seed=7, **kw) -> dict
        The belt outside the wall: instanced (one mesh per cell, shared
        template arrays), realistic size distribution, per-tree LOD.

    make_materials(MAT) -> (leaf_mat, bark_mat)
    wind(objects, t=0.0, amp=0.045, dir=(1.0, 0.0)) -> n
        Vertex-level wind.  Unlike hd_weather.sway (which rotates a whole
        object about its origin and is therefore useless on a batched cell)
        this bends each vertex by (z/H)**1.5, so a cell of 200 trees sways.

LOD
===
    L0  < 40 m   trunk + forks + sub-boughs, 11-15 lumps, leaf boards
    L1  40-150 m 3-5 boughs, 5-8 lumps, ~20 % of L0 faces
    L2  > 150 m  crossed cards + an umbrella cap (the 52 deg camera sees the
                 TOP of a distant tree, so a card-only billboard is a sliver)

Units are metres, Z up, origin at the base of the trunk.
"""

import math
import random
import time

try:
    import numpy as np
except Exception:                                                # noqa: BLE001
    np = None

TAU = math.tau

# material slots inside one tree mesh
MAT_BARK, MAT_LEAF = 0, 1

# --------------------------------------------------------------------------
# species
# --------------------------------------------------------------------------
#   H        natural height range, metres
#   trunk    fork height as a fraction of H
#   r0       trunk radius at the base as a fraction of H
#   crown    envelope: dome / vase / column / weep / cone / round
#   spread   crown radius as a fraction of H
#   clumps   (min, max) lumps in the crown at L0
SPECIES = {
    "oak": dict(H=(9.5, 14.5), trunk=0.30, r0=0.082, crown="dome",
                spread=0.44, clumps=(11, 15), boughs=(4, 5),
                leaf="#41602a", dark="#2b431c", light="#6d8f3c",
                bark="#5b5145", bark_dark="#332c24", squash=0.84),
    "elm": dict(H=(13.0, 19.0), trunk=0.36, r0=0.062, crown="vase",
                spread=0.30, clumps=(10, 13), boughs=(4, 5),
                leaf="#4a6a2b", dark="#324a1e", light="#7b9a45",
                bark="#635a4c", bark_dark="#382f26", squash=0.80),
    "linden": dict(H=(11.0, 16.0), trunk=0.32, r0=0.070, crown="dome",
                   spread=0.38, clumps=(10, 13), boughs=(4, 4),
                   leaf="#587a30", dark="#3b5520", light="#86a44e",
                   bark="#6a6051", bark_dark="#3b332a", squash=0.88),
    "poplar": dict(H=(14.0, 20.0), trunk=0.24, r0=0.042, crown="column",
                   spread=0.15, clumps=(8, 11), boughs=(3, 4),
                   leaf="#6b8b39", dark="#4a6326", light="#9ab558",
                   bark="#6f6656", bark_dark="#3e372d", squash=0.72),
    "willow": dict(H=(7.0, 11.0), trunk=0.26, r0=0.078, crown="weep",
                   spread=0.42, clumps=(9, 12), boughs=(4, 5),
                   leaf="#69824a", dark="#465c30", light="#9db06b",
                   bark="#5d5344", bark_dark="#332c23", squash=0.70),
    "spruce": dict(H=(12.0, 20.0), trunk=0.20, r0=0.050, crown="cone",
                   spread=0.20, clumps=(0, 0), boughs=(0, 0),
                   leaf="#2d4a27", dark="#1d331a", light="#486b34",
                   bark="#4c4238", bark_dark="#2a241d", squash=1.0),
    "fruit": dict(H=(3.6, 5.8), trunk=0.32, r0=0.056, crown="round",
                  spread=0.46, clumps=(7, 10), boughs=(3, 4),
                  leaf="#4f7030", dark="#354d1e", light="#7fa04a",
                  bark="#6b5c4a", bark_dark="#3a3025", squash=0.80),
}
KINDS = ("oak", "elm", "linden", "poplar", "willow", "spruce", "fruit")

# role -> weighted species list, used by place()
ROLE_SPECIES = {
    "courtyard": (("fruit", 6), ("linden", 2), ("oak", 1)),
    "corner": (("elm", 5), ("linden", 3), ("oak", 2)),
    "square": (("linden", 6), ("elm", 3), ("oak", 1)),
    "avenue": (("poplar", 4), ("elm", 3), ("linden", 3)),
    "river": (("willow", 7), ("poplar", 2), ("linden", 1)),
    "landmark": (("linden", 4), ("oak", 3), ("elm", 2)),
    "wall": (("oak", 4), ("spruce", 3), ("elm", 2)),
    "forest": (("oak", 5), ("spruce", 4), ("elm", 2), ("poplar", 1)),
}

# LOD bands, metres from the nearest focus point
BANDS = (40.0, 150.0)


def _lin(hexs):
    """sRGB hex -> linear RGB tuple."""
    h = hexs.lstrip("#")
    out = []
    for i in (0, 2, 4):
        v = int(h[i:i + 2], 16) / 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def _mixc(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


# season ramp: 0 = cold deep green, 0.5 = the ordinary green of the species,
# 1.0 = full orange.  The 0.5 anchor is deliberate -- `tint` is a *relative*
# multiplier, so the species colour survives at neutral.
_TINT_KEYS = ((0.00, (0.72, 0.86, 0.68)),
              (0.35, (0.88, 0.96, 0.86)),
              (0.50, (1.00, 1.00, 1.00)),
              (0.68, (1.10, 1.02, 0.74)),
              (0.84, (1.28, 0.98, 0.50)),
              (1.00, (1.34, 0.66, 0.30)))


def tint(t, kind=None):
    """Season / colour multiplier for a 0..1 tint value.

    0.5 is neutral (the species' own green).  0.80-0.90 turns a tree yellow,
    0.95-1.0 orange-red.  Values are >1 on purpose: they multiply a vertex
    colour that is already the species green, so a yellow tree has to push the
    red channel past 1 and pull blue down.  Clamp at the material.
    """
    t = max(0.0, min(1.0, float(t)))
    for i in range(len(_TINT_KEYS) - 1):
        t0, c0 = _TINT_KEYS[i]
        t1, c1 = _TINT_KEYS[i + 1]
        if t <= t1:
            f = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
            return _mixc(c0, c1, max(0.0, min(1.0, f)))
    return _TINT_KEYS[-1][1]


def _pick_tint(rng, autumn=0.09):
    """Per-tree tint: most trees are green with a hue jitter, `autumn` of them
    are yellow/orange.  This is what stops a wood from being one flat colour."""
    r = rng.random()
    if r < autumn * 0.34:
        return rng.uniform(0.93, 1.00)          # orange / red
    if r < autumn:
        return rng.uniform(0.74, 0.90)          # yellow
    return rng.uniform(0.40, 0.60)              # green, wide hue jitter


# --------------------------------------------------------------------------
# tiny vector helpers (tuples: fast enough for ~90 templates, no numpy needed)
# --------------------------------------------------------------------------
def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _len(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _norm(a):
    L = _len(a)
    return (a[0] / L, a[1] / L, a[2] / L) if L > 1e-12 else (0.0, 0.0, 1.0)


def _lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def _rot_axis(v, axis, ang):
    """Rodrigues rotation of v about a unit axis."""
    c, s = math.cos(ang), math.sin(ang)
    return _add(_add(_mul(v, c), _mul(_cross(axis, v), s)),
                _mul(axis, _dot(axis, v) * (1.0 - c)))


def _perp(d):
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.92 else (1.0, 0.0, 0.0)
    return _norm(_cross(d, ref))


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
_ICO = {}


def _ico(sub=1):
    """Unit icosphere, cached.  sub=0 -> 12 v / 20 f, sub=1 -> 42 v / 80 f."""
    if sub in _ICO:
        return _ICO[sub]
    t = (1.0 + 5.0 ** 0.5) * 0.5
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
         (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    V = [_norm(p) for p in V]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
         (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
         (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(int(sub)):
        mid = {}
        NF = []

        def m(a, b):
            k = (a, b) if a < b else (b, a)
            j = mid.get(k)
            if j is None:
                j = len(V)
                V.append(_norm(_mul(_add(V[a], V[b]), 0.5)))
                mid[k] = j
            return j

        for (a, b, c) in F:
            ab, bc, ca = m(a, b), m(b, c), m(c, a)
            NF.extend([(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)])
        F = NF
    _ICO[sub] = (V, F)
    return V, F


def _blob(c, r, rng, squash=(1.0, 1.0, 1.0), jitter=0.13, sub=0, lump=1.0):
    """A deformed icosphere: three smooth sine lobes plus a little hash noise.

    Per-vertex *random* displacement would give a spiky sea urchin; the lobes
    are smooth in space, so neighbouring vertices move together and the result
    is a cauliflower lump, which is what a leaf clump actually looks like.
    """
    V0, F0 = _ico(sub)
    ph1, ph2, ph3 = (rng.uniform(0.0, TAU) for _ in range(3))
    k = 1.0 + 0.22 * rng.random()
    out = []
    for (x, y, z) in V0:
        w = (0.52 * math.sin(2.7 * x * k + ph1) * math.sin(2.2 * y * k + ph2)
             + 0.48 * math.sin(2.1 * z * k + ph3))
        j = 1.0 + jitter * lump * w + 0.045 * (rng.random() - 0.5)
        out.append((c[0] + x * r * j * squash[0],
                    c[1] + y * r * j * squash[1],
                    c[2] + z * r * j * squash[2]))
    return out, [tuple(f) for f in F0]


def _frames(pts):
    """Per-point (tangent, u, v) with parallel transport -- no twist pops."""
    n = len(pts)
    T = []
    for i in range(n):
        if n == 1:
            d = (0.0, 0.0, 1.0)
        elif i == 0:
            d = _sub(pts[1], pts[0])
        elif i == n - 1:
            d = _sub(pts[-1], pts[-2])
        else:
            d = _add(_sub(pts[i], pts[i - 1]), _sub(pts[i + 1], pts[i]))
        T.append(_norm(d))
    u = _perp(T[0])
    U, W = [], []
    for i in range(n):
        if i:
            a, b = T[i - 1], T[i]
            ax = _cross(a, b)
            s = _len(ax)
            if s > 1e-7:
                ang = math.atan2(s, _dot(a, b))
                u = _rot_axis(u, _mul(ax, 1.0 / s), ang)
        u = _norm(_sub(u, _mul(T[i], _dot(u, T[i]))))
        U.append(u)
        W.append(_cross(T[i], u))
    return T, U, W


def _tube(pts, radii, seg=8, cap0=False, cap1=False, groove=0.0, ngr=5,
          phase=0.0, twist=0.0):
    """Swept circle along a polyline.  Returns (V, F, G) with G = groove shade
    per vertex (1.0 = ridge, darker in the furrow)."""
    T, U, W = _frames(pts)
    n = len(pts)
    V, F, G = [], [], []
    for i in range(n):
        p = pts[i]
        r = radii[i]
        for k in range(seg):
            a = TAU * k / seg + phase + twist * i
            if groove > 0.0:
                dip = groove * (0.5 - 0.5 * math.cos(ngr * a))
            else:
                dip = 0.0
            rr = r * (1.0 - dip)
            ca, sa = math.cos(a), math.sin(a)
            V.append((p[0] + (U[i][0] * ca + W[i][0] * sa) * rr,
                      p[1] + (U[i][1] * ca + W[i][1] * sa) * rr,
                      p[2] + (U[i][2] * ca + W[i][2] * sa) * rr))
            G.append(1.0 - 0.62 * dip)
    for i in range(n - 1):
        for k in range(seg):
            a = i * seg + k
            b = i * seg + (k + 1) % seg
            c = (i + 1) * seg + (k + 1) % seg
            d = (i + 1) * seg + k
            F.append((a, b, c))
            F.append((a, c, d))
    if cap0:
        i0 = len(V)
        V.append(pts[0])
        G.append(0.72)
        for k in range(seg):
            F.append((i0, (k + 1) % seg, k))
    if cap1:
        i0 = len(V)
        V.append(pts[-1])
        G.append(0.86)
        b = (n - 1) * seg
        for k in range(seg):
            F.append((i0, b + k, b + (k + 1) % seg))
    return V, F, G


def _blade(acc, p0, d, up, L, W, rng, col_lo, col_hi, roll=0.5):
    """One opaque leaf board: a diamond, double-wound, tilted to face the sky.

    The game camera looks down at 52 deg.  A leaf plane whose normal is
    horizontal is edge-on and disappears; a plane whose normal is up reads as
    leaf mass.  So every board is laid nearly flat and tilted only 25-35 deg
    outward -- enough to break the silhouette from the side, still facing the
    camera from above.
    """
    nrm = _norm(_add(_mul(up, 1.0), _mul(d, 0.52)))
    t1 = _norm(_sub(d, _mul(nrm, _dot(d, nrm))))
    t2 = _cross(nrm, t1)
    rl = (rng.random() - 0.5) * 2.0 * roll
    t2 = _rot_axis(t2, t1, rl)
    mid = _add(_mul(t1, L * 0.44), _mul(t2, W * 0.5))
    tip = _add(_mul(t1, L), _mul(nrm, L * 0.20))
    a = p0
    b = _add(p0, mid)
    c = _add(p0, tip)
    d2 = _sub(p0, mid)
    i = acc.nv
    acc.V.extend([a, b, c, d2])
    acc.C.extend([col_lo, col_hi, col_hi, col_lo])
    acc.F.extend([(i, i + 1, i + 2), (i, i + 2, i + 3),
                  (i + 2, i + 1, i), (i + 3, i + 2, i)])
    acc.M.extend([MAT_LEAF] * 4)
    acc.L.extend([1, 1, 1, 1])
    acc.nv += 4


class _Acc(object):
    """Vertex/face/colour accumulator for one tree template."""

    __slots__ = ("V", "F", "M", "C", "L", "nv")

    def __init__(self):
        self.V = []
        self.F = []
        self.M = []
        self.C = []
        self.L = []
        self.nv = 0

    def add(self, V, F, mat, col, leaf=0, g=None):
        i = self.nv
        self.V.extend(V)
        self.F.extend([(a + i, b + i, c + i) for (a, b, c) in F])
        self.M.extend([mat] * len(F))
        if isinstance(col, tuple):
            base = [col] * len(V)
        else:
            base = list(col)
        if g is not None:
            base = [(base[k][0] * g[k], base[k][1] * g[k], base[k][2] * g[k])
                    for k in range(len(base))]
        self.C.extend(base)
        self.L.extend([leaf] * len(V))
        self.nv += len(V)

    def result(self):
        V = np.asarray(self.V, dtype=np.float64) if np is not None else self.V
        F = np.asarray(self.F, dtype=np.int32) if np is not None else self.F
        M = np.asarray(self.M, dtype=np.int32) if np is not None else self.M
        C = np.asarray(self.C, dtype=np.float64) if np is not None else self.C
        L = np.asarray(self.L, dtype=np.uint8) if np is not None else self.L
        return V, F, M, C, L


# --------------------------------------------------------------------------
# growth
# --------------------------------------------------------------------------
def _trunk(acc, rng, cfg, H, lean):
    """Tapered, fluted trunk with a root flare and a forked top."""
    b = _lin(cfg["bark"])
    bd = _lin(cfg["bark_dark"])
    zf = cfg["trunk"] * H
    r0 = cfg["r0"] * H
    n = 5
    pts, rad = [], []
    for i in range(n + 1):
        t = i / float(n)
        z = -0.04 * H + (zf + 0.04 * H) * t
        # the lean is a curve, not a shear: a trunk that stays straight is a pole
        x = lean[0] * H * (t ** 1.6)
        y = lean[1] * H * (t ** 1.6)
        pts.append((x, y, z))
        # flare at the base, then a taper that accelerates near the fork
        rad.append(r0 * (1.0 - 0.62 * t) * (1.0 + 0.42 * (1.0 - t) ** 3.2))
    V, F, G = _tube(pts, rad, seg=10, cap0=True, groove=0.15, ngr=5,
                    phase=rng.uniform(0.0, TAU))
    acc.add(V, F, MAT_BARK, b, 0, g=G)
    # buttress roots: 4-5 short ridges at the base.  Without them the trunk
    # meets the ground at a mathematical point and reads as a stuck pole.
    for i in range(rng.randint(4, 5)):
        a = TAU * i / 4.6 + rng.uniform(-0.3, 0.3)
        d = (math.cos(a), math.sin(a), 0.0)
        L = r0 * rng.uniform(1.5, 2.4)
        p0 = (pts[0][0] + d[0] * r0 * 0.5, pts[0][1] + d[1] * r0 * 0.5,
              pts[0][2] + r0 * 0.10)
        p1 = (pts[0][0] + d[0] * L, pts[0][1] + d[1] * L,
              pts[0][2] + r0 * 0.55)
        v, f, g = _tube([p0, _lerp3(p0, p1, 0.55), p1],
                        [r0 * 0.42, r0 * 0.26, r0 * 0.05], seg=5, cap1=True)
        acc.add(v, f, MAT_BARK, bd, 0, g=g)
    return pts, rad, zf


def _boughs(acc, rng, cfg, H, zf, lean, level):
    """Fork the trunk into 3-5 boughs and (at L0) a second generation.

    Returns [(tip_pos, tip_radius, tip_dir)] -- the crown is built from these,
    which is the whole point: a lump has to sit on a branch or it is a ball in
    the air.
    """
    b = _lin(cfg["bark"])
    bd = _lin(cfg["bark_dark"])
    crown = cfg["crown"]
    spread = cfg["spread"] * H
    nb = rng.randint(*cfg["boughs"])
    if nb <= 0:
        return []
    tips = []
    a0 = rng.uniform(0.0, TAU)
    for i in range(nb):
        a = a0 + TAU * i / nb + rng.uniform(-0.28, 0.28)
        ca, sa = math.cos(a), math.sin(a)
        if crown == "column":
            out, up = spread * rng.uniform(0.25, 0.55), H * rng.uniform(0.62, 0.80)
        elif crown == "vase":
            out, up = spread * rng.uniform(0.72, 1.02), H * rng.uniform(0.44, 0.58)
        elif crown == "weep":
            out, up = spread * rng.uniform(0.85, 1.15), H * rng.uniform(0.46, 0.58)
        elif crown == "round":
            out, up = spread * rng.uniform(0.60, 0.90), H * rng.uniform(0.40, 0.55)
        else:                                            # dome
            out, up = spread * rng.uniform(0.62, 0.96), H * rng.uniform(0.36, 0.52)
        top = (lean[0] * H + ca * out, lean[1] * H + sa * out, zf + up)
        # a bough is a curve: out first, then up, and it thins as it goes
        mid = _lerp3((lean[0] * H * 0.9, lean[1] * H * 0.9, zf), top, 0.52)
        mid = (mid[0] + ca * out * 0.10, mid[1] + sa * out * 0.10,
               mid[2] - H * 0.03)
        r_base = cfg["r0"] * H * rng.uniform(0.34, 0.46)
        pts = [(lean[0] * H * 0.9, lean[1] * H * 0.9, zf - H * 0.01),
               mid, top]
        rad = [r_base, r_base * 0.62, r_base * 0.24]
        V, F, G = _tube(pts, rad, seg=6, cap1=True)
        acc.add(V, F, MAT_BARK, bd, 0, g=G)
        d = _norm(_sub(top, mid))
        tips.append((top, rad[-1], d))
        if level > 0:
            for j in range(2):
                a2 = a + rng.uniform(-1.15, 1.15)
                t = rng.uniform(0.45, 0.72)
                base = _lerp3(pts[1], pts[2], t)
                L2 = spread * rng.uniform(0.30, 0.52)
                t2 = (base[0] + math.cos(a2) * L2,
                      base[1] + math.sin(a2) * L2,
                      base[2] + H * rng.uniform(0.10, 0.22))
                r2 = rad[1] * rng.uniform(0.38, 0.52)
                v2, f2, g2 = _tube([base, _lerp3(base, t2, 0.55), t2],
                                   [r2, r2 * 0.58, r2 * 0.18], seg=4, cap1=True)
                acc.add(v2, f2, MAT_BARK, bd, 0, g=g2)
                tips.append((t2, r2 * 0.18, _norm(_sub(t2, base))))
    return tips


def _clump(acc, rng, c, r, leaf, dark, light, lod, boards=0, squash=0.85):
    """One lump of leaf mass: a low-poly blob plus (at L0) rim boards."""
    sub = 1 if (lod == 0 and r > 0.85) else 0
    V, F = _blob(c, r, rng, squash=(1.0, 1.0, squash), jitter=0.15, sub=sub,
                 lump=rng.uniform(0.75, 1.25))
    cols = []
    for p in V:
        t = max(0.0, min(1.0, 0.5 + (p[2] - c[2]) / (2.2 * r)))
        # underside in shadow, top in sun: a lump with one flat colour is a ball
        cols.append(_mixc(_mul(dark, 0.86), light, t * 0.82))
    acc.add(V, F, MAT_LEAF, cols, leaf=1)
    if boards and lod == 0:
        up = (0.0, 0.0, 1.0)
        for i in range(boards):
            a = TAU * i / boards + rng.uniform(-0.35, 0.35)
            d = _norm((math.cos(a), math.sin(a), rng.uniform(-0.12, 0.34)))
            p0 = _add(c, _mul(d, r * rng.uniform(0.48, 0.72)))
            p0 = (p0[0], p0[1], p0[2] + r * rng.uniform(0.05, 0.42))
            _blade(acc, p0, d, up, r * rng.uniform(0.72, 1.10),
                   r * rng.uniform(0.42, 0.66), rng, dark, light)


def _crown(acc, rng, cfg, H, tips, lod):
    """Place 5-15 lumps: one on every branch tip, then fillers inside the
    envelope so the crown has a core and not just a ring of satellites."""
    leaf = _lin(cfg["leaf"])
    dark = _lin(cfg["dark"])
    light = _lin(cfg["light"])
    spread = cfg["spread"] * H
    lo, hi = cfg["clumps"]
    if lod == 0:
        want = rng.randint(lo, hi)
    elif lod == 1:
        want = rng.randint(4, 6)
    else:
        want = 2
    squash = cfg.get("squash", 0.85)
    r_base = spread * (0.34 if lod == 0 else 0.44)
    # tips first -- they define the silhouette
    order = list(tips)
    rng.shuffle(order)
    placed = 0
    for (p, rt, d) in order:
        if placed >= want:
            break
        r = r_base * rng.uniform(0.72, 1.20)
        c = (p[0] + d[0] * r * 0.42, p[1] + d[1] * r * 0.42,
             p[2] + d[2] * r * 0.34)
        _clump(acc, rng, c, r, leaf, dark, light, lod,
               boards=(7 if lod == 0 else 0), squash=squash)
        placed += 1
    # fillers: a dome around the crown centre, biased to the outside
    zc = H * (0.62 if cfg["crown"] != "column" else 0.70)
    while placed < want:
        a = rng.uniform(0.0, TAU)
        rr = spread * math.sqrt(rng.random()) * 0.78
        zz = zc + (rng.random() - 0.42) * H * 0.26
        c = (math.cos(a) * rr, math.sin(a) * rr, zz)
        _clump(acc, rng, c, r_base * rng.uniform(0.70, 1.05), leaf, dark,
               light, lod, boards=(6 if lod == 0 else 0), squash=squash)
        placed += 1
    return placed


def _willow_strands(acc, rng, cfg, H, tips, lod):
    """The signature of a willow: 8-14 thin strands hanging off the crown."""
    dark = _lin(cfg["dark"])
    light = _lin(cfg["light"])
    n = 10 if lod == 0 else 0
    for i in range(n):
        if not tips:
            break
        p, rt, d = tips[i % len(tips)]
        a = rng.uniform(0.0, TAU)
        out = (math.cos(a), math.sin(a), 0.0)
        L = H * rng.uniform(0.28, 0.46)
        p0 = _add(p, _mul(out, rng.uniform(0.10, 0.55) * H * cfg["spread"]))
        p1 = (p0[0] + out[0] * L * 0.30, p0[1] + out[1] * L * 0.30,
              p0[2] - L * 0.55)
        p2 = (p1[0] + out[0] * L * 0.16, p1[1] + out[1] * L * 0.16,
              p1[2] - L * 0.62)
        V, F, G = _tube([p0, p1, p2], [H * 0.006, H * 0.005, H * 0.002],
                        seg=3, cap1=True)
        acc.add(V, F, MAT_LEAF, _mul(dark, 1.10), leaf=1, g=G)
        for j in range(2):
            q = _lerp3(p0, p2, 0.45 + 0.3 * j)
            _blade(acc, q, out, (0.0, 0.0, 1.0), L * 0.30, L * 0.16, rng,
                   dark, light)


def _spruce(acc, rng, cfg, H, lod):
    """Conifer: a straight pole and tiers of drooping skirts with visible gaps."""
    b = _lin(cfg["bark"])
    bd = _lin(cfg["bark_dark"])
    dark = _lin(cfg["dark"])
    light = _lin(cfg["light"])
    if lod == 2:
        # silhouette: a six-sided cone.  From 52 deg above a distant spruce is
        # a dark triangle; 12 triangles is all it can resolve.
        r = cfg["spread"] * H
        base = H * 0.10
        V = [(0.0, 0.0, H)]
        F = []
        for k in range(6):
            a = TAU * k / 6.0
            V.append((math.cos(a) * r, math.sin(a) * r, base))
        for k in range(6):
            F.append((0, 1 + k, 1 + (k + 1) % 6))
        acc.add(V, F, MAT_LEAF, _mul(dark, 1.06), leaf=1)
        tv, tf, tg = _tube([(0, 0, -0.03 * H), (0, 0, base + 0.05 * H)],
                           [cfg["r0"] * H * 0.8, cfg["r0"] * H * 0.5], seg=4)
        acc.add(tv, tf, MAT_BARK, b, 0, g=tg)
        return
    ntiers = (11 if lod == 0 else 6)
    sides = (8 if lod == 0 else 5)
    top = H * 0.99
    base = H * 0.09
    tv, tf, tg = _tube([(0, 0, -0.04 * H), (0, 0, H * 0.28),
                        (0, 0, H * 0.62), (0, 0, top)],
                       [cfg["r0"] * H * 1.05, cfg["r0"] * H * 0.70,
                        cfg["r0"] * H * 0.40, cfg["r0"] * H * 0.14],
                       seg=(6 if lod == 0 else 4), cap0=True, cap1=True)
    acc.add(tv, tf, MAT_BARK, b, 0, g=tg)
    for i in range(ntiers):
        t = i / float(ntiers - 1)
        z = base + (top - base) * t
        r = cfg["spread"] * H * (1.0 - t) ** 0.86 * rng.uniform(0.94, 1.08)
        r = max(r, H * 0.012)
        h = (top - base) / ntiers
        droop = h * rng.uniform(0.26, 0.44)
        ring_o, ring_i = [], []
        for k in range(sides):
            a = TAU * k / sides + i * 0.62
            jo = rng.uniform(0.90, 1.10)
            ring_o.append((math.cos(a) * r * 1.18 * jo,
                           math.sin(a) * r * 1.18 * jo, z - droop))
            ring_i.append((math.cos(a) * r * 0.52,
                           math.sin(a) * r * 0.52, z + h * 0.62))
        tip = (rng.uniform(-0.02, 0.02) * H, rng.uniform(-0.02, 0.02) * H,
               z + h * 1.02)
        V = ring_o + ring_i + [tip]
        F = []
        tp = 2 * sides
        for k in range(sides):
            k1 = (k + 1) % sides
            a0, b0 = k, sides + k
            a1, b1 = k1, sides + k1
            F.append((a0, a1, b1))
            F.append((a0, b1, b0))
            F.append((b0, b1, tp))
        cols = []
        for p in V:
            cols.append(_mixc(dark, light,
                              max(0.0, min(1.0, (p[2] - z) / (h * 1.4) * 0.5
                                              + 0.35))))
        acc.add(V, F, MAT_LEAF, cols, leaf=1)
        if lod == 0 and i % 2 == 0:
            # needle sprays hanging off the skirt rim: they break the smooth
            # cone silhouette that made far spruces read as dark party hats
            for k in range(3):
                a = TAU * rng.random()
                p0 = (math.cos(a) * r * 1.05, math.sin(a) * r * 1.05,
                      z - droop)
                _blade(acc, p0, _norm((math.cos(a), math.sin(a), -0.55)),
                       (0.0, 0.0, 1.0), h * 1.5, h * 0.55, rng, dark, light)


def _fruit_dots(acc, rng, cfg, H, tips, lod):
    """A dozen fruit-coloured specks.  At 5 m they are what says 'orchard'."""
    if lod != 0:
        return
    col = (0.72, 0.16, 0.10) if rng.random() < 0.6 else (0.78, 0.55, 0.12)
    for i in range(rng.randint(8, 15)):
        p, rt, d = tips[i % max(1, len(tips))]
        a = rng.uniform(0.0, TAU)
        rr = H * rng.uniform(0.10, 0.30)
        c = (p[0] + math.cos(a) * rr, p[1] + math.sin(a) * rr,
             p[2] - H * rng.uniform(0.02, 0.16))
        s = H * 0.022
        i0 = acc.nv
        acc.V.extend([(c[0] - s, c[1] - s, c[2]), (c[0] + s, c[1] - s, c[2]),
                      (c[0], c[1] + s, c[2] + s * 0.6)])
        acc.F.append((i0, i0 + 1, i0 + 2))
        acc.C.extend([col, col, col])
        acc.M.append(MAT_LEAF)
        acc.L.extend([1, 1, 1])
        acc.nv += 3


def _lod2_tree(acc, rng, cfg, H):
    """A distant tree: three crossed cards plus an umbrella cap.

    The cap is the part that matters.  From the game camera the top of a tree
    is most of what you see, so a vertical-card-only billboard is a sliver with
    sky above it -- that is why the far woods read as a row of thin marks.
    """
    leaf = _lin(cfg["leaf"])
    dark = _lin(cfg["dark"])
    b = _lin(cfg["bark"])
    r = cfg["spread"] * H * 1.15
    z0 = H * 0.30
    z1 = H * 0.96
    for j in range(3):
        a = math.pi * j / 3.0
        ca, sa = math.cos(a), math.sin(a)
        q = [(-r * 0.86, z0 + H * 0.10), (r * 0.86, z0 + H * 0.10),
             (r * 0.62, z1), (-r * 0.62, z1)]
        i0 = len(acc.V)
        acc.V.extend([(p[0] * ca, p[0] * sa, p[1]) for p in q])
        acc.C.extend([_mul(dark, 0.92), _mul(dark, 0.92), _mul(leaf, 1.06),
                      _mul(leaf, 1.06)])
        acc.F.extend([(i0, i0 + 1, i0 + 2), (i0, i0 + 2, i0 + 3)])
        acc.M.extend([MAT_LEAF] * 2)
        acc.L.extend([1] * 4)
        acc.nv += 4
    # umbrella cap: a hexagonal plate at 0.74 H, wider than the cards
    zc = H * 0.74
    rc = cfg["spread"] * H * 1.30
    i0 = len(acc.V)
    acc.V.append((0.0, 0.0, zc + H * 0.11))
    for k in range(6):
        a = TAU * k / 6.0
        acc.V.append((math.cos(a) * rc, math.sin(a) * rc, zc))
    acc.C.extend([_mul(leaf, 1.10)] + [_mul(dark, 1.02)] * 6)
    for k in range(6):
        acc.F.append((i0, i0 + 1 + k, i0 + 1 + (k + 1) % 6))
    acc.M.extend([MAT_LEAF] * 6)
    acc.L.extend([1] * 7)
    acc.nv += 7
    tv, tf, tg = _tube([(0, 0, -0.04 * H), (0, 0, z0 + H * 0.05)],
                       [cfg["r0"] * H * 1.1, cfg["r0"] * H * 0.45], seg=4)
    acc.add(tv, tf, MAT_BARK, b, 0, g=tg)


# --------------------------------------------------------------------------
# template cache
# --------------------------------------------------------------------------
NVAR = (5, 4, 3)                    # variants per LOD
_TMPL = {}


def _finish(acc, H, kind, lod, variant):
    """Normalise the built tree so its top is exactly H metres above z=0.

    The generator places clumps and boughs by proportion, which lands a tree
    within a few percent of its nominal height -- and for the willow, whose
    crown hangs low, several percent short.  `scale` is documented as "how tall
    the tree is", so it has to be exact: one uniform correction here is cheaper
    than hand-tuning every species, and it keeps the placement code honest.
    """
    zmax = max(p[2] for p in acc.V) if acc.V else H
    k = H / zmax if zmax > 1e-6 else 1.0
    if abs(k - 1.0) > 1e-4:
        acc.V = [(p[0] * k, p[1] * k, p[2] * k) for p in acc.V]
    V, F, M, C, L = acc.result()
    return dict(V=V, F=F, M=M, C=C, L=L, H=H, kind=kind, lod=lod,
                variant=variant)


def _build(kind, variant, lod):
    cfg = SPECIES[kind]
    # NOT hash(): Python salts string hashing per process, so hash((kind, ...))
    # differs between runs and the same seed would build a different tree in
    # every Blender session.  crc32 is stable across processes and versions.
    import zlib
    rng = random.Random(zlib.crc32(("%s|%d|%d" % (kind, variant, lod))
                                   .encode("utf-8")))
    # a variant sits at a fixed point in the species' height range, so five
    # variants of an oak are five different trees, not one tree five times
    f = (variant + 0.5) / float(NVAR[lod])
    H = cfg["H"][0] + (cfg["H"][1] - cfg["H"][0]) * (0.18 + 0.70 * f)
    H *= rng.uniform(0.94, 1.06)
    acc = _Acc()
    if lod == 2:
        if cfg["crown"] == "cone":
            _spruce(acc, rng, cfg, H, 2)
        else:
            _lod2_tree(acc, rng, cfg, H)
        V, F, M, C, L = acc.result()
        return _finish(acc, H, kind, lod, variant)
    if cfg["crown"] == "cone":
        _spruce(acc, rng, cfg, H, lod)
    else:
        lean = (rng.uniform(-0.045, 0.045), rng.uniform(-0.045, 0.045))
        pts, rad, zf = _trunk(acc, rng, cfg, H, lean)
        tips = _boughs(acc, rng, cfg, H, zf, lean, 1 if lod == 0 else 0)
        _crown(acc, rng, cfg, H, tips, lod)
        if cfg["crown"] == "weep":
            _willow_strands(acc, rng, cfg, H, tips, lod)
        if kind == "fruit":
            _fruit_dots(acc, rng, cfg, H, tips, lod)
    V, F, M, C, L = acc.result()
    return _finish(acc, H, kind, lod, variant)


def template(kind, lod=0, variant=0):
    """Cached template dict: V, F, M, C, L, H (natural height in metres)."""
    key = (kind, int(lod), int(variant) % NVAR[int(lod)])
    t = _TMPL.get(key)
    if t is None:
        t = _build(key[0], key[2], key[1])
        _TMPL[key] = t
    return t


def tree(kind, rng=None, scale=1.0, lod=0):
    """One tree as raw geometry, `scale` metres tall, standing on z = 0.

    Returns (V, F, M, C, L): verts, tris, per-face material index (0 bark /
    1 leaf), per-vertex linear colour, per-vertex leaf mask.  `rng` only picks
    which of the cached variants you get; pass None for variant 0.
    """
    if kind not in SPECIES:
        raise KeyError("unknown tree kind %r (have %s)"
                       % (kind, ", ".join(KINDS)))
    lod = max(0, min(2, int(lod)))
    v = 0 if rng is None else int(rng.random() * NVAR[lod]) % NVAR[lod]
    t = template(kind, lod, v)
    s = float(scale) / t["H"]
    V = t["V"] * s
    return V, t["F"].copy(), t["M"].copy(), t["C"].copy(), t["L"].copy()


def tree_template(kind, lod, seed=0):
    """hd_landscape_geo.tree_template contract: (V, F, shade), height 0..1.

    `kind` here is the landscape's integer species code so the far-field
    instancer can be switched over without touching it:
        0 spruce, 1 oak, 2 poplar, 3 orchard
    `shade` is per-vertex brightness (crown lit from above, trunk dark).
    """
    names = {0: "spruce", 1: "oak", 2: "poplar", 3: "fruit"}
    name = names.get(int(kind), "oak")
    lod = max(0, min(2, int(lod)))
    t = template(name, lod, int(seed) % NVAR[lod])
    H = t["H"]
    V = t["V"] / H
    C = np.clip(t["C"], 0.0, 1.0)
    shade = np.clip(C * 1.55, 0.10, 1.0)
    return V, t["F"].copy(), shade


# --------------------------------------------------------------------------
# plan helpers: streets, units, polygons
# --------------------------------------------------------------------------
def _segdist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L < 1e-12 else max(0.0, min(1.0,
                                          ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class StreetIndex(object):
    """Which street is near (x, y) and how wide is it.

    Same contract as hd_dense._Streets.near() -> (kind, width, distance), so a
    caller can pass either one in.  A tree must clear the carriageway by its
    own radius plus a metre, otherwise it stands in the road.
    """

    CELL = 24.0

    def __init__(self, streets):
        self.seg = []
        self.grid = {}
        for s in streets or ():
            kind = str(s.get("kind") or "")
            w = float(s.get("w") or 6.0)
            for seg in (s.get("segs") or ()):
                try:
                    if isinstance(seg[0], (list, tuple)):
                        pts = [(float(p[0]), float(p[1])) for p in seg]
                    else:
                        pts = [(float(seg[0]), float(seg[1])),
                               (float(seg[2]), float(seg[3]))]
                except (TypeError, IndexError, ValueError):
                    continue
                for i in range(len(pts) - 1):
                    x1, y1 = pts[i]
                    x2, y2 = pts[i + 1]
                    if math.hypot(x2 - x1, y2 - y1) < 0.05:
                        continue
                    j = len(self.seg)
                    self.seg.append((x1, y1, x2, y2, kind, w))
                    for gx in range(int(math.floor(min(x1, x2) / self.CELL)),
                                    int(math.floor(max(x1, x2) / self.CELL)) + 1):
                        for gy in range(int(math.floor(min(y1, y2) / self.CELL)),
                                        int(math.floor(max(y1, y2) / self.CELL)) + 1):
                            self.grid.setdefault((gx, gy), []).append(j)

    def near(self, x, y, r=26.0):
        gx, gy = int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL))
        bk, bw, bd = "", 6.0, r
        best = -1
        for ix in (gx - 1, gx, gx + 1):
            for iy in (gy - 1, gy, gy + 1):
                for i in self.grid.get((ix, iy), ()):
                    x1, y1, x2, y2, kind, w = self.seg[i]
                    d = _segdist(x, y, x1, y1, x2, y2)
                    if d < bd:
                        bd, bk, bw, best = d, kind, w, i
        if best < 0:
            return None, 6.0, r
        return bk, bw, bd


class UnitIndex(object):
    """Occupancy of the house placements, as oriented boxes on a hash grid.

    A tree 1.2 m from a facade is fine (it is a courtyard tree); a tree 0.2 m
    from one is growing through a wall.  `pad` is the clearance in metres.
    """

    CELL = 10.0

    def __init__(self, units):
        self.g = {}
        n = 0
        for u in units or ():
            q = u.get("quad")
            rec = None
            if q and len(q) >= 4:
                try:
                    pts = [(float(p[0]), float(p[1])) for p in q[:4]]
                except (TypeError, IndexError, ValueError):
                    pts = None
                if pts:
                    cx = sum(p[0] for p in pts) / 4.0
                    cy = sum(p[1] for p in pts) / 4.0
                    ex = 0.0
                    ey = 0.0
                    for p in pts:
                        ex = max(ex, abs(p[0] - cx))
                        ey = max(ey, abs(p[1] - cy))
                    # axis-aligned bound is enough: units are 5-15 m and the
                    # clearance is ~1 m, so the over-estimate only costs a few
                    # rejected candidates at the corners
                    rec = (cx, cy, ex, ey)
            if rec is None:
                x = u.get("x")
                y = u.get("y")
                if x is None or y is None:
                    continue
                rec = (float(x), float(y), float(u.get("w") or 6.0) * 0.5,
                       float(u.get("d") or 6.0) * 0.5)
            cx, cy, ex, ey = rec
            for gx in range(int(math.floor((cx - ex) / self.CELL)),
                            int(math.floor((cx + ex) / self.CELL)) + 1):
                for gy in range(int(math.floor((cy - ey) / self.CELL)),
                                int(math.floor((cy + ey) / self.CELL)) + 1):
                    self.g.setdefault((gx, gy), []).append(rec)
            n += 1
        self.n = n

    def hit(self, x, y, pad=1.2):
        gx, gy = int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL))
        for ix in (gx - 1, gx, gx + 1):
            for iy in (gy - 1, gy, gy + 1):
                for (cx, cy, ex, ey) in self.g.get((ix, iy), ()):
                    if abs(x - cx) <= ex + pad and abs(y - cy) <= ey + pad:
                        return True
        return False


def _area(poly):
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return a * 0.5


def _ccw(poly):
    return list(poly) if _area(poly) > 0 else list(reversed(poly))


def _pip(x, y, poly):
    """Even-odd point in polygon."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xc = xi + (y - yi) * (xj - xi) / (yj - yi + 1e-12)
            if x < xc:
                inside = not inside
        j = i
    return inside


def _inset(poly, d):
    """Inset a CCW polygon by `d` metres; returns [] when it collapses."""
    n = len(poly)
    if n < 3 or d <= 0.0:
        return list(poly)
    lines = []
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ux, uy = bx - ax, by - ay
        L = math.hypot(ux, uy)
        if L < 1e-9:
            return []
        ux, uy = ux / L, uy / L
        nx, ny = -uy, ux                    # inward normal for CCW
        lines.append(((ax + nx * d, ay + ny * d), (ux, uy)))
    out = []
    for i in range(n):
        (p1, u1) = lines[i - 1]
        (p2, u2) = lines[i]
        den = u1[0] * u2[1] - u1[1] * u2[0]
        if abs(den) < 1e-9:
            out.append(p2)
            continue
        t = ((p2[0] - p1[0]) * u2[1] - (p2[1] - p1[1]) * u2[0]) / den
        out.append((p1[0] + u1[0] * t, p1[1] + u1[1] * t))
    # an inset that folds over itself is worse than no inset at all
    if abs(_area(out)) < 0.12 * abs(_area(poly)):
        return []
    for i in range(len(out)):
        a = out[i]
        b = out[(i + 1) % len(out)]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.4:
            return []
    return out


def _bisector_in(poly, i, d):
    """Move vertex i `d` metres along the inward bisector (a street corner)."""
    n = len(poly)
    a = poly[i - 1]
    b = poly[i]
    c = poly[(i + 1) % n]
    u1 = _norm((b[0] - a[0], b[1] - a[1], 0.0))
    u2 = _norm((c[0] - b[0], c[1] - b[1], 0.0))
    m = _norm((u1[0] + u2[0], u1[1] + u2[1], 0.0))
    if m[0] == 0.0 and m[1] == 0.0:
        m = (-u1[1], u1[0], 0.0)
    nx, ny = -m[1], m[0]                # inward for CCW
    cosh = max(0.30, abs(u1[0] * u2[0] + u1[1] * u2[1]))
    k = min(2.6, 1.0 / cosh)
    return (b[0] + nx * d * k, b[1] + ny * d * k)


def _wall_radius(res):
    """Outer radius of the curtain, from the plan if it carries one."""
    r = 0.0
    city = (res or {}).get("city") or {}
    for key in ("rim", "wall"):
        pts = city.get(key)
        if pts:
            for p in pts:
                try:
                    r = max(r, math.hypot(float(p[0]), float(p[1])))
                except (TypeError, IndexError, ValueError):
                    pass
    if r > 0.0:
        return r
    for b in ((res or {}).get("blocks") or ()):
        for p in (b.get("poly") or ()):
            r = max(r, math.hypot(p[0], p[1]))
    return r if r > 0.0 else 947.2


def _pick_weighted(rng, table):
    tot = sum(w for _k, w in table)
    r = rng.random() * tot
    for k, w in table:
        r -= w
        if r <= 0.0:
            return k
    return table[-1][0]


class _Focus(object):
    """Nearest-focus distance, used to pick a LOD band."""

    CELL = 40.0

    def __init__(self, pts):
        self.g = {}
        self.pts = [(float(p[0]), float(p[1])) for p in (pts or ())]
        for (x, y) in self.pts:
            self.g.setdefault((int(math.floor(x / self.CELL)),
                               int(math.floor(y / self.CELL))), []).append((x, y))

    def dist(self, x, y, cap=1e9):
        best = cap
        gx, gy = int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL))
        rad = int(math.ceil(cap / self.CELL))
        for ix in range(gx - rad, gx + rad + 1):
            for iy in range(gy - rad, gy + rad + 1):
                for (fx, fy) in self.g.get((ix, iy), ()):
                    d = math.hypot(x - fx, y - fy)
                    if d < best:
                        best = d
        return best


def _auto_focus(res, wall_r, step=60.0):
    """Default focus: a grid over the walled town, 40 m inside the curtain.

    The player can walk anywhere inside the walls, so every city tree has to be
    L0; the L1 band then starts just outside the curtain, which is exactly
    where a tree is 40-60 m from the nearest walkable point.
    """
    pts = [(0.0, 0.0)]
    R = max(20.0, wall_r - 40.0)
    n = int(R / step) + 1
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = i * step, j * step
            if math.hypot(x, y) <= R:
                pts.append((x, y))
    return pts


# --------------------------------------------------------------------------
# placement
# --------------------------------------------------------------------------
def place(units=None, res=None, seed=7, street=None, blocked=None,
          wall_r=None, focus=None, bands=BANDS, lod=2, target=2600,
          autumn=0.09, min_gap=4.2, verbose=False):
    """Lay trees out in a walled town.  Pure python -- no bpy.

    units   hd_pick()/hd_dense.placements() records; only "quad" is used, and
            a tree may not stand inside one (plus 1.25 m).
    res     plan dict: "blocks" (poly, role, open), "streets", "landmarks",
            optional "city"->"rim".
    street  anything with .near(x, y) -> (kind, width, dist); built from
            res["streets"] when omitted.
    blocked callable(x, y) -> True to refuse a spot (capital.py passes its own
            _reserved here; without it a tree can land on the market hall).
    focus   points the camera/player can reach, for the LOD bands.  None ->
            a 60 m grid over the walled town (see _auto_focus).
    bands   (near, mid) in metres: L0 inside `near`, L1 inside `mid`, L2 beyond.
    lod     maximum LOD to assign.
    target  soft target for the number of city trees (1500-3000 wanted).

    Returns a list of dicts: x, y, z, kind, scale, rot, tint, lod, role, seed.
    """
    t0 = time.time()
    rng = random.Random(int(seed) * 7919 + 41)
    res = res or {}
    if wall_r is None:
        wall_r = _wall_radius(res)
    if street is None:
        street = StreetIndex(res.get("streets") or ())
    ui = UnitIndex(units or ())
    if focus is None:
        focus = _auto_focus(res, wall_r)
    F = _Focus(focus)
    far = bands[1] * 1.6 if bands else 1e9
    lod_cap = max(0, min(2, int(lod)))

    blocks = []
    for b in (res.get("blocks") or ()):
        pts = b.get("poly") or b.get("polygon") or b.get("pts")
        if not pts or len(pts) < 3:
            continue
        poly = _ccw([(float(p[0]), float(p[1])) for p in pts])
        blocks.append(dict(poly=poly, role=str(b.get("role") or ""),
                           open=bool(b.get("open")), area=abs(_area(poly))))
    if not blocks:
        # no plan: fall back to a disc so build() still produces something
        poly = [(math.cos(TAU * i / 48.0) * wall_r * 0.92,
                 math.sin(TAU * i / 48.0) * wall_r * 0.92) for i in range(48)]
        blocks = [dict(poly=poly, role="residential", open=False,
                       area=abs(_area(poly)))]

    # tree spacing: 6 m cells, 2 m query radius -> no two trunks in one hole
    taken = {}

    def free(x, y, gap):
        gx, gy = int(math.floor(x / 6.0)), int(math.floor(y / 6.0))
        for ix in (gx - 1, gx, gx + 1):
            for iy in (gy - 1, gy, gy + 1):
                for (tx, ty) in taken.get((ix, iy), ()):
                    if (x - tx) ** 2 + (y - ty) ** 2 < gap * gap:
                        return False
        return True

    def claim(x, y):
        taken.setdefault((int(math.floor(x / 6.0)),
                          int(math.floor(y / 6.0))), []).append((x, y))

    out = []
    rej = {"road": 0, "house": 0, "blocked": 0, "gap": 0, "wall": 0}

    def consider(x, y, role, gap=None, road_pad=1.35):
        rr = math.hypot(x, y)
        if rr > wall_r - 2.5:
            rej["wall"] += 1
            return None
        kind_s, w, d = street.near(x, y, 30.0)
        if d < w * 0.5 + road_pad:
            rej["road"] += 1
            return None
        if ui.hit(x, y, 1.25):
            rej["house"] += 1
            return None
        if blocked is not None and blocked(x, y):
            rej["blocked"] += 1
            return None
        g = min_gap if gap is None else gap
        if not free(x, y, g):
            rej["gap"] += 1
            return None
        claim(x, y)
        d_foc = F.dist(x, y, far)
        if not bands:
            lo = 0
        elif d_foc <= bands[0]:
            lo = 0
        elif d_foc <= bands[1]:
            lo = 1
        else:
            lo = 2
        lo = min(lo, lod_cap)
        sp = _pick_weighted(rng, ROLE_SPECIES.get(role, ROLE_SPECIES["corner"]))
        cfg = SPECIES[sp]
        sc = cfg["H"][0] + (cfg["H"][1] - cfg["H"][0]) * rng.random()
        if role == "courtyard":
            sc *= rng.uniform(0.82, 1.02)
        elif role == "square":
            sc *= rng.uniform(0.95, 1.15)
        elif role == "wall":
            sc *= rng.uniform(1.0, 1.25)
        rec = dict(x=round(x, 2), y=round(y, 2), z=0.0, kind=sp,
                   scale=round(sc, 3), rot=round(rng.uniform(0.0, TAU), 4),
                   tint=round(_pick_tint(rng, autumn), 4), lod=lo,
                   role=role, seed=rng.getrandbits(30))
        out.append(rec)
        return rec

    # ---- 1. street corners: the elm on the corner is the classic silhouette
    for b in blocks:
        if b["open"]:
            continue
        n = len(b["poly"])
        for i in range(n):
            if rng.random() < 0.34:
                continue
            x, y = _bisector_in(b["poly"], i, rng.uniform(3.0, 5.2))
            consider(x, y, "corner")

    # ---- 2. courtyard trees: fruit inside the block, clear of the houses
    for b in blocks:
        if b["open"]:
            continue
        inner = _inset(b["poly"], 5.0)
        if not inner:
            continue
        area = abs(_area(inner))
        # one tree per ~210 m2 of courtyard, capped: a 40 000 m2 block must not
        # turn into an orchard
        want = int(min(9, max(1, area / 210.0)))
        placed_here = 0
        xs = [p[0] for p in inner]
        ys = [p[1] for p in inner]
        for _ in range(want * 9):
            if placed_here >= want:
                break
            x = rng.uniform(min(xs), max(xs))
            y = rng.uniform(min(ys), max(ys))
            if not _pip(x, y, inner):
                continue
            if consider(x, y, "courtyard", gap=3.4) is not None:
                placed_here += 1

    # ---- 3. squares and plazas: a ring of lindens just inside the paving edge
    for b in blocks:
        role = b["role"]
        if role not in ("square", "plaza", "temple", "guild", "palace"):
            continue
        inner = _inset(b["poly"], 3.6)
        if not inner:
            continue
        n = len(inner)
        for i in range(n):
            if rng.random() < 0.25:
                continue
            a = inner[i]
            c = inner[(i + 1) % n]
            t = rng.uniform(0.3, 0.7)
            x = a[0] + (c[0] - a[0]) * t
            y = a[1] + (c[1] - a[1]) * t
            consider(x, y, "square", gap=6.0)

    # ---- 4. landmark surroundings: churchyard, guild court, market hall
    for lm in (res.get("landmarks") or ()):
        pos = lm.get("pos") or lm.get("x")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            lx, ly = float(pos[0]), float(pos[1])
        elif pos is not None and lm.get("y") is not None:
            lx, ly = float(pos), float(lm.get("y"))
        else:
            continue
        w = float(lm.get("w") or 12.0)
        d = float(lm.get("d") or 12.0)
        rad = 0.5 * math.hypot(w, d) + rng.uniform(5.0, 9.0)
        n = rng.randint(4, 8)
        for i in range(n):
            a = TAU * i / n + rng.uniform(-0.3, 0.3)
            consider(lx + math.cos(a) * rad, ly + math.sin(a) * rad,
                     "landmark", gap=6.5)

    # ---- 5. avenue verges: every gate road is lined with trees
    gates = (((res.get("city") or {}).get("gates")) or ())
    for g in gates:
        try:
            gx, gy = float(g[0]), float(g[1])
        except (TypeError, IndexError, ValueError):
            continue
        r = math.hypot(gx, gy) or 1.0
        ux, uy = gx / r, gy / r
        t = r * 0.30
        while t < r - 26.0:
            for side in (-1.0, 1.0):
                off = 8.6 + rng.uniform(-0.8, 0.8)
                x = ux * t - uy * off * side
                y = uy * t + ux * off * side
                consider(x, y, "avenue", gap=7.5)
            t += rng.uniform(16.0, 24.0)

    # ---- 6. the wall foot: scrubby oaks and spruces in the dead zone
    nw = max(1, int(wall_r / 12.0))
    for i in range(nw):
        a = TAU * i / nw + rng.uniform(-0.02, 0.02)
        rr = wall_r - rng.uniform(5.0, 13.0)
        consider(math.cos(a) * rr, math.sin(a) * rr, "wall", gap=9.0)

    # ---- 7. top up to the target with verge trees along the big streets
    if len(out) < target:
        for s in (res.get("streets") or ()):
            if len(out) >= target:
                break
            w = float(s.get("w") or 6.0)
            if w < 7.0:
                continue
            for seg in (s.get("segs") or ()):
                if len(out) >= target:
                    break
                try:
                    if isinstance(seg[0], (list, tuple)):
                        pts = [(float(p[0]), float(p[1])) for p in seg]
                    else:
                        pts = [(float(seg[0]), float(seg[1])),
                               (float(seg[2]), float(seg[3]))]
                except (TypeError, IndexError, ValueError):
                    continue
                for i in range(len(pts) - 1):
                    ax, ay = pts[i]
                    bx, by = pts[i + 1]
                    L = math.hypot(bx - ax, by - ay)
                    if L < 14.0:
                        continue
                    ux, uy = (bx - ax) / L, (by - ay) / L
                    t = 6.0
                    while t < L - 6.0:
                        if rng.random() < 0.30:
                            off = w * 0.5 + rng.uniform(2.2, 3.4)
                            for side in (-1.0, 1.0):
                                consider(ax + ux * t - uy * off * side,
                                         ay + uy * t + ux * off * side,
                                         "avenue", gap=7.0)
                        t += rng.uniform(11.0, 17.0)

    if verbose:
        print("[nature] place: %d trees in %.2fs  rejected %s"
              % (len(out), time.time() - t0, rej), flush=True)
    _LAST["place"] = dict(n=len(out), seconds=time.time() - t0, rejected=rej,
                          wall_r=wall_r, units=ui.n, blocks=len(blocks))
    return out


# --------------------------------------------------------------------------
# batching and mesh emission
# --------------------------------------------------------------------------
_LAST = {}


def _mk_obj(name, V, F, M, C, mats, smooth=True):
    """One mesh from numpy arrays.  All faces must be triangles."""
    import bpy
    me = bpy.data.meshes.new(name)
    nv = int(V.shape[0])
    nf = int(F.shape[0])
    me.vertices.add(nv)
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    me.loops.add(nf * 3)
    me.loops.foreach_set("vertex_index", F.astype(np.int32).ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start",
                            np.arange(0, nf * 3, 3, dtype=np.int32))
    try:
        me.polygons.foreach_set("loop_total", np.full(nf, 3, dtype=np.int32))
    except Exception:                                            # noqa: BLE001
        pass
    me.update(calc_edges=False)
    ca = me.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
    C4 = np.ones((nv, 4), dtype=np.float32)
    C4[:, :3] = np.clip(C, 0.0, 1.0)
    ca.data.foreach_set("color", C4.ravel())
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", M.astype(np.int32))
    if smooth:
        me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=np.int32))
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


class _Cell(object):
    """Accumulator for one spatial cell: many trees, one mesh."""

    __slots__ = ("V", "F", "M", "C", "nv")

    def __init__(self):
        self.V = []
        self.F = []
        self.M = []
        self.C = []
        self.nv = 0

    def add(self, t, x, y, z, rot, scale, tint_rgb):
        V0 = t["V"]
        s = float(scale) / t["H"]
        ca, sa = math.cos(rot), math.sin(rot)
        v = np.empty((V0.shape[0], 3), dtype=np.float64)
        v[:, 0] = (V0[:, 0] * ca - V0[:, 1] * sa) * s + x
        v[:, 1] = (V0[:, 0] * sa + V0[:, 1] * ca) * s + y
        v[:, 2] = V0[:, 2] * s + z
        self.V.append(v)
        self.F.append(t["F"] + self.nv)
        self.M.append(t["M"])
        # the tint multiplies LEAF vertices only: a yellow tree keeps its bark
        C0 = t["C"]
        L0 = t["L"][:, None].astype(np.float64)
        tr = np.asarray(tint_rgb, dtype=np.float64)[None, :]
        self.C.append(C0 * (1.0 - L0) + C0 * tr * L0)
        self.nv += V0.shape[0]

    def push(self, name, mats):
        if not self.V:
            return None
        V = np.concatenate(self.V, 0)
        F = np.concatenate(self.F, 0)
        M = np.concatenate(self.M, 0)
        C = np.concatenate(self.C, 0)
        return _mk_obj(name, V, F, M, C, mats)


def make_materials(MAT):
    """Two materials for the whole tree layer: bark and leaf.

    Both read the "Col" vertex attribute, so ONE material serves seven species,
    every season tint and every LOD.  The noise adds the mottling that a flat
    vertex colour cannot give at 5 m.
    """
    import bpy
    out = []
    for name, base_rough, furrow in (("nat_leaf", 0.74, 0.0),
                                     ("nat_bark", 0.90, 1.0)):
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out_n = nt.nodes.new("ShaderNodeOutputMaterial")
        out_n.location = (620, 0)
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (320, 0)
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.location = (-680, 180)
        attr.attribute_name = "Col"
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.location = (-900, -220)
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.location = (-720, -220)
        mp.inputs["Scale"].default_value = (1.0 / 2.4, 1.0 / 2.4,
                                            1.0 / 6.0 if furrow else 1.0 / 2.4)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        noi = nt.nodes.new("ShaderNodeTexNoise")
        noi.location = (-520, -240)
        noi.inputs["Scale"].default_value = (3.6 if furrow else 9.0)
        noi.inputs["Detail"].default_value = 4.0
        noi.inputs["Roughness"].default_value = 0.55
        nt.links.new(mp.outputs["Vector"], noi.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.location = (-300, -240)
        ramp.color_ramp.elements[0].position = 0.32
        ramp.color_ramp.elements[0].color = (0.78, 0.80, 0.72, 1.0)
        ramp.color_ramp.elements[1].position = 0.72
        ramp.color_ramp.elements[1].color = (1.16, 1.12, 1.04, 1.0)
        nt.links.new(noi.outputs["Fac"], ramp.inputs["Fac"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.location = (60, 60)
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(attr.outputs["Color"], mix.inputs[6])
        nt.links.new(ramp.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = base_rough
        for key, val in (("Specular IOR Level", 0.22),
                         ("Subsurface Weight", 0.06 if not furrow else 0.0)):
            if key in bsdf.inputs:
                try:
                    bsdf.inputs[key].default_value = val
                except Exception:                                # noqa: BLE001
                    pass
        if furrow:
            bump = nt.nodes.new("ShaderNodeBump")
            bump.location = (60, -320)
            bump.inputs["Strength"].default_value = 0.55
            bump.inputs["Distance"].default_value = 0.06
            nt.links.new(noi.outputs["Fac"], bump.inputs["Height"])
            nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        nt.links.new(bsdf.outputs["BSDF"], out_n.inputs["Surface"])
        MAT[name] = m
        out.append(m)
    return out[0], out[1]


def build(MAT, units=None, res=None, seed=7, cell=64.0, lod=2, **kw):
    """Build the city tree layer.  See the module docstring for the contract."""
    t0 = time.time()
    leaf_mat, bark_mat = make_materials(MAT)
    mats = [bark_mat, leaf_mat]
    recs = place(units, res, seed=seed, lod=lod, **kw)
    cells = {}
    for r in recs:
        k = (int(math.floor(r["x"] / cell)), int(math.floor(r["y"] / cell)))
        c = cells.get(k)
        if c is None:
            c = cells[k] = _Cell()
        c.add(template(r["kind"], r["lod"], r["seed"] % NVAR[r["lod"]]),
              r["x"], r["y"], r["z"], r["rot"], r["scale"], tint(r["tint"]))
    objs = []
    for (k, c) in sorted(cells.items()):
        ob = c.push("nature_trees_%d_%d" % (k[0], k[1]), mats)
        if ob is not None:
            objs.append(ob)
    nf = sum(len(o.data.polygons) for o in objs) if objs else 0
    info = dict(count=len(recs), objects=len(objs), tris=nf,
                seconds=time.time() - t0, peak_mb=_peak_mb(),
                by_lod={}, by_kind={}, place=_LAST.get("place", {}))
    for r in recs:
        info["by_lod"][r["lod"]] = info["by_lod"].get(r["lod"], 0) + 1
        info["by_kind"][r["kind"]] = info["by_kind"].get(r["kind"], 0) + 1
    _LAST["build"] = info
    return dict(objects=objs, records=recs, info=info)


# --------------------------------------------------------------------------
# the belt outside the wall
# --------------------------------------------------------------------------
def forest(MAT=None, res=None, seed=7, r0=None, r1=None, density=0.020,
           cell=180.0, focus=None, bands=BANDS, lod=2, autumn=0.11,
           clear=None, verbose=False):
    """Woodland outside the wall: shared templates, real size distribution.

    `density` is trees per square metre (0.020 = one tree per 50 m2 inside the
    wood, which is a closed canopy with gaps).  Sizes are drawn per tree from
    the species' range and then multiplied by a per-tree factor, so a belt is
    not a field of clones -- that flatness is half of why the far woods read as
    green dots.
    """
    t0 = time.time()
    rng = random.Random(int(seed) * 104729 + 7)
    if MAT is not None:
        leaf_mat, bark_mat = make_materials(MAT)
    else:
        import bpy
        leaf_mat = bpy.data.materials.get("nat_leaf")
        bark_mat = bpy.data.materials.get("nat_bark")
    mats = [bark_mat, leaf_mat]
    if r0 is None:
        r0 = _wall_radius(res) + 8.0
    if r1 is None:
        r1 = r0 + 900.0
    if focus is None:
        focus = _auto_focus(res or {}, r0 - 8.0)
    F = _Focus(focus)
    far = bands[1] * 1.6 if bands else 1e9
    # jittered grid, spacing set by density
    step = max(4.0, 1.0 / math.sqrt(max(1e-6, density)))
    cells = {}
    n = 0
    nr = int(r1 / step) + 2
    for i in range(-nr, nr + 1):
        for j in range(-nr, nr + 1):
            x = i * step + rng.uniform(-0.42, 0.42) * step
            y = j * step + rng.uniform(-0.42, 0.42) * step
            r = math.hypot(x, y)
            if r < r0 or r > r1:
                continue
            # a wood has glades: two noise octaves, not a uniform fill
            g = (0.62 + 0.38 * math.sin(x * 0.0061 + 1.7)
                 * math.sin(y * 0.0053 - 0.4)
                 + 0.20 * math.sin(x * 0.021 - y * 0.017))
            if g < 0.42 or rng.random() > g:
                continue
            if clear is not None and clear(x, y):
                continue
            d_foc = F.dist(x, y, far)
            if not bands:
                lo = 0
            elif d_foc <= bands[0]:
                lo = 0
            elif d_foc <= bands[1]:
                lo = 1
            else:
                lo = 2
            lo = min(lo, max(0, min(2, int(lod))))
            sp = _pick_weighted(rng, ROLE_SPECIES["forest"])
            cfg = SPECIES[sp]
            sc = cfg["H"][0] + (cfg["H"][1] - cfg["H"][0]) * rng.random()
            sc *= rng.uniform(0.80, 1.22)          # real woods are uneven
            k = (int(math.floor(x / cell)), int(math.floor(y / cell)))
            c = cells.get(k)
            if c is None:
                c = cells[k] = _Cell()
            c.add(template(sp, lo, rng.randrange(NVAR[lo])), x, y, 0.0,
                  rng.uniform(0.0, TAU), sc, tint(_pick_tint(rng, autumn)))
            n += 1
    objs = []
    for (k, c) in sorted(cells.items()):
        ob = c.push("nature_forest_%d_%d" % (k[0], k[1]), mats)
        if ob is not None:
            objs.append(ob)
    nf = sum(len(o.data.polygons) for o in objs) if objs else 0
    info = dict(count=n, objects=len(objs), tris=nf,
                seconds=time.time() - t0, peak_mb=_peak_mb(),
                r0=r0, r1=r1)
    if verbose:
        print("[nature] forest: %d trees / %d tris / %.1fs"
              % (n, nf, info["seconds"]), flush=True)
    _LAST["forest"] = info
    return dict(objects=objs, info=info)


# --------------------------------------------------------------------------
# wind
# --------------------------------------------------------------------------
def wind(objects, t=0.0, amp=0.045, dir=(1.0, 0.0), speed=1.0):
    """Bend every vertex by (z / H)**1.5 along the wind.

    hd_weather.sway() rotates a whole object about its origin, which is right
    for one tree and wrong for a 64 m cell of 200 trees: the cell would lean as
    a slab.  This deforms per vertex, so a batched cell sways like a wood.
    Rest positions are cached on the object the first time, so repeated calls
    do not accumulate.
    """
    dx, dy = float(dir[0]), float(dir[1])
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    k = 0
    for ob in objects or ():
        if ob is None or ob.type != "MESH":
            continue
        me = ob.data
        nv = len(me.vertices)
        if nv == 0:
            continue
        rest = ob.get("nat_rest")
        if rest is None or len(rest) != nv * 3:
            co = np.empty(nv * 3, dtype=np.float64)
            me.vertices.foreach_get("co", co)
            ob["nat_rest"] = co.tolist()
            rest = ob["nat_rest"]
        R = np.asarray(rest, dtype=np.float64).reshape(nv, 3)
        zmax = float(R[:, 2].max()) or 1.0
        w = np.clip(R[:, 2] / zmax, 0.0, 1.0) ** 1.5
        ph = R[:, 0] * 0.11 + R[:, 1] * 0.07
        s = amp * speed * np.sin(t * 1.9 + ph) * w
        co = R.copy()
        co[:, 0] += dx * s
        co[:, 1] += dy * s
        me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        me.update()
        k += 1
    return k


# --------------------------------------------------------------------------
# stats
# --------------------------------------------------------------------------
def _peak_mb():
    """Peak working set of this process in MB (Windows), 0.0 elsewhere."""
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / (1024.0 * 1024.0)
    except Exception:                                            # noqa: BLE001
        return 0.0


def stats():
    """Last place()/build()/forest() numbers, plus the template face table."""
    out = dict(_LAST)
    tab = {}
    for kind in KINDS:
        tab[kind] = {}
        for lod in (0, 1, 2):
            t = template(kind, lod, 0)
            tab[kind][lod] = dict(faces=int(t["F"].shape[0]),
                                  verts=int(t["V"].shape[0]),
                                  H=round(t["H"], 2))
    out["templates"] = tab
    return out


def face_table():
    """Printed summary: faces per LOD per species."""
    lines = ["%-8s %8s %8s %8s   %s" % ("kind", "L0", "L1", "L2", "L1/L0")]
    for kind in KINDS:
        f = [int(template(kind, i, 0)["F"].shape[0]) for i in (0, 1, 2)]
        lines.append("%-8s %8d %8d %8d   %5.1f%%"
                     % (kind, f[0], f[1], f[2], 100.0 * f[1] / max(1, f[0])))
    tot = [sum(int(template(k, i, 0)["F"].shape[0]) for k in KINDS)
           for i in (0, 1, 2)]
    lines.append("%-8s %8d %8d %8d" % ("ALL 7", tot[0], tot[1], tot[2]))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# self test (plain python, no Blender)
# --------------------------------------------------------------------------
def _selftest():
    t0 = time.time()
    print(face_table())
    print()
    for kind in KINDS:
        for lod in (0, 1, 2):
            V, F, M, C, L = tree(kind, random.Random(3), 10.0, lod)
            z = V[:, 2]
            assert abs(float(z.min())) < 0.9, (kind, lod, float(z.min()))
            assert abs(float(z.max()) - 10.0) < 1.4, (kind, lod, float(z.max()))
            assert C.min() >= 0.0 and C.max() <= 2.0, (kind, lod, C.min(),
                                                       C.max())
            assert int(M.max()) <= 1
    print("geometry ok  (%.2fs)" % (time.time() - t0))
    rng = random.Random(7)
    n = 0
    for i in range(1000):
        lod = 0 if i % 20 == 0 else (1 if i % 3 == 0 else 2)
        t = template(rng.choice(KINDS), lod, rng.randrange(NVAR[lod]))
        n += int(t["F"].shape[0])
    print("1000 trees -> %d tris (mixed LOD)" % n)
    res = dict(blocks=[], streets=[])
    for i in range(6):
        for j in range(6):
            x0, y0 = i * 70.0 - 210.0, j * 70.0 - 210.0
            poly = [(x0 + 4, y0 + 4), (x0 + 62, y0 + 4), (x0 + 62, y0 + 62),
                    (x0 + 4, y0 + 62)]
            res["blocks"].append(dict(poly=poly, role="residential",
                                      open=False))
            res["streets"].append(dict(kind="secondary", w=8.0,
                                       segs=[(x0 + 62, y0 + 4, x0 + 70, y0 + 4),
                                             (x0 + 4, y0 + 62, x0 + 4, y0 + 70)]))
    units = []
    for b in res["blocks"]:
        p = b["poly"]
        units.append(dict(x=p[0][0] + 5, y=p[0][1] + 5, w=9.0, d=9.0))
    t0 = time.time()
    recs = place(units, res, seed=7, wall_r=260.0, target=300, verbose=True)
    print("place ok: %d records in %.2fs" % (len(recs), time.time() - t0))
    if recs:
        import json
        print(json.dumps(recs[0], ensure_ascii=False))
    print("peak_mb %.1f" % _peak_mb())


if __name__ == "__main__":
    _selftest()
