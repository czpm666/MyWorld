"""hd_landscape_fields -- the agricultural belt.

What was there before: a rotated BSP cut 641 rectangles, each a single flat
colour with 24 m alternating rows.  From above it read as a patchwork quilt,
because a field that differs from its neighbour only in hue *is* a patch.

What is here now: a field is a piece of land with real agricultural structure,
from the outside in --

  * a boundary shared with the neighbour: a 3-5 m hedge bank with gaps and a
    wavy top, or a dry stone wall, or post and rail, or a green lane
  * a headland: 1.4-2.3 m of unploughed turnrow carrying a low earth bank, so
    every parcel edge gets a lit crest and a shadow line
  * selions: ridge and furrow at a 2.4-3.6 m pitch, running the long way of
    the parcel

Three levels of detail, by distance from the wall:

  * under ~1340 m  real ridge-and-furrow triangles (one strip per selion, six
                   quads, independent of the selion's length)
  * out to 1.6 km the bank and the boundary are still solid, the crop material
                   paints the ridges from a per-vertex attribute
  * beyond         boundary and material only

Boundaries are *deduplicated*: two parcels sharing an edge emit one hedge, not
two, and parcels are all axis-aligned inside one 16-degree rotated frame so
that shared edges really do coincide.  A district (a 700 m block) then picks one
enclosure style, because that is how the countryside is: hedgerow country next
to stone-wall country.

The attribute `Fur` (FLOAT_COLOR on the field mesh) carries the ridge frame per
vertex:  r = cos(angle) * 0.5 + 0.5, g = sin(angle) * 0.5 + 0.5, b = pitch / 4,
a = (crop id + 0.5) / 16.  `hd_landscape_mat.land_crop` un-packs it, so the
shader knows which way to run the drill marks without a UV in sight.
"""
import math

import numpy as np

import hd_landscape_geo as GEO
from hd_landscape_geo import tq

# crop: colour key, ridge pitch, ridge amplitude, stripe readability,
# build ridge geometry, share far from the city, share near it
CROPS = {
    "wheat":    dict(col="wheat",   p=2.7, amp=0.34, rip=1.00, geo=1, far=0.26, near=0.14),
    "rye":      dict(col="rye",     p=2.9, amp=0.32, rip=0.95, geo=1, far=0.12, near=0.05),
    "rapeseed": dict(col="rape",    p=2.6, amp=0.28, rip=0.85, geo=1, far=0.06, near=0.00),
    "pasture":  dict(col="pasture", p=0.0, amp=0.00, rip=0.20, geo=0, far=0.24, near=0.15),
    "plough":   dict(col="plough",  p=2.5, amp=0.40, rip=1.05, geo=1, far=0.10, near=0.11),
    "fallow":   dict(col="fallow",  p=2.8, amp=0.22, rip=0.55, geo=0, far=0.11, near=0.06),
    "root":     dict(col="root",    p=0.9, amp=0.15, rip=0.70, geo=1, far=0.07, near=0.19),
    "vine":     dict(col="vine",    p=2.2, amp=0.18, rip=0.80, geo=1, far=0.00, near=0.10),
    "orchard":  dict(col="pasture", p=3.4, amp=0.08, rip=0.30, geo=1, far=0.03, near=0.20),
}
CROP_NAMES = tuple(CROPS)
CROP_ID = dict((k, i) for i, k in enumerate(CROP_NAMES))

# How bright a parcel of each crop reads from the air.  This is a proxy for
# height and for how much of the bed the rows shade: rape and rye stand waist
# high and catch the light on their heads, ploughed land is a dark slot between
# its own furrows, a young root crop shows bare soil between every plant.  The
# point is that the belt should separate into parcels by value first and hue
# second -- the painter's complaint was a belt that jumped in hue at constant
# brightness, which is what a colour card is.
TONE = {
    "wheat": 1.12, "rye": 1.16, "rapeseed": 1.18, "pasture": 0.92,
    "plough": 0.74, "fallow": 0.99, "root": 0.86, "vine": 0.88,
    "orchard": 0.95,
}

