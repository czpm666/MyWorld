"""hd_landscape.py -- the medieval world outside the walls of Ars.

Replaces the flat olive disc (`ground_outer`) and the 22 squashed-sphere
"mountains" with a real landscape: a heightfield that leaves the city plateau
untouched, rolls out into farmland, cuts a river valley, and climbs into
layered mountain ridges with snow and forest.

Entry points
------------
    info = build(MAT, res=20.0, seed=1337, **opts)
        MAT   -- capital.py's material dict (missing keys fall back to the
                 .blend's material names, so MAT={} works too)
        res   -- terrain cell size in metres.  20.0 is the shipping setting
                 (361x361 grid over 7.2 km); 40.0 is a fast draft; 10.0 is a
                 hero still and costs ~1.3M extra faces.
        opts  -- town=True/False, fields=..., woods=..., rings=..., water=...
                 to build only part of the world (used by the test lab).
        returns {"objects", "count", "faces", "tris", "verts", "seconds",
                 "ram_mb", "peak_mb"}.

    n = strip_old(fields=True)
        Deletes `ground_outer`, `hill0..21`, `field*` and `hedge*` (the flat
        decals).  Call it before build().  The city's own `road_out*` stubs are
        kept: this module's roads start exactly where they end.

    z = height(x, y)          terrain height, float or numpy array
    z = heights(xs, ys)       vector form

Wiring into capital.py:build(), after the city geometry and after init_mats():

    import hd_landscape
    hd_landscape.strip_old()
    info = hd_landscape.build(MAT, res=20.0, seed=1337)
    LOG("landscape: %d objects, %d faces, %.1fs"
        % (info["count"], info["faces"], info["seconds"]))

Nothing else has to change: every object is named `land_*`, so a later run can
find and delete them again with strip_old().

Everything is authored in world space; every object sits at the identity
transform and its mesh vertices are absolute.  That is what lets one material
read world Z (snow line) and distance-from-origin (aerial perspective) without
any per-object plumbing.

Object budget: terrain 1, far ridges 1, fields ~1 per 700 m cell, hedges merged
into the field cells, woods ~1 per 600 m cell, roads 1, water 1, buildings ~1
per settlement.  Measured: see `report()`.
"""

import math
import random
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

TAG = "[land]"
_T0 = time.time()


def log(*a):
    print(TAG, *a, flush=True)


# --------------------------------------------------------------------------- #
#  constants
# --------------------------------------------------------------------------- #
CELL = 20.0                       # terrain grid spacing, metres
HALF = 3600.0                     # terrain half-extent -- far ridges take over
FLAT_IN = 700.0                   # brief: dead flat inside 700 m
FLAT_OUT = 900.0                  # props/suburbs live out here at z=0
RIDGE_R = 3600.0                  # first far-ridge loop == terrain boundary
RING_SIDES = 360                  # == int(2*HALF/CELL)
# The far-field loops are generated adaptively from HALF out to RINGS_MAX; the
# step is chosen so the ground never rises or falls more than TARGET_DZ between
# two loops (see _build_rings).
RINGS_MAX = 23000.0
RINGS = (RINGS_MAX,)
TARGET_DZ = 26.0
MIN_STEP = 26.0
MAX_STEP = 900.0

FARM_IN = 940.0
FARM_OUT = 2100.0

_SEED = 1337

# --------------------------------------------------------------------------- #
#  the city outline
# --------------------------------------------------------------------------- #
#  capital.py builds a 20-gon outer wall, not a circle: radius R_OUTER with a
#  3 % jitter per vertex, from random.Random(SEED + 61).  The landscape apron
#  follows that polygon (see _pre), so the edge of the town never reads as a
#  drawn circle, and the wall foot is flat right up to the masonry.
R_OUTER = 947.2                   # capital.py: 640.0 * CITY_SCALE (1.48)
OUTER_N = 20
CITY_JIT = 0.03
CITY_SEED = 20261022
_CITY = {}

# material key -> name used in capital_v23.blend (MAT dict may be empty)
FALLBACK = {
    "grass": "grass_dry", "hill": "hill_far", "hill_dark": "hill_far_dark",
    "earth": "earth", "rock": "rock_cliff", "leaf": "leaf",
    "leaf_dark": "leaf_dark", "water": "water", "stone": "stone",
    "stone_warm": "stone_sand", "wood": "timber", "wood_dark": "timber_dark",
    "tile": "roof_tile", "tile_blue": "roof_slate", "plaster": "plaster",
    "cobble": "cobble", "flag": "flag", "thatch": "thatch.001",
    "sand": "sand", "moat": "moat_water", "bark": "wood_bark",
}

# palette, sRGB hex
#
# The ground palette is deliberately narrow in *hue*: everything from the
# meadow through the crops sits between 38 and 70 degrees, so the farmland
# reads as one kind of earth seen in different states, never as a colour card.
# Separation is carried by value (0.25 rock-face to 0.92 snow, a 3.6:1 swing)
# and by saturation, not by hue jumps -- a field of winter wheat is a *dark
# grey-green*, a field of fallow is a *pale buff*, and both are the same hue
# family as the grass between them.
P = {
    "meadow": "#6f6c51", "meadow2": "#7a7660", "meadow3": "#5e5c45",
    "forest": "#3b4130", "forest2": "#474c37",
    "rock": "#8e887c", "rock2": "#6c675e", "scree": "#9c968a",
    "snow": "#e8e9e8", "frost": "#c9cfcb",
    "wheat": "#767a62", "rye": "#75735f", "rape": "#807d5a",
    "pasture": "#6b7058", "plough": "#4f4736", "vine": "#5d6049",
    "fallow": "#8a8068", "green": "#6c7050", "root": "#5f614a",
    "stubble": "#877e64", "hay": "#918869",
    "hedge": "#333a26", "hedge2": "#3f4830",
    "wall": "#8b867c", "wall2": "#6a655c",
    "sand": "#9d917a", "silt": "#857b63",
    "water": "#2b3c44", "shore": "#54797a",
    "haze": "#8ea2b8",
    "road": "#87795e", "road_d": "#5a4e3a", "verge": "#6c704c",
    "tile": "#8f5a44", "tile_blue": "#58646e", "thatchc": "#ab9767",
    "timber": "#6b4f34", "timber_d": "#453224", "plaster": "#cfc4ae",
    "leaf": "#3a4526", "wood_dark": "#3c2e22",
}


def srgb(hexstr):
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        v = int(h[i:i + 2], 16) / 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return np.array(out, dtype=np.float64)


def rgb(key):
    return srgb(P[key])


# --------------------------------------------------------------------------- #
#  vectorised value noise
# --------------------------------------------------------------------------- #
def _hash2(ix, iy, s):
    a = (ix * np.int64(73856093)) & 0x3FFFFFFF
    a = a ^ ((iy * np.int64(19349663)) & 0x3FFFFFFF)
    a = a ^ ((np.int64(int(s)) * np.int64(83492791)) & 0x3FFFFFFF)
    a = (a ^ (a >> 13)) & 0x3FFFFFFF
    a = (a * np.int64(1274126177)) & 0x3FFFFFFF
    a = a ^ (a >> 16)
    return (a & 0xFFFFFF).astype(np.float64) / 16777215.0


def vnoise(x, y, freq, s):
    fx = np.asarray(x, dtype=np.float64) * freq
    fy = np.asarray(y, dtype=np.float64) * freq
    x0 = np.floor(fx)
    y0 = np.floor(fy)
    tx = fx - x0
    ty = fy - y0
    x0 = x0.astype(np.int64)
    y0 = y0.astype(np.int64)
    u = tx * tx * (3.0 - 2.0 * tx)
    v = ty * ty * (3.0 - 2.0 * ty)
    n00 = _hash2(x0, y0, s)
    n10 = _hash2(x0 + 1, y0, s)
    n01 = _hash2(x0, y0 + 1, s)
    n11 = _hash2(x0 + 1, y0 + 1, s)
    a = n00 + (n10 - n00) * u
    b = n01 + (n11 - n01) * u
    return a + (b - a) * v


def fbm(x, y, freq, oct, s, gain=0.5, lac=2.03):
    tot = 0.0
    amp = 1.0
    nrm = 0.0
    f = freq
    for i in range(oct):
        tot = tot + vnoise(x, y, f, s + i * 17) * amp
        nrm += amp
        amp *= gain
        f *= lac
    return tot / nrm


def ridged(x, y, freq, oct, s, warp=0.0, gain=0.52):
    if warp:
        wx = (fbm(x, y, freq * 0.55, 3, s + 301) - 0.5) * warp / freq
        wy = (fbm(x, y, freq * 0.55, 3, s + 307) - 0.5) * warp / freq
        x = x + wx
        y = y + wy
    tot = 0.0
    amp = 1.0
    nrm = 0.0
    f = freq
    for i in range(oct):
        v = vnoise(x, y, f, s + i * 29)
        r = 1.0 - np.abs(v * 2.0 - 1.0)
        r = r * r * (3.0 - 2.0 * r)
        tot = tot + r * amp
        nrm += amp
        amp *= gain
        f *= 2.07
    return tot / nrm


