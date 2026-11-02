"""hd_landscape_props -- the small stuff in the near belt.

Everything here is 0.5-5 m across and exists to answer one question at eye
level: *who works this land?*  A wall of hedge and a painted field is scenery;
a cart with its shafts down, a rick on a staddle stone and a row of skeps is a
farm.

All props take (LS, acc, x, y, z, rng, mat, ...).  `z=None` means "sample the
ground yourself".  Faces come out as triangles so every accumulator stays
uniform arity and `mk_obj` keeps its foreach_set fast path.
"""
import math

import numpy as np

from hd_landscape_geo import _box, _triF, tq                      # noqa: F401


def _gzz(LS, x, y):
    return float(LS._gz(np.array([x], dtype=np.float64),
                        np.array([y], dtype=np.float64))[0])


# --------------------------------------------------------------------------- #
#  fodder and fuel
# --------------------------------------------------------------------------- #
def hayrick(LS, acc, x, y, z, rng, mat, w=3.6, h=4.2, cap=None):
    """A round hayrick, conical, thatched, a pole through the middle."""
    if z is None:
        z = _gzz(LS, x, y)
    # straw at 0.46 linear is bone white under this sun, so ricks are pulled
    # down to something closer to the albedo of old hay
    col = (0.29, 0.22, 0.11)
    seg = 7
    V = []
    for i, (zf, rf) in enumerate(((0.0, 0.88), (0.34, 1.0), (0.78, 0.90),
                                  (1.0, 0.52))):
        for k in range(seg):
            a = 2.0 * math.pi * k / seg + i * 0.2
            j = 0.92 + 0.16 * rng.random()
            V.append((x + rf * w * 0.5 * j * math.cos(a),
                      y + rf * w * 0.5 * j * math.sin(a), z + h * zf))
    F = []
    for i in range(3):
        for k in range(seg):
            a = i * seg + k
            b = i * seg + (k + 1) % seg
            c = (i + 1) * seg + (k + 1) % seg
            d = (i + 1) * seg + k
            F.append((a, b, c, d))
    tip = len(V)
    V.append((x, y, z + h * 1.10))
    for k in range(seg):
        F.append((3 * seg + k, 3 * seg + (k + 1) % seg, tip))
    acc.add(V, _triF(F), cap or mat, col=col)
    pv, pf = LS.boxv(None, 0.09, 0.09, h * 1.32)
    _box(acc, [(p[0] + x, p[1] + y, p[2] + z + h * 0.66) for p in pv], pf,
         cap or mat, (0.19, 0.14, 0.08))


def haystack(LS, acc, x, y, z, rng, mat, w=7.0, d=3.4, h=3.8, ang=0.0):
    """A long stack under a thatched ridge -- the shape of a barn roof, in hay."""
    if z is None:
        z = _gzz(LS, x, y)
    cs, sn = math.cos(ang), math.sin(ang)
    col = (0.28, 0.21, 0.10)

    def W(p):
        return (x + p[0] * cs - p[1] * sn, y + p[0] * sn + p[1] * cs, z + p[2])

    lv = []
    for zf, sy in ((0.0, d * 0.5), (0.52, d * 0.5), (0.86, d * 0.30),
                   (1.0, 0.0)):
        for (su, sv) in ((-w * 0.5, -sy), (w * 0.5, -sy),
                         (w * 0.5, sy), (-w * 0.5, sy)):
            lv.append((su, sv, h * zf))
    F = []
    for i in range(3):
        for k in range(4):
            a = i * 4 + k
            b = i * 4 + (k + 1) % 4
            c = (i + 1) * 4 + (k + 1) % 4
            d2 = (i + 1) * 4 + k
            if i == 2 and k in (0, 3):
                continue
            F.append((a, b, c, d2))
    for k in range(4):
        F.append((k, 4 + k, 4 + (k + 1) % 4, (k + 1) % 4))
    acc.add([W(p) for p in lv], _triF(F), mat, col=col)


