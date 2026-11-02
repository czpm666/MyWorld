"""The belt of working land between the outer wall and the open fields.

The gap between "city" and "country" is what makes a capital look pasted
together.  Four hundred metres of kitchen gardens against the wall foot,
orchards, sheep folds, wood yards and cart lanes is enough to make the
transition read as a place where people actually work.  Placement is by
bearing, so the belt has a rhythm from above -- six personalities repeated
every sector, with the four special trades (mill, sawyer, quarry, ruin) taking
one sector each.
"""

import math

import numpy as np

import hd_landscape_fields as FLD
import hd_landscape_geo as G
import hd_landscape_props as PR

TAU = math.pi * 2.0
SEC = 48                       # 7.5 deg sectors
BEAR = TAU / SEC
GARDEN_POS = []                # (x, y, z, ang) of the wall-foot gardens; lab uses it
CARPET = 11.0                  # close size of the near-belt mosaic, metres

# What the near belt is sown with, in the order the cumulative weights run.
# Weighted towards pasture and plough because this is the land that feeds the
# capital every day, with the cash crops further out.
_CARPET_MIX = (("pasture", 0.34), ("root", 0.11), ("plough", 0.13),
               ("wheat", 0.11), ("fallow", 0.08), ("rye", 0.08),
               ("vine", 0.06), ("orchard", 0.05), ("rapeseed", 0.04))


def _carpet(LS, rng, rp, band, mat_crop):
    """A continuous mosaic of small closes over the whole near belt.

    A scattering of isolated plots never reads as farmland from the wall: the
    eye wants a *continuous* patchwork with visible boundaries, close enough
    together that no sheet of plain grass survives between them.  One 17 m grid
    over the whole annulus, each cell a quad lifted a fifth of a metre, buys
    that for about a hundred thousand triangles -- far cheaper than filling the
    same ground with individual plots -- and it is exactly the layer the
    `Fur` attribute on ``land_crop`` was written for.
    """
    tot = sum(w for _k, w in _CARPET_MIX)
    cuts = []
    acc = 0.0
    for k, w in _CARPET_MIX:
        acc += w / tot
        cuts.append((acc, k))
    names = [k for k, _w in _CARPET_MIX]
    ids = {k: i for i, k in enumerate(names)}

    step = CARPET
    lo = LS.R_OUTER - 6.0
    hi = LS.R_OUTER + band[1]
    nb = int(hi / step) + 2
    vg = np.arange(-nb, nb + 1, dtype=np.float64) * step
    cg = vg[:-1] + step * 0.5
    CX, CY = np.meshgrid(cg, cg)
    cx = CX.ravel()
    cy = CY.ravel()
    rr = np.hypot(cx, cy)
    sel = (rr >= lo) & (rr <= hi)

    # Everything that varies smoothly is evaluated once over the whole grid:
    # the noise sampler costs a millisecond a call as a scalar, so a per-cell
    # loop over it is the difference between two seconds and three minutes.
    sd = np.asarray(LS._city_sd(cx, cy), dtype=np.float64)
    dR, _ix = LS._poly_dist(cx, cy, LS._RIV["px"], LS._RIV["py"])
    dR = np.asarray(dR, dtype=np.float64)
    tv = np.asarray(LS.vnoise(cx, cy, 1.0 / 190.0, 21), dtype=np.float64)
    jv = np.asarray(LS.vnoise(cx, cy, 1.0 / 70.0, 29), dtype=np.float64)
    hv = np.asarray(LS.vnoise(cx, cy, 1.0 / 61.0, 23), dtype=np.float64)
    av = np.asarray(LS.vnoise(cx, cy, 1.0 / 240.0, 25), dtype=np.float64) * 3.14159
    lx, ly, lr, _lwl = LS._RIV["lake"]

    # the same noise at the cell corners, so no two closes are one flat tone
    VX, VY = np.meshgrid(vg, vg)
    vn = np.asarray(LS.vnoise(VX, VY, 1.0 / 47.0, 27), dtype=np.float64)
    zg = np.asarray(LS._gz(VX, VY), dtype=np.float64)
    ncp = cg.size

    b = FLD.Bucket()
    ncell = 0
    for iy in range(ncp):
        for ix in range(ncp):
            i = iy * ncp + ix
            if not sel[i]:
                continue
            x = float(cx[i])
            y = float(cy[i])
            if sd[i] < 12.0 or dR[i] < 44.0:
                continue
            if math.hypot(x - lx, y - ly) < lr * 1.12:
                continue
            if _in_field(x, y):
                continue
            hot = False
            for P in rp:
                if _near(P, x, y) < 9.0:
                    hot = True
                    break
            if hot:
                continue
            # a 190 m field picks the crop and a 70 m one jitters it, so runs of
            # neighbouring closes agree and read as one parcel from the air
            # instead of a field of confetti
            t = float(min(1.0, max(0.0, tv[i] + (jv[i] - 0.5) * 0.22)))
            kind = cuts[-1][1]
            for c, k in cuts:
                if t <= c:
                    kind = k
                    break
            cr = FLD.CROPS[kind]
            # Every close is compressed towards a common exposure and left to
            # differ in hue: real farmland under one sun reads as a mosaic of
            # colours, with tilled soil genuinely darker than pasture, not as a
            # mosaic of brightnesses.  Equalising luminance outright turns a
            # ploughed close into a salmon field, so the range is only squeezed
            # (0.09 to 0.31 linear) rather than flattened.
            base = np.asarray(LS.rgb(cr["col"]), dtype=np.float64)
            lum = float(base[0] * 0.30 + base[1] * 0.59 + base[2] * 0.11)
            k2 = (0.16 / max(lum, 1e-4)) ** 0.45 * 0.85
            jit = 0.90 + 0.20 * float(jv[i])
            coarse = base * k2 * jit
            X = np.array([vg[ix], vg[ix + 1], vg[ix + 1], vg[ix]])
            Y = np.array([vg[iy], vg[iy], vg[iy + 1], vg[iy + 1]])
            # every close sits a little proud of its neighbours: the step is
            # what draws the boundary, and it costs nothing
            h = 0.10 + 0.16 * float(hv[i])
            Z = np.array([zg[iy, ix], zg[iy, ix + 1],
                          zg[iy + 1, ix + 1], zg[iy + 1, ix]]) + h
            cn = np.array([vn[iy, ix], vn[iy, ix + 1],
                           vn[iy + 1, ix + 1], vn[iy + 1, ix]])
            cols = [tuple(float(min(1.0, v)) for v in coarse * (0.88 + 0.24 * c))
                    for c in cn]
            ca, sa = math.cos(float(av[i])), math.sin(float(av[i]))
            fur = (ca * 0.5 + 0.5, sa * 0.5 + 0.5, cr["p"] / 4.0,
                   (ids[kind] + 0.5) / 16.0)
            b.add(LS, list(zip(X.tolist(), Y.tolist(), Z.tolist())),
                  [(0, 1, 2), (0, 2, 3)], mat_crop, cols, [fur] * 4)
            ncell += 1
    ob = b.push(LS, "land_carpet")
    return ob, ncell