def smoothstep(a, lo, hi):
    t = np.clip((np.asarray(a, dtype=np.float64) - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# --------------------------------------------------------------------------- #
#  the river -- a polyline with a descending water surface
# --------------------------------------------------------------------------- #
# (x, y, half width of the carved corridor, channel depth)
# The water *surface* is not authored here -- it is sampled from the terrain
# along this line and forced to fall downstream, so the river can never end up
# floating above the ground or running uphill.
#
# The middle reach is not free: hd_river.py owns a straight harbour channel at
# y = -762 with a 92 m width and water at z = -0.62, cutting right through the
# city, with quay walls, piers and a road bridge.  This polyline therefore runs
# *along* that channel for x in [-1150, +1150] and only bends away outside it,
# so the carved bed and hd_river's channel are the same hole in the ground.
RIVER = [
    (-5600.0, 2400.0, 30.0, 3.9),
    (-4900.0, 2050.0, 30.0, 3.8),
    (-4200.0, 1760.0, 29.0, 3.7),
    (-3600.0, 1530.0, 28.0, 3.6),
    (-3050.0, 1330.0, 27.0, 3.5),
    (-2550.0, 1180.0, 26.0, 3.4),
    (-2100.0, 1050.0, 25.0, 3.3),
    (-1750.0, 880.0, 24.0, 3.2),
    (-1500.0, 620.0, 24.0, 3.1),
    (-1360.0, 330.0, 23.0, 3.0),
    (-1290.0, 20.0, 23.0, 2.9),     # WEST ROAD BRIDGE  (road y = 0)
    (-1250.0, -260.0, 24.0, 2.9),
    (-1210.0, -520.0, 26.0, 2.8),
    (-1180.0, -700.0, 32.0, 2.7),
    (-1150.0, -762.0, 46.0, 2.6),   # hd_river channel, west end
    (-700.0, -762.0, 46.0, 2.6),
    (-350.0, -762.0, 46.0, 2.6),
    (0.0, -762.0, 46.0, 2.6),       # SOUTH ROAD BRIDGE (hd_river.bridge)
    (350.0, -762.0, 46.0, 2.6),
    (700.0, -762.0, 46.0, 2.6),
    (1150.0, -762.0, 46.0, 2.6),    # hd_river channel, east end
    (1250.0, -800.0, 36.0, 2.8),
    (1450.0, -940.0, 31.0, 3.0),
    (1750.0, -1150.0, 30.0, 3.1),
    (2150.0, -1400.0, 30.0, 3.2),
    (2600.0, -1700.0, 31.0, 3.3),
    (3150.0, -2080.0, 32.0, 3.4),
    (3800.0, -2560.0, 33.0, 3.5),
    (4600.0, -3200.0, 34.0, 3.6),
    (5600.0, -4050.0, 36.0, 3.7),
]

# hd_river.py's channel, which the terrain has to agree with
HARBOUR_Y = -762.0
HARBOUR_HW = 46.0
HARBOUR_X = 1150.0
HARBOUR_Z = -0.62

_RIV = {}


def _catmull(pts, n_per):
    """Resample a list of tuples through a Catmull-Rom spline."""
    p = np.asarray(pts, dtype=np.float64)
    k = p.shape[1]
    q = np.vstack([p[0] * 2 - p[1], p, p[-1] * 2 - p[-2]])
    out = []
    for i in range(len(p) - 1):
        a, b, c, d = q[i], q[i + 1], q[i + 2], q[i + 3]
        for j in range(n_per):
            t = j / float(n_per)
            t2 = t * t
            t3 = t2 * t
            out.append(0.5 * ((2 * b) + (-a + c) * t
                              + (2 * a - 5 * b + 4 * c - d) * t2
                              + (-a + 3 * b - 3 * c + d) * t3))
    out.append(p[-1])
    return np.asarray(out)


def _river_arrays(seed):
    if "px" in _RIV and _RIV.get("seed") == seed:
        return _RIV
    _RIV.clear()
    _RIV["seed"] = int(seed)
    s = _catmull(RIVER, 14)
    _RIV["px"] = s[:, 0].copy()
    _RIV["py"] = s[:, 1].copy()
    _RIV["hw"] = s[:, 2].copy()
    _RIV["dp"] = s[:, 3].copy()
    t = np.zeros((s.shape[0], 2))
    t[1:-1] = s[2:, :2] - s[:-2, :2]
    t[0] = s[1, :2] - s[0, :2]
    t[-1] = s[-1, :2] - s[-2, :2]
    ln = np.hypot(t[:, 0], t[:, 1]) + 1e-9
    _RIV["tx"] = t[:, 0] / ln
    _RIV["ty"] = t[:, 1] / ln

    # water surface: a smoothed, strictly falling read of the ground it crosses.
    # A plain has no slope at all, so the smoothing alone leaves the surface at
    # ground level and the river lakes out over half the valley; taking the
    # rolling MINIMUM over the same window and sinking it a further 1.6 m keeps
    # the surface below whatever the banks actually are.
    px, py = _RIV["px"], _RIV["py"]
    g = _pre(px, py)
    K = 12
    pad = np.pad(g, K, mode="edge")
    sm = np.convolve(pad, np.ones(2 * K + 1) / (2 * K + 1), mode="same")[K:-K]
    rmin = np.array([pad[k:k + 2 * K + 1].min() for k in range(g.size)])
    w = np.minimum(sm - 1.05, rmin - 1.60)

    # The harbour reach is not ours to invent.  hd_river.py cuts a straight
    # channel at y = -762, 92 m wide, with water at z = -0.62, and builds its
    # quay walls, piers and the south road bridge to that level.  Meet it
    # exactly there, and let the river fall away on both sides of the reach.
    inH = (np.abs(px) <= HARBOUR_X + 40.0) & (np.abs(py - HARBOUR_Y) < 120.0)
    k0 = k1 = -1
    if inH.any():
        k0 = int(np.argmax(inH))
        k1 = int(inH.size - 1 - np.argmax(inH[::-1]))
        w[k0:k1 + 1] = HARBOUR_Z
        # upstream inches down to the harbour, downstream away from it, so the
        # water surface has no step at either end of the reach
        n = k0
        if n:
            w[:n] = np.maximum(w[:n], HARBOUR_Z + 0.02 * np.arange(n, 0, -1))
        n = w.size - 1 - k1
        if n:
            w[k1 + 1:] = np.minimum(w[k1 + 1:],
                                    HARBOUR_Z - 0.02 * np.arange(1, n + 1))
    for k in range(1, w.size):
        if k0 <= k <= k1:
            continue
        lim = w[k - 1] - 0.02
        if w[k] > lim:
            w[k] = lim
    _RIV["wl"] = w

    # A mere in one of the low basins of the valley floor.  It has to stay well
    # clear of the channel: two water bodies fighting over the same hole in the
    # ground would leave the lake mesh hanging in the air.
    ang = np.radians(np.arange(0.0, 360.0, 8.0))
    rr = np.arange(1500.0, 2400.0, 60.0)
    A, R2 = np.meshgrid(ang, rr, indexing="ij")
    cx = (R2 * np.cos(A)).ravel()
    cy = (R2 * np.sin(A)).ravel()
    dd, _i = _poly_dist(cx, cy, px, py)
    zz = np.where(dd > 520.0, _pre(cx, cy), 1.0e9)
    # and clear of the four roads, which run down the axes
    zz = np.where((np.abs(cx) > 430.0) & (np.abs(cy) > 430.0), zz, 1.0e9)
    j = int(np.argmin(zz))
    _RIV["lake"] = (float(cx[j]), float(cy[j]), 300.0, float(zz[j]) - 2.2)
    return _RIV



def _poly_dist(xs, ys, px, py, chunk=12000):
    """Distance from every (xs,ys) point to a polyline + index of nearest vertex."""
    n = xs.size
    best = np.empty(n)
    idx = np.empty(n, dtype=np.int32)
    for c0 in range(0, n, chunk):
        c1 = min(n, c0 + chunk)
        d2 = ((xs[c0:c1, None] - px[None, :]) ** 2
              + (ys[c0:c1, None] - py[None, :]) ** 2)
        i = np.argmin(d2, axis=1)
        best[c0:c1] = d2[np.arange(c1 - c0), i]
        idx[c0:c1] = i
    return np.sqrt(best), idx


# --------------------------------------------------------------------------- #
#  the height field
# --------------------------------------------------------------------------- #
BANDS = (
    # (radius, width, height, ridge wavelength, octaves, seed offset)
    (1650.0, 260.0, 170.0, 320.0, 4, 21),
    (2400.0, 380.0, 420.0, 540.0, 4, 31),
    (3300.0, 720.0, 780.0, 950.0, 4, 41),
    (4700.0, 1250.0, 1350.0, 1450.0, 4, 51),
)


def _ang_strength(deg):
    """Mountain height by bearing: tall N and W, low to the SE where the river
    leaves.  Everything here is in degrees, 0 = +X, 90 = +Y."""
    m = 0.62 + 0.38 * (0.5 + 0.5 * np.cos(np.radians(deg - 152.0)))
    se = np.clip((np.cos(np.radians(deg - 318.0)) - 0.30) / 0.70, 0.0, 1.0)
    e = np.clip((np.cos(np.radians(deg - 8.0)) - 0.55) / 0.45, 0.0, 1.0)
    return m * (1.0 - 0.30 * se) * (1.0 - 0.08 * e)


def _relief(x, y, seed):
    r = np.hypot(x, y)
    deg = np.degrees(np.arctan2(y, x)) % 360.0
    m = _ang_strength(deg)
    dg = np.radians(deg)
    # distinct massifs with real passes between them, so the skyline is a set of
    # peaks rather than a wall.  Both lobes peak due north; neither is allowed
    # to fall to zero or the range would vanish at that bearing.
    a = 0.5 + 0.5 * np.cos(3.0 * dg + 1.571)
    b = 0.5 + 0.5 * np.cos(5.0 * dg - 1.571)
    massif = 0.40 + 0.60 * np.clip(a * 1.60, 0.0, 1.0) * (0.55 + 0.45 * b)
    s = int(seed)

    # Ranges that meander.  Every band used to sit on a true circle, so from
    # any bearing the skyline was the same smooth arc at the same distance --
    # a wall, not a range.  A 2.9 km wobble of +-620 m on the *radius* pulls
    # each band in and out, and the peaks line up along the wobble instead of
    # along a circle.
    wv = (fbm(x, y, 1.0 / 2900.0, 3, s + 301) - 0.5) * 2.0
    rw = r + wv * 620.0

    h = np.zeros_like(r)
    # --- farmland undulation, 900..2600 m -----------------------------------
    farm = (fbm(x, y, 1.0 / 620.0, 4, s + 7) - 0.5) * 46.0
    farm += (fbm(x, y, 1.0 / 190.0, 3, s + 11) - 0.5) * 7.0
    bump = smoothstep(r, 780.0, 1250.0) * (1.0 - smoothstep(r, 2400.0, 3400.0))
    h += farm * bump
    # --- the far wall: a continuous ring so the horizon is never empty ------
    env = np.exp(-((rw - 9200.0) / 3400.0) ** 2)
    rd0 = ridged(x, y, 1.0 / 2000.0, 4, s + 71, warp=0.80)
    h += env * 1980.0 * (0.44 + 0.56 * m) * (0.42 + 0.58 * rd0 ** 1.35)
    # --- main ranges --------------------------------------------------------
    for bi, (rc, w, H, wl, oc, sd) in enumerate(BANDS):
        env = np.exp(-((rw - rc) / w) ** 2)
        live = env > 0.004
        if not np.any(live):
            continue
        rd = ridged(x, y, 1.0 / wl, oc, s + sd, warp=0.90)
        mm = m * (massif if bi >= 1 else (0.55 + 0.45 * massif))
        # three to five massifs per range, with real passes between them: the
        # crest exponent is what turns a rounded fbm hump into a ridge line.
        ang = np.radians(deg + sd * 1.7)
        lob = 0.58 + 0.42 * np.clip(np.cos((2 + bi) * ang + sd * 0.9), 0.0, 1.0) ** 0.6
        h += env * H * mm * lob * (rd ** 1.65)
    # --- a long ridge that frames the north --------------------------------
    ang = np.radians(deg)
    lobe = (0.5 + 0.5 * np.cos(ang - np.radians(96.0))) ** 3
    h += lobe * np.exp(-((rw - 2350.0) / 620.0) ** 2) * 95.0 * m
    return h


def _riv_seed():
    return int(_RIV.get("seed", _SEED))


def _city_pts():
    """The city's outer ring, rebuilt exactly as capital.outer_ring_pts() does.

    A 20-gon with a 3 % radius jitter per vertex, so the edge of the town is
    neither a circle nor a ring of equal facets.  That matters here: the apron
    of the landscape is keyed to *this* outline, so no radius of the terrain can
    ever read as a drawn circle from above.
    """
    pts = _CITY.get("pts")
    if pts is not None:
        return pts
    rw = random.Random(CITY_SEED + 61)
    pts = []
    for k in range(OUTER_N):
        a = 2.0 * math.pi * (k + 0.5) / OUTER_N + rw.uniform(-0.02, 0.02)
        r = R_OUTER * (1.0 + rw.uniform(-CITY_JIT, CITY_JIT))
        pts.append((r * math.cos(a), r * math.sin(a)))
    P = np.asarray(pts, dtype=np.float64)
    E = np.roll(P, -1, axis=0) - P
    N = np.stack([E[:, 1], -E[:, 0]], axis=1)
    N /= (np.hypot(N[:, 0], N[:, 1])[:, None] + 1e-12)
    _CITY["pts"] = P
    _CITY["nrm"] = N
    return P


def _city_sd(x, y):
    """Signed distance from the city outline, metres; positive outside.

    Convex polygon, so the signed distance is the largest projection onto any
    one edge normal -- 20 vectorised dot products and no square roots.
    """
    P = _city_pts()
    N = _CITY["nrm"]
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    sd = np.full(x.shape, -1.0e9)
    for k in range(P.shape[0]):
        d = (x - P[k, 0]) * N[k, 0] + (y - P[k, 1]) * N[k, 1]
        sd = np.maximum(sd, d)
    return sd


def _apron():
    """Where the ground stops being dead flat, as distance outside the wall.

    capital.py sets FLAT_IN / FLAT_OUT to absolute radii (R_OUTER + 60 and
    R_OUTER + 190) before calling build().  Read them as offsets from the
    outline, but stretch the ramp a long way past them: its own out-roads are
    flat boxes 238 m long drawn at z = 0.07, so the ground has to stay level
    under them, and 190 m of ramp is a visible step from the wall walk.
    """
    a = float(FLAT_IN) - float(R_OUTER)
    b = float(FLAT_OUT) - float(R_OUTER)
    if not (b > a + 20.0):
        a, b = 60.0, 190.0
    a = max(245.0, a)
    b = max(a + 780.0, b)
    return a, b


def _pre(x, y):
    """Ground before the river is cut into it.

    The city's polygon is dead flat at z = 0 and must stay that way: capital.py
    puts every building, its cobbled apron and its harbour quays there at z = 0,
    and its out-road boxes are flat for another 238 m.  Outside that the ground
    rises, but the rise is keyed to the distance from the *wall outline* and
    then broken up by two octaves of noise, so the foot of the hill wanders in
    and out by up to 150 m.  There is no radius in this function, which is the
    whole point.
    """
    sd = _city_sd(x, y)
    a, b = _apron()
    s = _riv_seed()
    n1 = fbm(x, y, 1.0 / 430.0, 4, s + 77)
    n2 = fbm(x, y, 1.0 / 104.0, 3, s + 78)
    wob = (n1 - 0.5) * 150.0 + (n2 - 0.5) * 44.0
    t = smoothstep(sd + wob * 0.42, a, b)
    t *= smoothstep(sd, 4.0, 46.0)          # dead flat at the foot of the wall
    h = _relief(x, y, s) * t
    # Shallow meadow undulation -- about 1.2 m over a 170 m wavelength -- that
    # starts only once we are clear of the flat apron capital.py needs for its
    # out-road boxes.  Without it the first kilometre outside the wall is a
    # sheet of glass under a 48-degree sun: every facet faces the same way, so
    # it takes no shading at all and the eye has nothing to judge distance by.
    u = smoothstep(sd, 235.0, 560.0)
    m = u > 0.004
    if m.any():
        und = (fbm(x[m], y[m], 1.0 / 170.0, 4, s + 91) - 0.5) * 2.2 \
            + (fbm(x[m], y[m], 1.0 / 110.0, 3, s + 92) - 0.5) * 0.6
        h[m] += u[m] * und
    # A one-percent pediment, so the ground keeps climbing gently out of the
    # terrace instead of leaving it as a plinth with a plumb-cut edge.
    h += 0.0060 * np.minimum(np.maximum(sd - 150.0, 0.0), 1500.0) \
        * smoothstep(sd, 150.0, 520.0)
    return h


def _carve(z, x, y):
    """Cut the river corridor, the harbour slot and the lake out of the field."""
    R = _RIV
    px, py = R["px"], R["py"]

    # Outside this box the river cannot reach the ground at all; the far ridge
    # loops are 95 % of the points, so skipping them is most of the build time.
    box = R.get("box")
    if box is None:
        box = (float(px.min()) - 320.0, float(px.max()) + 320.0,
               float(py.min()) - 320.0, float(py.max()) + 320.0)
        R["box"] = box
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    near = ((x > box[0]) & (x < box[1]) & (y > box[2]) & (y < box[3]))
    if not near.all():
        if not near.any():
            return z
        flat = z.ravel()
        sel = np.flatnonzero(near.ravel())
        flat[sel] = _carve_near(flat[sel], x.ravel()[sel], y.ravel()[sel])
        return flat.reshape(z.shape)
    return _carve_near(z, x, y)


def _carve_near(z, x, y):
    R = _RIV
    d, i = _poly_dist(x, y, R["px"], R["py"])
    wl = R["wl"][i]
    hw = R["hw"][i]
    dp = R["dp"][i]

    # --- open country: a real valley ---------------------------------------
    # The ground may not rise away from the water faster than roughly 1 in 8,
    # so a 150 m corridor is pulled down to the bank height and the hills climb
    # back out of it.  This has to stay a *local* cut: an earlier version capped
    # the whole world with a 10 % cone around the polyline, which planed entire
    # mountain ranges down and left a fan of vertical facets where the cone
    # sliced through the peaks.
    wall = wl + 1.6
    tw = np.clip((d - hw) / 150.0, 0.0, 1.0)
    zc = wall + np.maximum(z - wall, 0.0) * (tw ** 1.8)
    z = np.where(d < hw + 150.0, np.minimum(z, zc), z)

    outer = hw * 2.6
    s = np.clip(d / outer, 0.0, 1.0)
    zb = wl - dp + (dp + np.maximum(z - wl, 0.0)) * (s ** 2.6)
    z = np.where(d < outer, np.minimum(z, zb), z)

    # --- inside the walls: a clean slot -----------------------------------
    # hd_river.py owns the quay walls there, so the terrain must not build its
    # own levee: it just drops out of the flat plateau straight into a channel
    # the quays can cover.
    sd = _city_sd(x, y)
    city = 1.0 - smoothstep(sd, -8.0, 30.0)
    if city.any():
        slot = wl - dp + np.maximum(d - hw, 0.0) * 5.5
        z = z * (1.0 - city) + np.minimum(0.0, slot) * city

    # --- the mere ---------------------------------------------------------
    lx, ly, lr, lwl = R["lake"]
    dl = np.sqrt((x - lx) ** 2 + (y - ly) ** 2)
    lt = np.clip(1.0 - dl / lr, 0.0, 1.0)
    lt = lt * lt * (3.0 - 2.0 * lt)
    z = z * (1.0 - lt * 0.94) + (lwl - 3.5) * lt * 0.94
    return z


def heights(xs, ys):
    if "px" not in _RIV:
        _river_arrays(_SEED)
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    shp = xs.shape
    z = _pre(xs.ravel(), ys.ravel())
    return _carve(z, xs.ravel(), ys.ravel()).reshape(shp)


def height(x, y):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 0:
        return float(heights(x.reshape(1), np.asarray([y], dtype=np.float64))[0])
    return heights(x, np.asarray(y, dtype=np.float64))


def h1(x, y):
    return height(float(x), float(y))


def _water_level(x, y):
    R = _RIV
    d, i = _poly_dist(np.array([x], dtype=np.float64),
                      np.array([y], dtype=np.float64), R["px"], R["py"])
    return float(R["wl"][i[0]]), float(d[0]), float(R["hw"][i[0]])


# --------------------------------------------------------------------------- #
#  materials
# --------------------------------------------------------------------------- #
def _get_mat(MAT, key):
    """Resolve a city material by MAT key, then by its real name, and only if
    the scene has neither (a cold factory-startup Blender) make a stand-in."""
    if MAT:
        m = MAT.get(key)
        if m is not None:
            return m
    for name in (FALLBACK.get(key), key):
        if name:
            m = bpy.data.materials.get(name)
            if m is not None:
                return m
    return _std_mat(key)


# flat stand-ins so the module also builds in an empty scene
MATCOL = {
    "plaster": "#cfc4ae", "timber": "#6b4f34", "wood": "#6b4f34",
    "wood_dark": "#3c2e22", "stone": "#8a8478", "stone_warm": "#9a8f78",
    "roof": "#8f5a44", "roof2": "#58646e", "thatch": "#ab9767",
    "cobble": "#8b8579", "leaf": "#35491f", "earth": "#6b5236",
    "grass": "#5a6733", "water": "#1e3742", "rock": "#544d41",
}


def _std_mat(key):
    name = "land_std_" + str(key)
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                bsdf = n
                break
    c = srgb(MATCOL.get(key, "#8a8578"))
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1.0)
        bsdf.inputs["Roughness"].default_value = 0.86
    m.diffuse_color = (c[0], c[1], c[2], 1.0)
    return m


def _nn(nt, kind, loc, **kw):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def _mix(nt, loc, blend="MIX"):
    n = nt.nodes.new("ShaderNodeMixRGB")
    n.blend_type = blend
    n.location = loc
    return n


def _ramp(nt, loc, a, b, lo=0.0, hi=1.0):
    n = nt.nodes.new("ShaderNodeValToRGB")
    n.location = loc
    n.color_ramp.elements[0].position = lo
    n.color_ramp.elements[0].color = a if len(a) == 4 else (a[0], a[1], a[2], 1.0)
    n.color_ramp.elements[1].position = hi
    n.color_ramp.elements[1].color = b if len(b) == 4 else (b[0], b[1], b[2], 1.0)
    return n


def mat_ground():
    """One material for every painted surface: terrain, fields, roads, verges.

    All the *hue* comes from the mesh's `Col` point attribute, which is computed
    in numpy from height, slope, crop type and noise.  The shader only adds
    grain, and the aerial perspective that turns the far ridges pale blue.
    """
    name = "land_ground"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = _nn(nt, "ShaderNodeOutputMaterial", (1400, 0))
    bsdf = _nn(nt, "ShaderNodeBsdfPrincipled", (1100, 0))

    tex = _nn(nt, "ShaderNodeTexCoord", (-1400, 0))
    col = _nn(nt, "ShaderNodeAttribute", (-1400, 300))
    col.attribute_name = "Col"

    # broad patchiness: hedgerow shade / soil warmth at 300-800 m
    n1 = _nn(nt, "ShaderNodeTexNoise", (-1200, -220))
    n1.inputs["Scale"].default_value = 1.0 / 340.0
    n1.inputs["Detail"].default_value = 5.0
    n1.inputs["Roughness"].default_value = 0.62
    nt.links.new(tex.outputs["Object"], n1.inputs["Vector"])
    r1 = _ramp(nt, (-1000, -220), (0.80, 0.83, 0.74), (1.14, 1.12, 1.02))

    # field grain
    n2 = _nn(nt, "ShaderNodeTexNoise", (-1200, -520))
    n2.inputs["Scale"].default_value = 1.0 / 17.0
    n2.inputs["Detail"].default_value = 8.0
    n2.inputs["Roughness"].default_value = 0.72
    nt.links.new(tex.outputs["Object"], n2.inputs["Vector"])
    r2 = _ramp(nt, (-1000, -520), (0.83, 0.85, 0.80), (1.12, 1.10, 1.06))

    # close-up bump grain
    n3 = _nn(nt, "ShaderNodeTexNoise", (-1200, -820))
    n3.inputs["Scale"].default_value = 1.0 / 2.6
    n3.inputs["Detail"].default_value = 6.0
    n3.inputs["Roughness"].default_value = 0.75
    nt.links.new(tex.outputs["Object"], n3.inputs["Vector"])

    mx1 = _mix(nt, (-800, 150), "MULTIPLY")
    mx1.inputs["Fac"].default_value = 0.85
    nt.links.new(col.outputs["Color"], mx1.inputs["Color1"])
    nt.links.new(r1.outputs["Color"], mx1.inputs["Color2"])

    mx2 = _mix(nt, (-600, 60), "OVERLAY")
    mx2.inputs["Fac"].default_value = 0.55
    nt.links.new(mx1.outputs["Color"], mx2.inputs["Color1"])
    nt.links.new(r2.outputs["Color"], mx2.inputs["Color2"])

    # --- aerial perspective, baked into the surface -------------------------
    ln = _nn(nt, "ShaderNodeVectorMath", (-1000, 420))
    ln.operation = "LENGTH"
    nt.links.new(tex.outputs["Object"], ln.inputs[0])
    fade = _nn(nt, "ShaderNodeMapRange", (-800, 420))
    fade.inputs["From Min"].default_value = 3000.0
    fade.inputs["From Max"].default_value = 13000.0
    fade.inputs["To Min"].default_value = 0.0
    fade.inputs["To Max"].default_value = 0.46
    nt.links.new(ln.outputs["Value"], fade.inputs["Value"])

    hz = _nn(nt, "ShaderNodeRGB", (-800, 600))
    hz.outputs[0].default_value = tuple(rgb("haze")) + (1.0,)

    mx3 = _mix(nt, (-400, 300), "MIX")
    nt.links.new(fade.outputs["Result"], mx3.inputs["Fac"])
    nt.links.new(mx2.outputs["Color"], mx3.inputs["Color1"])
    nt.links.new(hz.outputs[0], mx3.inputs["Color2"])

    nt.links.new(mx3.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.93
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.16

    bmp = _nn(nt, "ShaderNodeBump", (800, -600))
    bmp.inputs["Strength"].default_value = 0.32
    bmp.inputs["Distance"].default_value = 0.6
    nt.links.new(n3.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_water_land():
    name = "land_water"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = _nn(nt, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _nn(nt, "ShaderNodeBsdfPrincipled", (600, 0))
    tex = _nn(nt, "ShaderNodeTexCoord", (-900, 0))
    col = _nn(nt, "ShaderNodeAttribute", (-900, 260))
    col.attribute_name = "Col"
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.17
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.333
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.36
    n = _nn(nt, "ShaderNodeTexNoise", (-900, -320))
    n.inputs["Scale"].default_value = 1.0 / 9.0
    n.inputs["Detail"].default_value = 5.0
    nt.links.new(tex.outputs["Object"], n.inputs["Vector"])
    bmp = _nn(nt, "ShaderNodeBump", (300, -400))
    bmp.inputs["Strength"].default_value = 0.14
    bmp.inputs["Distance"].default_value = 0.35
    nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


# --------------------------------------------------------------------------- #
#  mesh construction
# --------------------------------------------------------------------------- #
def _link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mk_obj(name, verts, faces, mats, face_mats=None, smooth=True, vcol=None):
    me = bpy.data.meshes.new(name)
    V = np.asarray(verts, dtype=np.float64)
    if V.ndim != 2 or V.shape[1] != 3:
        V = V.reshape(-1, 3)
    nv = len(V)
    me.vertices.add(nv)
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())

    if isinstance(faces, np.ndarray):
        A = faces
        nf = int(A.shape[0])
        k0 = int(A.shape[1])
        uniform = True
    else:
        k0 = len(faces[0])
        nf = len(faces)
        uniform = (sum(len(f) for f in faces) == k0 * nf)
        A = None
    if uniform:
        F = (A if A is not None else np.asarray(faces, dtype=np.int32))
        F = F.astype(np.int32, copy=False).ravel()
        me.loops.add(len(F))
        me.loops.foreach_set("vertex_index", F)
        me.polygons.add(nf)
        me.polygons.foreach_set(
            "loop_start", np.arange(0, len(F), k0, dtype=np.int32))
        try:
            me.polygons.foreach_set(
                "loop_total", np.full(nf, k0, dtype=np.int32))
        except Exception:                                        # noqa: BLE001
            pass
    else:
        ls, lt, vi = [], [], []
        c = 0
        for f in faces:
            ls.append(c)
            lt.append(len(f))
            vi.extend(int(x) for x in f)
            c += len(f)
        me.loops.add(len(vi))
        me.loops.foreach_set("vertex_index", np.asarray(vi, dtype=np.int32))
        me.polygons.add(len(faces))
        me.polygons.foreach_set("loop_start", np.asarray(ls, dtype=np.int32))
        me.polygons.foreach_set("loop_total", np.asarray(lt, dtype=np.int32))
    me.update(calc_edges=True)

    if vcol is not None:
        ca = me.color_attributes.new(name="Col", type="FLOAT_COLOR",
                                     domain="POINT")
        ca.data.foreach_set("color", np.asarray(vcol, dtype=np.float32).ravel())
    for m in mats:
        me.materials.append(m)
    if face_mats is not None and len(mats) > 1:
        me.polygons.foreach_set("material_index",
                                np.asarray(face_mats, dtype=np.int32))
    if smooth:
        me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons),
                                                      dtype=np.int32))
    me.update()
    ob = bpy.data.objects.new(name, me)
    return _link(ob)