GRID = 22.0          # ground sampling step inside a parcel, metres
LIFT = 0.12         # parcel surface above the terrain, metres


def _m(LS, key):
    """Resolve a material by short name.  `build()` puts the landscape kit into
    LS.GBL; anything else falls through to the town's material table."""
    m = LS.GBL.get(key + "_land")
    if m is not None:
        return m
    m = LS.GBL.get(key)
    if m is not None:
        return m
    return LS._get_mat(getattr(LS, "_MAT", None), key)


def _pick_crop(rng, t):
    """t = 0 at the wall, 1 at the far edge of the belt."""
    ks = list(CROP_NAMES)
    w = np.array([CROPS[k]["near"] * (1.0 - t) + CROPS[k]["far"] * t
                  for k in ks], dtype=np.float64)
    if w.sum() <= 0.0:
        return "pasture"
    c = np.cumsum(w / w.sum())
    return ks[int(np.searchsorted(c, rng.random() * c[-1]))]


class Field(object):
    """One parcel.  Local frame: +u across the selions, +v along them."""

    __slots__ = ("cx", "cy", "w", "d", "ang", "crop", "farm", "seed", "r",
                 "pitch", "head", "ok")

    def __init__(self, cx, cy, w, d, ang, crop, farm, seed, r):
        self.cx = cx
        self.cy = cy
        self.w = w
        self.d = d
        self.ang = ang
        self.crop = crop
        self.farm = farm
        self.seed = seed
        self.r = r
        self.pitch = CROPS[crop]["p"]
        self.head = 1.35 + min(0.95, 0.0014 * min(w, d))
        self.ok = True

    def world(self, u, v):
        cs, sn = math.cos(self.ang), math.sin(self.ang)
        return (self.cx + u * cs - v * sn, self.cy + u * sn + v * cs)

    def corners(self):
        hw, hd = self.w * 0.5, self.d * 0.5
        return [self.world(-hw, -hd), self.world(hw, -hd),
                self.world(hw, hd), self.world(-hw, hd)]


# --------------------------------------------------------------------------- #
#  layout
# --------------------------------------------------------------------------- #
def _tgt(r):
    """Target parcel size at radius r.

    Not one size everywhere: a medieval belt is a handful of big open fields
    out where the plough teams can turn, a mosaic of small plots and gardens
    against the town, and long strips in between.  A single BSP rule gave every
    parcel 60-200 m, which is why the aerial read as one uniform grid of
    rectangles -- the "paint colour card" the painter objected to was largely
    this, a grid with no scale hierarchy.
    """
    t = (r - 250.0) / 2150.0
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return 44.0 + 128.0 * (t ** 0.72)


def _bsp(rng, x0, y0, x1, y1, depth, out):
    w, h = x1 - x0, y1 - y0
    tgt = _tgt(0.5 * math.hypot(x0 + x1, y0 + y1))
    if depth >= 12 or max(w, h) < tgt:
        out.append((x0, y0, x1, y1))
        return
    # a long thin cell is already a strip field; stop and let the caller split
    # it into selions across the short axis
    if depth >= 3 and max(w, h) > 2.6 * min(w, h) and min(w, h) < tgt * 0.85:
        out.append((x0, y0, x1, y1))
        return
    if max(w, h) < tgt * 1.9 and rng.random() < 0.34:
        out.append((x0, y0, x1, y1))
        return
    if w > h:
        cut = x0 + w * rng.uniform(0.32, 0.68)
        _bsp(rng, x0, y0, cut, y1, depth + 1, out)
        _bsp(rng, cut, y0, x1, y1, depth + 1, out)
    else:
        cut = y0 + h * rng.uniform(0.32, 0.68)
        _bsp(rng, x0, y0, x1, cut, depth + 1, out)
        _bsp(rng, x0, cut, x1, y1, depth + 1, out)