def _m(LS, key):
    m = LS.GBL.get(key + "_land")
    if m is not None:
        return m
    m = LS.GBL.get(key)
    if m is not None:
        return m
    return LS._get_mat(getattr(LS, "_MAT", None), key)


def _road_pts(LS):
    out = []
    for p in LS.ROADS.values():
        P = np.asarray(LS._spline(p, 18.0)[0], dtype=np.float64)
        if len(P) > 1:
            out.append(P)
    return out


def _near(P, x, y):
    return float(np.hypot(P[:, 0] - x, P[:, 1] - y).min())


# --------------------------------------------------------------------------- #
#  a raster mask of the open-field parcels, so the belt does not build on them
# --------------------------------------------------------------------------- #
_FM = {}


def _field_mask(fields, res=10.0, half=1700.0):
    n = int(2.0 * half / res) + 1
    M = np.zeros((n, n), dtype=bool)
    for f in fields:
        ca, sa = math.cos(f.ang), math.sin(f.ang)
        hw = f.w * 0.5 + 2.5
        hd = f.d * 0.5 + 2.5
        rr = math.hypot(hw, hd)
        i0 = max(0, int((f.cx - rr + half) / res))
        i1 = min(n - 1, int((f.cx + rr + half) / res) + 1)
        j0 = max(0, int((f.cy - rr + half) / res))
        j1 = min(n - 1, int((f.cy + rr + half) / res) + 1)
        if i1 <= i0 or j1 <= j0:
            continue
        xs = -half + np.arange(i0, i1 + 1) * res
        ys = -half + np.arange(j0, j1 + 1) * res
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        u = (X - f.cx) * ca + (Y - f.cy) * sa
        v = -(X - f.cx) * sa + (Y - f.cy) * ca
        M[i0:i1 + 1, j0:j1 + 1] |= (np.abs(u) <= hw) & (np.abs(v) <= hd)
    _FM.update(M=M, res=res, half=half, n=n)
    return _FM


def _in_field(x, y):
    M = _FM.get("M")
    if M is None:
        return False
    r = _FM["res"]
    i = int((x + _FM["half"]) / r + 0.5)
    j = int((y + _FM["half"]) / r + 0.5)
    n = _FM["n"]
    if i < 0 or j < 0 or i >= n or j >= n:
        return False
    return bool(M[i, j])


def _clear(LS, rp, x, y, gap=13.0, riv=44.0):
    if LS._city_sd(x, y) < 12.0:
        return False
    if _in_field(x, y):
        return False
    for P in rp:
        if _near(P, x, y) < gap:
            return False
    d, _i = LS._poly_dist(np.array([x]), np.array([y]),
                          LS._RIV["px"], LS._RIV["py"])
    if float(d[0]) < riv:
        return False
    lx, ly, lr, _l = LS._RIV["lake"]
    if math.hypot(x - lx, y - ly) < lr * 1.12:
        return False
    return True


def _flat(LS, x, y, lim=0.14):
    gx, gy = LS._gzs(x, y, 14.0)
    return math.hypot(gx, gy) < lim


def _spot(LS, rp, rng, ang, d0, d1, gap=13.0, flat=True):
    """First clear, flat-ish point along a bearing, or None."""
    ca, sa = math.cos(ang), math.sin(ang)
    off = rng.uniform(-26.0, 26.0)
    for i in range(22):
        d = d0 + (d1 - d0) * (i / 21.0)
        x = ca * d - sa * off
        y = sa * d + ca * off
        if _clear(LS, rp, x, y, gap) and (not flat or _flat(LS, x, y)):
            return x, y, float(LS._gz(x, y))
    return None


