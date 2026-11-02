"""hd_landscape_geo -- the kit the outer landscape is built from.

Four things live here, in this order:

  1. micro-meshes   -- icosphere, tapered tube, blobs.  Everything is
     triangles only, because `LS.mk_obj` has a fast path for a uniform face
     arity and 200 k trees are not funny through a Python per-face loop.
  2. trees          -- one template per (species, LOD), instantiated by the
     metre.  Four species (spruce, oak, poplar, apple) x three LODs, so the
     silhouette survives out to 3 km.
  3. field furniture-- hedge banks with gaps and height noise, dry stone walls,
     post-and-rail fences, ridge-and-furrow strips.
  4. small props    -- hayricks, wood stacks, compost, beehives, carts, folds.

Everything takes `LS`, the hd_landscape module, as its first argument instead of
importing it, so there is no circular import: hd_landscape imports this, this
never imports hd_landscape.

All output is world space with an identity object transform (that is what lets
the shaders use Object coordinates as world coordinates).
"""
import math

import numpy as np

# --------------------------------------------------------------------------- #
#  micro-meshes
# --------------------------------------------------------------------------- #


def _icosphere():
    """Unit icosphere, one subdivision: 42 verts, 80 triangles.  Cached."""
    global _ICO
    if _ICO is not None:
        return _ICO
    t = (1.0 + 5.0 ** 0.5) / 2.0
    v = np.array([
        [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
        [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
        [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
    ], dtype=np.float64)
    f = np.array([
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ], dtype=np.int32)
    v = v / np.linalg.norm(v, axis=1)[:, None]
    # subdivide: 30 edge midpoints -> 80 faces
    mid = {}
    verts = list(v)
    faces = []
    for a, b, c in f:
        ids = []
        for p, q in ((a, b), (b, c), (c, a)):
            k = (min(p, q), max(p, q))
            j = mid.get(k)
            if j is None:
                m = verts[p] + verts[q]
                m = m / np.linalg.norm(m)
                j = len(verts)
                verts.append(m)
                mid[k] = j
            ids.append(j)
        ab, bc, ca = ids
        faces += [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]
    _ICO = (np.asarray(verts), np.asarray(faces, dtype=np.int32))
    return _ICO


_ICO = None


def _xform(V, pos=(0.0, 0.0, 0.0), rot=0.0, scale=1.0, squash=(1.0, 1.0, 1.0)):
    """Rotate about Z, squash, scale, translate.  V is (n,3)."""
    V = np.asarray(V, dtype=np.float64)
    S = np.asarray(squash, dtype=np.float64) * float(scale)
    P = V * S
    if rot:
        cs, sn = math.cos(rot), math.sin(rot)
        x = P[:, 0] * cs - P[:, 1] * sn
        y = P[:, 0] * sn + P[:, 1] * cs
        P = np.stack([x, y, P[:, 2]], 1)
    P = P + np.asarray(pos, dtype=np.float64)[None, :]
    return P


def _blob(pos, r, rng, squash=(1.0, 1.0, 1.0), jitter=0.14):
    """An icosphere clump, radially jittered so it does not read as a ball."""
    v, f = _icosphere()
    n = np.linalg.norm(v, axis=1)
    d = 1.0 + (rng.random(v.shape[0]) - 0.5) * 2.0 * jitter
    return _xform(v * (d / n)[:, None], pos, rng.uniform(0, 6.283), r, squash), f


def _tube(secs, seg=6, cap_top=True, cap_bot=False, phase=0.0):
    """Tapered tube through sections [(x, y, z, r), ...].  Returns (V, F)."""
    V = []
    for (x, y, z, r) in secs:
        for k in range(seg):
            a = 2.0 * math.pi * k / seg + phase
            V.append((x + r * math.cos(a), y + r * math.sin(a), z))
    F = []
    ns = len(secs)
    for i in range(ns - 1):
        for k in range(seg):
            a = i * seg + k
            b = i * seg + (k + 1) % seg
            c = (i + 1) * seg + (k + 1) % seg
            d = (i + 1) * seg + k
            F.append((a, b, c))
            F.append((a, c, d))
    if cap_top:
        tip = len(V)
        x, y, z, _r = secs[-1]
        V.append((x, y, z))
        b0 = (ns - 1) * seg
        for k in range(seg):
            F.append((b0 + k, b0 + (k + 1) % seg, tip))
    if cap_bot:
        tip = len(V)
        x, y, z, _r = secs[0]
        V.append((x, y, z))
        for k in range(seg):
            F.append((k, tip, (k + 1) % seg))
    return np.asarray(V, dtype=np.float64), F


def _tri_faces(F):
    """Faces already triangles; kept as a named step so intent is obvious."""
    return F


def _triF(F):
    """Quads and fans -> triangles, for props that build their own face lists."""
    out = []
    for f in F:
        if len(f) == 3:
            out.append(tuple(f))
        else:
            for k in range(1, len(f) - 1):
                out.append((f[0], f[k], f[k + 1]))
    return out


# --------------------------------------------------------------------------- #
#  trees
# --------------------------------------------------------------------------- #
#  0 = spruce / fir   1 = oak / ash   2 = poplar   3 = apple / pear
SPRUCE, OAK, POPLAR, ORCHARD = 0, 1, 2, 3
KIND_NAME = ("spruce", "oak", "poplar", "orchard")

_TMPL = {}


def _tree_spruce(lod, rng):
    """A conifer: a straight pole and tiers of drooping skirts.

    A spruce reads as a cone with *steps* in it -- the tiers matter more than
    the triangle count, so LOD0 spends its budget on 13 of them.
    """
    V, F = [], []

    def add(v, f):
        i = sum(len(x) for x in V)
        V.append(np.asarray(v, dtype=np.float64))
        F.extend([tuple(k + i for k in t) for t in f])

    if lod == 0:
        nseg, ntiers, sides = 6, 24, 10
    elif lod == 1:
        nseg, ntiers, sides = 4, 9, 6
    else:
        # far: a star of three crossed triangles plus a stub trunk.  The
        # triangles have to be merged into the returned mesh -- returning the
        # trunk alone leaves far conifers as bare posts.
        w = 0.20
        for a in (0.0, math.pi / 3.0, 2.0 * math.pi / 3.0):
            cs, sn = math.cos(a), math.sin(a)
            for p in ((-w, 0.08), (w, 0.08), (0.0, 1.0)):
                V.append(np.array([p[0] * cs, p[0] * sn, p[1]]))
            F.append((len(V) - 3, len(V) - 2, len(V) - 1))
        tv, tf = _tube([(0, 0, -0.02, 0.026), (0, 0, 0.16, 0.020)],
                       seg=4, cap_top=False)
        i0 = len(V)
        V.extend(np.asarray(x, dtype=np.float64) for x in tv)
        F.extend(tuple(k + i0 for k in t) for t in tf)
        return np.asarray(V, dtype=np.float64), F

    tv, tf = _tube([(0, 0, -0.035, 0.030), (0, 0, 0.20, 0.022),
                    (0, 0, 0.55, 0.012)], seg=nseg, cap_top=False)
    add(tv, tf)
    base = 0.05
    top = 0.94
    for i in range(ntiers):
        t = i / float(ntiers - 1)
        z = base + (top - base) * t
        r = 0.315 * (1.0 - t) ** 0.92 * (1.0 + 0.16 * (rng.random() - 0.5))
        r = max(r, 0.035)
        h = (top - base) / ntiers * 1.75
        skirt = r * 1.16
        droop = h * 0.30
        i0 = len(V)
        ring = []
        for k in range(sides):
            a = 2.0 * math.pi * k / sides + i * 0.7
            ring.append((skirt * math.cos(a), skirt * math.sin(a), z - droop))
        V.append(np.asarray(ring))
        V.append(np.asarray([(r * math.cos(2.0 * math.pi * k / sides + i * 0.7),
                              r * math.sin(2.0 * math.pi * k / sides + i * 0.7),
                              z) for k in range(sides)]))
        V.append(np.asarray([(0.0, 0.0, z + h)]))
        a0, b0, tip = i0, i0 + sides, i0 + 2 * sides
        for k in range(sides):
            k1 = (k + 1) % sides
            F.append((a0 + k, a0 + k1, b0 + k1))
            F.append((a0 + k, b0 + k1, b0 + k))
            F.append((b0 + k, b0 + k1, tip))
    return _cat(V), F


def _tree_oak(lod, rng):
    """Broadleaf: a leaning trunk, three boughs, and a cauliflower crown.

    The crown is 5-7 icosphere clumps on a dome, which is what makes an oak
    silhouette read as an oak at 52 degrees from above: lobed, not round.
    """
    V, F = [], []

    def add(v, f):
        i = sum(len(x) for x in V)
        V.append(np.asarray(v, dtype=np.float64))
        F.extend([tuple(k + i for k in t) for t in f])

    if lod == 2:
        # Three crossed quads plus a stub trunk: a star billboard that keeps a
        # crown from every angle a player can walk round it, for twenty
        # triangles.  Built here and merged, not returned on their own -- the
        # first version threw the quads away and far trees were bare posts.
        w = 0.42
        for a in (0.0, math.pi / 3.0, 2.0 * math.pi / 3.0):
            cs, sn = math.cos(a), math.sin(a)
            q = [(-w, 0.16), (w, 0.16), (w * 0.92, 0.98), (-w * 0.92, 0.98)]
            i0 = sum(len(x) for x in V)
            V.append(np.asarray([(p[0] * cs, p[0] * sn, p[1]) for p in q]))
            F += [(i0, i0 + 1, i0 + 2), (i0, i0 + 2, i0 + 3)]
        tv, tf = _tube([(0, 0, -0.04, 0.045), (0, 0, 0.24, 0.030)],
                       seg=4, cap_top=False)
        add(tv, tf)
        return _cat(V), F

    lean = rng.uniform(-0.05, 0.05)
    tv, tf = _tube([(0, 0, -0.05, 0.055), (lean * 0.4, 0, 0.13, 0.040),
                    (lean, 0, 0.34, 0.030), (lean * 1.5, 0, 0.52, 0.020)],
                   seg=6 if lod == 0 else 4, cap_top=False)
    add(tv, tf)
    nb = 3 if lod == 0 else 0
    for i in range(nb):
        a = 2.0 * math.pi * i / nb + rng.uniform(-0.4, 0.4)
        r0 = 0.30 - 0.05 * i
        bv, bf = _tube([(lean, 0, 0.30 + 0.05 * i, 0.020),
                        (math.cos(a) * r0 * 0.6, math.sin(a) * r0 * 0.6,
                         0.30 + 0.13 * i, 0.014),
                        (math.cos(a) * r0, math.sin(a) * r0,
                         0.30 + 0.22 * i, 0.008)],
                       seg=4, cap_top=True)
        add(bv, bf)
    if lod == 0:
        nclump, cr = 8, 0.238
    else:
        nclump, cr = 2, 0.33
    for i in range(nclump):
        if nclump == 2:
            a = rng.uniform(0, 6.283)
            rz = 0.62 + i * 0.20
            rad = 0.10 * i
        else:
            a = 2.0 * math.pi * i / nclump + rng.uniform(-0.3, 0.3)
            f = i / float(nclump - 1)
            rz = 0.60 + 0.26 * math.sin(f * math.pi) + rng.uniform(-0.04, 0.04)
            rad = 0.20 + 0.10 * math.sin(f * math.pi)
        cx = math.cos(a) * rad
        cy = math.sin(a) * rad
        rr = cr * rng.uniform(0.80, 1.18)
        v, f = _blob((cx, cy, rz), rr, rng,
                     squash=(1.0, 1.0, rng.uniform(0.72, 0.92)))
        add(v, f)
    return _cat(V), F


def _tree_poplar(lod, rng):
    """Lombardy poplar: a column, so a hedge of them reads as a wall of spires."""
    if lod == 2:
        V = []
        F = []
        w = 0.13
        for a in (0.0, math.pi / 3.0, 2.0 * math.pi / 3.0):
            cs, sn = math.cos(a), math.sin(a)
            for z, ww in ((0.10, w * 0.35), (0.40, w), (0.75, w * 0.8),
                          (1.0, 0.0)):
                V.append(np.array([-ww * cs, -ww * sn, z]))
                V.append(np.array([ww * cs, ww * sn, z]))
            i0 = len(V) - 8
            for k in range(3):
                F.append((i0 + 2 * k, i0 + 2 * k + 1, i0 + 2 * k + 3))
                F.append((i0 + 2 * k, i0 + 2 * k + 3, i0 + 2 * k + 2))
        tv, tf = _tube([(0, 0, -0.03, 0.030), (0, 0, 0.14, 0.024)],
                       seg=4, cap_top=False)
        i0 = len(V)
        V.extend(np.asarray(x, dtype=np.float64) for x in tv)
        F.extend(tuple(k + i0 for k in t) for t in tf)
        return np.asarray(V, dtype=np.float64), F
    nring = 20 if lod == 0 else 6
    sides = 14 if lod == 0 else 6
    V = []
    F = []
    z0, z1 = 0.03, 0.99
    rows = []
    for i in range(nring):
        t = i / float(nring - 1)
        z = z0 + (z1 - z0) * t
        r = 0.135 * (math.sin(math.pi * (0.06 + 0.88 * t)) ** 0.55)
        rows.append((z, r))
    for i, (z, r) in enumerate(rows):
        for k in range(sides):
            a = 2.0 * math.pi * k / sides + i * 0.4
            j = 0.86 + 0.28 * rng.random()
            V.append((r * j * math.cos(a), r * j * math.sin(a), z))
    for i in range(nring - 1):
        for k in range(sides):
            a = i * sides + k
            b = i * sides + (k + 1) % sides
            c = (i + 1) * sides + (k + 1) % sides
            d = (i + 1) * sides + k
            F.append((a, b, c))
            F.append((a, c, d))
    tv, tf = _tube([(0, 0, -0.03, 0.028), (0, 0, 0.12, 0.022)],
                   seg=5, cap_top=False)
    i0 = len(V)
    V.extend([tuple(p) for p in tv])
    F.extend([tuple(k + i0 for k in t) for t in tf])
    return np.asarray(V, dtype=np.float64), F


def _tree_orchard(lod, rng):
    """Apple / pear: short, wide, low -- the top of an orchard from 52 deg is a
    dotted grid of round crowns, which is exactly the texture a garden belt
    needs."""
    V, F = [], []

    def add(v, f):
        i = sum(len(x) for x in V)
        V.append(np.asarray(v, dtype=np.float64))
        F.extend([tuple(k + i for k in t) for t in f])

    if lod == 2:
        w = 0.36
        for a in (0.0, math.pi / 3.0, 2.0 * math.pi / 3.0):
            cs, sn = math.cos(a), math.sin(a)
            q = [(-w, 0.14), (w, 0.14), (w * 0.8, 0.60), (-w * 0.8, 0.60)]
            i0 = sum(len(x) for x in V)
            V.append(np.asarray([(p[0] * cs, p[0] * sn, p[1]) for p in q]))
            F += [(i0, i0 + 1, i0 + 2), (i0, i0 + 2, i0 + 3)]
        tv, tf = _tube([(0, 0, -0.03, 0.035), (0, 0, 0.16, 0.026)],
                       seg=4, cap_top=False)
        add(tv, tf)
        return _cat(V), F
    tv, tf = _tube([(0, 0, -0.04, 0.042), (0, 0, 0.12, 0.032),
                    (0, 0, 0.26, 0.024)], seg=5, cap_top=False)
    add(tv, tf)
    for i in range(3):
        a = 2.0 * math.pi * i / 3 + rng.uniform(-0.3, 0.3)
        r0 = 0.20
        bv, bf = _tube([(0, 0, 0.20, 0.016),
                        (math.cos(a) * r0, math.sin(a) * r0, 0.30, 0.010)],
                       seg=4, cap_top=True)
        add(bv, bf)
    if lod == 0:
        spots = [(0.0, 0.0, 0.46, 0.24), (0.18, 0.05, 0.40, 0.17),
                 (-0.15, 0.12, 0.41, 0.16), (0.02, -0.17, 0.39, 0.15),
                 (0.22, -0.12, 0.37, 0.13), (-0.20, -0.10, 0.38, 0.12)]
    else:
        spots = [(0.0, 0.0, 0.44, 0.30)]
    for (cx, cy, cz, r) in spots:
        v, f = _blob((cx, cy, cz), r * rng.uniform(0.86, 1.14), rng,
                     squash=(1.0, 1.0, 0.80))
        add(v, f)
    return _cat(V), F


_TREE_FN = (_tree_spruce, _tree_oak, _tree_poplar, _tree_orchard)


def _cat(V):
    return np.concatenate([np.asarray(x, dtype=np.float64) for x in V], 0)


def tree_template(kind, lod, seed=0):
    """(verts, faces, shade) for one species at one LOD.  Height-normalised.

    `shade` is a per-vertex brightness multiplier around 1.0: the crown darker
    underneath, the sunlit top brighter, the trunk its own value.  Per-instance
    hue is applied later, so one template serves a whole hillside of trees.
    """
    key = (kind, lod, seed)
    t = _TMPL.get(key)
    if t is not None:
        return t
    rng = np.random.default_rng(int(seed) * 7919 + kind * 131 + lod * 17 + 3)
    V, F = _TREE_FN[kind](lod, rng)
    z = V[:, 2]
    zlo, zhi = float(z.min()), float(z.max())
    t01 = (z - zlo) / max(1e-6, zhi - zlo)
    # trunk vs crown: the lowest 22 % of a tree is bark
    crown = t01 > (0.20 if lod < 2 else 0.16)
    shade = np.empty((V.shape[0], 3), dtype=np.float64)
    up = 0.80 + 0.42 * t01
    # a per-vertex jitter so no two clumps share a value
    jit = 0.88 + 0.24 * np.random.default_rng(seed * 31 + kind + lod).random(
        V.shape[0])
    shade[:, 0] = np.where(crown, up * jit, 0.30 * jit)
    shade[:, 1] = np.where(crown, up * jit, 0.24 * jit)
    shade[:, 2] = np.where(crown, up * jit * 0.92, 0.18 * jit)
    F = np.asarray(F, dtype=np.int32)
    _TMPL[key] = (V, F, shade)
    return _TMPL[key]


class TBuf(object):
    """Batched tree instances for one (species, LOD) bucket.

    Placement is done with numpy: N trees x V verts is one concatenate, not N
    Python calls, which is what makes 200 k trees affordable at 40 s.
    """

    __slots__ = ("V", "F", "C", "nv")

    def __init__(self):
        self.V = []
        self.F = []
        self.C = []
        self.nv = 0

    def add_many(self, V0, F0, shade, X, Y, Z, ROT, SC, COL):
        n = len(X)
        if n == 0:
            return
        nv = V0.shape[0]
        cs = np.cos(ROT)[:, None]
        sn = np.sin(ROT)[:, None]
        S = SC[:, None]
        xr = (V0[None, :, 0] * cs - V0[None, :, 1] * sn) * S + X[:, None]
        yr = (V0[None, :, 0] * sn + V0[None, :, 1] * cs) * S + Y[:, None]
        zr = V0[None, :, 2] * S + Z[:, None]
        self.V.append(np.stack([xr, yr, zr], 2).reshape(n * nv, 3))
        base = (self.nv + np.arange(n, dtype=np.int64) * nv)[:, None, None]
        self.F.append((F0[None, :, :] + base).reshape(-1, 3))
        self.C.append((shade[None, :, :] * COL[:, None, :]).reshape(n * nv, 3))
        self.nv += n * nv

    def empty(self):
        return not self.V

    def push(self, LS, name, mat):
        if not self.V:
            return None
        V = np.concatenate(self.V, 0)
        F = np.concatenate(self.F, 0)
        C = np.clip(np.concatenate(self.C, 0), 0.0, 1.0)
        V4 = np.ones((V.shape[0], 4), dtype=np.float32)
        V4[:, :3] = C
        return LS.mk_obj(name, V, F, [mat], None, smooth=True, vcol=V4)


# --------------------------------------------------------------------------- #
#  hedge banks, dry stone walls, fences
# --------------------------------------------------------------------------- #
_HEDGE_SEC = (
    # (across, height factor, colour factor)
    (-1.00, 0.00, 0.55),
    (-0.98, 0.52, 0.62),
    (-0.72, 0.88, 0.86),
    (-0.30, 1.00, 1.06),
    (0.30, 1.00, 1.06),
    (0.72, 0.88, 0.86),
    (0.98, 0.52, 0.62),
    (1.00, 0.00, 0.55),
)


def tq(acc, a, b, c, d, mat, col):
    """Quad as two triangles: every acc object stays uniform arity, which is
    what keeps mk_obj on its fast path."""
    acc.tri(a, b, c, mat, col)
    acc.tri(a, c, d, mat, col)


def hedge_band(LS, acc, P, w, h, rng, col, mat, crowns=None,
               step=2.6, gaps=None, gap_p=0.0):
    """A hedge *bank*: 3-5 m wide, 1.6-3.2 m tall, with gaps and a wavy top.

    The old `_hedge_run` emitted two vertical walls and a lid, which is why
    every hedge in V24 is a thin black line from above.  A hedge is a solid
    mass of foliage with a rounded top: it needs a cross-section, not a box.

    `P` is a list of (x, y) in world space; y is up=z.  `gaps` lets the caller
    force holes (gateways); `gap_p` is the chance of a random hole per station.
    """
    n = len(P)
    if n < 2:
        return 0
    Q = np.asarray(P, dtype=np.float64)
    # resample to `step`
    seg = np.hypot(np.diff(Q[:, 0]), np.diff(Q[:, 1]))
    L = float(seg.sum())
    if L < 4.0:
        return 0
    ns = max(2, int(L / step) + 1)
    t = np.concatenate([[0.0], np.cumsum(seg)]) / max(1e-6, L)
    ts = np.linspace(0.0, 1.0, ns)
    px = np.interp(ts, t, Q[:, 0])
    py = np.interp(ts, t, Q[:, 1])
    # tangent + normal
    dx = np.gradient(px)
    dy = np.gradient(py)
    dl = np.hypot(dx, dy) + 1e-9
    nx, ny = -dy / dl, dx / dl

    # per-station width / height noise (this is what kills the "hard line")
    s = int(rng.random() * 1e6)
    wobw = 1.0 + 0.30 * np.sin(ts * 41.0 + s % 7) + 0.18 * np.sin(ts * 17.0 + 1.3)
    wobh = 1.0 + 0.26 * np.sin(ts * 29.0 + 2.1) + 0.14 * np.sin(ts * 61.0)
    ww = w * np.clip(wobw, 0.55, 1.55)
    hh = h * np.clip(wobh, 0.62, 1.38)

    # gaps
    keep = np.ones(ns, dtype=bool)
    if gap_p > 0.0:
        r = np.random.default_rng(s)
        keep &= r.random(ns) > gap_p
        # a gap must be wide enough to read: 3 stations
        for i in range(ns):
            if not keep[i]:
                keep[max(0, i - 1):min(ns, i + 2)] = False
    if gaps:
        for (g0, g1) in gaps:
            keep[(ts >= g0) & (ts <= g1)] = False
    if keep.sum() < 2:
        return 0

    # emit strips over runs of `keep`
    i = 0
    ntri = 0
    zs = LS._gz(px, py)
    while i < ns:
        if not keep[i]:
            i += 1
            continue
        j = i
        while j + 1 < ns and keep[j + 1]:
            j += 1
        if j - i >= 1:
            ntri += _hedge_strip(acc, px, py, zs, nx, ny, ww, hh,
                                 i, j, col, mat, crowns, rng)
        i = j + 1
    return ntri


def _hedge_strip(acc, px, py, zs, nx, ny, ww, hh, i0, i1, col, mat,
                 crowns, rng):
    """One continuous run of a hedge bank, plus the standards growing out of it."""
    ns = i1 - i0 + 1
    nsx = len(_HEDGE_SEC)
    V = []
    for k in range(ns):
        i = i0 + k
        for (u, hf, cf) in _HEDGE_SEC:
            jx = (rng.random() - 0.5) * 0.10
            jz = (rng.random() - 0.5) * 0.10
            x = px[i] + nx[i] * u * ww[i] * 0.5
            y = py[i] + ny[i] * u * ww[i] * 0.5
            z = zs[i] + hh[i] * (hf + jz) - 0.10
            V.append((x + jx, y + jx, z))
    for k in range(ns - 1):
        for s in range(nsx - 1):
            a = k * nsx + s
            b = k * nsx + s + 1
            c = (k + 1) * nsx + s + 1
            d = (k + 1) * nsx + s
            tq(acc, V[a], V[b], V[c], V[d], mat, col)
    # end caps so the hedge has a face when it stops
    for k in (0, ns - 1):
        base = k * nsx
        for s in range(nsx - 2):
            acc.tri(V[base + s], V[base + s + 2], V[base + s + 1], mat, col)
    if crowns is not None and ns > 2:
        # a standard every ~30 m, standing in the bank
        per = max(4, int(30.0 / 2.6))
        for k in range(per // 2, ns, per):
            i = i0 + k
            crowns.append((px[i], py[i], zs[i] + hh[i] * 0.80))
    return (ns - 1) * (nsx - 1) * 2 + (nsx - 2) * 2


def drystone(LS, acc, P, h, t, rng, col, mat, step=1.6):
    """A dry stone wall: two faces, a coping course, a ragged top.

    Field walls are the other half of the enclosure pattern -- in limestone
    country there is no hedge, there is a wall, and it is 3 m of pale rubble in
    plan, not a hairline.
    """
    Q = np.asarray(P, dtype=np.float64)
    if len(Q) < 2:
        return 0
    seg = np.hypot(np.diff(Q[:, 0]), np.diff(Q[:, 1]))
    L = float(seg.sum())
    if L < 3.0:
        return 0
    ns = max(2, int(L / step) + 1)
    tt = np.concatenate([[0.0], np.cumsum(seg)]) / max(1e-6, L)
    ts = np.linspace(0.0, 1.0, ns)
    px = np.interp(ts, tt, Q[:, 0])
    py = np.interp(ts, tt, Q[:, 1])
    dx = np.gradient(px)
    dy = np.gradient(py)
    dl = np.hypot(dx, dy) + 1e-9
    nx, ny = -dy / dl, dx / dl
    zs = LS._gz(px, py)
    s = int(rng.random() * 1e6)
    hh = h * (1.0 + 0.16 * np.sin(ts * 23.0 + s % 5)
              + 0.10 * np.sin(ts * 57.0 + 1.1))
    # batched: 4 rings of 2 points -> quads; then coping blocks on top
    V = []
    for k in range(ns):
        for side in (-1.0, 1.0):
            for (zf, tf_) in ((0.0, 1.0), (0.62, 0.96), (0.90, 0.72)):
                V.append((px[k] + nx[k] * side * t * 0.5 * tf_,
                          py[k] + ny[k] * side * t * 0.5 * tf_,
                          zs[k] - 0.10 + hh[k] * zf))
    ntri = 0
    for k in range(ns - 1):
        for side in (0, 1):
            b = k * 6 + side * 3
            for r in range(2):
                a = b + r
                c = b + r + 1
                tq(acc, V[a], V[a + 3], V[c + 3], V[c], mat, col)
                ntri += 2
        # easy top face
        a0 = k * 6
        tq(acc, V[a0 + 2], V[a0 + 5], V[a0 + 8], V[a0 + 3], mat, col)
        ntri += 2
    return ntri


def _box(acc, verts, faces, mat, col):
    """A box as 12 triangles, so the object stays uniform arity."""
    for f in faces:
        tq(acc, verts[f[0]], verts[f[1]], verts[f[2]], verts[f[3]], mat, col)


def fence_line(LS, acc, P, h, rng, col, mat, step=3.0, post_step=3.4):
    """Post and rail: two rails and a post every 3.4 m.  Cheap, and it reads as
    a boundary from 400 m because of the light coming through it."""
    Q = np.asarray(P, dtype=np.float64)
    if len(Q) < 2:
        return 0
    seg = np.hypot(np.diff(Q[:, 0]), np.diff(Q[:, 1]))
    L = float(seg.sum())
    if L < 3.0:
        return 0
    npst = max(2, int(L / post_step) + 1)
    tt = np.concatenate([[0.0], np.cumsum(seg)]) / max(1e-6, L)
    ts = np.linspace(0.0, 1.0, npst)
    px = np.interp(ts, tt, Q[:, 0])
    py = np.interp(ts, tt, Q[:, 1])
    zs = LS._gz(px, py)
    pv, pf = LS.boxv(None, 0.15, 0.15, h + 0.30)
    for k in range(npst):
        _box(acc, [(p[0] + px[k], p[1] + py[k],
                    p[2] + zs[k] + (h + 0.30) * 0.5 - 0.16) for p in pv],
             pf, mat, col)
    for k in range(npst - 1):
        dx = px[k + 1] - px[k]
        dy = py[k + 1] - py[k]
        dl = math.hypot(dx, dy) + 1e-9
        ang = math.atan2(dy, dx)
        ca, sa = math.cos(ang), math.sin(ang)
        z0 = 0.5 * (zs[k] + zs[k + 1])
        cx = 0.5 * (px[k] + px[k + 1])
        cy = 0.5 * (py[k] + py[k + 1])
        for (zf, th) in ((0.88, 0.075), (0.60, 0.065)):
            v, f = LS.boxv(None, dl, th, th * 1.2)
            _box(acc, [(p[0] * ca - p[1] * sa + cx, p[0] * sa + p[1] * ca + cy,
                        p[2] + z0 + h * zf) for p in v], f, mat, col)
    return npst * 12 + (npst - 1) * 24


# --------------------------------------------------------------------------- #
#  ridge and furrow
# --------------------------------------------------------------------------- #
#  cross-section of one selion, as (offset in ridge widths, height factor)
RIDGE_SEC = ((-0.50, 0.0), (-0.30, 0.55), (-0.12, 0.94), (0.0, 1.0),
             (0.12, 0.94), (0.30, 0.55), (0.50, 0.0))


def furrow_mesh(LS, ang, x0, y0, w, d, period, amp, rng, col_lo, col_hi,
                along=(0.0, 1.0)):
    """Real ridge-and-furrow geometry over a field footprint.

    The footprint is given in the *field's* frame: origin (x0, y0), width w
    across the ridges, depth d along them, rotated by `ang`.  Each ridge is a
    strip of 6 quads, independent of its length, so a 120 m selion costs the
    same as a 20 m one.

    Returns (verts, faces, cols) ready for `acc.add`, or None.
    """
    if w < period * 1.5 or d < 3.0:
        return None
    nr = int(w / period)
    if nr < 1:
        return None
    cs, sn = math.cos(ang), math.sin(ang)
    sec = RIDGE_SEC
    nsx = len(sec)
    nseg = 2
    V = []
    C = []
    for r in range(nr):
        u0 = -0.5 * w + r * period
        for q in range(nseg + 1):
            t = q / float(nseg)
            # a slight bow along the ridge so the selion is not a ruler
            bow = (0.06 * period) * math.sin(t * 3.1 + r * 0.7)
            for (uo, hf) in sec:
                u = u0 + uo * period + bow
                v = (t - 0.5) * d
                hh = amp * hf
                # the ridge dips and rises a little along its length
                hh *= 1.0 + 0.22 * math.sin(t * 5.3 + r * 1.9)
                V.append((u, v, hh))
                k = 0.5 + 0.5 * hf
                C.append((col_lo[0] + (col_hi[0] - col_lo[0]) * k,
                          col_lo[1] + (col_hi[1] - col_lo[1]) * k,
                          col_lo[2] + (col_hi[2] - col_lo[2]) * k))
    F = []
    for r in range(nr):
        for q in range(nseg):
            b = (r * (nseg + 1) + q) * nsx
            b2 = (r * (nseg + 1) + q + 1) * nsx
            for s in range(nsx - 1):
                F.append((b + s, b + s + 1, b2 + s + 1))
                F.append((b + s, b2 + s + 1, b2 + s))
    # rotate into world space and place
    Vw = []
    for (u, v, z) in V:
        Vw.append((x0 + u * cs - v * sn, y0 + u * sn + v * cs, z))
    return Vw, F, C