def _strips(rng, r):
    """Cut one cell into 3-6 long parallel strips (条田 / open-field furlongs).

    Strip farming is how a shared plough team worked a furlong: narrow selions
    of different crops side by side inside one boundary.  It is also the only
    way to get a 20-30 m wide parcel that still reads at 900 m, and it breaks
    up the square grid of the BSP without adding any new area.
    """
    x0, y0, x1, y1 = r
    w, h = x1 - x0, y1 - y0
    along_x = w >= h
    n = 3 + int(rng.random() * 4.0)
    out = []
    for i in range(n):
        a, b = i / float(n), (i + 1) / float(n)
        a += rng.uniform(-0.10, 0.10) * (1.0 / n)
        b += rng.uniform(-0.10, 0.10) * (1.0 / n)
        if b - a < 0.10:
            continue
        if along_x:
            out.append((x0 + w * a, y0, x0 + w * b, y1))
        else:
            out.append((x0, y0 + h * a, x1, y0 + h * b))
    return out


def layout(LS, rng, roads, seed=1337, frame_ang=0.279, size=2360.0):
    """Cut the belt into parcels and decide what grows in each.

    Parcels stay aligned inside the rotated frame, and the frame is turned 16
    degrees off the world axes, so no parcel edge is parallel to a street, a
    field in front of it, or the screen.
    """
    raw = []
    _bsp(rng, -size * 0.5, -size * 0.5, size * 0.5, size * 0.5, 0, raw)

    # Some cells are furlongs, not single fields: split them into parallel
    # strips before anything else is decided, so a strip gets its own crop and
    # its own boundary treatment.
    cells = []
    for r in raw:
        w, h = r[2] - r[0], r[3] - r[1]
        rw = 0.5 * math.hypot(r[0] + r[2], r[1] + r[3])
        big = max(w, h) > 130.0 and min(w, h) > 26.0
        if big and rw > 340.0 and rng.random() < 0.42:
            cells.extend(_strips(rng, r))
        else:
            cells.append(r)
    raw = cells
    ca, sa = math.cos(frame_ang), math.sin(frame_ang)

    road_pts = []
    try:
        for k, pts in roads.items():
            P = LS._spline(pts, 14.0)[0]
            if len(P):
                road_pts.append(np.asarray(P, dtype=np.float64))
    except Exception:                                            # noqa: BLE001
        pass
    rp = np.concatenate(road_pts, 0) if road_pts else np.zeros((1, 2))

    try:
        RIV = LS._river_arrays(seed)
        rpx, rpy, rhw = RIV["px"], RIV["py"], RIV["hw"]
        lake = RIV["lake"]
    except Exception:                                            # noqa: BLE001
        rpx = rpy = np.zeros(1)
        rhw = np.ones(1)
        lake = None

    rim = float(getattr(LS, "R_OUTER", 947.2))
    out = []
    for (x0, y0, x1, y1) in raw:
        w, d = x1 - x0, y1 - y0
        if min(w, d) < 24.0:
            continue
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        pts = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1],
                        [cx, cy]], dtype=np.float64)
        wx = pts[:, 0] * ca - pts[:, 1] * sa
        wy = pts[:, 0] * sa + pts[:, 1] * ca
        rmin = float(np.hypot(wx, wy).min())
        # Fields start where the town's own terrace ends -- measured from the
        # wall outline, not from the centre, and pushed in and out by noise so
        # the edge of the farmland is not a ring.
        sd = LS._city_sd(wx, wy)
        edge = 205.0 + 130.0 * (float(LS.vnoise(np.array([cx]), np.array([cy]),
                                                1.0 / 640.0, 91)[0]) - 0.5)
        if float(sd.min()) < edge:
            continue
        if rmin > 3000.0:
            continue
        zz = LS._gz(wx, wy)
        if float(zz[:4].min()) > 250.0:
            continue
        rough = float(zz[:4].max() - zz[:4].min()) > 0.22 * max(w, d)
        mx, my = float(wx[4]), float(wy[4])
        if float(LS._forest_mask(np.array([mx]), np.array([my]), seed)[0]) > 0.58:
            continue
        if len(rp) > 2 and np.min(np.hypot(rp[:, 0] - mx, rp[:, 1] - my)) \
                < 11.0 + 0.28 * min(w, d):
            continue
        if len(rpx) > 2:
            dm = np.hypot(rpx - mx, rpy - my)
            j = int(np.argmin(dm))
            if dm[j] < rhw[j] * 2.2 + 26.0:
                continue
        if lake is not None and math.hypot(mx - lake[0], my - lake[1]) \
                < lake[2] * 1.12 + 20.0:
            continue
        ang = frame_ang + (0.0 if w >= d else math.pi * 0.5)
        out.append([mx, my, w, d, ang, rmin, float(sd.mean()), rough])

    fields = []
    farm = -1
    left = 0
    for o in out:
        mx, my, w, d, ang, rmin, sd, rough = o
        thin = 0.55 * float(LS.smoothstep(np.array([rmin]), 2050.0, 2950.0)[0])
        if rng.random() < thin:
            continue
        if left <= 0:
            farm += 1
            left = int(2 + rng.random() * 6)
        left -= 1
        t = float(LS.smoothstep(np.array([sd]), 340.0, 2100.0)[0])
        # Rough ground still gets a parcel -- just one that is grazed, not
        # ploughed.  Leaving it out is what left bare ground between the
        # furrowed plates in the aerial.
        crop = "pasture" if rough else _pick_crop(rng, t)
        fields.append(Field(mx, my, w, d, ang, crop, farm,
                            int(rng.random() * 1e6), rmin))
    return fields