def _fence_rect(LS, acc, x, y, ang, w, d, h, rng, mat, col, gate_side=0):
    """Four runs of post-and-rail with one side left open."""
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hd = w * 0.5, d * 0.5
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    for k in range(4):
        if k == gate_side:
            continue
        a = corners[k]
        b = corners[(k + 1) % 4]
        # break each side into two runs so the fence follows the ground
        for s in range(2):
            t0 = s * 0.5
            t1 = t0 + 0.5
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            P = np.array([[x + p0[0] * ca - p0[1] * sa,
                           y + p0[0] * sa + p0[1] * ca],
                          [x + p1[0] * ca - p1[1] * sa,
                           y + p1[0] * sa + p1[1] * ca]])
            G.fence_line(LS, acc, P, h, rng, col, mat, step=3.0)


def _shed(LS, acc, x, y, ang, rng, mat_w, mat_r, w=4.6, d=3.2, h=2.3):
    """A lean-to: four posts, a plank wall on the weather side, thatch on top."""
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hd = w * 0.5, d * 0.5

    def P(u, v, dz):
        return (x + u * ca - v * sa, y + u * sa + v * ca, z + dz)

    wood = tuple(LS.rgb("timber") * rng.uniform(0.78, 1.04))
    for u, v in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)):
        p = P(u, v, 0.0)
        acc.tri(p, (p[0] + 0.14, p[1], p[2]), (p[0], p[1] + 0.14, p[2] + h),
                mat_w, wood)
        G.tq(acc, (p[0] - 0.11, p[1] - 0.11, p[2]),
             (p[0] + 0.11, p[1] - 0.11, p[2]),
             (p[0] + 0.11, p[1] - 0.11, p[2] + h),
             (p[0] - 0.11, p[1] - 0.11, p[2] + h), mat_w, wood)
    # back wall, planks
    nb = max(2, int(w / 0.42))
    for k in range(nb):
        u0 = -hw + w * k / nb
        u1 = -hw + w * (k + 1) / nb
        G.tq(acc, P(u0, -hd, 0.0), P(u1, -hd, 0.0),
             P(u1, -hd, h * 0.96), P(u0, -hd, h), mat_w,
             tuple(LS.rgb("timber_d") * rng.uniform(0.82, 1.06)))
    # roof, sloping to the front
    G.tq(acc, P(-hw - 0.25, -hd - 0.25, h + 0.02),
         P(hw + 0.25, -hd - 0.25, h + 0.02),
         P(hw + 0.25, hd + 0.55, h - 0.55),
         P(-hw - 0.25, hd + 0.55, h - 0.55), mat_r,
         tuple(LS.rgb("thatchc") * rng.uniform(0.86, 1.08)))
    return z


def _garden(LS, acc, rng, x, y, ang, w, d, mat_crop, mat_w, mat_leaf):
    """Kitchen garden: beds, a hedge on two sides, compost, a water butt."""
    z = float(LS._gz(x, y))
    PR.garden_beds(LS, acc, x, y, z, rng, mat_crop, w=w, d=d, ang=ang)
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hd = w * 0.5, d * 0.5
    for side in (0, 1):
        u = -hw - 1.1 if side == 0 else hw + 1.1
        P = np.array([[x + u * ca + hd * sa, y + u * sa - hd * ca],
                      [x + u * ca - hd * sa, y + u * sa + hd * ca]])
        G.hedge_band(LS, acc, P, rng.uniform(1.6, 2.6), rng.uniform(1.1, 1.9),
                     rng, tuple(LS.rgb("hedge") * rng.uniform(0.9, 1.12)),
                     mat_leaf)
    PR.compost_heap(LS, acc, x + (hw + 2.6) * ca - hd * 0.5 * sa,
                    y + (hw + 2.6) * sa + hd * 0.5 * ca, None, rng,
                    _m(LS, "earth"), r=rng.uniform(1.9, 2.9), h=1.1)
    PR.beehives(LS, acc, x - hd * 0.7 * sa, y + hd * 0.7 * ca, None, rng,
                mat_w, n=4, ang=ang)
    if rng.random() < 0.6:
        _shed(LS, acc, x + (hw - 2.4) * ca - (hd + 3.0) * sa,
              y + (hw - 2.4) * sa + (hd + 3.0) * ca, ang, rng, mat_w,
              _m(LS, "prop"))


def _orchard(LS, acc, rng, x, y, ang, w, d, tb, mat_w):
    """Rows of fruit trees inside a low fence or hedge."""
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    row = 7.0
    sp = 5.6
    nr = max(2, int(d / row))
    nc = max(2, int(w / sp))
    xs = []
    ys = []
    for i in range(nr):
        v = -d * 0.5 + row * (i + 0.5)
        for j in range(nc):
            u = -w * 0.5 + sp * (j + 0.5)
            xs.append(x + u * ca - v * sa + rng.uniform(-0.5, 0.5))
            ys.append(y + u * sa + v * ca + rng.uniform(-0.5, 0.5))
    X = np.array(xs)
    Y = np.array(ys)
    Z = np.asarray(LS._gz(X, Y), dtype=np.float64)
    n = X.size
    V0, F0, shade = G.tree_template(G.ORCHARD, 0, 3)
    nr = np.random.default_rng(rng.randrange(1 << 30))
    COL = np.clip(np.array(LS.rgb("hedge2"))[None, :]
                  * nr.uniform(0.86, 1.14, (n, 1)), 0.0, 1.0)
    # orchard trees are pruned short and wide
    SC = nr.uniform(0.36, 0.52, n)
    tb.add_many(V0, F0, shade, X, Y, Z, nr.uniform(0.0, TAU, n), SC, COL)
    hw, hd = w * 0.5 + 1.6, d * 0.5 + 1.6
    # hedge on the long sides
    for s in (-1.0, 1.0):
        v = s * hd
        Q = np.array([[x + hw * ca - v * sa, y + hw * sa + v * ca],
                      [x - hw * ca - v * sa, y - hw * sa + v * ca]])
        G.hedge_band(LS, acc, Q, rng.uniform(1.5, 2.4), rng.uniform(1.0, 1.7),
                     rng, tuple(LS.rgb("hedge") * rng.uniform(0.9, 1.1)),
                     _m(LS, "leaf"), gap_p=0.10)
    return z