def woodpile(LS, acc, x, y, z, rng, mat, w=4.2, d=1.9, h=1.5, ang=0.0):
    """A cord of split logs, stacked end on: from the side, a wall of circles."""
    if z is None:
        z = _gzz(LS, x, y)
    cs, sn = math.cos(ang), math.sin(ang)
    col = (0.34, 0.24, 0.14)
    r = 0.115
    nl = max(1, int(w / (2.0 * r) * 0.86))
    nrow = max(1, int(h / (2.0 * r) * 0.86))
    V = []
    F = []
    seg = 6
    for row in range(nrow):
        for k in range(nl):
            u = -w * 0.5 + r + k * 2.0 * r
            zz = r + row * 2.0 * r * 0.90
            side = ((k + row) % 3 - 1) * 0.10
            i0 = len(V)
            for s2 in range(seg):
                a = 2.0 * math.pi * s2 / seg
                V.append((u + r * math.cos(a), side, zz + r * math.sin(a)))
            for s2 in range(seg):
                a = 2.0 * math.pi * s2 / seg
                V.append((u + r * math.cos(a), side + d, zz + r * math.sin(a)))
            for s2 in range(seg):
                F.append((i0 + s2, i0 + (s2 + 1) % seg,
                          i0 + seg + (s2 + 1) % seg, i0 + seg + s2))
            for s2 in range(1, seg - 1):
                F.append((i0, i0 + s2, i0 + s2 + 1))
                F.append((i0 + seg, i0 + seg + s2 + 1, i0 + seg + s2))
    Vw = [(x + p[0] * cs - p[1] * sn, y + p[0] * sn + p[1] * cs, z + p[2])
          for p in V]
    acc.add(Vw, _triF(F), mat, col=col)


def compost_heap(LS, acc, x, y, z, rng, mat, r=3.0, h=1.5):
    """A dung heap: a lumpy dome, the same dark colour as ploughed soil."""
    if z is None:
        z = _gzz(LS, x, y)
    col = (0.27, 0.20, 0.10)
    seg = 11
    V = [(x, y, z + h)]
    F = []
    for i, rf in enumerate((0.52, 0.90, 1.0)):
        for k in range(seg):
            a = 2.0 * math.pi * k / seg + i * 0.15
            j = 0.90 + 0.18 * rng.random()
            V.append((x + r * rf * j * math.cos(a),
                      y + r * rf * j * math.sin(a),
                      z + h * (0.74 - 0.31 * i)))
    for k in range(seg):
        F.append((0, 1 + k, 1 + (k + 1) % seg))
    for i in range(2):
        for k in range(seg):
            a = 1 + i * seg + k
            b = 1 + i * seg + (k + 1) % seg
            c = 1 + (i + 1) * seg + (k + 1) % seg
            d = 1 + (i + 1) * seg + k
            F.append((a, b, c, d))
    acc.add(V, _triF(F), mat, col=col)


def charcoal_clamp(LS, acc, x, y, z, rng, mat, r=3.4):
    """A charcoal clamp: a turf covered dome of stacked wood under a pole."""
    if z is None:
        z = _gzz(LS, x, y)
    col = (0.17, 0.15, 0.12)
    seg = 9
    V = [(x, y, z + r * 0.80)]
    F = []
    for i, (zf, rf) in enumerate(((0.30, 0.62), (0.66, 0.95), (0.94, 1.0))):
        for k in range(seg):
            a = 2.0 * math.pi * k / seg + i * 0.3
            j = 0.92 + 0.14 * rng.random()
            V.append((x + r * rf * j * math.cos(a),
                      y + r * rf * j * math.sin(a), z + r * 0.80 * zf))
    for k in range(seg):
        F.append((0, 1 + k, 1 + (k + 1) % seg))
    for i in range(2):
        for k in range(seg):
            a = 1 + i * seg + k
            b = 1 + i * seg + (k + 1) % seg
            c = 1 + (i + 1) * seg + (k + 1) % seg
            d = 1 + (i + 1) * seg + k
            F.append((a, b, c, d))
    acc.add(V, _triF(F), mat, col=col)
    pv, pf = LS.boxv(None, 0.10, 0.10, r * 1.4)
    _box(acc, [(p[0] + x, p[1] + y, p[2] + z + r * 0.7) for p in pv], pf,
         mat, (0.20, 0.15, 0.09))


# --------------------------------------------------------------------------- #
#  the working kit
# --------------------------------------------------------------------------- #
def beehives(LS, acc, x, y, z, rng, mat, n=6, ang=0.0):
    """A row of straw skeps on a low bench: the clearest read of a garden."""
    cs, sn = math.cos(ang), math.sin(ang)
    col = (0.28, 0.21, 0.08)
    for k in range(n):
        u = (k - (n - 1) * 0.5) * 1.30
        xx, yy = x + u * cs, y + u * sn
        zz = _gzz(LS, xx, yy) if z is None else z
        V = []
        for i, (zf, rf) in enumerate(((0.0, 0.46), (0.32, 0.52), (0.68, 0.42),
                                      (0.94, 0.20))):
            for s2 in range(6):
                a = 2.0 * math.pi * s2 / 6 + i * 0.22
                V.append((xx + rf * math.cos(a), yy + rf * math.sin(a),
                          zz + 0.66 * zf))
        F = []
        for i in range(3):
            for s2 in range(6):
                a = i * 6 + s2
                b = i * 6 + (s2 + 1) % 6
                c = (i + 1) * 6 + (s2 + 1) % 6
                d = (i + 1) * 6 + s2
                F.append((a, b, c, d))
        acc.add(V, _triF(F), mat, col=col)