# --------------------------------------------------------------------------- #
#  emission helpers
# --------------------------------------------------------------------------- #
def _tri(F):
    """Split quads / n-gons into triangles.  Uniform arity keeps `mk_obj` on its
    foreach_set fast path -- the difference between 20 s and 400 s."""
    out = []
    for f in F:
        n = len(f)
        if n == 3:
            out.append(f)
        else:
            for k in range(1, n - 1):
                out.append((f[0], f[k], f[k + 1]))
    return out


def _fur_of(f):
    cs, sn = math.cos(f.ang), math.sin(f.ang)
    return (cs * 0.5 + 0.5, sn * 0.5 + 0.5,
            min(1.0, CROPS[f.crop]["p"] / 4.0),
            (CROP_ID[f.crop] + 0.5) / 16.0)


def _grid(LS, f, head):
    """Sample the parcel interior on a 22 m grid fed through `_gz`, so the
    parcel surface follows the real terrain and its ridges sit on it exactly."""
    hw, hd = f.w * 0.5 - head, f.d * 0.5 - head
    if hw < 1.0 or hd < 1.0:
        return None
    nu = max(1, int(math.ceil(2.0 * hw / GRID)))
    nv = max(1, int(math.ceil(2.0 * hd / GRID)))
    us = np.linspace(-hw, hw, nu + 1)
    vs = np.linspace(-hd, hd, nv + 1)
    U, V = np.meshgrid(us, vs, indexing="ij")
    cs, sn = math.cos(f.ang), math.sin(f.ang)
    X = f.cx + U.ravel() * cs - V.ravel() * sn
    Y = f.cy + U.ravel() * sn + V.ravel() * cs
    Z = LS._gz(X, Y) + LIFT
    return X, Y, Z, nu, nv


def _ring(LS, f, head):
    """The headland band: a quad ring between the parcel edge and the inset."""
    hw, hd = f.w * 0.5, f.d * 0.5
    iw, id_ = hw - head, hd - head
    us = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    inside = [(-iw, -id_), (iw, -id_), (iw, id_), (-iw, id_)]
    P = []
    for (u, v) in us + inside:
        P.append(f.world(u, v))
    X = np.array([p[0] for p in P], dtype=np.float64)
    Y = np.array([p[1] for p in P], dtype=np.float64)
    Z = LS._gz(X, Y) + LIFT
    # The outer four are the parcel edge: they sit on the ground so the
    # headland ramps down and meets it, instead of leaving a lip you could see
    # under from a low camera.
    Z[:4] = LS._gz(X[:4], Y[:4]) + 0.02
    V = list(zip(X.tolist(), Y.tolist(), Z.tolist()))
    F = []
    for k in range(4):
        k1 = (k + 1) % 4
        F.append((k, k1, 4 + k, 4 + k1))
    return V, _tri(F)


