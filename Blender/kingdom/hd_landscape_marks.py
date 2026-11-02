"""Mid-distance landmarks: the story points you can pick out from the walls.

A city seen from its own battlements needs things to look *at* -- a windmill on
the ridge, a broken abbey in the trees, a ferry plying the river, a gallows
where the roads meet.  Without them the middle distance is a green slope with
invisible detail.  Eleven pieces, spread from 1.4 km to 3.2 km, each on ground
chosen for its silhouette rather than at random.
"""

import math

import numpy as np

import hd_landscape_geo as G

TAU = math.pi * 2.0


def _m(LS, key):
    m = LS.GBL.get(key + "_land")
    if m is not None:
        return m
    m = LS.GBL.get(key)
    if m is not None:
        return m
    return LS._get_mat(getattr(LS, "_MAT", None), key)


def _slash(LS, acc, p, q, th, mat, col):
    """A flat vertical strip from p to q, `th` thick, as two triangles."""
    dx = q[0] - p[0]
    dy = q[1] - p[1]
    dl = math.hypot(dx, dy) + 1e-9
    nx, ny = -dy / dl * th * 0.5, dx / dl * th * 0.5
    G.tq(acc, (p[0] - nx, p[1] - ny, p[2]), (q[0] - nx, q[1] - ny, q[2]),
         (q[0] + nx, q[1] + ny, q[2]), (p[0] + nx, p[1] + ny, p[2]), mat, col)


def _wall(LS, acc, x, y, ang, w, d, h, mat, col, rng, breach=0.30):
    """A ruined rectangular enclosure: four runs, some dropped to knee height."""
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hd = w * 0.5, d * 0.5
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    for k in range(4):
        a = corners[k]
        b = corners[(k + 1) % 4]
        nseg = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 4.0))
        for s in range(nseg):
            t0 = s / float(nseg)
            t1 = (s + 1) / float(nseg)
            if rng.random() < breach * 0.35:
                continue
            hh = h * rng.uniform(0.18, 1.0)
            if rng.random() < breach:
                hh = h * rng.uniform(0.10, 0.30)
            u0 = a[0] + (b[0] - a[0]) * t0
            v0 = a[1] + (b[1] - a[1]) * t0
            u1 = a[0] + (b[0] - a[0]) * t1
            v1 = a[1] + (b[1] - a[1]) * t1
            p0 = (x + u0 * ca - v0 * sa, y + u0 * sa + v0 * ca,
                  float(LS._gz(x + u0 * ca - v0 * sa, y + u0 * sa + v0 * ca)))
            p1 = (x + u1 * ca - v1 * sa, y + u1 * sa + v1 * ca,
                  float(LS._gz(x + u1 * ca - v1 * sa, y + u1 * sa + v1 * ca)))
            c = tuple(v * rng.uniform(0.84, 1.08) for v in col)
            _slash(LS, acc, p0, p1, 0.62, mat, c)
            # the same run at height, so the wall has a face and a top
            G.tq(acc, (p0[0], p0[1], p0[2]), (p1[0], p1[1], p1[2]),
                 (p1[0], p1[1], p1[2] + hh), (p0[0], p0[1], p0[2] + hh), mat, c)
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            dl = math.hypot(dx, dy) + 1e-9
            nx, ny = -dy / dl * 0.31, dx / dl * 0.31
            G.tq(acc, (p0[0] - nx, p0[1] - ny, p0[2] + hh),
                 (p1[0] - nx, p1[1] - ny, p1[2] + hh),
                 (p1[0] + nx, p1[1] + ny, p1[2] + hh),
                 (p0[0] + nx, p0[1] + ny, p0[2] + hh), mat,
                 tuple(v * 0.88 for v in c))