def set_normals(ob, N):
    try:
        ob.data.normals_split_custom_set_from_vertices(
            [tuple(v) for v in np.asarray(N, dtype=np.float64)])
    except Exception:                                            # noqa: BLE001
        pass


class Acc(object):
    """Accumulator for hand-built props: world-space verts, per-face material."""

    __slots__ = ("v", "f", "m", "mats", "c")

    def __init__(self):
        self.v = []
        self.f = []
        self.m = []
        self.mats = []
        self.c = []

    def _mi(self, mat):
        if mat is None:
            mat = self.mats[0] if self.mats else None
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def poly(self, pts, mat, col=None):
        i = len(self.v)
        self.v.extend(pts)
        for k in range(len(pts)):
            self.c.append(col[k] if isinstance(col, list) else col)
        self.f.append(tuple(range(i, i + len(pts))))
        self.m.append(self._mi(mat))

    def tri(self, a, b, c, mat, col=None):
        self.poly([a, b, c], mat, col)

    def quad(self, a, b, c, d, mat, col=None):
        self.poly([a, b, c, d], mat, col)

    def add(self, verts, faces, mat, T=None, col=None):
        i = len(self.v)
        if T is None:
            self.v.extend(tuple(p) for p in verts)
        else:
            for p in verts:
                self.v.append(tuple(T @ Vector((p[0], p[1], p[2]))))
        if isinstance(col, list):
            n = len(col)
            for k in range(len(verts)):
                self.c.append(col[k] if k < n else col[-1])
        else:
            self.c.extend([col] * len(verts))
        for fi, f in enumerate(faces):
            mm = mat if not isinstance(mat, (list, tuple)) else mat[fi]
            self.f.append(tuple(x + i for x in f))
            self.m.append(self._mi(mm))

    def empty(self):
        return not self.f

    def push(self, name, smooth=True, vcol=True):
        if not self.f:
            return None
        V4 = None
        if vcol and self.c:
            V4 = np.ones((len(self.v), 4), dtype=np.float64)
            V4[:, :3] = np.clip(np.asarray(self.c, dtype=np.float64), 0.0, 1.0)
        return mk_obj(name, self.v, self.f, list(self.mats), self.m,
                      smooth=smooth, vcol=V4)