def _bank(LS, f, head, h=0.26, t=0.85):
    """A low earth bank along the inner edge of the headland.

    This one thing does more for the aerial read than anything else, because it
    puts a lit crest and a shadow line along every parcel boundary: parcels
    stop being flat swatches and start being land.
    """
    hw, hd = f.w * 0.5, f.d * 0.5
    iw, id_ = hw - head, hd - head
    if iw < 2.0 or id_ < 2.0:
        return None, None
    sides = [((-iw, -id_ - t), (iw, -id_ - t), (-iw, -id_), (iw, -id_)),
             ((iw + t, -id_), (iw + t, id_), (iw, -id_), (iw, id_)),
             ((iw, id_ + t), (-iw, id_ + t), (iw, id_), (-iw, id_)),
             ((-iw - t, id_), (-iw - t, -id_), (-iw, id_), (-iw, -id_))]
    V = []
    F = []
    for (a, b, c, d) in sides:
        i0 = len(V)
        for (u, v) in (a, b, c, d):
            V.append(f.world(u, v))
        base = LS._gz(np.array([V[i0][0], V[i0 + 1][0]]),
                      np.array([V[i0][1], V[i0 + 1][1]])) + LIFT
        top = LS._gz(np.array([V[i0 + 2][0], V[i0 + 3][0]]),
                     np.array([V[i0 + 2][1], V[i0 + 3][1]])) + LIFT + h
        V[i0] = (V[i0][0], V[i0][1], float(base[0]))
        V[i0 + 1] = (V[i0 + 1][0], V[i0 + 1][1], float(base[1]))
        V[i0 + 2] = (V[i0 + 2][0], V[i0 + 2][1], float(top[0]))
        V[i0 + 3] = (V[i0 + 3][0], V[i0 + 3][1], float(top[1]))
        F.append((i0, i0 + 1, i0 + 2))
        F.append((i0 + 1, i0 + 3, i0 + 2))
    return V, F


class Bucket(object):
    """One LS.Acc plus the per-vertex `Fur` payload for the parcel material."""

    __slots__ = ("acc", "fur")

    def __init__(self):
        self.acc = None
        self.fur = []

    def add(self, LS, V, faces, mat, cols, fur):
        if not len(V):
            return
        if self.acc is None:
            self.acc = LS.Acc()
        self.acc.add(V, faces, mat, None, list(cols))
        self.fur.append(np.tile(np.asarray(fur, dtype=np.float32), (len(V), 1)))

    def push(self, LS, name, fur_attr=True):
        if self.acc is None or self.acc.empty():
            return None
        ob = self.acc.push(name)
        if ob is not None and fur_attr and self.fur:
            fur = np.concatenate(self.fur, 0)
            me = ob.data
            n = len(me.vertices)
            if fur.shape[0] == n:
                at = me.attributes.new("Fur", "FLOAT_COLOR", "POINT")
                at.data.foreach_set("color", np.ascontiguousarray(
                    fur, dtype=np.float32).reshape(-1))
        self.acc = None
        self.fur = []
        return ob