def _arch(LS, acc, x, y, ang, span, h, mat, col, rng):
    """A standing pointed arch: eleven blocks around the opening."""
    ca, sa = math.cos(ang), math.sin(ang)
    z0 = float(LS._gz(x, y))
    n = 11
    for k in range(n):
        a0 = math.pi * k / n
        a1 = math.pi * (k + 1) / n
        r = span * 0.5
        p0 = (x + r * math.cos(a0) * ca - 0.0, y + r * math.cos(a0) * sa, z0)
        p1 = (x + r * math.cos(a1) * ca, y + r * math.cos(a1) * sa, z0)
        _slash(LS, acc, (p0[0], p0[1], z0 + h),
               (p1[0], p1[1], z0 + h + math.sin(a1) * span * 0.42),
               0.66, mat, tuple(v * rng.uniform(0.86, 1.06) for v in col))
        G.tq(acc, (p0[0], p0[1], z0),
             (p1[0], p1[1], z0),
             (p1[0], p1[1], z0 + h),
             (p0[0], p0[1], z0 + h), mat, col)
    for s in (-1.0, 1.0):
        p = (x + s * span * 0.5 * ca, y + s * span * 0.5 * sa, z0)
        V, F = LS.boxv(None, 1.5, 1.0, h, z0=0.0)
        acc.add(V, G._triF(F), mat,
                T=(LS.Matrix.Translation((p[0], p[1], z0))
                   @ LS.Matrix.Rotation(ang, 4, 'Z')),
                col=col)


def _monolith(LS, acc, x, y, w, h, t, ang, mat, col, rng, lean=0.0):
    z = float(LS._gz(x, y))
    V, F = LS.boxv(None, w, t, h, z0=0.0)
    T = (LS.Matrix.Translation((x, y, z))
         @ LS.Matrix.Rotation(ang + lean, 4, 'Z'))
    acc.add(V, G._triF(F), mat, T=T,
            col=tuple(v * rng.uniform(0.8, 1.12) for v in col))


def _round_tower(LS, acc, x, y, r, h, seg, mat, col, rng, broken=0.45):
    z = float(LS._gz(x, y))
    top = []
    for k in range(seg):
        a = TAU * k / seg
        hh = h * (1.0 - broken * rng.random())
        top.append((x + r * math.cos(a), y + r * math.sin(a), z + hh))
    base = [(x + r * math.cos(TAU * k / seg), y + r * math.sin(TAU * k / seg),
             z - 1.0) for k in range(seg)]
    for k in range(seg):
        k1 = (k + 1) % seg
        c = tuple(v * rng.uniform(0.85, 1.08) for v in col)
        G.tq(acc, base[k], base[k1], top[k1], top[k], mat, c)
    return top


def _sails(LS, acc, x, y, z, r, mat, col):
    """Four lattice sails on a hub, the signature of a windmill."""
    hub = (x, y, z)
    for k in range(4):
        a = TAU * k / 4.0 + 0.22
        ca, sa = math.cos(a), math.sin(a)
        tip = (x + r * ca, y + r * sa, z)
        for s in (-1.0, 1.0):
            off = (s * 0.9 * sa, -s * 0.9 * ca)
            G.tq(acc, (hub[0], hub[1], hub[2]),
                 (tip[0] + off[0] * 0.6, tip[1] + off[1] * 0.6, tip[2]),
                 (tip[0] + off[0], tip[1] + off[1], tip[2] - 1.1),
                 (hub[0] + off[0] * 0.25, hub[1] + off[1] * 0.25, hub[2] - 0.3),
                 mat, col)


# --------------------------------------------------------------------------- #
#  the pieces
# --------------------------------------------------------------------------- #
def stone_circle(LS, acc, x, y, mat, rng):
    col = tuple(LS.rgb("wall2") * 0.92)
    z = float(LS._gz(x, y))
    n = 13
    R = 9.5
    for k in range(n):
        a = TAU * k / n + 0.13
        px = x + R * math.cos(a)
        py = y + R * math.sin(a)
        if k == 5:
            _monolith(LS, acc, px + 2.4, py + 1.0, 1.5, 0.8, 0.9, a, mat, col,
                      rng, lean=1.45)
            continue
        _monolith(LS, acc, px, py, rng.uniform(1.1, 1.7),
                  rng.uniform(2.4, 4.4), rng.uniform(0.55, 0.9), a, mat, col,
                  rng, lean=rng.uniform(-0.16, 0.16))
    _monolith(LS, acc, x + 0.6, y - 0.4, 2.2, 0.75, 1.3, 0.4, mat, col, rng)
    for k in range(7):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(1.0, 8.0)
        _monolith(LS, acc, x + rr * math.cos(a), y + rr * math.sin(a),
                  rng.uniform(0.5, 1.1), rng.uniform(0.3, 0.7), 0.5, a, mat,
                  col, rng, lean=rng.uniform(0.9, 1.57))
    return z