def boxv(T, sx, sy, sz, z0=None):
    """8 corners of an axis-aligned box, then transformed.  z0 = bottom z
    override (local).  Returns verts, faces."""
    if z0 is None:
        hz = sz * 0.5
        zlo, zhi = -hz, hz
    else:
        zlo, zhi = z0, z0 + sz
    hx, hy = sx * 0.5, sy * 0.5
    v = [(-hx, -hy, zlo), (hx, -hy, zlo), (hx, hy, zlo), (-hx, hy, zlo),
         (-hx, -hy, zhi), (hx, -hy, zhi), (hx, hy, zhi), (-hx, hy, zhi)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


# --------------------------------------------------------------------------- #
#  ground colour -- height / slope / forest / snow, baked to a point attribute
# --------------------------------------------------------------------------- #
SNOW_Z = 1600.0                 # metres above the city plateau


def _tree_line(z):
    """1 below the tree line, 0 above it -- nothing grows on the high rock."""
    return 1.0 - smoothstep(z, 860.0, 1060.0)


def _forest_mask(x, y, seed):
    """0..1, where the world wants trees.  Shared by the terrain shade and by
    the wood planter so the painted forest and the instanced forest agree."""
    s = int(seed)
    n = fbm(x, y, 1.0 / 390.0, 4, s + 205)
    n2 = fbm(x, y, 1.0 / 96.0, 3, s + 211)
    v = n * 0.74 + n2 * 0.26
    thr = 0.585
    return smoothstep(v, thr, thr + 0.13)


def _grad(x, y, e):
    """Analytic central-difference gradient of the height field."""
    return ((heights(x + e, y) - heights(x - e, y)) / (2.0 * e),
            (heights(x, y + e) - heights(x, y - e)) / (2.0 * e))


def _gzs(x, y, e=12.0):
    """Cheap gradient off the built grid (must run after _build_terrain)."""
    if _Z is None:
        gx, gy = _grad(x, y, e)
        return float(gx), float(gy)
    return ((float(_gz(x + e, y)) - float(_gz(x - e, y))) / (2.0 * e),
            (float(_gz(x, y + e)) - float(_gz(x, y - e))) / (2.0 * e))


def _ground_col(X, Y, Z, gx, gy, seed):
    s = int(seed)
    x = X.ravel()
    y = Y.ravel()
    z = Z.ravel()
    gx = gx.ravel()
    gy = gy.ravel()
    n = z.size
    r = np.hypot(x, y)
    slope = np.sqrt(gx * gx + gy * gy)
    sd = _city_sd(x, y)

    t1 = fbm(x, y, 1.0 / 760.0, 4, s + 101)
    t2 = fbm(x, y, 1.0 / 205.0, 4, s + 107)
    t3 = fbm(x, y, 1.0 / 48.0, 3, s + 113)

    c = np.tile(rgb("meadow"), (n, 1))
    m = smoothstep(t1, 0.28, 0.74)[:, None]
    c = c * (1.0 - m) + rgb("meadow2") * m
    m = smoothstep(t2, 0.50, 0.88)[:, None]
    c = c * (1.0 - m) + rgb("meadow3") * m

    # --- woods -------------------------------------------------------------
    # The near belt is gardens and small closes, not woodland: hold the forest
    # tint back until the far side of the fields.
    fm = (_forest_mask(x, y, seed) * _tree_line(z)
          * smoothstep(sd, 340.0, 980.0))
    fc = rgb("forest") * 0.45 + rgb("forest2") * 0.55
    m = (fm * 0.90)[:, None]
    c = c * (1.0 - m) + fc * m

    # --- river silt and valley floors --------------------------------------
    if "px" in _RIV:
        box = _RIV.get("box")
        near = np.ones(n, dtype=bool)
        if box is not None:
            near = ((x > box[0]) & (x < box[1]) & (y > box[2]) & (y < box[3]))
        if near.any():
            d = np.full(n, 1.0e6)
            i = np.zeros(n, dtype=np.int32)
            d[near], i[near] = _poly_dist(x[near], y[near], _RIV["px"], _RIV["py"])
            m = (np.exp(-((d / (_RIV["hw"][i] * 6.0)) ** 2)) * 0.55)[:, None]
            c = c * (1.0 - m) + (rgb("silt") * 0.7 + rgb("pasture") * 0.3) * m

    # --- scrub and gorse patches -------------------------------------------
    m = (smoothstep(t3, 0.34, 0.78) * 0.42)[:, None]
    c = c * (1.0 - m) + rgb("forest2") * m

    # --- dry / lush micro-variation ----------------------------------------
    # 20 m vertex colour is the only thing the ground can show at eye height
    # without a texture, so the value swing has to be readable, not subtle.
    t4 = fbm(x, y, 1.0 / 92.0, 3, s + 131)
    c = c * (0.74 + 0.60 * t4)[:, None]
    t5 = fbm(x, y, 1.0 / 53.0, 3, s + 133)
    c = c * (0.86 + 0.28 * t5)[:, None]
    dry = np.clip((t3 - 0.58) * 2.4, 0.0, 1.0)[:, None]
    c = c * (1.0 - 0.18 * dry) + (c * np.array([1.30, 1.10, 0.70])) * (0.18 * dry)

    # --- the cultivated belt: patches of earth, not one grey sheet -----------
    # Only about a third of the belt carries a geometry parcel; the rest is
    # headland, ley, rough grazing and the ground under a hedge.  If it stayed
    # meadow the parcels would sit on the landscape like stickers, so the
    # ground itself carries a 90..240 m patchwork of stubble, fallow, ley and
    # hay -- the same four states the parcels are cut from.
    belt = (1.0 - smoothstep(r, 2600.0, 3300.0)) * smoothstep(sd, 130.0, 360.0)
    if float(belt.max()) > 0.01:
        p1 = fbm(x, y, 1.0 / 205.0, 4, s + 141)
        q = np.clip((p1 - 0.22) / 0.58, 0.0, 1.0) * 2.999
        i0 = np.clip(q.astype(np.int32), 0, 2)
        fq = (q - i0)[:, None]
        cols = np.array([rgb(k) for k in ("stubble", "fallow", "pasture", "hay")])
        patch = cols[i0] * (1.0 - fq) + cols[i0 + 1] * fq
        p2 = fbm(x, y, 1.0 / 96.0, 3, s + 143)
        patch = patch * (0.90 + 0.20 * p2)[:, None]
        m = (belt * 0.86)[:, None]
        c = c * (1.0 - m) + patch * m

    # --- dry / lush micro-variation ----------------------------------------
    # 20 m vertex colour is the only thing the ground can show at eye height
    # without a texture, so the value swing has to be readable, not subtle --
    # but a +-40 % swing at 92 m is what made the aerial ground read as dirty
    # concrete, so the swing is now a third of what it was and the scale is
    # twice as coarse.
    t4 = fbm(x, y, 1.0 / 148.0, 3, s + 131)
    c = c * (0.86 + 0.28 * t4)[:, None]
    t5 = fbm(x, y, 1.0 / 53.0, 3, s + 133)
    c = c * (0.92 + 0.16 * t5)[:, None]
    dry = np.clip((t3 - 0.58) * 2.4, 0.0, 1.0)[:, None]
    c = c * (1.0 - 0.18 * dry) + (c * np.array([1.22, 1.06, 0.74])) * (0.18 * dry)

    # --- relief shading: steep ground reads darker and rockier ---------------
    m = (smoothstep(slope, 0.16, 0.85) * 0.20)[:, None]
    c = c * (1.0 - m) + rgb("forest2") * m

    # --- alpine turf: green has to leave before the rock does ------------------
    # Otherwise the range stays a green blanket with a white hat on it.
    alp = rgb("pasture") * 0.50 + rgb("scree") * 0.50
    m = (smoothstep(z, 860.0, 1210.0) * 0.80)[:, None]
    c = c * (1.0 - m) + alp * m

    # --- rock on steep ground ----------------------------------------------
    rk = smoothstep(slope, 0.55, 1.30)
    rk = rk * (0.62 + 0.38 * smoothstep(t3, 0.22, 0.78))
    # high ground shows scree and bare rock even where it is not vertical,
    # otherwise every ridge under 800 m reads as a smooth green blanket.
    # Kept deliberately weak (0.30): at 0.66 it painted every ring above 980 m
    # the same flat grey, and the vertex layer has no resolution left at 9 km
    # anyway -- the crisp bedding and the snow line are drawn in the shader,
    # where they do not depend on the mesh at all.
    rk = np.clip(rk + smoothstep(z, 380.0, 980.0) * 0.30
                 * smoothstep(slope, 0.20, 0.70), 0.0, 1.0)
    # Horizontal bedding.  A rock face is never one value, and at 4 km this
    # banding is the only cue left that says "mountain".  0.019 is a 330 m
    # period: the ridge rings are 100-200 m apart, so anything faster aliases
    # into noise instead of reading as a band.
    strata = 0.5 + 0.5 * np.sin(z * 0.019 + t3 * 5.2 + t4 * 3.1)
    rkc = rgb("rock") * (0.78 + 0.36 * strata)[:, None] + rgb("rock2") * 0.30
    m = rk[:, None]
    c = c * (1.0 - m) + rkc * m

    # --- snow ---------------------------------------------------------------
    # Coarse base only; the hard line lives in `land_ground`.
    sl = SNOW_Z + (t2 - 0.5) * 240.0
    snow = smoothstep(z, sl, sl + 170.0) * (1.0 - smoothstep(slope, 0.58, 1.20))
    snow = snow * (0.72 + 0.28 * smoothstep(t3, 0.2, 0.8))
    m = snow[:, None]
    c = c * (1.0 - m) + rgb("snow") * m

    out = np.empty((n, 4), dtype=np.float64)
    # 0.46: an 88 W sun at 48 degrees on a 0.16 albedo pushes the green right
    # into the shoulder of AgX, where a +-30 % albedo swing turns into a 6 %
    # pixel swing and meadow reads as pale cream.  Grass really is dark -- a
    # healthy pasture sits near 0.07 linear in green, not 0.16 -- so the whole
    # ground layer is pulled down to where AgX still has slope to spend.
    #
    # This used to be 0.46 *and* a (0.60, 0.85, 0.68) multiply in
    # `land_ground`.  With the green multiply gone the sum still lands in the
    # right band: measured against the crop parcels, bare ground and a field of
    # winter wheat now sit within 2:1 of each other instead of the parcels
    # floating three times brighter than the ground they sit in.
    out[:, :3] = np.clip(c * 0.46, 0.0, 1.0)
    out[:, 3] = 1.0
    return out


# --------------------------------------------------------------------------- #
#  terrain mesh + far ridge rings
# --------------------------------------------------------------------------- #
def _loop(nside, half):
    """The square boundary, walked counter-clockwise from (-h,-h), with
    nside segments per side.  Point k4nside of the outer terrain loop and point
    k of every ring loop are the same bearing, so bands never twist."""
    t = np.arange(nside) / float(nside)
    side0 = np.stack([-half + 2 * half * t, np.full(nside, -half)], 1)
    side1 = np.stack([np.full(nside, half), -half + 2 * half * t], 1)
    side2 = np.stack([half - 2 * half * t, np.full(nside, half)], 1)
    side3 = np.stack([np.full(nside, -half), half - 2 * half * t], 1)
    return np.vstack([side0, side1, side2, side3])


def _build_terrain(res, mat):
    nx = int(round(2.0 * HALF / float(res))) + 1
    xs = np.linspace(-HALF, HALF, nx)
    X, Y = np.meshgrid(xs, xs, indexing="xy")
    Z = heights(X, Y)
    # The grid *is* the surface, so its own differences are the right normals:
    # the analytic four-sample gradient was four more evaluations of the whole
    # field per vertex and disagreed with the triangles anyway.
    gy, gx = np.gradient(Z, float(res))
    col = _ground_col(X, Y, Z, gx, gy, _RIV["seed"])

    V = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    J = np.arange(nx - 1)
    I = np.arange(nx - 1)
    I, J = np.meshgrid(I, J, indexing="ij")
    I = I.ravel()
    J = J.ravel()
    a = I * nx + J
    b = a + 1
    c = b + nx
    d = a + nx
    faces = np.stack([a, b, c, d], 1)

    ob = mk_obj("land_terrain", V, faces, [mat], vcol=col)
    N = np.stack([-gx.ravel(), -gy.ravel(), np.ones(V.shape[0])], 1)
    N /= np.linalg.norm(N, axis=1)[:, None]
    set_normals(ob, N)
    ob["land_z"] = float(Z.max())
    return ob, Z


def _build_rings(res, mat):
    """The far field, as concentric square loops welded to the terrain edge.

    The radial step is *adaptive*: on a mountain face the height changes fast,
    and a fixed 100 m step turns the slope into a staircase whose facets catch
    the sun in alternating stripes.  So each loop is spaced to keep the height
    change per step near TARGET_DZ; on flat ground the loops stretch out to
    hundreds of metres and cost nothing.

    Everything here is done off the bands themselves -- the step from the
    radial difference to the band below, the normals from the differences
    between neighbouring bands and neighbouring points.  The old version asked
    the height field for an analytic gradient four times per vertex, which was
    most of the build time and gave normals that did not match the triangles.
    """
    nside = int(round(2.0 * HALF / float(res)))
    limit = max(RINGS)
    loops = [_loop(nside, HALF)]
    hs = [HALF]
    zs = [heights(loops[0][:, 0], loops[0][:, 1])]
    h = HALF
    while h < limit - 1.0 and len(loops) < 150:
        step = MAX_STEP
        if len(zs) >= 2:
            dr = max(hs[-1] - hs[-2], 1e-3)
            g = np.abs(zs[-1] - zs[-2]) / dr
            arc = 8.0 * hs[-1] / nside
            gt = np.abs(np.roll(zs[-1], -1) - zs[-1]) / arc
            step = float(np.clip(TARGET_DZ / max(1e-3, 1.15 * float(np.max(
                np.maximum(g, gt)))), MIN_STEP, MAX_STEP))
        h = min(h + step, limit)
        loops.append(_loop(nside, h))
        hs.append(h)
        zs.append(heights(loops[-1][:, 0], loops[-1][:, 1]))

    V = []
    C = []
    NN = []
    last = len(loops) - 1
    for li, lp in enumerate(loops):
        x, y, z = lp[:, 0], lp[:, 1], zs[li]
        hh = hs[li]
        arc = 8.0 * hh / nside
        if li == 0:
            rz = (zs[1] - z) / max(hs[1] - hs[0], 1e-3)
        elif li == last:
            rz = (z - zs[last - 1]) / max(hs[last] - hs[last - 1], 1e-3)
        else:
            rz = (zs[li + 1] - zs[li - 1]) / max(hs[li + 1] - hs[li - 1], 1e-3)
        tz = (np.roll(z, -1) - np.roll(z, 1)) / (2.0 * arc)
        tx = (np.roll(x, -1) - np.roll(x, 1)) / (2.0 * arc)
        ty = (np.roll(y, -1) - np.roll(y, 1)) / (2.0 * arc)
        gx = tz * tx + rz * (x / hh)
        gy = tz * ty + rz * (y / hh)
        V.append(np.stack([x, y, z], 1))
        C.append(_ground_col(x, y, z, gx, gy, _RIV["seed"]))
        N = np.stack([-gx, -gy, np.ones(z.size)], 1)
        N /= np.linalg.norm(N, axis=1)[:, None]
        NN.append(N)
    L = len(loops[0])
    faces = []
    for li in range(len(loops) - 1):
        o0 = li * L
        o1 = (li + 1) * L
        m = np.arange(L)
        m1 = (m + 1) % L
        faces.append(np.stack([o0 + m, o1 + m, o1 + m1, o0 + m1], 1))
    faces = np.vstack(faces)
    ob = mk_obj("land_ridges", np.vstack(V), faces, [mat], vcol=np.vstack(C))
    set_normals(ob, np.vstack(NN))
    return ob


# --------------------------------------------------------------------------- #
#  ground sampling -- everything laid on the ground uses the *built* surface
# --------------------------------------------------------------------------- #
_Z = None
_MAT = None
_ZRES = 20.0
_FIELDS = []          # exposed for the lab so shots can land inside a real field
_NEARINFO = {}


def _gz(x, y):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if _Z is None:
        return heights(x, y)
    n = _Z.shape[0]
    fx = np.clip((x + HALF) / _ZRES, 0.0, n - 1.001)
    fy = np.clip((y + HALF) / _ZRES, 0.0, n - 1.001)
    j = fx.astype(np.int32)
    i = fy.astype(np.int32)
    tx = fx - j
    ty = fy - i
    a = _Z[i, j] * (1.0 - tx) + _Z[i, j + 1] * tx
    b = _Z[i + 1, j] * (1.0 - tx) + _Z[i + 1, j + 1] * tx
    return a * (1.0 - ty) + b * ty


def _spline(pts, step=10.0):
    p = np.asarray(pts, dtype=np.float64)
    dense = _catmull(p, 24)
    d = np.r_[0.0, np.cumsum(np.hypot(np.diff(dense[:, 0]),
                                      np.diff(dense[:, 1])))]
    L = float(d[-1])
    n = max(2, int(L / step) + 1)
    s = np.linspace(0.0, L, n)
    return np.stack([np.interp(s, d, dense[:, 0]),
                     np.interp(s, d, dense[:, 1])], 1), L


def _tangents(P):
    T = np.zeros_like(P)
    T[1:-1] = P[2:] - P[:-2]
    T[0] = P[1] - P[0]
    T[-1] = P[-1] - P[-2]
    T /= (np.linalg.norm(T, axis=1)[:, None] + 1e-9)
    return T


# --------------------------------------------------------------------------- #
#  roads
# --------------------------------------------------------------------------- #
ROADS = {
    # starts exactly where capital.py's road_out* boxes stop
    "east": [(870.0, 0.0), (1060.0, 55.0), (1310.0, 62.0), (1560.0, -34.0),
             (1880.0, -6.0), (2250.0, 175.0), (2700.0, 520.0),
             (3250.0, 900.0), (3600.0, 1250.0)],
    "north": [(0.0, 882.0), (46.0, 1080.0), (4.0, 1350.0), (-64.0, 1620.0),
              (-30.0, 1900.0), (62.0, 2250.0), (150.0, 2700.0),
              (300.0, 3250.0), (520.0, 3560.0)],
    "west": [(-878.0, 0.0), (-940.0, 7.0), (-1000.0, 0.0), (-1064.0, -12.0),
             (-1200.0, -34.0), (-1400.0, 16.0), (-1650.0, 62.0),
             (-1950.0, 8.0), (-2350.0, 120.0), (-2900.0, 300.0),
             (-3350.0, 620.0)],
    "south": [(0.0, -886.0), (0.0, -905.0), (8.0, -1010.0), (-22.0, -1160.0),
              (22.0, -1360.0), (86.0, -1600.0), (64.0, -1900.0),
              (150.0, -2300.0), (330.0, -2800.0), (560.0, -3300.0)],
}


def _road_cols(width):
    u = np.array([-1.0, -0.66, -0.34, 0.0, 0.34, 0.66, 1.0])
    out = []
    for k in u:
        a = abs(k)
        if a > 0.80:
            c = rgb("verge") * 0.55 + rgb("road") * 0.45
        elif 0.20 < a < 0.62:
            c = rgb("road_d") * 0.85 + rgb("road") * 0.15
        else:
            c = rgb("road")
        out.append(tuple(c))
    return u, out


def _road_mesh(acc, pts, width, lift, mat, step=9.0, crown=0.07):
    P, L = _spline(pts, step)
    T = _tangents(P)
    Nn = np.stack([T[:, 1], -T[:, 0]], 1)
    u, cols = _road_cols(width)
    offs = u * width * 0.5
    C = len(u)
    base = len(acc.v)
    for i in range(len(P)):
        for j in range(C):
            x = P[i, 0] + Nn[i, 0] * offs[j]
            y = P[i, 1] + Nn[i, 1] * offs[j]
            z = float(_gz(x, y)) + lift + crown * (1.0 - u[j] * u[j])
            acc.v.append((x, y, z))
            acc.c.append(cols[j])
    for i in range(len(P) - 1):
        for j in range(C - 1):
            a = base + i * C + j
            b = base + i * C + j + 1
            c = base + (i + 1) * C + j + 1
            d = base + (i + 1) * C + j
            acc.f.append((a, b, c, d))
            acc.m.append(acc._mi(mat))
    return P


# --------------------------------------------------------------------------- #
#  water
# --------------------------------------------------------------------------- #
def _river_mesh(mat, acc=None):
    R = _RIV
    if acc is None:
        acc = Acc()
    acc._mi(mat)
    P = np.stack([R["px"], R["py"]], 1)
    T = _tangents(P)
    Nn = np.stack([T[:, 1], -T[:, 0]], 1)
    u = np.array([-2.70, -2.10, -1.55, -1.00, -0.45, 0.0,
                  0.45, 1.00, 1.55, 2.10, 2.70])
    deep = rgb("water")
    shore = rgb("shore")
    C = len(u)
    base = len(acc.v)
    # hd_river.py owns the harbour: its quays, water and bridge are built at
    # x in [-1100, 1100], so this mesh must stop short of them or the sand
    # banks of the rural river would be laid over the stone quays.
    harb = (np.abs(P[:, 0]) < 1080.0) & (np.abs(P[:, 1] - HARBOUR_Y) < 200.0)
    for i in range(len(P)):
        hw = R["hw"][i]
        wl = R["wl"][i]
        for j, k in enumerate(u):
            a = abs(k)
            t = smoothstep(a, 1.35, 2.55)
            col = deep * (1.0 - t) + shore * t
            acc.v.append((P[i, 0] + Nn[i, 0] * k * hw,
                          P[i, 1] + Nn[i, 1] * k * hw,
                          float(wl) + 0.02))
            acc.c.append(tuple(col))
    for i in range(len(P) - 1):
        if harb[i] and harb[i + 1]:
            continue
        for j in range(C - 1):
            a = base + i * C + j
            b = base + i * C + j + 1
            c = base + (i + 1) * C + j + 1
            d = base + (i + 1) * C + j
            acc.f.append((a, b, c, d))
            acc.m.append(acc._mi(mat))
    return acc


def _lake_mesh(mat):
    lx, ly, lr, lvl = _RIV["lake"]
    acc = Acc()
    acc._mi(mat)
    deep = rgb("water")
    shore = rgb("shore")
    seg = 44
    rings = [0.0, 0.35, 0.62, 0.82, 0.94, 1.0]
    a = np.linspace(0.0, 2.0 * np.pi, seg, endpoint=False)
    wob = 1.0 + 0.11 * np.sin(a * 3.0 + 0.7) + 0.06 * np.sin(a * 7.0 + 2.1)
    base = 0
    for ri, rf in enumerate(rings):
        for j in range(seg):
            t = rf / 1.0
            rr = lr * rf * wob[j]
            col = deep * (1.0 - t * 0.9) + shore * (t * 0.9)
            acc.v.append((lx + rr * np.cos(a[j]), ly + rr * np.sin(a[j]),
                          lvl + 0.02))
            acc.c.append(tuple(col))
    cx = len(acc.v)
    acc.v.append((lx, ly, lvl + 0.02))
    acc.c.append(tuple(deep))
    for j in range(seg):
        acc.f.append((cx, j, (j + 1) % seg))
        acc.m.append(acc._mi(mat))
    for ri in range(len(rings) - 1):
        o0 = ri * seg
        o1 = (ri + 1) * seg
        for j in range(seg):
            j1 = (j + 1) % seg
            acc.f.append((o0 + j, o0 + j1, o1 + j1, o1 + j))
            acc.m.append(acc._mi(mat))
    return acc


# --------------------------------------------------------------------------- #
#  farmland -- BSP patchwork
# --------------------------------------------------------------------------- #
CROPS = ("wheat", "pasture", "plough", "fallow", "root", "green")


def _bsp(rng, x0, y0, x1, y1, depth, out):
    w = x1 - x0
    h = y1 - y0
    stop = (depth >= 12 or max(w, h) < 62.0
            or (max(w, h) < 158.0 and rng.random() < 0.45))
    if stop:
        out.append((x0, y0, x1, y1))
        return
    if w > h * 1.12:
        s = x0 + w * rng.uniform(0.34, 0.66)
        _bsp(rng, x0, y0, s, y1, depth + 1, out)
        _bsp(rng, s, y0, x1, y1, depth + 1, out)
    elif h > w * 1.12:
        s = y0 + h * rng.uniform(0.34, 0.66)
        _bsp(rng, x0, y0, x1, s, depth + 1, out)
        _bsp(rng, x0, s, x1, y1, depth + 1, out)
    else:
        if rng.random() < 0.5:
            s = x0 + w * rng.uniform(0.36, 0.64)
            _bsp(rng, x0, y0, s, y1, depth + 1, out)
            _bsp(rng, s, y0, x1, y1, depth + 1, out)
        else:
            s = y0 + h * rng.uniform(0.36, 0.64)
            _bsp(rng, x0, y0, x1, s, depth + 1, out)
            _bsp(rng, x0, s, x1, y1, depth + 1, out)


def _hedge_run(acc, P, w, h, mat, col, wall=False, step=8.0):
    if len(P) < 2:
        return
    T = _tangents(P)
    Nn = np.stack([T[:, 1], -T[:, 0]], 1)
    zs = _gz(P[:, 0], P[:, 1])
    for i in range(len(P) - 1):
        x0, y0, z0 = P[i, 0], P[i, 1], float(zs[i])
        x1, y1, z1 = P[i + 1, 0], P[i + 1, 1], float(zs[i + 1])
        n0 = (Nn[i, 0] * w * 0.5, Nn[i, 1] * w * 0.5, 0.0)
        n1 = (Nn[i + 1, 0] * w * 0.5, Nn[i + 1, 1] * w * 0.5, 0.0)
        L0 = (x0 - n0[0], y0 - n0[1], z0)
        R0 = (x0 + n0[0], y0 + n0[1], z0)
        L1 = (x1 - n1[0], y1 - n1[1], z1)
        R1 = (x1 + n1[0], y1 + n1[1], z1)
        if wall:
            M0 = (x0, y0, z0 + h)
            M1 = (x1, y1, z1 + h)
            acc.poly([L0, M0, M1, L1], mat, col)
            acc.poly([R0, R1, M1, M0], mat, col)
            acc.poly([L0, L1, R1, R0], mat, col)
        else:
            M0 = (x0, y0, z0 + h)
            M1 = (x1, y1, z1 + h)
            acc.poly([L0, M0, M1, L1], mat, col)
            acc.poly([R0, R1, M1, M0], mat, col)
    # end caps
    x0, y0 = P[0, 0], P[0, 1]
    x1, y1 = P[-1, 0], P[-1, 1]
    n = (Nn[0, 0] * w * 0.5, Nn[0, 1] * w * 0.5, 0.0)
    acc.poly([(x0 - n[0], y0 - n[1], float(zs[0])),
              (x0, y0, float(zs[0]) + h),
              (x0 + n[0], y0 + n[1], float(zs[0]))], mat, col)
    n = (Nn[-1, 0] * w * 0.5, Nn[-1, 1] * w * 0.5, 0.0)
    acc.poly([(x1 + n[0], y1 + n[1], float(zs[-1])),
              (x1, y1, float(zs[-1]) + h),
              (x1 - n[0], y1 - n[1], float(zs[-1]))], mat, col)


def _fields(rng, gmat, roads, seed):
    """BSP the farmland into non-overlapping rectangles and lay each one on the
    ground; hedges and dry-stone walls go on the north and west edges only, so
    every boundary is drawn exactly once."""
    ang = math.radians(16.0)
    ca, sa = math.cos(ang), math.sin(ang)
    S = 2360.0
    leaves = []
    _bsp(rng, -S, -S, S, S, 0, leaves)
    L = np.asarray(leaves, dtype=np.float64)
    uc = (L[:, 0] + L[:, 2]) * 0.5
    vc = (L[:, 1] + L[:, 3]) * 0.5
    cxa = uc * ca - vc * sa
    cya = uc * sa + vc * ca
    wa = L[:, 2] - L[:, 0]
    ha = L[:, 3] - L[:, 1]
    r = np.hypot(cxa, cya)
    ok = (r > 902.0) & (wa > 30.0) & (ha > 30.0)
    # farmland thins out with distance instead of stopping at a circle, so the
    # patchwork dissolves into pasture and hills rather than ending on a seam
    thin = smoothstep(r, 1700.0, 2550.0)
    fr = np.random.default_rng(int(seed) * 977 + 5).random(r.size)
    ok &= fr > thin * 0.94

    za = _gz(cxa, cya)
    ok &= za < 210.0
    gx = (_gz(cxa + 12.0, cya) - _gz(cxa - 12.0, cya)) / 24.0
    gy = (_gz(cxa, cya + 12.0) - _gz(cxa, cya - 12.0)) / 24.0
    ok &= np.hypot(gx, gy) < 0.26
    ok &= _forest_mask(cxa, cya, seed) < 0.46
    lx, ly, lr, _lv = _RIV["lake"]
    ok &= np.hypot(cxa - lx, cya - ly) > lr * 1.15 + 20.0

    rp = np.vstack([_spline(v, 16.0)[0] for v in roads.values()])
    dr, _i = _poly_dist(cxa, cya, rp[:, 0], rp[:, 1])
    ok &= dr > 10.0 + 0.5 * np.minimum(wa, ha)
    dw, _i2 = _poly_dist(cxa, cya, _RIV["px"], _RIV["py"])
    ok &= dw > 96.0

    keep = []
    for k in np.nonzero(ok)[0]:
        keep.append((L[k, 0], L[k, 1], L[k, 2], L[k, 3], cxa[k], cya[k],
                     max(wa[k], ha[k])))

    # group by 800 m cell so each object covers a chunk of countryside
    cells = {}
    for (u0, v0, u1, v1, cx, cy, sz) in keep:
        cells.setdefault((int(math.floor(cx / 800.0)),
                          int(math.floor(cy / 800.0))), []).append(
            (u0, v0, u1, v1, cx, cy))

    hedge_c = rgb("hedge")
    wall_c = rgb("wall")
    out = []
    for (ci, cj), group in sorted(cells.items()):
        acc = Acc()
        acc._mi(gmat)
        for (u0, v0, u1, v1, cx, cy) in group:
            crop = CROPS[rng.randrange(len(CROPS))]
            base = rgb(crop)
            tint = base * rng.uniform(0.87, 1.12)
            w = u1 - u0
            h = v1 - v0
            nu = max(2, int(w / 24.0) + 1)
            nv = max(2, int(h / 24.0) + 1)
            stripes = crop == "wheat" or crop == "plough"
            vs = []
            for i in range(nu):
                s = i / float(nu - 1)
                for j in range(nv):
                    t = j / float(nv - 1)
                    uu = u0 + w * s
                    vv = v0 + h * t
                    x = uu * ca - vv * sa
                    y = uu * sa + vv * ca
                    z = float(_gz(x, y)) + 0.05
                    vs.append((x, y, z))
                    c = tint
                    if stripes:
                        c = c * (1.0 if (j % 2 == 0) else 0.88)
                    # large soft patches inside the field: a real crop is never
                    # one flat colour, and a flat plate reads as a decal
                    c = c * (0.90 + 0.20 * (0.5 + 0.5 * math.sin(x * 0.062)
                                            * math.cos(y * 0.048)))
                    e = min(s, 1.0 - s, t, 1.0 - t)
                    c = c * (0.965 + 0.045 * min(1.0, e * 6.0))
                    acc.v.append((x, y, z))
                    acc.c.append(tuple(c))
            b = len(acc.v) - nu * nv
            for i in range(nu - 1):
                for j in range(nv - 1):
                    a0 = b + i * nv + j
                    a1 = b + (i + 1) * nv + j
                    a2 = b + (i + 1) * nv + j + 1
                    a3 = b + i * nv + j + 1
                    acc.f.append((a0, a1, a2, a3))
                    acc.m.append(acc._mi(gmat))

            # boundary: north (max v) and west (min u) edges
            for edge in (0, 1):
                if edge == 0:
                    p0 = (u0, v1)
                    p1 = (u1, v1)
                else:
                    p0 = (u0, v0)
                    p1 = (u0, v1)
                L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
                n = max(2, int(L / 12.0) + 1)
                pts = []
                for k in range(n):
                    s = k / float(n - 1)
                    uu = p0[0] + (p1[0] - p0[0]) * s
                    vv = p0[1] + (p1[1] - p0[1]) * s
                    pts.append((uu * ca - vv * sa, uu * sa + vv * ca))
                pm = np.asarray(pts)
                if _poly_dist(pm[:, 0], pm[:, 1],
                              rp[:, 0], rp[:, 1])[0].min() < 9.0:
                    continue
                wall = rng.random() < 0.34
                if wall:
                    _hedge_run(acc, np.asarray(pts), 2.6, 1.05, gmat,
                               tuple(wall_c * rng.uniform(0.9, 1.08)),
                               wall=True)
                else:
                    # a hedgerow is 3-5 m thick including its bank and ditch;
                    # at 1-3 km that is the difference between "painted
                    # rectangles" and "field boundaries"
                    hh = rng.uniform(1.4, 2.4)
                    _hedge_run(acc, np.asarray(pts), rng.uniform(3.4, 5.0),
                               hh, gmat,
                               tuple(hedge_c * rng.uniform(0.85, 1.15)))
                    # hedgerow oaks: the thing that turns a patchwork of flat
                    # rectangles into hedgerow country when seen from the air
                    if L > 44.0 and rng.random() < 0.72:
                        nt = max(2, int(L / rng.uniform(34.0, 58.0)))
                        for q in range(nt):
                            if rng.random() < 0.42:
                                continue
                            s = (q + rng.uniform(0.25, 0.75)) / nt
                            x = p0[0] * ca - p0[1] * sa
                            y = p0[0] * sa + p0[1] * ca
                            x1 = p1[0] * ca - p1[1] * sa
                            y1 = p1[0] * sa + p1[1] * ca
                            tx = x + (x1 - x) * s
                            ty = y + (y1 - y) * s
                            hh2 = rng.uniform(9.0, 17.0)
                            lc = tuple(hedge_c * rng.uniform(0.72, 1.20)
                                       + np.array((0.012, 0.020, 0.004)))
                            v, f, c = _tree_geo(rng, 1, hh2, lc,
                                                tuple(rgb("wood_dark")))
                            acc.add(v, f, gmat,
                                    T=(Matrix.Translation((tx, ty,
                                                           float(_gz(tx, ty))))
                                       @ Matrix.Rotation(rng.uniform(0, 6.283),
                                                         4, 'Z')),
                                    col=c)
        ob = acc.push("land_field_%d_%d" % (ci, cj), smooth=False)
        if ob:
            out.append(ob)
    return out, keep, ca, sa


# --------------------------------------------------------------------------- #
#  woods
# --------------------------------------------------------------------------- #
def _cone(verts, faces, cols, cx, cy, cz, r, h, seg, col):
    i0 = len(verts)
    for k in range(seg):
        a = 2.0 * math.pi * k / seg
        verts.append((cx + r * math.cos(a), cy + r * math.sin(a), cz))
        cols.append(col)
    verts.append((cx, cy, cz + h))
    cols.append(col)
    tip = i0 + seg
    for k in range(seg):
        faces.append((i0 + k, i0 + (k + 1) % seg, tip))


def _tree_geo(rng, kind, h, leaf_col, bark_col):
    verts = []
    faces = []
    cols = []
    tr = 0.05 * h + 0.16
    th = h * (0.34 if kind == 0 else 0.46)
    i0 = 0
    for k in range(4):
        a = 2.0 * math.pi * k / 4 + 0.4
        verts.append((tr * math.cos(a), tr * math.sin(a), -0.4))
        cols.append(bark_col)
    for k in range(4):
        a = 2.0 * math.pi * k / 4 + 0.4
        verts.append((tr * 0.7 * math.cos(a), tr * 0.7 * math.sin(a), th))
        cols.append(bark_col)
    for k in range(4):
        k1 = (k + 1) % 4
        faces.append((i0 + k, i0 + k1, i0 + 4 + k1, i0 + 4 + k))
    if kind == 0:
        for k, (fz, fr) in enumerate(((0.30, 0.30), (0.53, 0.235),
                                      (0.75, 0.155))):
            _cone(verts, faces, cols, 0.0, 0.0, h * fz, h * fr,
                  h * (0.40 - 0.06 * k), 6, leaf_col)
    else:
        for (bz, br) in ((0.58, 0.30), (0.80, 0.21)):
            cx, cy, cz = 0.0, 0.0, h * bz
            r = h * br
            i0 = len(verts)
            verts.extend([(cx, cy, cz + r * 1.15),
                          (cx, cy, cz - r * 0.85)])
            cols.extend([leaf_col, leaf_col])
            for k in range(5):
                a = 2.0 * math.pi * k / 5
                verts.append((cx + r * math.cos(a), cy + r * math.sin(a), cz))
                cols.append(leaf_col)
            for k in range(5):
                a = i0 + 2 + k
                b = i0 + 2 + (k + 1) % 5
                faces.append((i0, a, b))
                faces.append((i0 + 1, b, a))
    return verts, faces, cols


def _woods(rng, gmat, fields, cell=1020.0, seed=1337):
    """Woodland, hedgerow oaks, poplars and orchards, in three LOD bands.

    The old version built every tree at one detail level with a Python loop
    around mathutils matrices, which is why 20 000 trees cost four seconds and
    still read as lollipops.  Here each species/LOD pair is one numpy batch:
    a 500-triangle oak for the rows you can walk up to, and an 18-triangle
    crossed-card tree for the far hillside, which is all that shows at 3 km.
    """
    import hd_landscape_geo as G
    gr = np.random.default_rng(int(seed) * 7919 + 13)

    fca = np.array([[math.cos(f.ang), math.sin(f.ang)] for f in fields])
    hue = np.array([f.w * 0.5 for f in fields])
    hve = np.array([f.d * 0.5 for f in fields])
    fcx = np.array([f.cx for f in fields])
    fcy = np.array([f.cy for f in fields])

    lx, ly, lr, _l = _RIV["lake"]
    resp = np.stack([_RIV["px"], _RIV["py"]], 1)
    road_pts = [np.asarray(_spline(p, 14.0)[0], dtype=np.float64)
                for p in ROADS.values()]

    # one bucket per (species, lod); they are pushed as one object per cell
    out = []
    ncell = int(HALF / cell) + 1
    for ci in range(-ncell, ncell):
        for cj in range(-ncell, ncell):
            x0 = ci * cell
            y0 = cj * cell
            step = 30.0
            gx, gy = np.meshgrid(np.arange(x0, x0 + cell, step),
                                 np.arange(y0, y0 + cell, step),
                                 indexing="xy")
            px = (gx + gr.uniform(-9.0, 9.0, gx.shape)).ravel()
            py = (gy + gr.uniform(-9.0, 9.0, gy.shape)).ravel()
            r = np.hypot(px, py)
            if not np.any(r < 3400.0):
                continue
            zg = _gz(px, py)
            sd = _city_sd(px, py)
            fm = _forest_mask(px, py, seed)
            dens = np.clip((fm - 0.24) / 0.38, 0.0, 1.0) * _tree_line(zg)
            # a thin scatter of hedgerow oaks and copses everywhere below the
            # tree line, so the valley is not bare pasture with woods in clumps
            dens += (smoothstep(sd, 420.0, 900.0)
                     * (1.0 - smoothstep(zg, 620.0, 900.0)) * 0.075)
            dens *= 1.0 - smoothstep(r, 3300.0, 3550.0)
            ok = dens > gr.random(px.size) * 1.05
            d, _i = _poly_dist(px, py, resp[:, 0], resp[:, 1])
            ok &= d > 26.0
            ok &= np.hypot(px - lx, py - ly) > lr * 1.15
            ok &= sd > 26.0
            for rr in road_pts:
                dd = np.empty(px.size)
                for k in range(0, px.size, 4096):
                    k1 = min(px.size, k + 4096)
                    dd[k:k1] = np.hypot(rr[None, :, 0] - px[k:k1, None],
                                        rr[None, :, 1] - py[k:k1, None]).min(1)
                ok &= dd > 11.0
            if fields:
                du = ((px[:, None] - fcx[None, :]) * fca[None, :, 0]
                      + (py[:, None] - fcy[None, :]) * fca[None, :, 1])
                dv = (-(px[:, None] - fcx[None, :]) * fca[None, :, 1]
                      + (py[:, None] - fcy[None, :]) * fca[None, :, 0])
                inside = (np.abs(du) < (hue[None, :] + 2.5)) & \
                         (np.abs(dv) < (hve[None, :] + 2.5))
                ok &= ~inside.any(1)
            if not np.any(ok):
                continue
            xs = px[ok]
            ys = py[ok]
            zs = zg[ok]
            rs = r[ok]
            sds = sd[ok]

            # --- species ---------------------------------------------------
            # spruce on the high ground, poplar along the water, orchard in the
            # near belt, oak everywhere else
            kind = np.full(xs.size, G.OAK, dtype=np.int32)
            kind[zs > 330.0] = G.SPRUCE
            wet = (d[ok] < 140.0) | (np.hypot(xs - lx, ys - ly) < lr * 1.35)
            kind[wet] = G.POPLAR
            near = sds < 430.0
            kind[near & (gr.random(xs.size) < 0.55)] = G.ORCHARD

            # --- LOD -------------------------------------------------------
            lod = np.where(rs < 1250.0, 0, np.where(rs < 1900.0, 1, 2))

            acc = Acc()
            acc._mi(gmat)
            bufs = {}
            for kk in range(4):
                for ll in range(3):
                    sel = (kind == kk) & (lod == ll)
                    n = int(sel.sum())
                    if n == 0:
                        continue
                    key = (kk, ll)
                    if key not in bufs:
                        bufs[key] = G.TBuf()
                    V0, F0, shade = G.tree_template(kk, ll, seed)
                    hgt = (gr.uniform(7.5, 18.0, n) if kk != G.SPRUCE
                           else gr.uniform(9.0, 22.0, n))
                    if kk == G.ORCHARD:
                        hgt = gr.uniform(3.4, 5.6, n)
                    if kk == G.POPLAR:
                        hgt = gr.uniform(13.0, 24.0, n)
                    base = (rgb("leaf") if kk != G.ORCHARD
                            else rgb("hedge2"))
                    tcol = np.clip(base[None, :] * gr.uniform(0.78, 1.20, (n, 1)),
                                   0.0, 1.0)
                    bufs[key].add_many(V0, F0, shade, xs[sel], ys[sel], zs[sel],
                                       gr.uniform(0.0, 6.283, n),
                                       hgt / 10.0, tcol)
            for key, bf in bufs.items():
                ob = bf.push(self_module(), "land_wood_%d_%d_%d_%d"
                             % (ci, cj, key[0], key[1]), gmat)
                if ob is not None:
                    out.append(ob)
    return out


def self_module():
    import sys
    return sys.modules[__name__]


# --------------------------------------------------------------------------- #
#  settlement kit -- low-poly, all world space, vertex coloured
# --------------------------------------------------------------------------- #
GBL = {}


def _cyl(verts, faces, cols, x, y, z0, r0, r1, h, seg, col, cap=True):
    i0 = len(verts)
    for k in range(seg):
        a = 2.0 * math.pi * k / seg
        verts.append((x + r0 * math.cos(a), y + r0 * math.sin(a), z0))
        cols.append(col)
    if r1 <= 0.02:
        verts.append((x, y, z0 + h))
        cols.append(col)
        for k in range(seg):
            faces.append((i0 + k, i0 + (k + 1) % seg, i0 + seg))
        return
    for k in range(seg):
        a = 2.0 * math.pi * k / seg
        verts.append((x + r1 * math.cos(a), y + r1 * math.sin(a), z0 + h))
        cols.append(col)
    for k in range(seg):
        k1 = (k + 1) % seg
        faces.append((i0 + k, i0 + k1, i0 + seg + k1, i0 + seg + k))
    if cap:
        faces.append(tuple(i0 + seg + k for k in range(seg)))


def _ground(x, y, drop=0.35):
    return float(_gz(x, y)) - drop


def _cottage(acc, rng, x, y, rot, w, d, h, stone=False, thatch=False,
             barn=False):
    z = _ground(x, y)
    T = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, 'Z')
    wm = GBL["stone"] if stone else GBL["plaster"]
    if barn:
        rm = GBL["thatch"]
    else:
        rm = GBL["thatch"] if thatch else (
            GBL["roof2"] if rng.random() < 0.28 else GBL["roof"])
    cw = tuple(rgb("plaster") * rng.uniform(0.84, 1.10))
    if stone or barn:
        cw = tuple(rgb("wall") * rng.uniform(0.88, 1.06))
    cr = tuple(rgb("thatchc") * rng.uniform(0.90, 1.12)) if (thatch or barn) \
        else tuple(rgb("tile") * rng.uniform(0.84, 1.14))
    v, f = boxv(None, w, d, h, z0=0.0)
    acc.add(v, f, wm, T=T, col=cw)
    ov = 0.55
    eave = h
    rise = (d * 0.5 + ov) * (0.86 if barn else 0.80)
    hw, hd = w * 0.5 + ov, d * 0.5 + ov
    rv = [(-hw, -hd, eave), (hw, -hd, eave), (hw, hd, eave), (-hw, hd, eave),
          (-hw, 0.0, eave + rise), (hw, 0.0, eave + rise)]
    acc.add(rv, [(0, 1, 5, 4), (2, 3, 4, 5)], rm, T=T, col=cr)
    acc.add(rv, [(1, 2, 5), (0, 4, 3)], wm, T=T, col=cw)
    if not barn and rng.random() < 0.55:
        acc.add(*boxv(None, 0.8, 0.8, rise * 1.25, z0=eave + rise * 0.15),
                GBL["stone"], T=T @ Matrix.Translation((w * 0.28, d * 0.16, 0.0)),
                col=tuple(rgb("wall2")))