def cart(LS, acc, x, y, z, rng, mat, ang=0.0, scale=1.0):
    """A two wheeled cart with its shafts down."""
    if z is None:
        z = _gzz(LS, x, y)
    cs, sn = math.cos(ang), math.sin(ang)
    col = (0.24, 0.17, 0.09)

    def W(p):
        return (x + p[0] * cs - p[1] * sn, y + p[0] * sn + p[1] * cs, z + p[2])

    bv, bf = LS.boxv(None, 2.5 * scale, 1.4 * scale, 0.52 * scale)
    _box(acc, [W((p[0], p[1], p[2] + 0.60 * scale)) for p in bv], bf, mat, col)
    for side in (-1.0, 1.0):
        cx = side * 0.76 * scale
        V = []
        seg = 10
        for s2 in range(seg):
            a = 2.0 * math.pi * s2 / seg
            V.append((cx, 0.68 * scale * math.cos(a),
                      0.56 * scale + 0.68 * scale * math.sin(a)))
            V.append((cx + 0.10 * scale, 0.68 * scale * math.cos(a),
                      0.56 * scale + 0.68 * scale * math.sin(a)))
        F = []
        for s2 in range(seg):
            a = 2 * s2
            b = 2 * ((s2 + 1) % seg)
            F.append((a, a + 1, b + 1, b))
        acc.add([W(p) for p in V], _triF(F), mat, col=col)
    # shafts
    for side in (-1.0, 1.0):
        v, f = LS.boxv(None, 3.2 * scale, 0.10, 0.10)
        _box(acc, [W((p[0] + 2.6 * scale, p[1] + side * 0.48 * scale,
                      p[2] + 0.44 * scale)) for p in v], f, mat, col)


def plough_rest(LS, acc, x, y, z, rng, mat, ang=0.0):
    """A plough left at the headland, beam up: a signature of a ploughed field."""
    if z is None:
        z = _gzz(LS, x, y)
    cs, sn = math.cos(ang), math.sin(ang)
    col = (0.22, 0.15, 0.08)

    def W(p):
        return (x + p[0] * cs - p[1] * sn, y + p[0] * sn + p[1] * cs, z + p[2])

    v, f = LS.boxv(None, 2.2, 0.14, 0.14)
    _box(acc, [W((p[0], p[1], p[2] + 0.46)) for p in v], f, mat, col)
    v, f = LS.boxv(None, 0.16, 0.16, 0.9)
    _box(acc, [W((p[0] - 0.9, p[1], p[2] + 0.45)) for p in v], f, mat, col)
    V = [(0.55, 0.0, 0.30), (0.55, 0.0, 0.60), (1.05, 0.0, 0.34),
         (0.98, -0.24, 0.42), (0.98, 0.24, 0.42), (0.86, 0.0, 0.20)]
    F = [(0, 1, 2), (0, 3, 1), (0, 1, 4), (0, 2, 3), (0, 4, 2), (1, 3, 5),
         (1, 5, 4), (2, 4, 5), (2, 5, 3)]
    acc.add([W(p) for p in V], _triF(F), mat, col=(0.26, 0.26, 0.25))


def sheep_fold(LS, acc, x, y, z, rng, mat, r=11.0, n=9):
    """A hurdle fold: a ring of hurdles, one side left open, plus a trough."""
    col = (0.20, 0.14, 0.08)
    for k in range(n):
        if k == 0:
            continue
        a0 = 2.0 * math.pi * k / n
        a1 = 2.0 * math.pi * (k + 1) / n
        x0 = x + r * math.cos(a0)
        y0 = y + r * math.sin(a0)
        x1 = x + r * math.cos(a1)
        y1 = y + r * math.sin(a1)
        zz = LS._gz(np.array([x0, x1]), np.array([y0, y1]))
        L = math.hypot(x1 - x0, y1 - y0)
        ang = math.atan2(y1 - y0, x1 - x0)
        ca, sa = math.cos(ang), math.sin(ang)
        for zf in (0.34, 0.66, 0.95):
            v, f = LS.boxv(None, L, 0.055, 0.10)
            _box(acc, [(p[0] * ca - p[1] * sa + 0.5 * (x0 + x1),
                        p[0] * sa + p[1] * ca + 0.5 * (y0 + y1),
                        p[2] + 0.5 * (zz[0] + zz[1]) + zf) for p in v],
                 f, mat, col)
        v, f = LS.boxv(None, 0.13, 0.13, 1.25)
        _box(acc, [(p[0] + x0, p[1] + y0, p[2] + zz[0] + 0.55) for p in v],
             f, mat, col)