def abbey(LS, acc, x, y, ang, mat, mat_r, rng):
    col = tuple(LS.rgb("wall") * 0.90)
    z = float(LS._gz(x, y))
    _wall(LS, acc, x, y, ang, 44.0, 21.0, 7.5, mat, col, rng, breach=0.34)
    ca, sa = math.cos(ang), math.sin(ang)
    # nave: two arcades of arches down the middle
    for k in range(4):
        u = -15.0 + k * 10.0
        _arch(LS, acc, x + u * ca - 3.0 * sa, y + u * sa + 3.0 * ca,
              ang + math.pi * 0.5, 5.2, 3.0, mat, col, rng)
        _arch(LS, acc, x + u * ca + 3.0 * sa, y + u * sa - 3.0 * ca,
              ang + math.pi * 0.5, 5.2, 3.0, mat, col, rng)
    # west gable fragment and the tower stump
    _round_tower(LS, acc, x - 17.0 * ca - 6.0 * sa, y - 17.0 * sa + 6.0 * ca,
                 3.4, 13.0, 9, mat, col, rng, broken=0.62)
    for k in range(9):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(3.0, 20.0)
        px = x + rr * math.cos(a)
        py = y + rr * math.sin(a)
        sz = rng.uniform(0.4, 1.4)
        V, F = LS.boxv(None, sz, sz * rng.uniform(0.6, 1.3), sz * 0.5, z0=0.0)
        acc.add(V, G._triF(F), mat,
                T=LS.Matrix.Translation((px, py, float(LS._gz(px, py)))),
                col=tuple(LS.rgb("wall2") * rng.uniform(0.72, 1.0)))
    return z


def windmill(LS, acc, x, y, ang, mat, mat_r, rng):
    col = tuple(LS.rgb("plaster") * 1.0)
    z = float(LS._gz(x, y))
    h = 11.0
    # tapered tower
    seg = 10
    for k in range(seg):
        a0 = TAU * k / seg
        a1 = TAU * (k + 1) / seg
        b0 = (x + 3.5 * math.cos(a0), y + 3.5 * math.sin(a0), z)
        b1 = (x + 3.5 * math.cos(a1), y + 3.5 * math.sin(a1), z)
        t0 = (x + 2.3 * math.cos(a0), y + 2.3 * math.sin(a0), z + h)
        t1 = (x + 2.3 * math.cos(a1), y + 2.3 * math.sin(a1), z + h)
        G.tq(acc, b0, b1, t1, t0, mat,
             tuple(v * rng.uniform(0.92, 1.05) for v in col))
    for k in range(seg):
        a0 = TAU * k / seg
        a1 = TAU * (k + 1) / seg
        p0 = (x + 2.5 * math.cos(a0), y + 2.5 * math.sin(a0), z + h)
        p1 = (x + 2.5 * math.cos(a1), y + 2.5 * math.sin(a1), z + h)
        G.tq(acc, p0, p1, (x, y, z + h + 2.6), (x, y, z + h + 2.6), mat_r,
             tuple(LS.rgb("thatchc") * 0.92))
    _sails(LS, acc, x + 2.9 * math.cos(ang), y + 2.9 * math.sin(ang),
           z + h - 1.4, 8.6, mat, tuple(LS.rgb("timber_d") * 0.86))
    return z