def emit(LS, fields, rng, near_r=2250.0, cell=880.0, want_ridges=True):
    """Build the belt.  Returns (objects, info, crown positions)."""
    buckets = {}

    def buck(x, y):
        key = (int(math.floor(x / cell)), int(math.floor(y / cell)))
        b = buckets.get(key)
        if b is None:
            b = buckets[key] = Bucket()
        return b

    ntri = 0
    nridge = 0
    for f in fields:
        # 1. interior surface, sampled on the terrain
        g = _grid(LS, f, f.head)
        if g is None:
            f.ok = False
            continue
        X, Y, Z, nu, nv = g
        n = (nu + 1) * (nv + 1)
        F = []
        # `_grid` builds U, V with meshgrid(indexing="ij"), so the verts are
        # flattened as i*(nv+1)+j -- u across the ridges runs fastest.  The old
        # index was j*(nu+1)+i, which only coincides when nu == nv: every
        # non-square parcel got its quads stitched to the wrong corners and
        # turned into a fan of black slivers.  That, not the palette, was the
        # spikes over the farmland.
        for i in range(nu):
            for j in range(nv):
                a = i * (nv + 1) + j
                F.append((a, a + nv + 1, a + 1))
                F.append((a + 1, a + nv + 1, a + nv + 2))
        base = np.asarray(LS.rgb(CROPS[f.crop]["col"]), dtype=np.float64)
        jit = 0.90 + 0.20 * ((f.seed % 97) / 97.0)
        # Crops are squeezed towards one exposure and left to differ in hue.
        # At face value the hexes are far too bright (wheat 0.45 linear goes
        # straight into the AgX shoulder and the parcel turns into a white
        # card), but scaling them all by one factor instead drives the dark
        # crops -- ploughed earth, vines -- into black.  Matching luminance
        # keeps wheat gold and plough brown rather than white and black.
        #
        # The exponent is deliberately mild: a 0.45 compress once pulled every
        # crop to the same brightness, so the only thing left for the eye to
        # read was hue, and the belt became a colour card.  Height, not hue, is
        # what separates a field of ripe wheat from a ploughed furrow, so the
        # parcel value now carries TONE -- roughly crop height and how much
        # shadow the rows throw on themselves.
        lum = float(base[0] * 0.30 + base[1] * 0.59 + base[2] * 0.11)
        k2 = (0.155 / max(lum, 1e-4)) ** 0.72
        col_i = tuple(min(1.0, v * k2 * TONE.get(f.crop, 1.0) * jit)
                      for v in base)
        col_o = tuple(min(1.0, v * 0.90) for v in col_i)
        # A parcel is never one flat wash of colour: drill, clods, damp
        # patches, a corner the horses missed.  Flat fills are half of why the
        # plates read as painted cardboard.
        vr = np.random.default_rng(f.seed & 0x7fffffff)
        mot = 0.92 + 0.16 * vr.random(n)
        cols = [(c[0] * m, c[1] * m, c[2] * m) for c, m in zip([col_i] * n, mot)]
        fur = _fur_of(f)
        b = buck(f.cx, f.cy)
        b.add(LS, list(zip(X.tolist(), Y.tolist(), Z.tolist())), F,
              _m(LS, "crop"), cols, fur)
        ntri += len(F)
        # 2. headland ring + bank
        V, FR = _ring(LS, f, f.head)
        b.add(LS, V, FR, _m(LS, "crop"), [col_o] * len(V), fur)
        ntri += len(FR)
        bv, bf = _bank(LS, f, f.head, 0.26)
        if bv:
            b.add(LS, bv, bf, _m(LS, "crop"), [col_o] * len(bv), fur)
            ntri += len(bf)
        # 3. selions, near the city only
        if want_ridges and f.r < near_r and CROPS[f.crop]["geo"] \
                and f.pitch > 0.4:
            hw, hd = f.w * 0.5 - f.head, f.d * 0.5 - f.head
            if hw > f.pitch * 1.6 and hd > 5.0:
                # the selions must be drawn with the same squeezed colour as
                # the parcel underneath them, or the ridged part of a field
                # reads as a different crop from the flat part
                r = GEO.furrow_mesh(LS, f.ang, f.cx, f.cy, hw * 2.0, hd * 2.0,
                                    f.pitch, CROPS[f.crop]["amp"], rng,
                                    tuple(v * 0.72 for v in col_i),
                                    tuple(min(1.0, v * 1.05) for v in col_i))
                if r is not None:
                    fv, ff, fc = r
                    ax = np.asarray([p[0] for p in fv], dtype=np.float64)
                    ay = np.asarray([p[1] for p in fv], dtype=np.float64)
                    zz = LS._gz(ax, ay) + LIFT + 0.055 \
                        + np.asarray([p[2] for p in fv], dtype=np.float64)
                    b.add(LS, list(zip(ax.tolist(), ay.tolist(), zz.tolist())),
                          ff, _m(LS, "crop"), fc, fur)
                    ntri += len(ff)
                    nridge += 1

    objs = []
    for key in sorted(buckets):
        ob = buckets[key].push(LS, "land_field_%d_%d" % key)
        if ob:
            objs.append(ob)
    edge_objs, crowns, netri = _edges(LS, fields, rng)
    objs.extend(edge_objs)
    ntri += netri
    return objs, dict(fields=len(fields), ridged=nridge, tris=ntri), crowns