def trough(LS, acc, x, y, z, rng, mat, L=2.4, ang=0.0):
    """A hollowed stone trough: four sides and a bottom, no top."""
    if z is None:
        z = _gzz(LS, x, y)
    cs, sn = math.cos(ang), math.sin(ang)
    col = (0.40, 0.39, 0.36)

    def W(p):
        return (x + p[0] * cs - p[1] * sn, y + p[0] * sn + p[1] * cs, z + p[2])

    for (dx, dy, sx, sy) in ((0.0, 0.34, L, 0.16), (0.0, -0.34, L, 0.16),
                             (L * 0.5, 0.0, 0.16, 0.84),
                             (-L * 0.5, 0.0, 0.16, 0.84)):
        v, f = LS.boxv(None, sx, sy, 0.58)
        _box(acc, [W((p[0] + dx, p[1] + dy, p[2] + 0.29)) for p in v],
             f, mat, col)
    v, f = LS.boxv(None, L, 0.82, 0.10)
    _box(acc, [W((p[0], p[1], p[2] + 0.05)) for p in v], f, mat, col)


def well(LS, acc, x, y, z, rng, mat, r=1.15, h=2.6):
    """A well head: a ring of stone, two posts, a windlass and a little roof."""
    if z is None:
        z = _gzz(LS, x, y)
    stone = (0.44, 0.43, 0.40)
    wood = (0.22, 0.15, 0.09)
    seg = 9
    V = []
    F = []
    for i, (zf, rf) in enumerate(((0.0, 1.0), (0.72, 0.96), (0.92, 0.88))):
        for k in range(seg):
            a = 2.0 * math.pi * k / seg
            V.append((x + r * rf * math.cos(a), y + r * rf * math.sin(a),
                      z + h * 0.34 * zf / 0.92))
    for i in range(2):
        for k in range(seg):
            a = i * seg + k
            b = i * seg + (k + 1) % seg
            c = (i + 1) * seg + (k + 1) % seg
            d = (i + 1) * seg + k
            F.append((a, b, c, d))
    acc.add(V, _triF(F), mat, col=stone)
    for sx in (-1.0, 1.0):
        v, f = LS.boxv(None, 0.16, 0.16, h)
        _box(acc, [(p[0] + x + sx * r * 0.86, p[1] + y, p[2] + z + h * 0.5)
                   for p in v], f, mat, wood)
    v, f = LS.boxv(None, 2.1, 0.13, 0.13)
    _box(acc, [(p[0] + x, p[1] + y, p[2] + z + h * 0.92) for p in v], f, mat,
         wood)
    for sx in (-1.0, 1.0):
        V2 = []
        for (u, w2, zz) in ((-1.4, 1.5, 0.0), (1.4, 1.5, 0.0), (0.0, 0.0, 0.9)):
            V2.append((x + u * 0.42, y + sx * w2, z + h + zz))
        acc.tri(V2[0], V2[1], V2[2], mat, (0.34, 0.22, 0.12))


def garden_beds(LS, acc, x, y, z, rng, mat, w=17.0, d=12.0, ang=0.0):
    """Raised vegetable beds between paths: the backbone of a cottage garden."""
    if z is None:
        z = _gzz(LS, x, y)
    cs, sn = math.cos(ang), math.sin(ang)
    col = (0.26, 0.20, 0.11)
    col2 = (0.20, 0.24, 0.10)
    nb = max(2, int(w / 1.7))
    for i in range(nb):
        u = -w * 0.5 + 0.55 + i * 1.7
        bv = []
        for zz in (0.0, 0.16):
            for (su, sv) in ((-0.62, -d * 0.5), (0.62, -d * 0.5),
                             (0.62, d * 0.5), (-0.62, d * 0.5)):
                bv.append((x + (u + su) * cs - sv * sn,
                           y + (u + su) * sn + sv * cs,
                           z + zz + (rng.random() - 0.5) * 0.03))
        F = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
             (4, 5, 6, 7)]
        acc.add(bv, _triF(F), mat, col=col2 if i % 2 else col)