def beacon(LS, acc, x, y, mat, col, rng):
    z = float(LS._gz(x, y))
    _round_tower(LS, acc, x, y, 3.2, 8.4, 9, mat, col, rng, broken=0.30)
    # fire basket on the crown
    for k in range(8):
        a = TAU * k / 8.0
        G.tq(acc, (x + 2.8 * math.cos(a), y + 2.8 * math.sin(a), z + 8.4),
             (x + 2.8 * math.cos(a + 0.8), y + 2.8 * math.sin(a + 0.8), z + 8.4),
             (x + 1.4 * math.cos(a + 0.8), y + 1.4 * math.sin(a + 0.8), z + 10.6),
             (x + 1.4 * math.cos(a), y + 1.4 * math.sin(a), z + 10.6),
             mat, tuple(LS.rgb("timber_d") * (0.8 + 0.14 * (k % 2))))
    return z


def ferry(LS, acc, x, y, ang, wl, mat_w, mat_s, rng):
    """A jetty and a punt on the river, with a toll hut on the bank."""
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    for k in range(9):
        u = -6.0 + k * 1.5
        p = (x + u * ca, y + u * sa, wl + 0.5)
        for s in (-1.0, 1.0):
            q = (p[0] + s * 0.9 * sa, p[1] - s * 0.9 * ca, wl + 0.5)
            G.tq(acc, (p[0], p[1], wl - 0.6), (q[0], q[1], wl - 0.6),
                 (q[0], q[1], wl + 0.38), (p[0], p[1], wl + 0.38),
                 mat_w, tuple(LS.rgb("wood_dark") * rng.uniform(0.8, 1.06)))
    for k in range(4):
        u = -5.0 + k * 3.4
        p = (x + u * ca, y + u * sa, wl)
        for s in (-1.0, 1.0):
            G.tq(acc, (p[0] + s * 0.85 * sa, p[1] - s * 0.85 * ca, z - 1.0),
                 (p[0] + s * 0.85 * sa, p[1] - s * 0.85 * ca, wl + 0.5),
                 (p[0] + s * 0.85 * sa + 0.2 * ca,
                  p[1] - s * 0.85 * ca + 0.2 * sa, wl + 0.5),
                 (p[0] + s * 0.85 * sa + 0.2 * ca,
                  p[1] - s * 0.85 * ca + 0.2 * sa, z - 1.0),
                 mat_w, tuple(LS.rgb("wood_dark") * 0.82))
    # the punt, drawn up beside the jetty
    px = x + 3.0 * sa + 2.0 * ca
    py = y - 3.0 * ca + 2.0 * sa
    for k in range(6):
        u = -2.2 + k * 0.9
        G.tq(acc, (px + u * ca - 0.8 * sa, py + u * sa + 0.8 * ca, wl + 0.18),
             (px + u * ca + 0.8 * sa, py + u * sa - 0.8 * ca, wl + 0.18),
             (px + (u + 0.9) * ca + 0.8 * sa,
              py + (u + 0.9) * sa - 0.8 * ca, wl + 0.18),
             (px + (u + 0.9) * ca - 0.8 * sa,
              py + (u + 0.9) * sa + 0.8 * ca, wl + 0.18),
             mat_w, tuple(LS.rgb("wood_dark") * rng.uniform(0.76, 0.98)))
    _hut(LS, acc, x - 12.0 * ca, y - 12.0 * sa, ang, mat_w,
         tuple(LS.rgb("plaster") * 0.94), rng, w=3.6, d=3.0, h=2.4)
    return z


def _hut(LS, acc, x, y, ang, mat, col, rng, w=3.4, d=2.8, h=2.2):
    z = float(LS._gz(x, y))
    T = (LS.Matrix.Translation((x, y, z))
         @ LS.Matrix.Rotation(ang, 4, 'Z'))
    V, F = LS.boxv(None, w, d, h, z0=0.0)
    acc.add(V, G._triF(F), mat, T=T, col=col)
    V, F = LS.boxv(None, w + 0.6, d + 0.6, 0.22, z0=h)
    acc.add(V, G._triF(F), mat, T=T,
            col=tuple(LS.rgb("thatchc") * 0.9))
    return z