def _pasture(LS, acc, rng, x, y, ang, w, d, mat_w, mat_leaf):
    z = float(LS._gz(x, y))
    PR.sheep_fold(LS, acc, x, y, z, rng, mat_w, r=rng.uniform(8.0, 12.0),
                  n=9)
    for k in range(3):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(0.55, 0.85) * min(w, d) * 0.5
        PR.hayrick(LS, acc, x + rr * math.cos(a), y + rr * math.sin(a), None,
                   rng, _m(LS, "prop"), w=rng.uniform(2.6, 3.4),
                   h=rng.uniform(3.2, 4.4))
    PR.trough(LS, acc, x + 6.0, y - 4.0, None, rng, mat_w, L=2.6, ang=ang)
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hd = w * 0.5, d * 0.5
    for s in (-1.0, 1.0):
        v = s * hd
        Q = np.array([[x + hw * ca - v * sa, y + hw * sa + v * ca],
                      [x - hw * ca - v * sa, y - hw * sa + v * ca]])
        G.drystone(LS, acc, Q, rng.uniform(0.8, 1.15), 0.55, rng,
                   tuple(LS.rgb("wall") * rng.uniform(0.86, 1.06)),
                   _m(LS, "stone"), step=1.8)
    return z


def _woodyard(LS, acc, rng, x, y, ang, mat_w):
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    for k in range(3):
        u = (k - 1) * 5.4
        v = rng.uniform(-2.0, 2.0)
        PR.woodpile(LS, acc, x + u * ca - v * sa, y + u * sa + v * ca, None,
                    rng, mat_w, w=rng.uniform(3.4, 5.2),
                    h=rng.uniform(1.1, 1.8), ang=ang + rng.uniform(-0.12, 0.12))
    PR.wood_lathe(LS, acc, x + 9.0 * ca + 3.0 * sa, y + 9.0 * sa - 3.0 * ca,
                  None, rng, mat_w, r=rng.uniform(3.2, 4.4))
    # saw pit: two long timbers beside a trench, and sawn baulks stacked up
    for s in (-1.0, 1.0):
        p = (x - 4.0 * ca + s * 1.2 * sa, y - 4.0 * sa - s * 1.2 * ca, z + 0.5)
        acc.tri(p, (p[0] + 7.0 * ca, p[1] + 7.0 * sa, p[2]),
                (p[0] + 7.0 * ca, p[1] + 7.0 * sa, p[2] - 0.5), mat_w,
                tuple(LS.rgb("wood_dark")))
    for k in range(7):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(2.0, 10.0)
        cx = x + rr * math.cos(a)
        cy = y + rr * math.sin(a)
        cz = float(LS._gz(cx, cy))
        ln = rng.uniform(2.4, 5.0)
        rad = rng.uniform(0.30, 0.50)
        V, F = LS.boxv(None, ln, rad * 2.0, rad * 2.0, z0=0.0)
        acc.add(V, G._triF(F), mat_w,
                T=(LS.Matrix.Translation((cx, cy, cz + rad))
                   @ LS.Matrix.Rotation(a, 4, 'Z')),
                col=tuple(LS.rgb("wood_dark") * rng.uniform(0.78, 1.08)))
    return z


def _quarry(LS, acc, rng, x, y, mat_w, mat_s):
    z = float(LS._gz(x, y))
    for k in range(14):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(1.0, 15.0)
        cx = x + rr * math.cos(a)
        cy = y + rr * math.sin(a)
        sz = rng.uniform(1.1, 3.0)
        V, F = LS.boxv(None, sz, sz * rng.uniform(0.7, 1.2), sz * 0.8, z0=0.0)
        acc.add(V, G._triF(F), mat_s,
                T=LS.Matrix.Translation((cx, cy, float(LS._gz(cx, cy)))),
                col=tuple(LS.rgb("wall2") * rng.uniform(0.82, 1.08)))
    # a crane: mast, jib and a block on a rope
    base = (x + 12.0, y + 4.0, float(LS._gz(x + 12.0, y + 4.0)))
    top = base[2] + 9.0
    for dx, dy in ((0.22, 0.22), (-0.22, 0.22), (0.22, -0.22), (-0.22, -0.22)):
        acc.tri((base[0] + dx, base[1] + dy, base[2]),
                (base[0] + dx * 1.7, base[1] + dy * 1.7, top),
                (base[0] - dx, base[1] - dy, base[2]), mat_w,
                tuple(LS.rgb("timber_d")))
    jib = (base[0] - 7.0, base[1] + 1.5, top + 0.3)
    acc.tri((base[0], base[1], top), jib, (base[0] + 2.0, base[1], top), mat_w,
            tuple(LS.rgb("timber")))
    return z