def _chapel(acc, x, y, rot):
    z = _ground(x, y)
    T = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, 'Z')
    cw = tuple(rgb("plaster") * 0.96)
    cr = tuple(rgb("tile_blue") * 0.9)
    acc.add(*boxv(None, 9.0, 17.0, 7.5, z0=0.0), GBL["plaster"], T=T, col=cw)
    rv = [(-5.1, -9.1, 7.5), (5.1, -9.1, 7.5), (5.1, 9.1, 7.5), (-5.1, 9.1, 7.5),
          (-5.1, 0.0, 13.6), (5.1, 0.0, 13.6)]
    acc.add(rv, [(0, 1, 5, 4), (2, 3, 4, 5)], GBL["roof2"], T=T, col=cr)
    acc.add(rv, [(1, 2, 5), (0, 4, 3)], GBL["plaster"], T=T, col=cw)
    TT = T @ Matrix.Translation((0.0, 12.4, 0.0))
    acc.add(*boxv(None, 4.2, 4.2, 15.0, z0=0.0), GBL["stone"], T=TT,
            col=tuple(rgb("wall")))
    v = []
    c = []
    f = []
    _cyl(v, f, c, 0.0, 0.0, 15.0, 2.9, 0.0, 9.0, 8, tuple(rgb("tile_blue") * 0.85))
    acc.add(v, f, GBL["roof2"], T=TT, col=c)