def gallows_hill(LS, acc, x, y, ang, mat_w, mat_s, rng):
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    # the mound, as a low ring of earth walls
    G.drystone(LS, acc,
               np.array([[x + 7.0 * ca - 7.0 * sa, y + 7.0 * sa + 7.0 * ca],
                         [x + 7.0 * ca + 7.0 * sa, y + 7.0 * sa - 7.0 * ca]]),
               0.7, 0.5, rng, tuple(LS.rgb("wall") * 0.9), mat_s, step=1.6)
    for k in range(3):
        a = TAU * k / 3.0 + 0.5
        px = x + 2.2 * math.cos(a)
        py = y + 2.2 * math.sin(a)
        V, F = LS.boxv(None, 0.42, 0.42, 4.4, z0=0.0)
        acc.add(V, G._triF(F), mat_w,
                T=LS.Matrix.Translation((px, py, z)),
                col=tuple(LS.rgb("timber_d") * 0.8))
    for k in range(3):
        a0 = TAU * k / 3.0 + 0.5
        a1 = TAU * (k + 1) / 3.0 + 0.5
        p0 = (x + 2.2 * math.cos(a0), y + 2.2 * math.sin(a0), z + 4.1)
        p1 = (x + 2.2 * math.cos(a1), y + 2.2 * math.sin(a1), z + 4.1)
        p2 = (x, y, z + 5.6)
        acc.tri(p0, p1, p2, mat_w, tuple(LS.rgb("timber_d") * 0.84))
        acc.tri(p0, p1, (p0[0], p0[1], z + 3.6), mat_w,
                tuple(LS.rgb("timber_d") * 0.8))
    for k in range(4):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(8.0, 15.0)
        _monolith(LS, acc, x + rr * math.cos(a), y + rr * math.sin(a), 0.9,
                  1.2, 0.4, a, mat_s, tuple(LS.rgb("wall2") * 0.86), rng,
                  lean=rng.uniform(-0.3, 0.3))
    return z


def charcoal_camp(LS, acc, x, y, mat_w, mat_e, rng):
    import hd_landscape_props as PR
    z = float(LS._gz(x, y))
    for k in range(3):
        a = TAU * k / 3.0 + 0.4
        rr = rng.uniform(9.0, 15.0)
        PR.charcoal_clamp(LS, acc, x + rr * math.cos(a), y + rr * math.sin(a),
                          None, rng, mat_e, r=rng.uniform(3.0, 4.2))
    _hut(LS, acc, x, y, rng.uniform(0, TAU), mat_w,
         tuple(LS.rgb("timber") * 0.9), rng, w=3.8, d=3.2, h=2.1)
    for k in range(4):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(2.0, 7.0)
        PR.woodpile(LS, acc, x + rr * math.cos(a), y + rr * math.sin(a), None,
                    rng, mat_w, w=rng.uniform(2.2, 3.2), h=1.0)
    return z


def hermitage(LS, acc, x, y, ang, mat_s, mat_w, rng):
    col = tuple(LS.rgb("wall") * 0.84)
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    # a rock face with a doorway cut into it
    for k in range(7):
        u = -6.0 + k * 1.9
        hh = rng.uniform(2.6, 5.4)
        p0 = (x + u * ca - 2.4 * sa, y + u * sa + 2.4 * ca, z)
        p1 = (x + (u + 1.9) * ca - 2.4 * sa, y + (u + 1.9) * sa + 2.4 * ca, z)
        G.tq(acc, p0, p1, (p1[0], p1[1], p1[2] + hh),
             (p0[0], p0[1], p0[2] + hh * 0.92), mat_s,
             tuple(v * rng.uniform(0.82, 1.1) for v in col))
    # the doorway
    d0 = (x - 1.0 * ca - 2.2 * sa, y - 1.0 * sa + 2.2 * ca, z)
    d1 = (x + 1.0 * ca - 2.2 * sa, y + 1.0 * sa + 2.2 * ca, z)
    G.tq(acc, d0, d1, (d1[0], d1[1], d1[2] + 2.0), (d0[0], d0[1], d0[2] + 2.0),
         mat_w, (0.03, 0.03, 0.04))
    # shrine: a stone cross on a plinth
    cx = x + 4.0 * ca + 4.0 * sa
    cy = y + 4.0 * sa - 4.0 * ca
    zz = float(LS._gz(cx, cy))
    V, F = LS.boxv(None, 1.4, 1.4, 0.6, z0=0.0)
    acc.add(V, G._triF(F), mat_s, T=LS.Matrix.Translation((cx, cy, zz)),
            col=col)
    V, F = LS.boxv(None, 0.34, 0.34, 2.6, z0=0.6)
    acc.add(V, G._triF(F), mat_s, T=LS.Matrix.Translation((cx, cy, zz)),
            col=col)
    V, F = LS.boxv(None, 1.5, 0.30, 0.30, z0=1.9)
    acc.add(V, G._triF(F), mat_s, T=LS.Matrix.Translation((cx, cy, zz)),
            col=col)
    return z