# --------------------------------------------------------------------------- #
#  boundaries: one feature per shared edge, chosen by district
# --------------------------------------------------------------------------- #
def _edge_key(P):
    """Snap to 0.25 m and order endpoints, so a shared edge is one key."""
    (x0, y0), (x1, y1) = P[0], P[1]
    a = (int(round(x0 * 4.0)), int(round(y0 * 4.0)))
    b = (int(round(x1 * 4.0)), int(round(y1 * 4.0)))
    return (a, b) if a <= b else (b, a)


def _edges(LS, fields, rng):
    """Hedges, walls, fences and green lanes on parcel edges.

    Every edge is emitted once however many parcels share it -- two hedge banks
    on the same line look like a wall of black from above and cost twice as
    much.
    """
    blocks = {}
    for f in fields:
        if not f.ok:
            continue
        bkey = (int(math.floor(f.cx / 700.0)), int(math.floor(f.cy / 700.0)))
        blocks.setdefault(bkey, []).append(f)

    objs = []
    crowns = []
    ntri = 0
    for bkey in sorted(blocks):
        fs = blocks[bkey]
        st = rng.random()
        if st < 0.40:
            kind = "hedge"
        elif st < 0.62:
            kind = "wall"
        elif st < 0.74:
            kind = "ditch"
        elif st < 0.90:
            kind = "fence"
        else:
            kind = "mixed"
        acc = LS.Acc()
        hedge_col = LS.rgb("hedge")
        wall_col = LS.rgb("wall")
        wood_col = (0.20, 0.15, 0.09)
        lane_col = LS.rgb("road")
        seen = set()
        for f in fs:
            hw, hd = f.w * 0.5, f.d * 0.5
            sides = [[f.world(-hw, -hd), f.world(-hw, hd)],
                     [f.world(hw, -hd), f.world(hw, hd)],
                     [f.world(-hw, -hd), f.world(hw, -hd)],
                     [f.world(-hw, hd), f.world(hw, hd)]]
            for si, P in enumerate(sides):
                k = _edge_key(P)
                if k in seen:
                    continue
                seen.add(k)
                if si < 2 and rng.random() < 0.05:
                    continue                     # an open edge, no boundary
                if si >= 2 and rng.random() < 0.26:
                    continue                     # short ends mostly open
                what = kind
                if what == "mixed":
                    what = ("hedge", "wall", "fence", "lane", "ditch")[
                        int(rng.random() * 5)]
                if rng.random() < 0.10:
                    what = "lane"
                if what == "lane":
                    ntri += _lane(LS, acc, P, lane_col, _m(LS, "track"))
                elif what == "ditch":
                    ntri += _ditch(LS, acc, P, LS.rgb("silt"),
                                   _m(LS, "ground"))
                elif what == "hedge":
                    GEO.hedge_band(LS, acc, P, rng.uniform(3.0, 5.0),
                                   rng.uniform(1.4, 2.7), rng,
                                   _jitter(hedge_col, rng), _m(LS, "leaf"),
                                   crowns=crowns, gap_p=0.010)
                elif what == "wall":
                    GEO.drystone(LS, acc, P, rng.uniform(0.85, 1.32),
                                 rng.uniform(0.55, 0.78), rng,
                                 _jitter(wall_col, rng), _m(LS, "stone"))
                else:
                    GEO.fence_line(LS, acc, P, rng.uniform(1.0, 1.3), rng,
                                   _jitter(wood_col, rng), _m(LS, "wood"))
        if not acc.empty():
            ob = acc.push("land_edge_%d_%d" % bkey)
            if ob:
                objs.append(ob)
                ntri += len(ob.data.polygons)
    return objs, crowns, ntri