def _mill(LS, acc, rng, x, y, ang, mat_w, mat_s, mat_r):
    """A mill with a raised timber launder feeding its wheel.

    A cut leat would mean carving the terrain, which at this scale is a whole
    hydrology problem.  A launder on trestles is what a real mill on a slope
    used anyway, and it gives the skyline something to read.
    """
    z = _shed(LS, acc, x, y, ang, rng, mat_w, mat_r, w=7.4, d=5.4, h=4.4)
    ca, sa = math.cos(ang), math.sin(ang)

    def P(u, v, dz):
        return (x + u * ca - v * sa, y + u * sa + v * ca, dz)

    # --- launder: level trough on trestles, running along -u ----------------
    us = np.linspace(-18.0, 0.0, 7)
    gz = np.asarray(LS._gz(x + us * ca, y + us * sa), dtype=np.float64)
    lz = float(np.max(gz) + 2.4)
    for k in range(len(us) - 1):
        u0 = us[k]
        u1 = us[k + 1]
        c = tuple(LS.rgb("wood_dark") * (0.88 if k % 2 else 0.98))
        G.tq(acc, P(u0, -0.55, lz), P(u1, -0.55, lz), P(u1, 0.55, lz),
             P(u0, 0.55, lz), mat_w, c)
        for v in (-0.55, 0.55):
            G.tq(acc, P(u0, v, lz), P(u1, v, lz), P(u1, v, lz - 0.62),
                 P(u0, v, lz - 0.62), mat_w, tuple(LS.rgb("timber_d")))
        if k % 2 == 0:
            g0 = float(gz[k])
            for v in (-0.5, 0.5):
                G.tq(acc, P(u0 - 0.1, v - 0.1, g0), P(u0 + 0.1, v - 0.1, g0),
                     P(u0 + 0.1, v - 0.1, lz - 0.62),
                     P(u0 - 0.1, v - 0.1, lz - 0.62), mat_w,
                     tuple(LS.rgb("timber_d") * 0.94))
    # --- wheel, in the pit under the launder's end --------------------------
    wx = x - 1.2 * ca
    wy = y - 1.2 * sa
    wz = float(LS._gz(wx, wy))
    seg = 18
    for k in range(seg):
        a0 = TAU * k / seg
        a1 = TAU * (k + 1) / seg
        c = tuple(LS.rgb("wood_dark") * (0.84 + 0.22 * (k % 2)))
        p0 = (wx - sa * 2.1 * math.cos(a0), wy + ca * 2.1 * math.cos(a0),
              wz + 1.6 + 2.1 * math.sin(a0))
        p1 = (wx - sa * 2.1 * math.cos(a1), wy + ca * 2.1 * math.cos(a1),
              wz + 1.6 + 2.1 * math.sin(a1))
        q0 = (p0[0] + ca * 0.5, p0[1] + sa * 0.5, p0[2])
        q1 = (p1[0] + ca * 0.5, p1[1] + sa * 0.5, p1[2])
        G.tq(acc, p0, q0, q1, p1, mat_w, c)
    # --- tail race: a short apron of stone back to the ditch ----------------
    for k in range(4):
        v = -1.6 + k * 1.05
        G.tq(acc, P(2.0, v, wz + 0.06), P(7.5, v, wz + 0.06),
             P(7.5, v + 1.05, wz + 0.06), P(2.0, v + 1.05, wz + 0.06),
             mat_s, tuple(LS.rgb("wall2") * (0.86 + 0.06 * (k % 2))))
    return z


def _ruin(LS, acc, rng, x, y, ang, mat_s):
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    col = tuple(LS.rgb("wall") * 0.86)
    for k in range(9):
        u = -13.0 + 3.2 * k
        hh = rng.uniform(0.6, 3.4)
        if rng.random() < 0.22:
            continue
        a = (x + u * ca - 4.0 * sa, y + u * sa + 4.0 * ca, z)
        b = (x + (u + 3.0) * ca - 4.0 * sa, y + (u + 3.0) * sa + 4.0 * ca, z)
        G.tq(acc, (a[0], a[1], a[2]), (b[0], b[1], b[2]),
             (b[0], b[1], b[2] + hh), (a[0], a[1], a[2] + hh * 0.94), mat_s,
             tuple(c * rng.uniform(0.86, 1.1) for c in col))
        # thickness so the wall is not a card
        G.tq(acc, (b[0], b[1], b[2] + hh), (a[0], a[1], a[2] + hh * 0.94),
             (a[0] - 0.55 * sa, a[1] + 0.55 * ca, a[2] + hh * 0.94),
             (b[0] - 0.55 * sa, b[1] + 0.55 * ca, b[2] + hh), mat_s,
             tuple(c * 0.8 for c in col))
    for k in range(7):
        a = rng.uniform(0, TAU)
        rr = rng.uniform(1.0, 12.0)
        cx = x + rr * math.cos(a)
        cy = y + rr * math.sin(a)
        sz = rng.uniform(0.4, 1.1)
        V, F = LS.boxv(None, sz, sz, sz * 0.6, z0=0.0)
        acc.add(V, G._triF(F), mat_s,
                T=LS.Matrix.Translation((cx, cy, float(LS._gz(cx, cy)))),
                col=tuple(LS.rgb("wall2") * rng.uniform(0.7, 0.95)))
    return z