def motte(LS, acc, x, y, ang, mat_s, mat_w, rng):
    """A Norman motte: conical mound, ring ditch, and a timber tower on top."""
    col = tuple(LS.rgb("wall2") * 0.9)
    z = float(LS._gz(x, y))
    R = 17.0
    H = 7.5
    seg = 18
    for k in range(seg):
        a0 = TAU * k / seg
        a1 = TAU * (k + 1) / seg
        G.tq(acc, (x + R * math.cos(a0), y + R * math.sin(a0), z - 0.4),
             (x + R * math.cos(a1), y + R * math.sin(a1), z - 0.4),
             (x + R * 0.34 * math.cos(a1), y + R * 0.34 * math.sin(a1), z + H),
             (x + R * 0.34 * math.cos(a0), y + R * 0.34 * math.sin(a0), z + H),
             mat_s, tuple(LS.rgb("silt") * (0.86 + 0.10 * (k % 2))))
    # tower on the crown
    for k in range(8):
        a0 = TAU * k / 8.0
        a1 = TAU * (k + 1) / 8.0
        p0 = (x + 3.6 * math.cos(a0), y + 3.6 * math.sin(a0), z + H - 0.6)
        p1 = (x + 3.6 * math.cos(a1), y + 3.6 * math.sin(a1), z + H - 0.6)
        G.tq(acc, p0, p1, (p1[0], p1[1], p1[2] + 6.2),
             (p0[0], p0[1], p0[2] + 6.2), mat_w,
             tuple(LS.rgb("timber_d") * (0.84 + 0.14 * (k % 2))))
        G.tq(acc, p0, p1, (p1[0], p1[1], p1[2] + 1.0),
             (p0[0], p0[1], p0[2] + 1.0), mat_s, col)
    # bailey wall on the north side
    _wall(LS, acc, x + 26.0 * math.cos(ang), y + 26.0 * math.sin(ang),
          ang, 38.0, 14.0, 2.6, mat_s, col, rng, breach=0.45)
    return z


def barrow(LS, acc, x, y, ang, mat_s, mat_w, rng):
    """A long barrow: turf mound with a stone portal."""
    col = tuple(LS.rgb("wall2") * 0.88)
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    L = 26.0
    n = 12
    for k in range(n):
        u0 = -L * 0.5 + L * k / n
        u1 = -L * 0.5 + L * (k + 1) / n
        w0 = 5.2 * math.sin(math.pi * (k / float(n)) ** 0.72 + 0.16)
        w1 = 5.2 * math.sin(math.pi * ((k + 1) / float(n)) ** 0.72 + 0.16)
        h0 = 3.6 * w0 / 5.2
        h1 = 3.6 * w1 / 5.2
        p0 = (x + u0 * ca, y + u0 * sa, z)
        p1 = (x + u1 * ca, y + u1 * sa, z)
        G.tq(acc, (p0[0] - w0 * sa, p0[1] + w0 * ca, z),
             (p1[0] - w1 * sa, p1[1] + w1 * ca, z),
             (p1[0], p1[1], z + h1), (p0[0], p0[1], z + h0), mat_s,
             tuple(LS.rgb("meadow2") * (0.84 + 0.1 * (k % 2))))
        G.tq(acc, (p0[0] + w0 * sa, p0[1] - w0 * ca, z),
             (p1[0] + w1 * sa, p1[1] - w1 * ca, z),
             (p1[0], p1[1], z + h1), (p0[0], p0[1], z + h0), mat_s,
             tuple(LS.rgb("meadow2") * (0.8 + 0.1 * (k % 2))))
    # portal stones at the wide end
    for s in (-1.0, 1.0):
        _monolith(LS, acc, x - (L * 0.5 + 0.6) * ca + s * 2.6 * sa,
                  y - (L * 0.5 + 0.6) * sa - s * 2.6 * ca, 1.6, 2.6, 1.0,
                  ang, mat_s, col, rng)
    _monolith(LS, acc, x - (L * 0.5 + 0.6) * ca,
              y - (L * 0.5 + 0.6) * sa, 3.4, 0.9, 1.2, ang, mat_s, col, rng)
    return z