def _windmill(acc, x, y, rot):
    z = _ground(x, y, 0.5)
    T = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, 'Z')
    v, f, c = [], [], []
    st = tuple(rgb("wall"))
    _cyl(v, f, c, 0.0, 0.0, 0.0, 4.9, 3.3, 13.0, 10, st, cap=False)
    _cyl(v, f, c, 0.0, 0.0, 13.0, 3.4, 0.0, 3.4, 10, st)
    acc.add(v, f, GBL["stone"], T=T, col=c)
    # cap + sails
    cap = tuple(rgb("timber_d") * 0.8)
    v = []
    c = []
    f = []
    _cyl(v, f, c, 0.0, 0.0, 16.2, 3.5, 0.3, 2.6, 10, cap)
    acc.add(v, f, GBL["wood_dark"], T=T, col=c)
    for k in range(4):
        a = k * math.pi * 0.5
        TT = (T @ Matrix.Translation((0.0, -3.6, 17.4))
              @ Matrix.Rotation(a, 4, 'Y'))
        acc.add(*boxv(None, 0.55, 0.30, 9.4, z0=0.0), GBL["wood_dark"], T=TT,
                col=cap)
        acc.add(*boxv(None, 0.28, 0.34, 9.4, z0=0.0),
                GBL["wood"], T=TT @ Matrix.Translation((0.0, 0.30, 0.0)),
                col=tuple(rgb("plaster") * 0.9))
    acc.add(*boxv(None, 0.9, 0.9, 1.2, z0=17.0), GBL["wood_dark"], T=T, col=cap)