def _lane(LS, acc, P, col, mat):
    """A green lane: 3 m of rutted earth where two parcels meet.

    The quilt reading comes as much from parcels touching with nothing between
    them as from the flat colours.  A lane network puts dark, textured ribbons
    through the mosaic and gives the eye somewhere to travel.
    """
    (x0, y0), (x1, y1) = P[0], P[1]
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 6.0:
        return 0
    ns = max(2, int(L / 9.0) + 1)
    ts = np.linspace(0.0, 1.0, ns)
    X = x0 + (x1 - x0) * ts
    Y = y0 + (y1 - y0) * ts
    Z = LS._gz(X, Y) + LIFT + 0.05
    dx, dy = x1 - x0, y1 - y0
    dl = math.hypot(dx, dy) + 1e-9
    nx, ny = -dy / dl, dx / dl
    W = 1.6
    ntri = 0
    for s in range(ns - 1):
        a0 = (X[s] - nx * W, Y[s] - ny * W, Z[s])
        b0 = (X[s] + nx * W, Y[s] + ny * W, Z[s])
        a1 = (X[s + 1] - nx * W, Y[s + 1] - ny * W, Z[s + 1])
        b1 = (X[s + 1] + nx * W, Y[s + 1] + ny * W, Z[s + 1])
        tq(acc, a0, b0, b1, a1, mat, col)
        ntri += 2
    for side in (-1.0, 1.0):
        u = side * 0.78
        for s in range(ns - 1):
            a0 = (X[s] + nx * (u - 0.19), Y[s] + ny * (u - 0.19),
                  Z[s] - 0.045)
            b0 = (X[s] + nx * (u + 0.19), Y[s] + ny * (u + 0.19),
                  Z[s] - 0.045)
            a1 = (X[s + 1] + nx * (u - 0.19), Y[s + 1] + ny * (u - 0.19),
                  Z[s + 1] - 0.045)
            b1 = (X[s + 1] + nx * (u + 0.19), Y[s + 1] + ny * (u + 0.19),
                  Z[s + 1] - 0.045)
            tq(acc, a0, b0, b1, a1, mat, tuple(c * 0.62 for c in col))
            ntri += 2
    return ntri


def _ditch(LS, acc, P, col, mat):
    """A drainage ditch: 2.6 m of sunken ground with a spoil lip on each side.

    Cheap and it reads from any height, because it is a *shadow* line rather
    than a colour: two lit crests with a dark channel between them.  Draining
    a heavy clay field is the first thing a farmer does, so almost every long
    boundary in this kind of country has one alongside the hedge or the wall.
    """
    (x0, y0), (x1, y1) = P[0], P[1]
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 8.0:
        return 0
    ns = max(2, int(L / 11.0) + 1)
    ts = np.linspace(0.0, 1.0, ns)
    X = x0 + (x1 - x0) * ts
    Y = y0 + (y1 - y0) * ts
    Z = LS._gz(X, Y) + LIFT
    dx, dy = x1 - x0, y1 - y0
    dl = math.hypot(dx, dy) + 1e-9
    nx, ny = -dy / dl, dx / dl
    # profile across the ditch: outer lip, bank, channel floor, bank, outer lip
    prof = ((-1.75, 0.02), (-1.05, 0.16), (-0.62, -0.28), (0.62, -0.28),
            (1.05, 0.16), (1.75, 0.02))
    ntri = 0
    for s in range(ns - 1):
        for k in range(len(prof) - 1):
            (u0, h0), (u1, h1) = prof[k], prof[k + 1]
            a0 = (X[s] + nx * u0, Y[s] + ny * u0, Z[s] + h0)
            b0 = (X[s] + nx * u1, Y[s] + ny * u1, Z[s] + h1)
            a1 = (X[s + 1] + nx * u0, Y[s + 1] + ny * u0, Z[s + 1] + h0)
            b1 = (X[s + 1] + nx * u1, Y[s + 1] + ny * u1, Z[s + 1] + h1)
            shade = 0.52 if k in (2, 3) else 1.0
            tq(acc, a0, b0, b1, a1, mat,
               (col[0] * shade, col[1] * shade, col[2] * shade))
            ntri += 2
    return ntri


def _jitter(C, rng):
    k = 0.84 + 0.28 * rng.random()
    h = 0.94 + 0.12 * rng.random()
    return (min(1.0, C[0] * k * h), min(1.0, C[1] * k),
            min(1.0, C[2] * k * (2.05 - h)))