# --------------------------------------------------------------------------- #
def _river_node(LS, lo=0.0, hi=1e9, want=1.0):
    px = LS._RIV["px"]
    py = LS._RIV["py"]
    rr = np.hypot(px, py)
    ok = (rr > lo) & (rr < hi)
    if not np.any(ok):
        return None
    idx = np.flatnonzero(ok)
    k = idx[int(np.argmin(np.abs(rr[idx] - want)))]
    return float(px[k]), float(py[k]), k


def build(LS, rng, roads=None):
    """Place the landmarks.  Returns (objects, info)."""
    mat_s = _m(LS, "stone")
    mat_w = _m(LS, "wood")
    mat_r = _m(LS, "thatch")
    mat_e = _m(LS, "earth")

    objs = []
    placed = []

    # --- hilltop pieces: pick the highest ground in a ring ------------------
    def high(deg, d0, d1, n=44):
        best = None
        for k in range(n):
            a = math.radians(deg + rng.uniform(-7.0, 7.0))
            d = rng.uniform(d0, d1)
            x = d * math.cos(a)
            y = d * math.sin(a)
            if LS._city_sd(x, y) < 400.0:
                continue
            zz = float(LS._gz(x, y))
            if best is None or zz > best[2]:
                best = (x, y, zz)
        return best

    def flat(deg, d0, d1, n=48):
        best = None
        for k in range(n):
            a = math.radians(deg + rng.uniform(-9.0, 9.0))
            d = rng.uniform(d0, d1)
            x = d * math.cos(a)
            y = d * math.sin(a)
            if LS._city_sd(x, y) < 500.0:
                continue
            gx, gy = LS._gzs(x, y, 16.0)
            sl = math.hypot(gx, gy)
            zz = float(LS._gz(x, y))
            if zz > 620.0:
                continue
            if best is None or sl < best[2]:
                best = (x, y, sl, zz)
        return None if best is None else (best[0], best[1], best[3])

    def emit(name, fn):
        acc = LS.Acc()
        acc._mi(mat_s)
        try:
            fn(acc)
        except Exception as exc:                     # noqa: BLE001
            print("[land] landmark %s failed: %s" % (name, exc))
            return
        ob = acc.push("land_mark_%s" % name, smooth=True)
        if ob is not None:
            objs.append(ob)
            placed.append(name)

    # 1. windmill on the west road, the first thing you see leaving by it
    sp = flat(288.0, 1430.0, 1620.0)
    if sp:
        emit("windmill", lambda a: windmill(LS, a, sp[0], sp[1],
                                            rng.uniform(0, TAU), mat_s, mat_r,
                                            rng))
    # 2. gallows where the east road forks
    sp = flat(10.0, 1330.0, 1520.0)
    if sp:
        emit("gallows", lambda a: gallows_hill(LS, a, sp[0], sp[1], 0.3,
                                               mat_w, mat_s, rng))
    # 3. stone circle on the north-east upland
    sp = high(64.0, 1900.0, 2350.0)
    if sp:
        emit("circle", lambda a: stone_circle(LS, a, sp[0], sp[1], mat_s, rng))
    # 4. ruined abbey in the south-east
    sp = flat(150.0, 2200.0, 2650.0)
    if sp:
        emit("abbey", lambda a: abbey(LS, a, sp[0], sp[1], rng.uniform(0, 3.14),
                                      mat_s, mat_r, rng))
    # 5. beacon on the northern ridge, the highest thing in sight
    sp = high(96.0, 2700.0, 3250.0)
    if sp:
        emit("beacon", lambda a: beacon(LS, a, sp[0], sp[1], mat_s,
                                        tuple(LS.rgb("wall") * 0.88), rng))
    # 6. charcoal burners in the woods to the north-east
    sp = flat(36.0, 1650.0, 2050.0)
    if sp:
        emit("charcoal", lambda a: charcoal_camp(LS, a, sp[0], sp[1], mat_w,
                                                 mat_e, rng))
    # 7. hermitage on the western scarp
    sp = flat(202.0, 2350.0, 2800.0)
    if sp:
        emit("hermitage", lambda a: hermitage(LS, a, sp[0], sp[1],
                                              rng.uniform(0, 3.14), mat_s,
                                              mat_w, rng))
    # 8. motte and bailey on the north-west
    sp = flat(322.0, 2050.0, 2500.0)
    if sp:
        emit("motte", lambda a: motte(LS, a, sp[0], sp[1], rng.uniform(0, 3.14),
                                      mat_s, mat_w, rng))
    # 9. long barrow on the southern down
    sp = high(250.0, 2500.0, 3000.0)
    if sp:
        emit("barrow", lambda a: barrow(LS, a, sp[0], sp[1],
                                        rng.uniform(0, 3.14), mat_s, mat_w, rng))
    # 10. ferry downstream, on the flat reach below the harbour mouth
    nd = _river_node(LS, 1500.0, 2400.0, 1900.0)
    if nd is not None:
        x, y, k = nd
        wl = float(LS._RIV["wl"][k])

        def _f(a, x=x, y=y, wl=wl):
            # stand the hut on the bank, not in the water
            nx = float(LS._RIV["ty"][k])
            ny = -float(LS._RIV["tx"][k])
            ferry(LS, a, x + nx * 0.0, y + ny * 0.0, math.atan2(ny, nx), wl,
                  mat_w, mat_s, rng)
        emit("ferry", _f)
    # 11. old stone bridge upstream, where the road to the west crosses
    nd = _river_node(LS, 1200.0, 1700.0, 1380.0)
    if nd is not None:
        x, y, k = nd
        ang = math.atan2(float(LS._RIV["ty"][k]), float(LS._RIV["tx"][k]))

        def _b(a, x=x, y=y, ang=ang):
            acc = a
            bed = float(LS._gz(x, y))
            wlv, _d, hw = LS._water_level(x, y)
            deck = float(wlv) + 3.6
            T = (LS.Matrix.Translation((x, y, 0.0))
                 @ LS.Matrix.Rotation(ang, 4, 'Z'))
            V, F = LS.boxv(None, max(38.0, hw * 2.4), 4.6, 1.2, z0=deck)
            acc.add(V, G._triF(F), mat_s, T=T,
                    col=tuple(LS.rgb("wall")))
            for s in (-1.0, 1.0):
                V, F = LS.boxv(None, max(38.0, hw * 2.4), 0.5, 1.0, z0=deck + 1.2)
                acc.add(V, G._triF(F), mat_s,
                        T=T @ LS.Matrix.Translation((0.0, s * 2.1, 0.0)),
                        col=tuple(LS.rgb("wall2")))
            for t in (-0.30, 0.0, 0.30):
                h0 = deck - (bed - 1.8)
                V, F = LS.boxv(None, 4.6, 4.0, h0, z0=bed - 1.8)
                acc.add(V, G._triF(F), mat_s,
                        T=T @ LS.Matrix.Translation((t * 38.0, 0.0, 0.0)),
                        col=tuple(LS.rgb("wall2") * 0.92))
        emit("bridge", _b)

    return objs, {"marks": placed, "n": len(placed)}