def wood_lathe(LS, acc, x, y, z, rng, mat, r=4.0):
    """A saw pit with baulks rolled out beside it: the logging camp."""
    if z is None:
        z = _gzz(LS, x, y)
    col = (0.30, 0.21, 0.12)
    for i in range(3):
        a = 2.0 * math.pi * i / 3 + 0.4
        cx = x + math.cos(a) * r * 0.55
        cy = y + math.sin(a) * r * 0.55
        zz = _gzz(LS, cx, cy)
        v, f = LS.boxv(None, 5.4, 0.52, 0.52)
        _box(acc, [(p[0] * math.cos(a) - p[1] * math.sin(a) + cx,
                    p[0] * math.sin(a) + p[1] * math.cos(a) + cy,
                    p[2] + zz + 0.26 + (i % 2) * 0.10) for p in v], f, mat, col)


def gate(LS, acc, x, y, z, ang, w, h, rng, mat, col=(0.24, 0.17, 0.09)):
    """A five bar gate hung on a post: it closes a hedge gap and says so."""
    if z is None:
        z = _gzz(LS, x, y)
    cs, sn = math.cos(ang), math.sin(ang)

    def W(p):
        return (x + p[0] * cs - p[1] * sn, y + p[0] * sn + p[1] * cs, z + p[2])

    v, f = LS.boxv(None, 0.18, 0.18, h + 0.45)
    _box(acc, [W((p[0], p[1], p[2] + (h + 0.45) * 0.5 - 0.15)) for p in v],
         f, mat, col)
    for i in range(5):
        zf = 0.18 + (h - 0.18) * i / 4.0
        v, f = LS.boxv(None, w - 0.2, 0.09, 0.11)
        _box(acc, [W((p[0] + (w - 0.2) * 0.5, 0.0, p[2] + zf)) for p in v],
             f, mat, col)
    v, f = LS.boxv(None, 0.09, 0.09, h * 1.16)
    _box(acc, [W((p[0] + w * 0.5, 0.0, p[2] + h * 0.42)) for p in v],
         f, mat, col)


def ruts(LS, acc, P, w=2.9, col=(0.30, 0.24, 0.15), lift=0.055, step=8.0,
         mat=None):
    """Two wheel ruts and a crown of grass down a farm track.

    Carriage ruts are 1.4-1.5 m apart and 0.1-0.2 m deep, and they survive in
    the ground for decades -- the single cheapest sign that a road is used.
    """
    if mat is None:
        mat = LS.GBL.get("track_land")
    Q = np.asarray(P, dtype=np.float64)
    if len(Q) < 2:
        return 0
    seg = np.hypot(np.diff(Q[:, 0]), np.diff(Q[:, 1]))
    L = float(seg.sum())
    if L < 6.0:
        return 0
    ns = max(2, int(L / step) + 1)
    tt = np.concatenate([[0.0], np.cumsum(seg)]) / max(1e-6, L)
    ts = np.linspace(0.0, 1.0, ns)
    px = np.interp(ts, tt, Q[:, 0])
    py = np.interp(ts, tt, Q[:, 1])
    zs = LS._gz(px, py)
    dx = np.gradient(px)
    dy = np.gradient(py)
    dl = np.hypot(dx, dy) + 1e-9
    nx, ny = -dy / dl, dx / dl
    n = 0
    for side in (-1.0, 1.0):
        u = side * w * 0.5 * 0.52
        for k in range(ns - 1):
            a0 = (px[k] + nx[k] * (u - 0.20), py[k] + ny[k] * (u - 0.20),
                  zs[k] + lift - 0.045)
            b0 = (px[k] + nx[k] * (u + 0.20), py[k] + ny[k] * (u + 0.20),
                  zs[k] + lift - 0.045)
            a1 = (px[k + 1] + nx[k + 1] * (u - 0.20),
                  py[k + 1] + ny[k + 1] * (u - 0.20), zs[k + 1] + lift - 0.045)
            b1 = (px[k + 1] + nx[k + 1] * (u + 0.20),
                  py[k + 1] + ny[k + 1] * (u + 0.20), zs[k + 1] + lift - 0.045)
            acc.quad(a0, b0, b1, a1, mat, tuple(c * 0.66 for c in col))
            n += 2
    return n