def _watermill(acc, rng, px, py, tx, ty):
    hw = 30.0
    nx, ny = ty, -tx
    x = px + nx * (hw * 0.55)
    y = py + ny * (hw * 0.55)
    z = _ground(x, y, 0.4)
    rot = math.atan2(ty, tx)
    T = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, 'Z')
    cw = tuple(rgb("plaster") * 0.9)
    acc.add(*boxv(None, 11.0, 8.0, 6.5, z0=0.0), GBL["plaster"], T=T, col=cw)
    rv = [(-6.0, -4.5, 6.5), (6.0, -4.5, 6.5), (6.0, 4.5, 6.5), (-6.0, 4.5, 6.5),
          (-6.0, 0.0, 11.4), (6.0, 0.0, 11.4)]
    acc.add(rv, [(0, 1, 5, 4), (2, 3, 4, 5)], GBL["roof"], T=T,
            col=tuple(rgb("tile") * 0.9))
    acc.add(rv, [(1, 2, 5), (0, 4, 3)], GBL["plaster"], T=T, col=cw)
    # wheel
    wl = float(_RIV["wl"][0])
    for i in range(len(_RIV["px"])):
        if abs(_RIV["px"][i] - px) < 3.0 and abs(_RIV["py"][i] - py) < 3.0:
            wl = float(_RIV["wl"][i])
            break
    wz = min(z, wl + 1.6)
    wv, wf, wc = [], [], []
    wx = -4.5
    wood = tuple(rgb("wood_dark") * 0.9)
    _cyl(wv, wf, wc, wx, 0.0, 0.0, 2.6, 2.6, 0.9, 12, wood, cap=True)
    acc.add(wv, wf, GBL["wood_dark"], T=T @ Matrix.Translation((0.0, 0.0, wz)),
            col=wc)
    for k in range(8):
        a = 2.0 * math.pi * k / 8
        TT = (T @ Matrix.Translation((wx, 0.0, wz))
              @ Matrix.Rotation(a, 4, 'Y'))
        acc.add(*boxv(None, 0.35, 0.5, 2.4, z0=0.0), GBL["wood_dark"], T=TT,
                col=wood)
    # sluice / race
    acc.add(*boxv(None, 26.0, 5.0, 2.2, z0=-2.4),
            GBL["stone"], T=T @ Matrix.Translation((-13.0, 0.0, 0.0)),
            col=tuple(rgb("wall2")))


def _tower(acc, rng, x, y):
    z = _ground(x, y, 0.6)
    v, f, c = [], [], []
    st = tuple(rgb("wall") * 0.94)
    _cyl(v, f, c, 0.0, 0.0, 0.0, 5.2, 4.6, 15.0, 10, st, cap=False)
    n0 = len(v)
    for k in range(10):
        a = 2.0 * math.pi * k / 10
        hh = 15.0 - (2.4 if k in (2, 3) else 0.0) - (4.6 if k == 8 else 0.0)
        v.append((4.6 * math.cos(a), 4.6 * math.sin(a), hh))
        c.append(st)
    for k in range(10):
        k1 = (k + 1) % 10
        f.append((n0 - 10 + k, n0 - 10 + k1, n0 + k1, n0 + k))
    acc.add(v, f, GBL["stone"], col=c)
    for k in range(5):
        a = rng.uniform(0, 6.283)
        rr = rng.uniform(0.0, 5.4)
        acc.add(*boxv(None, rng.uniform(1.2, 3.0), rng.uniform(1.0, 2.4),
                      rng.uniform(0.6, 1.8), z0=0.0),
                GBL["stone"], T=Matrix.Translation(
                    (x + rr * math.cos(a), y + rr * math.sin(a), _ground(x, y))),
                col=tuple(rgb("wall2") * rng.uniform(0.8, 1.06)))


def _bridge(acc, cx, cy, ang, span, width):
    # deck must clear the WATER, not the bed: _gz() at the crossing is the
    # carved channel floor and sits several metres under the surface. The width
    # of the open water depends on the bank slope, so measure it: walk the deck
    # axis and find where the ground actually dives below the water level.
    bed = float(_gz(cx, cy))
    wlv, _dist, hw = _water_level(cx, cy)
    wl = float(wlv)
    ca, sa = math.cos(ang), math.sin(ang)
    lo = hi = 0.0
    for k in range(-90, 91):
        t = k * 2.0
        if float(_gz(cx + t * ca, cy + t * sa)) < wl:
            lo = min(lo, t)
            hi = max(hi, t)
    mid = 0.5 * (lo + hi)
    span = max(hw * 2.0 + 20.0, (hi - lo) + 20.0)
    cx = cx + mid * ca
    cy = cy + mid * sa
    deck_top = wl + 3.05
    T = Matrix.Translation((cx, cy, 0.0)) @ Matrix.Rotation(ang, 4, 'Z')
    st = tuple(rgb("wall"))
    acc.add(*boxv(None, span, width, 1.1, z0=deck_top - 1.1),
            GBL["stone"], T=T, col=st)
    for s in (-1.0, 1.0):
        acc.add(*boxv(None, span, 0.55, 1.05, z0=deck_top),
                GBL["stone"], T=T @ Matrix.Translation((0.0, s * (width * 0.5), 0.0)),
                col=tuple(rgb("wall2")))
    for k in (-0.34, 0.0, 0.34):
        h0 = deck_top - 1.1 - (bed - 1.6)
        acc.add(*boxv(None, 4.4, width * 0.92, h0, z0=bed - 1.6),
                GBL["stone"], T=T @ Matrix.Translation((k * span, 0.0, 0.0)),
                col=tuple(rgb("wall2") * 0.92))


def _farmyard(acc, rng, x, y, rot):
    z = _ground(x, y)
    T = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, 'Z')
    cw = tuple(rgb("timber") * 0.9)
    acc.add(*boxv(None, 22.0, 11.0, 7.0, z0=0.0), GBL["timber"], T=T, col=cw)
    rv = [(-11.6, -5.9, 7.0), (11.6, -5.9, 7.0), (11.6, 5.9, 7.0),
          (-11.6, 5.9, 7.0), (-11.6, 0.0, 12.4), (11.6, 0.0, 12.4)]
    acc.add(rv, [(0, 1, 5, 4), (2, 3, 4, 5)], GBL["thatch"], T=T,
            col=tuple(rgb("thatchc") * 0.95))
    acc.add(rv, [(1, 2, 5), (0, 4, 3)], GBL["timber"], T=T, col=cw)
    for k in range(3):
        hx = rng.uniform(-30.0, -16.0)
        hy = rng.uniform(-9.0, 9.0)
        acc.add(*boxv(None, 1.8, 1.8, 1.4, z0=0.0), GBL["thatch"],
                T=T @ Matrix.Translation((hx, hy, 0.0)),
                col=tuple(rgb("thatchc") * 0.9))