def _gate_yard(LS, acc, rng, rp, road, x, y, ang, mat_w, mat_l, mat_e):
    """Cart yard beside a gate: a well, carts, hay for the market, a lane."""
    z = float(LS._gz(x, y))
    PR.well(LS, acc, x, y, z, rng, mat_w)
    ca, sa = math.cos(ang), math.sin(ang)
    for k in range(2):
        u = rng.uniform(-7.0, 7.0)
        v = rng.uniform(4.0, 8.0)
        PR.cart(LS, acc, x + u * ca - v * sa, y + u * sa + v * ca, None, rng,
                mat_w, ang=rng.uniform(0, TAU))
    PR.haystack(LS, acc, x - 6.0 * ca - 6.0 * sa, y - 6.0 * sa + 6.0 * ca,
                None, rng, _m(LS, "prop"), w=rng.uniform(5.5, 7.0),
                d=rng.uniform(2.8, 3.6), h=rng.uniform(3.0, 3.8), ang=ang)
    PR.compost_heap(LS, acc, x + 7.0 * ca + 5.0 * sa, y + 7.0 * sa - 5.0 * ca,
                    None, rng, mat_e, r=rng.uniform(2.0, 3.0), h=1.0)
    # a lane running off the highway, with ruts
    P = np.array([[x + 12.0 * ca - 14.0 * sa, y + 12.0 * sa + 14.0 * ca],
                  [x + 34.0 * ca - 20.0 * sa, y + 34.0 * sa + 20.0 * ca],
                  [x + 58.0 * ca - 16.0 * sa, y + 58.0 * sa + 16.0 * ca]])
    PR.ruts(LS, acc, P, w=3.0, lift=0.05, step=9.0)
    return z


def _plot(LS, acc, rng, x, y, ang, w, d, mat_soil, mat_crop, mat_w, mat_l):
    """A croft-sized plot of vegetables or ploughed land.

    Fine ridge-and-furrow at 0.85-1.3 m pitch, which is what the brief calls
    for close to the walls: at 1.72 m eye height the ridges are waist high and
    from 300 m up they read as cultivation rather than as another colour patch.
    """
    z = float(LS._gz(x, y))
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hd = w * 0.5, d * 0.5
    soil = tuple(min(1.0, v * rng.uniform(0.80, 1.06))
                 for v in LS.rgb("plough"))
    crop = tuple(min(1.0, v * rng.uniform(0.78, 1.04))
                 for v in LS.rgb(rng.choice(("green", "pasture", "root",
                                             "rape", "root"))))

    def P(u, v, dz=0.02):
        return (x + u * ca - v * sa, y + u * sa + v * ca, z + dz)

    acc.quad(P(-hw, -hd), P(hw, -hd), P(hw, hd), P(-hw, hd), mat_soil, soil)

    per = rng.uniform(0.85, 1.32)
    r = G.furrow_mesh(LS, ang, x, y, hw * 1.90, hd * 1.92, per,
                      rng.uniform(0.09, 0.17), rng, soil, crop)
    if r is not None:
        V, F, C = r
        VW = [(x + p[0] * ca - p[1] * sa, y + p[0] * sa + p[1] * ca,
               z + 0.02 + p[2]) for p in V]
        acc.add(VW, F, mat_crop, col=C)

    # one or two edges get a low boundary so the plots are legible from above
    sides = [0, 1, 2, 3]
    rng.shuffle(sides)
    for k in sides[:rng.choice((1, 1, 2))]:
        u0, v0, u1, v1 = ((-hw, -hd, hw, -hd), (hw, -hd, hw, hd),
                          (hw, hd, -hw, hd), (-hw, hd, -hw, -hd))[k]
        P2 = np.array([[x + u0 * ca - v0 * sa, y + u0 * sa + v0 * ca],
                       [x + u1 * ca - v1 * sa, y + u1 * sa + v1 * ca]])
        if rng.random() < 0.55:
            G.hedge_band(LS, acc, P2, rng.uniform(1.1, 1.9),
                         rng.uniform(0.75, 1.30), rng,
                         tuple(LS.rgb("hedge") * rng.uniform(0.88, 1.10)),
                         mat_l, step=3.0)
        else:
            G.fence_line(LS, acc, P2, rng.uniform(0.85, 1.15), rng,
                         tuple(LS.rgb("timber") * rng.uniform(0.85, 1.05)),
                         mat_w, step=3.2)
    return z


def build(LS, rng, roads=None, band=(0.0, 430.0), fields=None):
    """Belt of worked land outside the walls.  Returns (objects, info)."""
    rp = _road_pts(LS)
    # Everything loose in the belt carries its own colour per vertex, so it is
    # drawn with the landscape's own prop material: the city's wood and thatch
    # materials are not this module's to reason about, and a lab with no city
    # loaded would render every rick and cart a pale grey.
    mat_w = _m(LS, "prop")
    mat_l = _m(LS, "leaf")
    mat_s = _m(LS, "stone")
    mat_c = _m(LS, "crop")
    mat_r = _m(LS, "prop")
    mat_e = _m(LS, "prop")
    mat_d = _m(LS, "soil")

    objs = []
    info = {"gardens": 0, "orchards": 0, "pastures": 0, "yards": 0,
            "trees": 0, "plots": 0, "parcels": 0}
    if fields:
        _field_mask(fields)
    else:
        _FM.clear()

    # --- wheel ruts down the four highways for the first kilometre ----------
    racc = LS.Acc()
    racc._mi(mat_e)
    nrut = 0
    for p in LS.ROADS.values():
        P = np.asarray(LS._spline(p, 12.0)[0], dtype=np.float64)
        dd = np.hypot(P[:, 0], P[:, 1])
        keep = dd > 880.0
        if not np.any(keep):
            continue
        k0 = int(np.argmax(keep))
        Q = P[max(0, k0 - 2):]
        nrut += PR.ruts(LS, racc, Q, w=4.4, lift=0.052, step=10.0)
    ob = racc.push("land_ruts", smooth=False)
    if ob is not None:
        objs.append(ob)
    info["ruts"] = nrut

    # --- wall-foot kitchen gardens, all the way round -----------------------
    gacc = LS.Acc()
    gacc._mi(mat_c)
    n = 0
    GARDEN_POS[:] = []
    for k in range(132):
        a = TAU * (k + rng.uniform(0.15, 0.85)) / 132.0
        sp = _spot(LS, rp, rng, a, 978.0, 1110.0, gap=8.0)
        if sp is None:
            continue
        x, y, z = sp
        _garden(LS, gacc, rng, x, y, a + math.pi * 0.5,
                rng.uniform(10.0, 17.0), rng.uniform(6.5, 11.0), mat_d, mat_w,
                mat_l)
        GARDEN_POS.append((float(x), float(y), float(z), float(a)))
        n += 1
        if n >= 92:
            break
    info["gardens"] = n
    ob = gacc.push("land_gardens", smooth=False)
    if ob is not None:
        objs.append(ob)

    # --- the continuous close mosaic ---------------------------------------
    # Placed before the loose props so the props sit on top of it, and after
    # the gardens so the carpet runs round them rather than through them.
    cob, ncel = _carpet(LS, rng, rp, band, mat_c)
    if cob is not None:
        objs.append(cob)
    info["carpet"] = ncel

    # --- infill: a jittered 44 m grid over the whole belt -------------------
    # The rays above give the set-pieces; a ring of dots is not a belt.  This
    # pass makes the belt continuous: every ~50 m cell clear of the roads, the
    # river, the city and the parcels gets one small piece of worked land, and
    # a 260 m noise field picks which kind, so kinds clump into districts
    # instead of scattering like confetti.
    pacc = LS.Acc()
    pacc._mi(mat_d)
    qacc = LS.Acc()
    qacc._mi(mat_w)
    step = 44.0
    lim = LS.R_OUTER + band[1]
    nb = int(lim / step) + 2
    taken = []
    tb = G.TBuf()
    for iy in range(-nb, nb + 1):
        for ix in range(-nb, nb + 1):
            x = ix * step + rng.uniform(-0.42, 0.42) * step
            y = iy * step + rng.uniform(-0.42, 0.42) * step
            rr = math.hypot(x, y)
            if rr < LS.R_OUTER - 8.0 or rr > LS.R_OUTER + band[1]:
                continue
            if not _clear(LS, rp, x, y, gap=11.0, riv=52.0):
                continue
            if any((x - a) * (x - a) + (y - b) * (y - b) < c * c
                   for a, b, c in taken):
                continue
            p = float(LS.vnoise(x, y, 1.0 / 260.0, 7))
            if p < 0.14:
                # rare, and deliberately larger than a carpet cell: an
                # occasional big close breaking the 17 m rhythm
                ang = float(LS.vnoise(x, y, 1.0 / 210.0, 11)) * 3.14
                w = rng.uniform(38.0, 62.0)
                d = rng.uniform(24.0, 40.0)
                _plot(LS, pacc, rng, x, y, ang, w, d,
                      mat_d, mat_d, mat_w, mat_l)
                taken.append((x, y, max(w, d) * 0.5 + 3.0))
                info["plots"] += 1
            elif p < 0.46:
                V0, F0, sh = G.tree_template(G.ORCHARD, 1, 3)
                nT = 7
                tx = np.array([x + rng.uniform(-13.0, 13.0)
                               for _ in range(nT)])
                ty = np.array([y + rng.uniform(-10.0, 10.0)
                               for _ in range(nT)])
                tz = LS._gz(tx, ty)
                tr = np.array([rng.uniform(0.0, 6.28) for _ in range(nT)])
                ts = np.array([rng.uniform(0.34, 0.52) for _ in range(nT)])
                tc = np.tile(np.asarray(LS.rgb("hedge2")), (nT, 1))
                tb.add_many(V0, F0, sh, tx, ty, tz, tr, ts, tc)
                taken.append((x, y, 14.0))
                info["trees"] += nT
            elif p < 0.80:
                PR.hayrick(LS, qacc, x, y, None, rng, _m(LS, "prop"))
                PR.hayrick(LS, qacc, x + 4.4, y - 3.1, None, rng,
                           _m(LS, "prop"))
                if rng.random() < 0.5:
                    PR.compost_heap(LS, qacc, x - 5.0, y + 2.6, None, rng,
                                    mat_e)
                taken.append((x, y, 9.0))
                info["yards"] += 1
            elif p < 0.90:
                # a short hedge run, so the belt gets structure instead of
                # being a carpet of objects
                a2 = float(LS.vnoise(x, y, 1.0 / 300.0, 13)) * 3.14
                ln = rng.uniform(26.0, 54.0)
                ca, sa = math.cos(a2), math.sin(a2)
                P = [(x - ca * ln * 0.5, y - sa * ln * 0.5),
                     (x + ca * ln * 0.5, y + sa * ln * 0.5)]
                G.hedge_band(LS, qacc, P, rng.uniform(3.0, 4.6),
                             rng.uniform(1.7, 2.9), rng, LS.rgb("hedge"),
                             mat_l, gap_p=0.12)
                taken.append((x, y, ln * 0.5 + 4.0))
            else:
                PR.woodpile(LS, qacc, x, y, None, rng, mat_w)
                PR.woodpile(LS, qacc, x + 3.8, y + 2.2, None, rng, mat_w)
                taken.append((x, y, 7.0))
    ob = pacc.push("land_belt_plots", smooth=True)
    if ob is not None:
        objs.append(ob)
    ob = qacc.push("land_belt_props", smooth=False)
    if ob is not None:
        objs.append(ob)

    # --- the ring of worked plots, one personality per sector ---------------
    per = (("gate", 0), ("orchard", 1), ("pasture", 2), ("garden", 3),
           ("crops", 4), ("special", 5))
    for k in range(SEC):
        kind = per[k % 6][0]
        ang = BEAR * (k + 0.5)
        if kind == "special":
            kind = ("mill", "lumber", "quarry", "ruin")[(k // 6) % 4]
        acc = LS.Acc()
        acc._mi(mat_w)
        sp = _spot(LS, rp, rng, ang, 1030.0, 1330.0, gap=15.0)
        if sp is None:
            continue
        x, y, z = sp
        rot = ang + rng.uniform(-0.22, 0.22)
        if kind == "gate":
            _gate_yard(LS, acc, rng, rp, None, x, y, rot, mat_w, mat_l, mat_e)
            info["yards"] += 1
        elif kind in ("orchard", "garden"):
            w = rng.uniform(34.0, 52.0)
            d = rng.uniform(22.0, 34.0)
            _orchard(LS, acc, rng, x, y, rot, w, d, tb, mat_w)
            info["orchards"] += 1
            info["trees"] += int(max(2, d / 7.0) * max(2, w / 5.6))
            if kind == "garden" and rng.random() < 0.7:
                sp2 = _spot(LS, rp, rng, ang, 1370.0, 1500.0, gap=15.0)
                if sp2 is not None:
                    _garden(LS, acc, rng, sp2[0], sp2[1], rot, 12.0, 8.0,
                            mat_c, mat_w, mat_l)
                    info["plots"] += 1
        elif kind == "pasture":
            _pasture(LS, acc, rng, x, y, rot, rng.uniform(40.0, 62.0),
                     rng.uniform(28.0, 40.0), mat_w, mat_l)
            info["pastures"] += 1
        elif kind == "crops":
            for j in range(3):
                PR.hayrick(LS, acc, x + rng.uniform(-16, 16),
                           y + rng.uniform(-14, 14), None, rng,
                           _m(LS, "prop"), w=rng.uniform(2.8, 3.6),
                           h=rng.uniform(3.0, 4.2))
            PR.plough_rest(LS, acc, x + 5.0, y + 5.0, None, rng, mat_w)
        elif kind == "mill":
            _mill(LS, acc, rng, x, y, rot, mat_w, mat_s, mat_r)
        elif kind == "lumber":
            _woodyard(LS, acc, rng, x, y, rot, mat_w)
            info["yards"] += 1
        elif kind == "quarry":
            _quarry(LS, acc, rng, x, y, mat_w, mat_s)
        elif kind == "ruin":
            _ruin(LS, acc, rng, x, y, rot, mat_s)
        ob = acc.push("land_near_%02d" % k, smooth=False)
        if ob is not None:
            objs.append(ob)

    # --- a second, closer ring of crofts ------------------------------------
    for k in range(48):
        kind = per[(k + 3) % 6][0]
        if kind == "special":
            kind = ("lumber", "quarry", "ruin", "mill")[(k // 6) % 4]
        ang = TAU * (k + rng.uniform(0.1, 0.9)) / 48.0
        acc = LS.Acc()
        acc._mi(mat_w)
        sp = _spot(LS, rp, rng, ang, 1120.0, 1520.0, gap=13.0)
        if sp is None:
            continue
        x, y, z = sp
        rot = ang + rng.uniform(-0.3, 0.3)
        if kind in ("orchard", "garden"):
            w = rng.uniform(26.0, 40.0)
            d = rng.uniform(18.0, 28.0)
            _orchard(LS, acc, rng, x, y, rot, w, d, tb, mat_w)
            info["orchards"] += 1
            info["trees"] += int(max(2, d / 7.0) * max(2, w / 5.6))
        elif kind == "pasture":
            _pasture(LS, acc, rng, x, y, rot, rng.uniform(34.0, 52.0),
                     rng.uniform(24.0, 34.0), mat_w, mat_l)
            info["pastures"] += 1
        elif kind == "crops":
            for j in range(2):
                PR.haystack(LS, acc, x + rng.uniform(-13, 13),
                            y + rng.uniform(-11, 11), None, rng,
                            _m(LS, "prop"), ang=rng.uniform(0, 3.14))
        elif kind == "lumber":
            _woodyard(LS, acc, rng, x, y, rot, mat_w)
            info["yards"] += 1
        elif kind == "quarry":
            _quarry(LS, acc, rng, x, y, mat_w, mat_s)
        else:
            _gate_yard(LS, acc, rng, rp, None, x, y, rot, mat_w, mat_l, mat_e)
            info["yards"] += 1
        ob = acc.push("land_croft_%02d" % k, smooth=False)
        if ob is not None:
            objs.append(ob)

    # --- small ridged plots, the layer that reads as cultivation -----------
    pacc = LS.Acc()
    pacc._mi(mat_c)
    for k in range(150):
        ang = TAU * (k + rng.uniform(0.05, 0.95)) / 150.0
        sp = _spot(LS, rp, rng, ang, 1030.0, 1620.0, gap=7.0)
        if sp is None:
            continue
        x, y, z = sp
        w = rng.uniform(14.0, 34.0)
        d = rng.uniform(11.0, 24.0)
        if rng.random() < 0.5:
            w, d = d, w
        _plot(LS, pacc, rng, x, y, ang + rng.uniform(-0.35, 0.35), w, d,
              mat_d, mat_d, mat_w, mat_l)
        info["plots"] += 1
        if info["plots"] >= 110:
            break
    ob = pacc.push("land_plots", smooth=True)
    if ob is not None:
        objs.append(ob)

    ob = tb.push(LS, "land_orchard_trees", mat_l)
    if ob is not None:
        objs.append(ob)
    return objs, info