def _hamlet(acc, rng, pts, cx, cy, n, seed=0):
    P, L = _spline(pts, 7.0)
    d = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    i0 = int(np.argmin(d))
    steps = np.r_[0.0, np.cumsum(np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1])))]
    side = 1
    s = 0.0
    made = 0
    while made < n:
        s += rng.uniform(19.0, 29.0)
        k = int(np.searchsorted(steps, steps[i0] + s))
        if k <= 1 or k >= len(P) - 2:
            break
        k0 = max(0, k - 3)
        k1 = min(len(P) - 1, k + 3)
        tx = P[k1, 0] - P[k0, 0]
        ty = P[k1, 1] - P[k0, 1]
        ln = math.hypot(tx, ty) + 1e-9
        tx /= ln
        ty /= ln
        off = rng.uniform(10.0, 17.0)
        x = P[k, 0] + ty * off * side
        y = P[k, 1] - tx * off * side
        gx, gy = _grad(x, y, 8.0)
        if math.hypot(float(gx), float(gy)) > 0.30:
            side = -side
            continue
        rot = math.atan2(ty, tx)
        w = rng.uniform(6.0, 9.5)
        dd = rng.uniform(5.5, 8.0)
        hh = rng.uniform(3.0, 4.6) * (1.25 if rng.random() < 0.3 else 1.0)
        _cottage(acc, rng, x, y, rot + rng.uniform(-0.12, 0.12), w, dd, hh,
                 stone=rng.random() < 0.22, thatch=rng.random() < 0.35)
        side = -side
        made += 1
        if rng.random() < 0.35:
            bx = x - ty * 13.0 * side
            by = y + tx * 13.0 * side
            _cottage(acc, rng, bx, by, rot, rng.uniform(3.4, 4.6),
                     rng.uniform(3.2, 4.4), rng.uniform(2.1, 2.8),
                     thatch=True, stone=rng.random() < 0.5)


def _pick_site(rng, rmin, rmax, slope_max=0.42, high=True):
    best = None
    for _k in range(240):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(rmin, rmax)
        x, y = r * math.cos(a), r * math.sin(a)
        z = float(_gz(x, y))
        gx, gy = _grad(x, y, 14.0)
        if math.hypot(float(gx), float(gy)) > slope_max:
            continue
        if best is None or (z > best[2] if high else z < best[2]):
            best = (x, y, z, a)
    if best is None:
        a = rng.uniform(0, 2 * math.pi)
        r = (rmin + rmax) * 0.5
        x, y = r * math.cos(a), r * math.sin(a)
        return (x, y, float(_gz(x, y)), a)
    return best


def _buildings(rng, roads):
    out = []
    specs = (
        ("land_ham_west", "west", (-1480.0, 30.0), 10),
        ("land_ham_north", "north", (55.0, 1720.0), 8),
        ("land_ham_east", "east", (1580.0, -40.0), 6),
        ("land_ham_south", "south", (70.0, -1440.0), 7),
    )
    for name, key, (cx, cy), n in specs:
        acc = Acc()
        acc._mi(GBL["plaster"])
        _hamlet(acc, rng, ROADS[key], cx, cy, n)
        ob = acc.push(name, smooth=False)
        if ob:
            out.append(ob)

    # chapel in the north hamlet
    acc = Acc()
    acc._mi(GBL["plaster"])
    _chapel(acc, 78.0, 1782.0, math.radians(-8.0))
    out.append(acc.push("land_chapel", smooth=False))

    # farmyard
    acc = Acc()
    acc._mi(GBL["timber"])
    _farmyard(acc, rng, -1210.0, -168.0, math.radians(24.0))
    out.append(acc.push("land_farm", smooth=False))

    # watermill on the river, downstream of the harbour mouth
    best = None
    for i in range(0, len(_RIV["px"]) - 2, 2):
        px, py = _RIV["px"][i], _RIV["py"][i]
        if abs(px) < 1350.0:
            continue
        d = math.hypot(px, py)
        if best is None or d < best[0]:
            best = (d, i)
    if best:
        i = best[1]
        acc = Acc()
        acc._mi(GBL["plaster"])
        _watermill(acc, rng, _RIV["px"][i], _RIV["py"][i],
                   _RIV["tx"][i], _RIV["ty"][i])
        out.append(acc.push("land_watermill", smooth=False))
    return out


def _clip_half(P, yv, keep_ge):
    """Clip a convex polygon against the horizontal line y = yv."""
    out = []
    n = len(P)
    for k in range(n):
        a = P[k]
        b = P[(k + 1) % n]
        ina = (a[1] >= yv) if keep_ge else (a[1] <= yv)
        inb = (b[1] >= yv) if keep_ge else (b[1] <= yv)
        if ina:
            out.append((float(a[0]), float(a[1])))
        if ina != inb:
            t = (yv - a[1]) / (b[1] - a[1])
            out.append((float(a[0] + t * (b[0] - a[0])), float(yv)))
    return out


def _town_floor(mat, z=0.03, inset=0.9):
    """The paved disc inside the outer wall, cut to the real 20-gon.

    capital.py lays its own disc at z = 0 and the height field is also 0 in
    there, which is the ring of z-fighting you can see in the aerial.  The
    polygon replaces it, sits 3 cm proud so it always wins, and stops at the
    wall's centreline where the 2.4 m curtain hides the edge.

    The harbour is cut out of it: hd_river owns the water, the quay walls and
    the bridge there, so the floor must not roof the channel over.
    """
    P = _city_pts()
    c = P.mean(0)
    d = np.hypot(P[:, 0] - c[0], P[:, 1] - c[1]) + 1e-9
    Q = P + (c - P) * (inset / d)[:, None]

    objs = []
    for tag, yv, ge in (("n", HARBOUR_Y + HARBOUR_HW, True),
                        ("s", HARBOUR_Y - HARBOUR_HW, False)):
        S = _clip_half(Q, yv, ge)
        if len(S) < 3:
            continue
        n = len(S)
        sx = sum(p[0] for p in S) / n
        sy = sum(p[1] for p in S) / n
        V = np.zeros((n + 1, 3))
        V[0, 0] = sx
        V[0, 1] = sy
        V[0, 2] = z
        V[1:, 0] = [p[0] for p in S]
        V[1:, 1] = [p[1] for p in S]
        V[1:, 2] = z
        F = np.array([[0, 1 + k, 1 + (k + 1) % n] for k in range(n)],
                     dtype=np.int32)
        col = np.empty((n + 1, 4))
        col[:, 0] = 0.42
        col[:, 1] = 0.38
        col[:, 2] = 0.33
        col[:, 3] = 1.0
        objs.append(mk_obj("land_townfloor_" + tag, V, F, [mat], None,
                           smooth=False, vcol=col))
    return objs


# --------------------------------------------------------------------------- #
#  public API
# --------------------------------------------------------------------------- #
def strip_old(fields=True):
    """Remove capital.py's flat ground disc, the squashed-sphere hills and the
    flat field/hedge decals.  Returns the number of objects deleted."""
    import bpy
    n = 0
    pats = ("ground_outer", "ground_town")
    for ob in list(bpy.data.objects):
        nm = ob.name
        kill = nm in pats
        if not kill and nm.startswith("hill"):
            rest = nm[4:]
            kill = len(rest) > 0 and rest.isdigit()
        if not kill and fields and (nm.startswith("field") or
                                    nm.startswith("hedge")):
            rest = nm[5:] if nm.startswith("field") else nm[5:]
            kill = len(rest) > 0 and rest.split(".")[0].isdigit()
        if not kill and nm.startswith("land_"):
            kill = True
        if kill:
            bpy.data.objects.remove(ob, do_unlink=True)
            n += 1
    log("strip_old: removed %d objects" % n)
    return n


def build(MAT, res=20.0, seed=1337, **opts):
    """Build the whole outer landscape.  Returns a dict with the objects."""
    t0 = time.time()
    global _Z, _ZRES, _MAT
    _MAT = MAT
    rng = random.Random(seed)
    _river_arrays(seed)

    import hd_landscape_mat as LM
    mats = LM.build_all(self_module())
    gmat = mats["ground"]
    wmat = mats["water"]

    GBL.clear()
    GBL.update({
        "plaster": _get_mat(MAT, "plaster"),
        "timber": _get_mat(MAT, "wood"),
        "wood": _get_mat(MAT, "wood"),
        "wood_dark": _get_mat(MAT, "wood_dark"),
        "stone": _get_mat(MAT, "stone"),
        "roof": _get_mat(MAT, "tile"),
        "roof2": _get_mat(MAT, "tile_blue"),
        "thatch": _get_mat(MAT, "thatch"),
        "cobble": _get_mat(MAT, "cobble"),
        "ground_land": gmat,
        "water_land": wmat,
        "crop_land": mats["crop"],
        "leaf_land": mats["leaf"],
        "stone_land": mats["stone"],
        "track_land": mats["track"],
        "soil_land": mats["soil"],
        "prop_land": mats["prop"],
    })
    out = []
    ob, Z = _build_terrain(res, gmat)
    _Z = Z
    _ZRES = (2.0 * HALF) / (Z.shape[0] - 1)
    out.append(ob)
    log("terrain %.2fs" % (time.time() - t0))

    if opts.get("town", True):
        tmat = MAT.get("town_ground") if hasattr(MAT, "get") else None
        if tmat is None:
            tmat = _get_mat(MAT, "cobble")
        out.extend(_town_floor(tmat))
        log("townfloor %.2fs" % (time.time() - t0))

    if opts.get("rings", True):
        out.append(_build_rings(res, gmat))
        log("rings %.2fs" % (time.time() - t0))

    racc = Acc()
    racc._mi(gmat)
    for key in ("east", "north", "west", "south"):
        _road_mesh(racc, ROADS[key], 5.4, 0.20, gmat)
    out.append(racc.push("land_roads", smooth=True))
    log("roads %.2fs" % (time.time() - t0))

    wacc = _river_mesh(wmat)
    ob = wacc.push("land_river", smooth=True)
    if ob is not None:
        out.append(ob)
    out.append(_lake_mesh(wmat).push("land_lake", smooth=True))
    log("water %.2fs" % (time.time() - t0))

    fields = []
    if opts.get("fields", True):
        import hd_landscape_fields as FL
        fields = FL.layout(self_module(), rng, ROADS, seed=seed, size=4300.0)
        fp, finfo, crowns = FL.emit(self_module(), fields, rng)
        out.extend(fp)
        log("fields %d parcels %.2fs" % (len(fields), time.time() - t0))
    else:
        finfo, crowns = {}, []
    _FIELDS[:] = list(fields)

    if opts.get("crowns", True) and crowns:
        import hd_landscape_geo as G
        tb = G.TBuf()
        n = len(crowns)
        X = np.array([c[0] for c in crowns])
        Y = np.array([c[1] for c in crowns])
        Zc = np.asarray(_gz(X, Y), dtype=np.float64)
        V0, F0, shade = G.tree_template(G.OAK, 1, seed)
        COL = np.clip(np.array(rgb("leaf"))[None, :]
                      * np.random.default_rng(seed + 5).uniform(0.80, 1.18, (n, 1)),
                      0.0, 1.0)
        tb.add_many(V0, F0, shade, X, Y, Zc,
                    np.random.default_rng(seed + 6).uniform(0.0, 6.283, n),
                    np.random.default_rng(seed + 7).uniform(0.85, 1.45, n),
                    COL)
        ob = tb.push(self_module(), "land_hedge_oaks", mats["leaf"])
        if ob is not None:
            out.append(ob)
        log("hedge oaks %d %.2fs" % (n, time.time() - t0))

    if opts.get("woods", True):
        out.extend(_woods(rng, gmat, fields, seed=seed))
        log("woods %.2fs" % (time.time() - t0))

    if opts.get("near", True):
        import hd_landscape_near as NR
        nob, ninfo = NR.build(self_module(), rng, ROADS, fields=fields)
        out.extend(nob)
        _NEARINFO.clear()
        _NEARINFO.update(ninfo)
        log("near %s %.2fs" % (ninfo, time.time() - t0))

    if opts.get("marks", True):
        import hd_landscape_marks as MK
        mob, minfo = MK.build(self_module(), rng, ROADS)
        out.extend(mob)
        log("marks %s %.2fs" % (minfo.get("marks"), time.time() - t0))

    if opts.get("buildings", True):
        out.extend(_buildings(rng, None))
        log("buildings %.2fs" % (time.time() - t0))

    out = [o for o in out if o is not None]
    nf = sum(len(o.data.polygons) for o in out)
    nv = sum(len(o.data.vertices) for o in out)
    ntr = 0
    for o in out:
        for p in o.data.polygons:
            ntr += p.loop_total - 2
    cur, peak = _rss_mb()
    info = {"objects": out, "count": len(out), "faces": nf, "tris": ntr,
            "verts": nv, "seconds": time.time() - t0, "ram_mb": cur,
            "peak_mb": peak,
            "parts": {"fields": finfo if fields else {},
                      "near": ninfo if opts.get("near", True) else {},
                      "marks": minfo.get("n", 0) if opts.get("marks", True)
                      else 0}}
    log("BUILD DONE %d objects, %d faces, %d tris, %.1fs, ram %.0f/%.0f MB"
        % (info["count"], nf, ntr, info["seconds"], cur, peak))
    return info


def _rss_mb():
    """(working set, peak working set) of this process in MB, Windows only."""
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        p = PMC()
        p.cb = ctypes.sizeof(PMC)
        k32 = ctypes.windll.kernel32
        fn = ctypes.windll.psapi.GetProcessMemoryInfo
        # 64-bit: without an explicit restype ctypes truncates the pseudo
        # handle to a signed 32-bit int, the call fails, and the whole thing
        # silently reported 0/0.
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wt.DWORD]
        fn.restype = wt.BOOL
        ok = fn(k32.GetCurrentProcess(), ctypes.byref(p), p.cb)
        if not ok:
            return 0.0, 0.0
        return p.WorkingSetSize / 1048576.0, p.PeakWorkingSetSize / 1048576.0
    except Exception:                                            # noqa: BLE001
        return 0.0, 0.0
