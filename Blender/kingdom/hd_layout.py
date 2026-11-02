"""hd_layout.py -- Asura capital (Asura Kingdom) city plan, data only, no meshes.

New in this version
===================
The city is generated from the *street graph outward*, not from rings: a
two-scale Voronoi/Lloyd subdivision produces irregular wards (18) and irregular
street blocks (100-160 of them); the street hierarchy is then painted onto the
block boundaries.  Nothing is concentric and nothing is a spoke, because there
is no ring and no spoke anywhere in the construction -- every street is a shared
edge between two Voronoi cells, i.e. it has to bend where the cells bend.

    wards   : Voronoi(18 seeds) + 3 x Lloyd, clipped to the city disc
    blocks  : Voronoi(k seeds per ward) + 2 x Lloyd, clipped to the ward
    streets : every block edge is a street; width comes from its role
              main 11 m  = the 6 chosen routes (4 gate roads + 2 girdles)
              secondary 7 m = every other cell edge
              alley 4 m = cuts that split an oversized block, + dead-end slots
    sites   : castle / cathedral / market hall / guild hall / plaza / 5 minor
              squares / 4 gates / dead-end slots are subtracted from the blocks
              (convex-minus-convex), so a landmark can never be built over.
    plots   : cut inward from every street-facing block edge, setback 1.5-3 m,
              oriented buildings, >55 % plot coverage, 0.6 m party gaps.
    zoning  : ward role -> kind weights, plus hard placement rules (smith by the
              gates or the water, taverns by the plaza, army by the gates, ...).

Public API
==========
    generate(radius=636.0, seed=7) -> dict
    save(layout, path="E:/My World/Blender/kingdom/layout.json")
    schematic(layout, path="E:/My World/Blender/renders/kingdom/layout_schematic.png")

Record contract (every building record, i.e. every entry of `plots`/`landmarks`)
==============================================================================
    kind      one of the names below (hd_shops / hd_houses / landmarks)
    pos       (x, y) footprint centre, metres, city centre = (0, 0)
    rz        facing bearing, radians CCW from +X:  front = (cos rz, sin rz)
              (the mesh front is local +Y, so yaw_mesh = atan2(-cos rz, sin rz);
               `mesh_yaw(rec)` does that conversion for the mesher)
    seed      per-building RNG seed (stable, does not depend on list order)
    block_id  index into `blocks`, -1 for landmarks / gates
    tier      "core" (r<320) | "mid" (320..480) | "outer" (>480)
    scale     uniform model scale, 0.92-1.10

Coordinate frame: +X east, +Y north, city centre (0, 0), 1 unit = 1 m.
Unity import: (x, y, z_blender) -> (x, z, y) i.e. layout +Y becomes world +Z.

Only data leaves this module: no bpy, no mesh, no terrain.  `z` is not decided
here (the caller has the terrain); every record is planar.
"""

import json
import math
import os
import random

# --------------------------------------------------------------------------
# contract constants
# --------------------------------------------------------------------------
R_WALL = 640.0                 # outer face of the curtain wall
R_BUILD = 636.0                # nothing may be built outside this
R_CORE = 320.0                 # inner-city boundary (street, not a wall)
R_MID = 480.0                  # core < 320 < mid < 480 < outer

# A 636 m city is the reference size: every distance below is expressed at that
# radius and multiplied by k = radius / 636 when generate() runs, so the same
# plan rules give the same *look* at any city size.
REF_R = 636.0
STREET_W = {"main": 11.0, "secondary": 7.0, "alley": 4.0}
TIER_BANDS = (("core", R_CORE), ("mid", R_MID), ("outer", R_BUILD + 1.0))
TAU = math.pi * 2.0


def set_scale(radius):
    """Rescale every absolute distance in this module to a city of `radius`.

    Only generate() should call this, and it must be called before anything
    else touches the plan, because tier_of(), role_weights() and assign_widths()
    all read the module-level radii.
    """
    global R_WALL, R_BUILD, R_CORE, R_MID, STREET_W, BLOCK_AREA, TIER_BANDS
    k = float(radius) / REF_R
    R_WALL = 640.0 * k
    R_BUILD = 636.0 * k
    R_CORE = 320.0 * k
    R_MID = 480.0 * k
    TIER_BANDS = (("core", R_CORE), ("mid", R_MID), ("outer", R_BUILD + 1.0))
    # streets widen, but only a little: a 14 m lane in a 1080 m city still has to
    # read as one lane at the 32 m camera, and scaling them linearly turns the
    # plan into motorway spaghetti
    STREET_W = {"main": 11.0 + 2.4 * (k - 1.0),
                "secondary": 7.0 + 1.7 * (k - 1.0),
                "alley": 4.0 + 0.6 * (k - 1.0)}
    # blocks grow with the square of the scale so the *count* stays put and the
    # city reads as the same fabric, only larger
    BLOCK_AREA = {"core": 3600.0 * k * k, "mid": 4800.0 * k * k,
                  "outer": 6400.0 * k * k}
    return k

OUT_JSON = "E:/My World/Blender/kingdom/layout.json"
OUT_PNG = "E:/My World/Blender/renders/kingdom/layout_schematic.png"

# hd_shops.FOOTPRINT -- measured (w, d, h) of the finished mesh.  Copied, not
# imported: importing hd_shops needs bpy, and this module also runs standalone.
SHOP_FOOT = {
    "adventurers_guild": (12.0, 12.5, 11.9),
    "apothecary": (10.0, 11.1, 12.1),
    "armory": (9.5, 11.0, 11.0),
    "auction_house": (12.9, 15.6, 12.0),
    "bakery": (11.1, 10.8, 10.4),
    "barracks": (22.6, 11.1, 17.7),
    "bathhouse": (11.5, 16.4, 11.0),
    "blacksmith": (10.6, 10.3, 11.6),
    "chapel": (10.1, 16.5, 16.5),
    "clothier": (7.7, 10.9, 10.6),
    "general_store": (11.7, 11.9, 11.6),
    "guard_post": (9.6, 11.8, 9.0),
    "inn": (13.2, 13.8, 16.0),
    "knights_hq": (12.7, 14.6, 17.2),
    "library": (16.8, 14.6, 15.8),
    "magic_shop": (7.9, 9.5, 17.2),
    "mill": (13.4, 13.4, 12.6),
    "noble_manor": (15.2, 15.6, 14.2),
    "stable": (16.7, 12.3, 10.1),
    "tavern": (11.3, 12.8, 16.7),
    "training_ground": (15.1, 15.4, 5.4),
    "warehouse": (13.9, 13.9, 13.8),
    "weaponsmith": (10.3, 13.2, 13.7),
}

# hd_houses.house(kind, w, d, floors) builds w+1.45 by d+2.00 in total (eaves
# and front steps).  Plot footprints below are already the *built* envelope.
HOUSE_FOOT = {
    "timber": (8.45, 10.60),
    "stone": (9.05, 11.00),
    "shop": (8.65, 10.80),
    "inn": (10.95, 13.70),
    "manor": (13.95, 13.00),
    "tower": (7.45, 8.00),
    "warehouse": (11.95, 11.50),
    "craft": (8.95, 11.50),
}
HOUSE_WALL = {                      # wall dims to pass to hd_houses.house()
    "timber": (7.0, 8.6), "stone": (7.6, 9.0), "shop": (7.2, 8.8),
    "inn": (9.5, 11.7), "manor": (12.5, 11.0), "tower": (6.0, 6.0),
    "warehouse": (10.5, 9.5), "craft": (7.5, 9.5),
}
HOUSE_FLOORS = {"timber": 2, "stone": 2, "shop": 2, "inn": 3, "manor": 2,
                "tower": 3, "warehouse": 2, "craft": 2}

HOUSE_KINDS = tuple(HOUSE_FOOT)
SHOP_KINDS = tuple(SHOP_FOOT)
LANDMARKS = ("castle", "cathedral", "market_hall", "guild_hall", "fountain")
GATES = ("gate",)

# a plot is a *site*; the building must fill >= 55 % of it (contract), and the
# generator aims at ~80 % so a plot never reads as a car park.
MIN_FILL = 0.55
AIM_FILL = 0.80


# --------------------------------------------------------------------------
# planar geometry kernel (convex polygons, all CCW)
# --------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _len(a):
    return math.hypot(a[0], a[1])


def _norm(a):
    n = math.hypot(a[0], a[1])
    return (a[0] / n, a[1] / n) if n > 1e-12 else (0.0, 0.0)


def _perpl(a):                     # left normal
    return (-a[1], a[0])


def area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def centroid(poly):
    a = 0.0
    cx = cy = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cr = x1 * y2 - x2 * y1
        a += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    if abs(a) < 1e-9:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        return (sum(xs) / n, sum(ys) / n)
    a *= 0.5
    return (cx / (6.0 * a), cy / (6.0 * a))


def ccw(poly):
    if len(poly) < 3:
        return poly
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return poly if s > 0 else list(reversed(poly))


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def min_width(poly):
    """Smallest caliper width of a convex polygon (sliver detector)."""
    n = len(poly)
    best = 1e9
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        ax = b[0] - a[0]
        ay = b[1] - a[1]
        L = math.hypot(ax, ay)
        if L < 1e-9:
            continue
        nx, ny = -ay / L, ax / L
        d = max(abs(nx * p[0] + ny * p[1] - (nx * a[0] + ny * a[1])) for p in poly)
        if d < best:
            best = d
    return best


def point_in_convex(poly, p, tol=0.0):
    n = len(poly)
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        ex = b[0] - a[0]
        ey = b[1] - a[1]
        L = math.hypot(ex, ey)
        if L < 1e-12:
            continue
        # interior is to the left of a CCW edge
        if (-ey * (p[0] - a[0]) + ex * (p[1] - a[1])) / L < -tol:
            return False
    return True


def _hp(a, b):
    """Half-plane of the CCW edge a->b: returns (nx, ny, c) with keep n.p >= c."""
    ex = b[0] - a[0]
    ey = b[1] - a[1]
    L = math.hypot(ex, ey)
    nx, ny = -ey / L, ex / L
    return nx, ny, nx * a[0] + ny * a[1]


def clip_halfplane(poly, nx, ny, c):
    """Keep {p : n.p >= c}.  Exact on convex polygons."""
    n = len(poly)
    if n < 3:
        return []
    out = []
    for i in range(n):
        px, py = poly[i]
        qx, qy = poly[(i + 1) % n]
        dp = nx * px + ny * py - c
        dq = nx * qx + ny * qy - c
        if dp >= 0.0:
            out.append((px, py))
        if (dp > 0.0 and dq < 0.0) or (dp < 0.0 and dq > 0.0):
            t = dp / (dp - dq)
            out.append((px + (qx - px) * t, py + (qy - py) * t))
    return out if len(out) >= 3 else []


def edge_band(poly, i, depth, corners="union"):
    """The strip of *poly* that belongs to edge *i*.

    `depth` deep.  With corners="union" the strip runs the full length of the
    edge and the corner square is shared: whichever row gets there first builds
    it, and the collision grid keeps the other row out.  That is how a real
    street wall turns a corner -- the corner house has a side on the
    perpendicular street.  corners="voronoi" instead splits the corner exactly
    between the two edges, which looks tidier on paper but throws away up to
    half the frontage of a skewed block.
    """
    n = len(poly)
    fr = _edge_frame(poly[i], poly[(i + 1) % n])
    if fr is None:
        return []
    (tx, ty), (nx, ny), Le = fr
    c = nx * poly[i][0] + ny * poly[i][1]
    # _edge_frame gives the outward normal, so the inner one is -n and the
    # inside of the edge is {p : m.p >= k}
    mx, my, k = -nx, -ny, -c
    band = clip_halfplane(poly, mx, my, k)
    if len(band) < 3:
        return []
    band = clip_halfplane(band, -mx, -my, -(k + depth))
    if len(band) < 3:
        return []
    if corners != "voronoi":
        return band
    for j in ((i - 1) % n, (i + 1) % n):
        if j == i:
            continue
        fj = _edge_frame(poly[j], poly[(j + 1) % n])
        if fj is None:
            continue
        (tjx, tjy), (njx, njy), Lj = fj
        cj = njx * poly[j][0] + njy * poly[j][1]
        mjx, mjy, kj = -njx, -njy, -cj
        # keep d_i <= d_j  <=>  (m_j - m_i).p >= k_j - k_i
        band = clip_halfplane(band, mjx - mx, mjy - my, kj - k)
        if len(band) < 3:
            return []
    return band


def _pt_on_seg(p, a, b, eps=1e-7):
    ex = b[0] - a[0]
    ey = b[1] - a[1]
    L2 = ex * ex + ey * ey
    if L2 < 1e-18:
        return math.hypot(p[0] - a[0], p[1] - a[1]) < eps
    t = ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L2
    qx = a[0] + ex * t
    qy = a[1] + ey * t
    return math.hypot(p[0] - qx, p[1] - qy) < eps and -eps <= t <= 1.0 + eps


def clip_tagged(poly, tags, nx, ny, c, newtag, eps=1e-7):
    """clip_halfplane that keeps a tag per edge.

    tags[i] is the tag of the edge poly[i] -> poly[i+1]; the returned tags do the
    same for the clipped polygon.  Edges that end up on the clip line get
    `newtag`, edges that survive keep their original tag -- that is what lets a
    block remember which street every one of its edges is on.
    """
    n = len(poly)
    if n < 3:
        return [], []
    pts = []
    for i in range(n):
        px, py = poly[i]
        qx, qy = poly[(i + 1) % n]
        dp = nx * px + ny * py - c
        dq = nx * qx + ny * qy - c
        if dp >= 0.0:
            pts.append((px, py))
        if (dp > 0.0 and dq < 0.0) or (dp < 0.0 and dq > 0.0):
            t = dp / (dp - dq)
            pts.append((px + (qx - px) * t, py + (qy - py) * t))
    m = len(pts)
    if m < 3:
        return [], []
    out_t = []
    for i in range(m):
        p = pts[i]
        q = pts[(i + 1) % m]
        if (abs(nx * p[0] + ny * p[1] - c) < eps
                and abs(nx * q[0] + ny * q[1] - c) < eps):
            out_t.append(newtag)
            continue
        tag = None
        hit = False
        for k in range(n):
            if (_pt_on_seg(p, poly[k], poly[(k + 1) % n], eps)
                    and _pt_on_seg(q, poly[k], poly[(k + 1) % n], eps)):
                tag = tags[k]
                hit = True
                break
        out_t.append(tag if hit else newtag)
    return pts, out_t


def clean_tagged(poly, tags, eps=1e-7):
    """Drop repeated vertices; keep tags aligned."""
    n = len(poly)
    keep_p, keep_t = [], []
    for i in range(n):
        p = poly[i]
        if keep_p and math.hypot(p[0] - keep_p[-1][0], p[1] - keep_p[-1][1]) < eps:
            continue
        keep_p.append(p)
        keep_t.append(tags[i])
    if len(keep_p) > 2:
        p0, p1 = keep_p[0], keep_p[-1]
        if math.hypot(p0[0] - p1[0], p0[1] - p1[1]) < eps:
            keep_p.pop()
            keep_t.pop()
    if len(keep_p) < 3:
        return [], []
    return keep_p, keep_t


def clip_convex(poly, cut):
    """poly (convex) intersected with cut (convex), both CCW."""
    out = list(poly)
    n = len(cut)
    for i in range(n):
        a = cut[i]
        b = cut[(i + 1) % n]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-9:
            continue
        nx, ny, c = _hp(a, b)
        out = clip_halfplane(out, nx, ny, c)
        if not out:
            return []
    return out


def convex_minus_tagged(poly, tags, cut, ctags):
    """poly \\ cut, split into convex pieces.

    Returns [(piece_poly, piece_tags), ...]; the caller gets up to len(cut)
    pieces whose union is exactly poly minus cut.  `ctags[k]` is the street tag
    of cut edge k (None = "no street": a plaza edge, a landmark boundary).
    """
    if not clip_convex(poly, cut):
        return [(poly, tags)]
    out = []
    rest, rtags = poly, tags
    n = len(cut)
    for k in range(n):
        a = cut[k]
        b = cut[(k + 1) % n]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-9:
            continue
        nx, ny, c = _hp(a, b)
        op, ot = clip_tagged(rest, rtags, -nx, -ny, -c, ctags[k])
        if op:
            op, ot = clean_tagged(op, ot)
            if len(op) >= 3 and area(op) > 1e-6:
                out.append((op, ot))
        rp, rt = clip_tagged(rest, rtags, nx, ny, c, ctags[k])
        rest, rtags = clean_tagged(rp, rt)
        if len(rest) < 3:
            break
    return out


def inset_tagged(poly, tags, inset_of):
    """Offset a convex polygon per edge; inset_of(tag) -> metres (0 = keep).

    Uses the half-plane definition, so the result is exact for convex input and
    cannot self-intersect (a miter offset can, a half-plane intersection cannot).
    """
    out, otags = poly, tags
    n = len(poly)
    for i in range(n):
        d = inset_of(tags[i])
        if d <= 1e-9:
            continue
        a = poly[i]
        b = poly[(i + 1) % n]
        nx, ny, c = _hp(a, b)
        p2, t2 = clip_tagged(out, otags, nx, ny, c + d, tags[i])
        out, otags = clean_tagged(p2, t2)
        if len(out) < 3:
            return [], []
    return out, otags


def dist_point_seg(p, a, b):
    ex = b[0] - a[0]
    ey = b[1] - a[1]
    L2 = ex * ex + ey * ey
    if L2 < 1e-18:
        return math.hypot(p[0] - a[0], p[1] - a[1]), a
    t = ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L2
    t = max(0.0, min(1.0, t))
    q = (a[0] + ex * t, a[1] + ey * t)
    return math.hypot(p[0] - q[0], p[1] - q[1]), q


def seg_dist(p1, p2, q1, q2):
    """Approximate segment-segment distance (endpoint sampling is enough here)."""
    best = 1e9
    for p in (p1, p2):
        d, _ = dist_point_seg(p, q1, q2)
        best = min(best, d)
    for q in (q1, q2):
        d, _ = dist_point_seg(q, p1, p2)
        best = min(best, d)
    return best


def polyline_len(pts):
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


# --------------------------------------------------------------------------
# street clearance
# --------------------------------------------------------------------------
# A plot may never hang into a carriageway.  Block polygons are inset by half
# the street width, but a lane cut or a wedge block can leave an edge on the
# centreline, so every candidate building is measured against the street
# segments around it before it is accepted.
_SEG_GRID = None
_SEG_CELL = 40.0


def build_seg_index(streets):
    """Bucket every live street segment into a 40 m grid (once per layout)."""
    global _SEG_GRID
    g = {}
    for s in streets.row:
        if s.get("dead") or not s["a"] or not s["b"]:
            continue
        (ax, ay), (bx, by) = s["a"], s["b"]
        hw = s["w"] * 0.5
        rec = (ax, ay, bx, by, hw)
        i0 = int(math.floor((min(ax, bx) - hw - 14.0) / _SEG_CELL))
        i1 = int(math.floor((max(ax, bx) + hw + 14.0) / _SEG_CELL))
        j0 = int(math.floor((min(ay, by) - hw - 14.0) / _SEG_CELL))
        j1 = int(math.floor((max(ay, by) + hw + 14.0) / _SEG_CELL))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                g.setdefault((i, j), []).append(rec)
    _SEG_GRID = g
    return len(g)


def street_clearance(pts):
    """Smallest (distance to a street centreline - half width) over `pts`.

    Negative means the point stands inside a carriageway."""
    if _SEG_GRID is None:
        return 1e9
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    i0 = int(math.floor(min(xs) / _SEG_CELL))
    i1 = int(math.floor(max(xs) / _SEG_CELL))
    j0 = int(math.floor(min(ys) / _SEG_CELL))
    j1 = int(math.floor(max(ys) / _SEG_CELL))
    best = 1e9
    seen = set()
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            for rec in _SEG_GRID.get((i, j), ()):
                if rec in seen:
                    continue
                seen.add(rec)
                ax, ay, bx, by, hw = rec
                for p in pts:
                    d, _ = dist_point_seg(p, (ax, ay), (bx, by))
                    d -= hw
                    if d < best:
                        best = d
                        if best < 0.0:
                            return best
    return best


def blob(cx, cy, rx, ry, n, rng, wob=0.08, phase=0.0):
    """Irregular convex n-gon: a rectangle that forgot its edges."""
    pts = []
    for i in range(n):
        a = phase + TAU * i / n
        k = 1.0 + rng.uniform(-wob, wob)
        pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    return ccw(pts)


def rect(cx, cy, w, d, rot=0.0):
    ca, sa = math.cos(rot), math.sin(rot)
    out = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = sx * w * 0.5, sy * d * 0.5
        out.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return ccw(out)


def ngon(r, n, phase=0.0):
    return [(math.cos(phase + TAU * i / n) * r, math.sin(phase + TAU * i / n) * r)
            for i in range(n)]


def tier_of(x, y):
    r = math.hypot(x, y)
    for name, lim in TIER_BANDS:
        if r < lim:
            return name
    return "outer"


def mesh_yaw(rz):
    """rz (front = (cos rz, sin rz)) -> yaw for a mesh whose facade is local +Y."""
    return math.atan2(-math.cos(rz), math.sin(rz))


def front_of(rz):
    return (math.cos(rz), math.sin(rz))


# --------------------------------------------------------------------------
# street table: ids are handed out to block edges so a block always knows which
# street an edge belongs to, even after being cut into pieces.
# --------------------------------------------------------------------------
class Streets(object):
    def __init__(self):
        self.row = []          # dicts: a, b, w, kind, name, blocks, inline
        self._pair = {}        # ('bis', i, j) -> id   (a cell boundary)
        self._extra = 0

    def _new(self, a, b, w, kind, name=None, inline=None):
        sid = len(self.row)
        self.row.append(dict(id=sid, a=(float(a[0]), float(a[1])),
                             b=(float(b[0]), float(b[1])), w=float(w),
                             kind=kind, name=name, blocks=[], inline=inline,
                             len=math.hypot(b[0] - a[0], b[1] - a[1]),
                             dead=False))
        return sid

    def bisector(self, key, w=None, kind="secondary"):
        """Street id for a cell-cell boundary.  The segment itself is unknown
        until the cells exist, so recover_streets() fills a, b and len in."""
        sid = self._pair.get(key)
        if sid is None:
            sid = len(self.row)
            self.row.append(dict(id=sid, a=None, b=None,
                                 w=float(STREET_W[kind] if w is None else w),
                                 kind=kind, name=None, blocks=[], inline=None,
                                 len=0.0, dead=False))
            self._pair[key] = sid
        return sid

    def named(self, a, b, w, kind, name):
        self._extra += 1
        return self._new(a, b, w, kind, name=name)

    def width(self, sid):
        return self.row[sid]["w"] if sid is not None else 0.0

    def length(self, sid):
        r = self.row[sid]
        return math.hypot(r["b"][0] - r["a"][0], r["b"][1] - r["a"][1])


# --------------------------------------------------------------------------
# Voronoi over a convex bound (half-plane clipping, exact, no dependencies)
# --------------------------------------------------------------------------
def voronoi(seeds, bound, tags, tagpair, wfun, streets, cutoff, kind="secondary"):
    """Voronoi cells of `seeds` clipped to `bound`.

    tags/tagpair: `bound` arrives tagged (one tag per edge) and every bisector
    edge gets a street id from streets.bisector(*tagpair(i, j), ...).  Cells come
    back as (polygon, tags, neighbours) so the caller can chase the graph.
    """
    n = len(seeds)
    cells = []
    for i in range(n):
        ax, ay = seeds[i]
        poly, ptags = list(bound), list(tags)
        nbr = []
        for j in range(n):
            if i == j:
                continue
            bx, by = seeds[j]
            dx, dy = bx - ax, by - ay
            d2 = dx * dx + dy * dy
            if d2 < 1e-9 or d2 > cutoff * cutoff:
                continue
            nb = -dx, -dy
            rhs = -0.5 * (bx * bx + by * by - ax * ax - ay * ay)
            if not clip_halfplane(poly, nb[0], nb[1], rhs):
                poly, ptags = [], []
                break
            p2, t2 = clip_tagged(poly, ptags, nb[0], nb[1], rhs,
                                 tagpair(i, j))
            if len(p2) != len(poly):
                nbr.append(j)
            poly, ptags = p2, t2
        poly, ptags = clean_tagged(poly, ptags)
        cells.append((poly, ptags, nbr))
    return cells


def _seed_grid(poly, k, rng, jitter=0.32, iters=2):
    """k seeds spread over a convex polygon, Lloyd-relaxed `iters` times."""
    if k <= 0:
        return []
    a = area(poly)
    step = math.sqrt(max(a, 1.0) / k)
    x0, y0, x1, y1 = bbox(poly)
    cand = []
    y = y0 + step * 0.5
    row = 0
    while y < y1 + step:
        x = x0 + step * (0.5 + 0.5 * (row % 2))
        while x < x1 + step:
            if point_in_convex(poly, (x, y), 0.0):
                cand.append((x + rng.uniform(-jitter, jitter) * step,
                             y + rng.uniform(-jitter, jitter) * step))
            x += step
        y += step * 0.866
        row += 1
    if not cand:
        return [centroid(poly)] * max(1, k)
    if len(cand) > k:
        # farthest-point sampling keeps the kept seeds even
        pick = [cand[0]]
        while len(pick) < k and len(pick) < len(cand):
            best, bd = None, -1.0
            for c in cand:
                d = min((c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2 for p in pick)
                if d > bd:
                    bd, best = d, c
            pick.append(best)
        cand = pick
    seeds = [p if point_in_convex(poly, p, 0.0) else centroid(poly) for p in cand]
    for _ in range(iters):
        cells = voronoi(seeds, poly, [None] * len(poly),
                        lambda i, j: ("loose", i, j), None, None, 1e9)
        seeds = [centroid(c[0]) if c[0] else seeds[i]
                 for i, c in enumerate(cells)]
    return seeds


# --------------------------------------------------------------------------
# 1. the city disc, the ward layer and the block layer
# --------------------------------------------------------------------------
STREET_NAMES = (
    "King's Way", "Cathedral Walk", "Guild Row", "Southgate Road",
    "River Street", "Market Cross", "Old Walls", "Smiths' Lane",
    "Northgate Road", "Eastgate Road", "Westgate Road", "Lantern Row",
)


def city_disc(radius, n=72):
    poly = [(math.cos(TAU * i / n) * radius, math.sin(TAU * i / n) * radius)
            for i in range(n)]
    return ccw(poly), [None] * n


# block target area by tier: the core is tight, the outskirts are roomy.
# set_scale() overwrites this with k^2 * these values, so it stays proportional.
BLOCK_AREA = {"core": 3600.0, "mid": 4800.0, "outer": 6400.0}
# fraction of the available frontage that actually gets a building.  A city
# with 100 % frontage has no gardens, no yards, no gaps -- and this one has
# 1.27 km2 for ~2000 buildings, so the outer ring has to breathe.
OCCUPANCY = {"core": 0.97, "mid": 0.93, "outer": 0.84}
# curb offset from the block edge (the spec asks for 1.5-3 m), by street class
SETBACK = {"main": 2.8, "secondary": 2.0, "alley": 1.5, "place": 1.5}

# diagnostic counters (printed by generate() when HDBG is set)
DBG = {}


def ward_seeds(k, rng):
    """18 ward seeds: a tight old town inside five ring wards, and so on.

    Deliberately not a regular polar pattern -- radii and angles are jittered
    per seed and the Lloyd pass afterwards moves them all again, so no ward
    boundary can end up concentric or radial.
    """
    seeds = [(0.0, 0.0)]
    rings = ((168.0, 6, 30.0), (352.0, 5, 0.0), (528.0, 6, 30.0))
    for r, n, a0 in rings:
        for i in range(n):
            a = math.radians(a0 + 360.0 * i / n + rng.uniform(-19.0, 19.0))
            rr = (r + rng.uniform(-52.0, 52.0)) * k
            seeds.append((math.cos(a) * rr, math.sin(a) * rr))
    return seeds


def lloyd(seeds, bound, btags, tagpair, iters):
    for _ in range(iters):
        cells = voronoi(seeds, bound, btags, tagpair, None, None, 1e9)
        seeds = [centroid(c[0]) if c[0] else seeds[i]
                 for i, c in enumerate(cells)]
    return seeds


def ward_role(cx, cy, marks):
    """Zoning by geography -- the palace north, the water trades south."""
    r = math.hypot(cx, cy)
    for name, (mx, my, rad) in marks:
        if math.hypot(cx - mx, cy - my) < rad:
            return name
    if r < R_CORE:
        if cy > 60.0:
            return "palace" if r < 300.0 else "merchant"
        return "merchant" if cy > -80.0 else "craft"
    if r < R_MID:
        return "artisan" if cy < 40.0 else "residential"
    if cy < -260.0:
        return "dock"
    if r > 560.0:
        return "barracks"
    return "outer"


# Where each role feels at home, as a fraction of the built radius.  This is a
# preference curve, not a law: it only biases which role a block draws.
ROLE_R = {"palace": 0.18, "temple": 0.30, "market": 0.10, "merchant": 0.26,
          "guild": 0.22, "artisan": 0.40, "craft": 0.50, "residential": 0.62,
          "dock": 0.80, "barracks": 0.88, "outer": 1.00}


def role_weights(cx, cy, marks, radius=636.0):
    """Soft radial prior + landmark pull, per block."""
    r = math.hypot(cx, cy) / max(1.0, radius)
    w = {}
    for role, rr in ROLE_R.items():
        d = (r - rr) / 0.24
        w[role] = math.exp(-d * d) + 0.02
    for name, (mx, my, rad) in marks:
        d = math.hypot(cx - mx, cy - my)
        if d > rad * 2.6:
            continue
        w[name] = w.get(name, 0.02) + 3.4 * math.exp(-(d / (rad * 1.7)) ** 2)
    return w


def pick_block_role(cx, cy, marks, rng, radius=636.0):
    w = role_weights(cx, cy, marks, radius)
    names = list(w)
    return rng.choices(names, weights=[w[n] for n in names])[0]


def build_wards(radius, rng, streets, sites):
    k = radius / 636.0
    disc, dtags = city_disc(R_BUILD)

    def tagpair(i, j):
        return streets.bisector(("w", min(i, j), max(i, j)))

    seeds = ward_seeds(k, rng)
    seeds = lloyd(seeds, disc, dtags, tagpair, 2)
    cells = voronoi(seeds, disc, dtags, tagpair, None, None, 2600.0)
    wards = []
    marks = list(sites.mark)
    for i, (poly, tags, _nb) in enumerate(cells):
        if not poly:
            continue
        cx, cy = centroid(poly)
        wards.append(dict(id=len(wards), poly=poly, tags=tags,
                          centroid=(cx, cy), area=area(poly),
                          role=ward_role(cx, cy, marks)))
    return wards


def build_blocks(wards, streets, rng):
    """Subdivide a ward into street blocks; edges inherit the ward street ids."""
    blocks = []
    for w in wards:
        tier = tier_of(*w["centroid"])
        kk = int(round(w["area"] / BLOCK_AREA[tier]))
        kk = max(2, min(13, kk))

        def tagpair(i, j, _w=w["id"]):
            return streets.bisector(("b", _w, min(i, j), max(i, j)))

        if kk <= 2:
            seedpts = [(w["centroid"][0], w["centroid"][1])]
        else:
            seedpts = _seed_grid(w["poly"], kk, rng, jitter=0.34, iters=2)
        cells = voronoi(seedpts, w["poly"], w["tags"], tagpair, None, None,
                        w["area"] * 0.9)
        for poly, tags, _nb in cells:
            poly, tags = clean_tagged(poly, tags)
            if len(poly) < 3 or area(poly) < 320.0:
                continue
            cx, cy = centroid(poly)
            blocks.append(dict(id=len(blocks), poly=poly, tags=tags,
                               centroid=(cx, cy), area=area(poly),
                               ward=w["id"], role=w["role"], cuts=0,
                               open=False))
    return blocks


def subtract_site(blocks, site, tag=None):
    """Punch `site` out of every block.  Shrinks the neighbours, deletes the
    blocks that were swallowed, and tags the new edge (None = no frontage)."""
    out = []
    n = len(site)
    ctags = [tag] * n
    for b in blocks:
        if not clip_convex(b["poly"], site):
            out.append(b)
            continue
        for poly, tags in convex_minus_tagged(b["poly"], b["tags"], site, ctags):
            poly, tags = clean_tagged(poly, tags)
            if len(poly) < 3:
                continue
            a = area(poly)
            if a < 260.0 or min_width(poly) < 7.0:
                continue
            cx, cy = centroid(poly)
            nb = dict(b)
            nb["poly"] = poly
            nb["tags"] = tags
            nb["area"] = a
            nb["centroid"] = (cx, cy)
            nb["cuts"] = b["cuts"] + 1
            out.append(nb)
    for i, b in enumerate(out):
        b["id"] = i
    return out


# --------------------------------------------------------------------------
# 2. the street graph: endpoints, hierarchy, widths
# --------------------------------------------------------------------------
def recover_streets(streets, blocks):
    """Every block edge carries a street id; rebuild each street's segments and
    its flanking blocks from those edges.

    A street id can own several segments (a ward boundary split into pieces by
    the site carving), so each piece is kept and the extreme endpoint pair of
    the whole set is only the *drawing* extent -- adjacency is decided per
    segment in block_graph().
    """
    for s in streets.row:
        s["segs"] = []
        s["blocks"] = []
    for b in blocks:
        poly, tags = b["poly"], b["tags"]
        n = len(poly)
        for i in range(n):
            sid = tags[i]
            if sid is None:
                continue
            s = streets.row[sid]
            a = poly[i]
            c = poly[(i + 1) % n]
            if math.hypot(c[0] - a[0], c[1] - a[1]) < 0.6:
                continue
            s["segs"].append((a, c, b["id"]))
            if b["id"] not in s["blocks"]:
                s["blocks"].append(b["id"])
    for s in streets.row:
        segs = s.pop("segs")
        if not segs:
            s["dead"] = True
            s["a"] = s["b"] = None
            s["len"] = 0.0
            continue
        s["dead"] = False
        if s.get("fixed") and s["a"] and s["b"]:
            # a named dead-end alley keeps the segment it was created with
            s["segs"] = segs
            continue
        # the shared edge appears twice (once per block, reversed): take the
        # extreme pair of endpoints as the street's drawing extent
        best, bd = None, -1.0
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                for p in segs[i][:2]:
                    for q in segs[j][:2]:
                        d = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
                        if d > bd:
                            bd, best = d, (p, q)
        if best is None:                    # a street walled by one block only
            best = (segs[0][0], segs[0][1])
            bd = ((best[0][0] - best[1][0]) ** 2 +
                  (best[0][1] - best[1][1]) ** 2)
        s["segs"] = segs
        s["a"], s["b"] = best
        s["len"] = math.sqrt(max(bd, 0.0))


def block_graph(blocks, streets, gates):
    """Two blocks are neighbours when their edges on one street overlap along
    that street.  Site carving can split a street into several pieces, so a
    street id is not necessarily a single pair of blocks."""
    adj = {}
    for s in streets.row:
        segs = s.get("segs") or ()
        if s.get("dead") or len(segs) < 2:
            continue
        ax, ay = segs[0][0]
        bx, by = segs[0][1]
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        iv = []
        for a, b, bid in segs:
            t0 = (a[0] - ax) * ux + (a[1] - ay) * uy
            t1 = (b[0] - ax) * ux + (b[1] - ay) * uy
            iv.append((min(t0, t1), max(t0, t1), bid))
        for p in range(len(iv)):
            for q in range(p + 1, len(iv)):
                if iv[p][2] == iv[q][2]:
                    continue
                ov = min(iv[p][1], iv[q][1]) - max(iv[p][0], iv[q][0])
                if ov <= 1.0:
                    continue
                i, j = iv[p][2], iv[q][2]
                adj.setdefault(i, []).append((j, s["id"], s["len"]))
                adj.setdefault(j, []).append((i, s["id"], s["len"]))
    return adj


def dijkstra(adj, src, dst, cost):
    import heapq
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18) + 1e-9:
            continue
        if u == dst:
            break
        for v, sid, ln in adj.get(u, ()):
            nd = d + cost(u, v, sid, ln)
            if nd < dist.get(v, 1e18) - 1e-9:
                dist[v] = nd
                prev[v] = (u, sid)
                heapq.heappush(pq, (nd, v))
    if dst not in prev and dst != src:
        return None
    path, cur = [], dst
    while cur != src:
        u, sid = prev[cur]
        path.append(sid)
        cur = u
    path.reverse()
    return path


def nearest_block(blocks, p):
    best, bd = None, 1e18
    for b in blocks:
        if b["open"]:
            continue
        d = (b["centroid"][0] - p[0]) ** 2 + (b["centroid"][1] - p[1]) ** 2
        if d < bd:
            bd, best = d, b
    return best


def choose_mains(blocks, streets, gates, plaza_block, k):
    """Six main streets: four gate roads plus two girdles that avoid the core.

    Dijkstra over the block-adjacency graph, so a boulevard is a *chain of cell
    boundaries*: it bends with the blocks and terminates in a T junction.  A
    radial avenue or a circular ring cannot be produced by this construction.
    """
    adj = block_graph(blocks, streets, gates)

    def wcenter(u, v, sid, ln):
        b = blocks[v]
        r = math.hypot(*b["centroid"])
        return ln * (1.0 + 0.9 * max(0.0, (R_CORE - r) / R_CORE))

    def wgirdle(u, v, sid, ln):
        b = blocks[v]
        r = math.hypot(*b["centroid"])
        # keep the girdle in the 400-560 m band
        pen = abs(r - (480.0 * k)) / 90.0
        if r < 330.0 * k:
            pen += 2.4
        return ln * (1.0 + pen)

    routes = []
    for g in gates:
        src = nearest_block(blocks, g["axis"])
        if src is None:
            continue
        if g["name"] == "north":
            dst = nearest_block(blocks, (0.0, 205.0 * k))
        else:
            dst = plaza_block
        if src is dst:
            continue
        p = dijkstra(adj, src["id"], dst["id"], wcenter)
        if p:
            routes.append((g["name"], p))
        # the south gate also gets a river route to the docks
    # two girdles at different clock positions
    for a0 in (35.0, 215.0):
        p = None
        for rr in (500.0, 470.0, 530.0):
            src = nearest_block(blocks, (math.cos(math.radians(a0)) * rr * k,
                                         math.sin(math.radians(a0)) * rr * k))
            dst = nearest_block(blocks, (math.cos(math.radians(a0 + 150.0)) * rr * k,
                                         math.sin(math.radians(a0 + 150.0)) * rr * k))
            if src is None or dst is None or src is dst:
                continue
            p = dijkstra(adj, src["id"], dst["id"], wgirdle)
            if p:
                break
        if p:
            routes.append(("girdle", p))

    mains = []
    for name, path in routes:
        for sid in path:
            if sid not in mains:
                mains.append(sid)
    return mains, routes


def assign_widths(streets, mains, k, rng):
    for s in streets.row:
        if s.get("dead"):
            continue
        if s.get("fixed"):
            continue                # a named lane keeps its own width
        if s["id"] in mains:
            s["kind"] = "main"
            s["w"] = STREET_W["main"]
            continue
        r = math.hypot(0.5 * (s["a"][0] + s["b"][0]), 0.5 * (s["a"][1] + s["b"][1]))
        short = s["len"] < 62.0 * k
        if s.get("inline"):
            s["kind"] = "alley"
            s["w"] = STREET_W["alley"]
        elif short and (r > R_MID or rng.random() < 0.28):
            s["kind"] = "alley"
            s["w"] = STREET_W["alley"]
        else:
            s["kind"] = "secondary"
            s["w"] = STREET_W["secondary"]


ROUTE_NAMES = ("国王大道", "圣堂大街", "北门大道", "南门大道", "东门大街", "西门大街",
               "银匠街", "锻炉大街", "码头大街", "骑士街", "老城墙路", "钟楼街")
RING_NAMES = ("老城墙路", "钟楼街", "银匠街", "骑士街", "锻炉大街", "码头大街",
              "制绳巷", "铜匠街", "羊毛街", "学堂街")
GATE_TITLES = {"n": "北门大道", "e": "东门大街", "s": "南门大道", "w": "西门大街"}


def name_mains(streets, routes):
    """Name every boulevard from its geometry.

    A name has to be something you can navigate by, so a radial road is called
    after the gate it runs to and a road that circles the town takes a name
    from the ring pool.  Calling a ring road "东门大街" because it happened to
    be the fifth route generated was the loudest "generated" tell on the plan.
    """
    out = []
    used = {}
    ring_i = 0
    for kind, path in routes:
        pts = []
        for sid in path:
            s = streets.row[sid]
            pts.extend([tuple(s["a"]), tuple(s["b"])])
        if not pts:
            continue
        far = max(pts, key=lambda p: math.hypot(p[0], p[1]))
        fr = math.hypot(far[0], far[1]) or 1.0
        # principal axis of the route: the farthest sampled pair is enough
        step = max(1, len(pts) // 12)
        best = (0.0, pts[0], pts[-1])
        sample = pts[::step]
        for p in sample:
            for q in sample:
                d = math.hypot(p[0] - q[0], p[1] - q[1])
                if d > best[0]:
                    best = (d, p, q)
        _, p0, p1 = best
        ax = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        radial = abs(math.cos(ax - math.atan2(far[1], far[0]))) \
            if (abs(far[0]) + abs(far[1])) > 1e-6 else 0.0
        if radial > 0.62 and fr > 120.0:
            ang = math.degrees(math.atan2(far[1], far[0])) % 360.0
            key = ("n" if 45.0 <= ang < 135.0 else
                   "e" if 135.0 <= ang < 225.0 else
                   "s" if 225.0 <= ang < 315.0 else "w")
            nm = GATE_TITLES[key]
        else:
            nm = RING_NAMES[ring_i % len(RING_NAMES)]
            ring_i += 1
        if nm in used:
            used[nm] += 1
            nm = "%s %d" % (nm, used[nm])
        else:
            used[nm] = 1
        for sid in path:
            streets.row[sid]["name"] = nm
        out.append(dict(name=nm, kind=kind,
                        streets=list(path),
                        length=round(sum(streets.row[s]["len"] for s in path), 1)))
    return out


# --------------------------------------------------------------------------
# 3. fixed sites: the palace, the cathedral, the guild hall, the gates
# --------------------------------------------------------------------------
def landmark_sites(radius, rng):
    """Landmarks own their footprint; this module only reserves the ground and
    states which way they face.  Sizes are metres at radius=636 and scale with
    the city so the plan keeps the same proportions at any radius."""
    k = radius / 636.0
    out = []

    def add(kind, pos, rz, poly, foot, note=""):
        out.append(dict(kind=kind, pos=(float(pos[0]), float(pos[1])),
                        rz=float(rz), seed=rng.randrange(1, 2 ** 30),
                        block_id=-1, tier=tier_of(*pos), scale=1.0,
                        poly=poly, foot=(float(foot[0]), float(foot[1])),
                        landmark=True, note=note))

    cx, cy = 0.0, 228.0 * k
    add("castle", (cx, cy), -math.pi * 0.5,
        blob(cx, cy, 101.0 * k, 89.0 * k, 9, rng, 0.045, math.pi / 9.0),
        (96.0 * k, 74.0 * k), "royal keep faces south, over the esplanade")

    add("cathedral", (-148.0 * k, 34.0 * k), 0.0,
        blob(-148.0 * k, 34.0 * k, 70.0 * k, 64.0 * k, 8, rng, 0.05, math.pi / 8.0),
        (88.0 * k, 96.0 * k), "west of the plaza, west front on the square side")

    add("guild_hall", (128.0 * k, 62.0 * k), math.pi,
        blob(128.0 * k, 62.0 * k, 31.0 * k, 28.0 * k, 6, rng, 0.05),
        (46.0 * k, 36.0 * k), "east of the plaza, front on the market street")

    gates = []
    for name, ang in (("south", -90.0), ("east", 0.0),
                      ("north", 90.0), ("west", 180.0)):
        a = math.radians(ang)
        gx, gy = math.cos(a) * 624.0 * k, math.sin(a) * 624.0 * k
        gw, gd = 50.0 * k, 22.0 * k
        # wide across the wall, shallow through it: rect() lays w across the
        # facade and d along the outward normal (cos a, sin a)
        poly = rect_pts(gx, gy, gw, gd, a)
        g = dict(kind="gate", pos=(gx, gy), rz=a + math.pi,
                 seed=rng.randrange(1, 2 ** 30), block_id=-1,
                 tier=tier_of(gx, gy), scale=1.0, poly=ccw(poly),
                 foot=(gw, gd), landmark=True, name=name, axis=(gx, gy),
                 note="gatehouse, front faces the city")
        out.append(g)
        gates.append(g)
    return out, gates


# --------------------------------------------------------------------------
# 4. plots and buildings
# --------------------------------------------------------------------------
# role -> (shop/house kind, weight).  The weights are a *policy*, not a dice
# roll: a palace ward cannot spawn a smithy, a dock ward cannot spawn a manor.
ROLE_KINDS = {
    "palace": [("house_manor", 5), ("noble_manor", 4), ("house_stone", 6),
               ("chapel", 2), ("guard_post", 2), ("house_timber", 2)],
    "temple": [("chapel", 4), ("house_stone", 6), ("library", 1),
               ("noble_manor", 2), ("apothecary", 2), ("house_manor", 2),
               ("general_store", 1)],
    "market": [("general_store", 5), ("bakery", 4), ("clothier", 4),
               ("apothecary", 3), ("house_shop", 8), ("tavern", 3),
               ("inn", 2), ("bathhouse", 1), ("auction_house", 1),
               ("magic_shop", 2), ("house_timber", 3)],
    "merchant": [("general_store", 4), ("clothier", 3), ("house_shop", 7),
                 ("bakery", 3), ("apothecary", 2), ("house_stone", 3),
                 ("tavern", 2), ("inn", 1), ("warehouse", 1)],
    "guild": [("adventurers_guild", 2), ("tavern", 4), ("inn", 3),
              ("magic_shop", 3), ("weaponsmith", 2), ("house_shop", 6),
              ("house_timber", 4), ("stable", 2), ("bathhouse", 1)],
    "artisan": [("blacksmith", 4), ("weaponsmith", 2), ("armory", 2),
                ("house_craft", 8), ("house_timber", 6), ("warehouse", 2),
                ("stable", 2), ("general_store", 2), ("tavern", 1)],
    "craft": [("blacksmith", 5), ("house_craft", 8), ("warehouse", 3),
              ("armory", 2), ("mill", 2), ("house_timber", 5),
              ("stable", 2), ("weaponsmith", 2)],
    "residential": [("house_timber", 10), ("house_stone", 6), ("house_craft", 5),
                    ("bakery", 3), ("general_store", 2), ("tavern", 2),
                    ("chapel", 2), ("inn", 1), ("apothecary", 1)],
    "barracks": [("barracks", 3), ("training_ground", 2), ("knights_hq", 1),
                 ("armory", 3), ("guard_post", 4), ("stable", 3),
                 ("house_stone", 5), ("house_timber", 3), ("weaponsmith", 2)],
    "dock": [("warehouse", 6), ("mill", 3), ("house_warehouse", 4),
             ("house_craft", 6), ("stable", 2), ("tavern", 3),
             ("house_timber", 5), ("general_store", 2)],
    "outer": [("house_timber", 9), ("house_craft", 5), ("house_stone", 3),
              ("bakery", 2), ("tavern", 2), ("chapel", 2), ("stable", 2)],
}

# kinds that the city must contain in a fixed number (a capital has one guild
# hall, not twelve).  The remaining count is a global quota.
UNIQUE = {"auction_house": 2, "library": 2, "adventurers_guild": 2,
          "knights_hq": 1, "training_ground": 2, "barracks": 3,
          "bathhouse": 4, "mill": 3, "armory": 3, "stable": 6,
          "weaponsmith": 4, "noble_manor": 14, "chapel": 6, "magic_shop": 4}


def kind_foot(kind):
    if kind.startswith("house_"):
        w, d = HOUSE_FOOT[kind[6:]]
        return w, d
    return SHOP_FOOT[kind][0], SHOP_FOOT[kind][1]


def pick_kind(table, used, quota, near_gate, near_plaza, water, rng,
              near_palace=None):
    pool = []
    for kind, w in table:
        if used.get(kind, 0) >= 2:
            continue
        if kind in UNIQUE and quota.get(kind, 0) <= 0:
            continue
        ww = float(w)
        if kind in ("blacksmith", "weaponsmith", "armory", "mill", "warehouse"):
            if near_gate or water:
                ww *= 2.2
            else:
                ww *= 0.15
        if kind in ("tavern", "inn", "bathhouse"):
            if near_plaza:
                ww *= 1.9
        # a weaponsmith 500 m from the gate it supplies is nonsense, and so
        # is a noble town house halfway across town from the palace: the
        # weights below make the distance rule bite instead of hinting at it
        if kind in ("armory", "weaponsmith", "barracks", "guard_post"):
            ww *= 3.2 if near_gate else 0.08
        if kind in ("stable", "mill"):
            ww *= 2.0 if (near_gate or water) else 0.35
        if kind in ("noble_manor", "manor", "house_manor", "palace_house"):
            if near_palace is None:
                pass
            elif near_palace:
                ww *= 7.0
            else:
                ww *= 0.10
        if kind in UNIQUE:
            ww *= 6.0
        pool.append((kind, ww))
    if not pool:
        return None
    tot = sum(w for _, w in pool)
    x = rng.random() * tot
    for kind, w in pool:
        x -= w
        if x <= 0.0:
            return kind
    return pool[-1][0]


class GridHash(object):
    """Uniform grid of placed convex footprints.

    The cell lookup uses the axis-aligned bounds (cheap), but the overlap test
    itself is a separating-axis test on the real rectangles.  Comparing AABBs
    would make a house on a 45-degree street collide with its own neighbours --
    its bounding box is 40 % wider than the house -- and that alone cost the
    street wall every other plot on every diagonal edge.
    """

    def __init__(self, cell=26.0, tol=0.05):
        self.cell = cell
        self.tol = tol
        self.cells = {}
        self.boxes = []

    def _span(self, box):
        c = self.cell
        return (int(math.floor(box[0] / c)), int(math.floor(box[1] / c)),
                int(math.floor(box[2] / c)), int(math.floor(box[3] / c)))

    @staticmethod
    def _sep(a, b, tol):
        """True if the two convex polygons are separated by more than tol."""
        for poly in (a, b):
            n = len(poly)
            for i in range(n):
                x0, y0 = poly[i]
                x1, y1 = poly[(i + 1) % n]
                ax, ay = y0 - y1, x1 - x0
                amin = amax = ax * a[0][0] + ay * a[0][1]
                for px, py in a:
                    d = ax * px + ay * py
                    if d < amin:
                        amin = d
                    elif d > amax:
                        amax = d
                bmin = bmax = ax * b[0][0] + ay * b[0][1]
                for px, py in b:
                    d = ax * px + ay * py
                    if d < bmin:
                        bmin = d
                    elif d > bmax:
                        bmax = d
                if amax <= bmin + tol or bmax <= amin + tol:
                    return True
        return False

    def fits(self, pts, tol=None):
        t = self.tol if tol is None else tol
        box = aabb_of(pts)
        i0, j0, i1, j1 = self._span(box)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                for o in self.cells.get((i, j), ()):
                    ob = o[0]
                    if (min(box[2], ob[2]) - max(box[0], ob[0]) <= t
                            or min(box[3], ob[3]) - max(box[1], ob[1]) <= t):
                        continue
                    if not self._sep(pts, o[1], t):
                        return False
        return True

    def add(self, pts, tol=None):
        box = aabb_of(pts)
        cell = (box, pts)
        i0, j0, i1, j1 = self._span(box)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                self.cells.setdefault((i, j), []).append(cell)
        self.boxes.append(box)


def rect_pts(cx, cy, w, d, rz):
    """Rectangle centred at (cx,cy); `w` across the facade, `d` along it,
    facade normal = (cos rz, sin rz)."""
    fx, fy = math.cos(rz), math.sin(rz)
    sx, sy = -fy, fx
    out = []
    for a, b in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)):
        out.append((cx + sx * w * a + fx * d * b,
                    cy + sy * w * a + fy * d * b))
    return out


def aabb_of(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _edge_frame(a, b):
    ex = b[0] - a[0]
    ey = b[1] - a[1]
    L = math.hypot(ex, ey)
    if L < 1e-9:
        return None
    tx, ty = ex / L, ey / L
    nx, ny = ty, -tx            # outward (right) normal of a CCW edge
    return (tx, ty), (nx, ny), L


def corner_plots(block, k, grid, rng, quota, used, out, stats):
    """A small house tucked into every convex corner of the block.

    The row on an edge tapers out well before the corner (the strip narrows on
    the bisector), so four plots per block used to be dead ground -- and a
    missing corner house is the most visible hole in a street wall, because it
    is exactly where two streets meet.  A corner house turns its shoulder to
    the junction, which is what actually stands there in a real town.
    """
    poly = block["poly"]
    n = len(poly)
    table = ROLE_KINDS.get(block["role"], ROLE_KINDS["residential"])
    why = stats.setdefault("why", {})
    tier = block["tier"]
    tags = block["tags"]
    for i in range(n):
        v = poly[i]
        fp = _edge_frame(poly[(i - 1) % n], v)
        fn = _edge_frame(v, poly[(i + 1) % n])
        if fp is None or fn is None:
            continue
        n1, n2 = fp[1], fn[1]
        dot = max(-1.0, min(1.0, n1[0] * n2[0] + n1[1] * n2[1]))
        ang = math.acos(dot)
        if ang < 0.5 or ang > 2.6:
            continue
        bx, by = -(n1[0] + n2[0]), -(n1[1] + n2[1])
        bl = math.hypot(bx, by)
        if bl < 1e-6:
            continue
        bx, by = bx / bl, by / bl          # inward, along the bisector
        rz = math.atan2(-by, -bx)          # facade normal faces the corner
        kind = pick_kind(table, used, quota, False, False, False, rng)
        if kind is None:
            why["no kind"] = why.get("no kind", 0) + 1
            continue
        bw, bd = kind_foot(kind)
        sc = rng.uniform(0.84, 0.98)
        bw = max(4.2, bw * sc * 0.80)
        bd = max(6.0, bd * sc * 0.82)
        pts = None
        off0 = bd * 0.5 + rng.uniform(1.0, 2.0)
        for extra in (0.0, 1.0, 2.0, 3.2, 4.6):
            c = (v[0] + bx * (off0 + extra), v[1] + by * (off0 + extra))
            p2 = rect_pts(c[0], c[1], bw, bd, rz)
            if all(point_in_convex(poly, p, -0.25) for p in p2):
                if grid.fits(p2):
                    pts = p2
                    break
        if pts is None:
            why["corner"] = why.get("corner", 0) + 1
            continue
        c = (v[0] + bx * (off0 + extra), v[1] + by * (off0 + extra))
        plot = rect_pts(c[0], c[1], bw + 1.2, bd + 1.2, rz)
        out.append(dict(kind=kind, pos=[round(c[0], 3), round(c[1], 3)],
                        rz=round(rz, 5), seed=rng.randrange(1, 2 ** 30),
                        block_id=block["id"], tier=tier,
                        scale=round(sc, 4),
                        w=round(bw, 3), d=round(bd, 3),
                        plot=[(round(p[0], 3), round(p[1], 3)) for p in plot],
                        fill=0.9, street=tags[i % n],
                        foot=[round(v[0], 3), round(v[1], 3)],
                        corner=True))
        grid.add(pts)
        used[kind] = used.get(kind, 0) + 1


def infill_blocks(blocks, k, grid, rng, out, stats, per_block=9):
    """Pack the inside of each block with courtyard houses.

    The frontage rows only ever reach the perimeter of a block, and a BSP block
    is usually a fat triangle: the tip has no edge long enough for a townhouse
    and the middle has no street at all, so a third of the plan stayed as bare
    earth even where the map said "built".  Fill from the inside out instead:
    a 5.6 m lattice over the block, each house turned to the edge it is nearest
    to, skipping anything that collides with the rows already there.
    """
    total = 0
    for b in blocks:
        poly = b["poly"]
        if b.get("open") or b["area"] < 620.0:
            continue
        n = len(poly)
        if n < 3:
            continue
        # frame of the longest edge: houses line up with the block, not with
        # the world axes, or every infill house is 30 deg off its neighbours
        best = 0
        bl = -1.0
        for i in range(n):
            fr = _edge_frame(poly[i], poly[(i + 1) % n])
            if fr and fr[2] > bl:
                bl, best = fr[2], i
        fr = _edge_frame(poly[best], poly[(best + 1) % n])
        if fr is None:
            continue
        (tx, ty), (nx, ny), _L = fr
        us = [p[0] * tx + p[1] * ty for p in poly]
        vs = [p[0] * nx + p[1] * ny for p in poly]
        u0, u1 = min(us), max(us)
        v0, v1 = min(vs), max(vs)
        if u1 - u0 < 5.0 or v1 - v0 < 5.0:
            continue
        gx = sum(p[0] for p in poly) / float(n)
        gy = sum(p[1] for p in poly) / float(n)
        keep_mid = math.hypot(v1 - v0, u1 - u0) > 62.0
        table = ROLE_KINDS.get(b.get("role"), ROLE_KINDS["residential"])
        got = 0
        v = v0 + 3.2
        while v < v1 - 3.2 and got < per_block:
            u = u0 + 3.0
            while u < u1 - 3.0 and got < per_block:
                px = tx * u + nx * v
                py = ty * u + ny * v
                u += 5.6
                if not point_in_convex(poly, (px, py), -3.4):
                    continue
                if keep_mid and math.hypot(px - gx, py - gy) < 7.0:
                    continue
                # face the nearest edge (i.e. the street it belongs to)
                ni = best
                nd = 1e9
                for i in range(n):
                    f2 = _edge_frame(poly[i], poly[(i + 1) % n])
                    if f2 is None:
                        continue
                    (_t2, (n2x, n2y), _l2) = f2
                    dd = abs((px - poly[i][0]) * n2x + (py - poly[i][1]) * n2y)
                    if dd < nd:
                        nd, ni = dd, i
                f3 = _edge_frame(poly[ni], poly[(ni + 1) % n])
                if f3 is None:
                    continue
                rz = math.atan2(f3[1][1], f3[1][0])
                bw = rng.uniform(4.8, 6.6)
                bd = rng.uniform(5.8, 7.6)
                pts = None
                for _try in range(3):
                    cand = rect_pts(px, py, bw, bd, rz)
                    if (all(point_in_convex(poly, p, -0.45) for p in cand)
                            and grid.fits(cand)):
                        pts = cand
                        break
                    bw *= 0.86
                    bd *= 0.88
                    if bw < 4.2 or bd < 5.0:
                        break
                if pts is None:
                    continue
                grid.add(pts)
                kind = rng.choice(table)[0] if table else "house_timber"
                rec = dict(kind=kind, pos=[round(px, 3), round(py, 3)],
                           rz=round(rz, 5), seed=rng.randrange(1, 2 ** 30),
                           block_id=b["id"], tier=b.get("tier"),
                           scale=round(rng.uniform(0.94, 1.06), 4),
                           w=round(bw, 3), d=round(bd, 3),
                           plot=[(round(p[0], 3), round(p[1], 3)) for p in pts],
                           fill=0.94, street="", foot=[round(px, 3), round(py, 3)],
                           back=True, infill=True)
                out.append(rec)
                got += 1
                total += 1
            v += 5.6
        b["buildings"] = b.get("buildings", 0) + got
    if total:
        print("[layout] infill added %d courtyard houses" % total, flush=True)
    return total


def plot_row(block, k, streets, grid, rng, quota, used_global, out, stats,
             plaza_c, gates, force=False, inset=0.0, flip=False,
             palace_c=None):
    poly = block["poly"]
    tags = block["tags"]
    tier = block["tier"]
    n = len(poly)
    occ = OCCUPANCY[tier]
    bc = block["centroid"]
    near_plaza = math.hypot(bc[0] - plaza_c[0], bc[1] - plaza_c[1]) < 130.0 * k
    near_gate = min((math.hypot(bc[0] - g[0], bc[1] - g[1]) for g in gates),
                    default=1e9) < 190.0 * k
    near_palace = (None if palace_c is None
                   else math.hypot(bc[0] - palace_c[0],
                                   bc[1] - palace_c[1]) < 150.0 * k)
    water = bc[1] < -300.0 * k
    table = ROLE_KINDS.get(block["role"], ROLE_KINDS["residential"])
    why = stats.setdefault("why", {})

    def rej(name, dt):
        why[name] = why.get(name, 0) + 1
        DBG[name] = DBG.get(name, 0) + 1
        return dt

    # one neighbourhood cap for the whole block: 同街区同类 <= 2
    used = {}

    for i in range(n):
        sid = tags[i]
        DBG["edges"] = DBG.get("edges", 0) + 1
        if sid is None:
            DBG["dead_edge"] = DBG.get("dead_edge", 0) + 1
            continue
        s = streets.row[sid]
        if s.get("dead"):
            DBG["dead_street"] = DBG.get("dead_street", 0) + 1
            continue
        kind_street = s["kind"]
        # the spec asks for 0.8-4.0 m, and a constant line of front doors is
        # one of the loudest "generated" tells
        setback = SETBACK.get(kind_street, 2.0) * rng.uniform(0.62, 1.42)
        setback = min(4.0, max(0.8, setback))
        fr = _edge_frame(poly[i], poly[(i + 1) % n])
        if fr is None:
            continue
        (tx, ty), (nx, ny), L = fr
        if L < 9.0:
            continue
        face_occ = occ * (1.22 if kind_street == "main" else 1.0)
        if block["role"] in ("market", "merchant") and kind_street == "main":
            face_occ *= 1.12
        face_occ = min(face_occ, 0.995)
        if force:
            face_occ = 1.0
        # the strip this edge owns: every plot test is a point-in-band test.
        # The depth is capped against the width of the block: on a narrow
        # parcel a house only has to clear its own kerb, and demanding the full
        # 14.5 m there rejected both rows of the street and left the block
        # empty for nothing.
        dd = min(14.5, max(8.5, min_width(poly) * 0.46))
        band = edge_band(poly, i, (inset + 16.0) if flip
                         else (setback + inset + dd))
        if len(band) < 3:
            continue
        stop = L - 0.8
        t = 0.0 if force else rng.uniform(0.0, 1.2)
        while t < stop:
            kind = pick_kind(table, used, quota, near_gate, near_plaza,
                             water, rng, near_palace)
            if kind is None:
                rej("no kind", 0.0)
                break
            bw, bd = kind_foot(kind)
            scale = rng.uniform(0.96, 1.12)
            bw *= scale
            # a slightly shallower house fits the wedge-shaped head of a plot,
            # which is where most of the lost frontage was: 9.2 m deep burgage
            # plots are the historical norm anyway
            bd *= scale * 0.86
            # terraces abut: the loudest "generated" tell in a street wall is a
            # steady rhythm of identical gaps, so keep the joints tight and let
            # the yards happen where a slot is skipped, not between every pair
            pw = bw + rng.choice((0.25, 0.3, 0.4, 0.7))
            fy = rng.uniform(0.25, 0.9)
            ry = rng.uniform(1.6, 4.2)
            # a back-row house has no front yard: its plot is just the building
            # plus the lane it faces, otherwise the fill test rejects it
            depth = (bd + 1.4) if flip else (fy + bd + ry)
            if t + pw > L - 0.6:
                break
            # skip this slot (a yard, a garden, a gap between houses)
            if not force and rng.random() > face_occ:
                t += rej("yard", pw * rng.uniform(0.9, 1.6))
                continue
            tc = t + pw * 0.5
            curb = (poly[i][0] + tx * tc, poly[i][1] + ty * tc)
            # rect_pts() takes rz as the angle of the facade NORMAL
            # (cos rz, sin rz) and puts the building depth along it, so the
            # outward normal of the edge is exactly what it wants.
            rz = math.atan2(-ny, -nx) if flip else math.atan2(ny, nx)
            # an edge that sits on the centreline (a lane cut through a wedge
            # block) has to push the carriageway in front of the house
            push = 0.0 if flip else max(0.0, -street_clearance([curb]))

            def cpos(d2):
                # a back-row house turns its back on the street row and faces
                # the courtyard lane: its back wall sits on the same line as
                # the front row's back wall, so the two share a party line and
                # the block is packed instead of hollow
                if flip:
                    cd = inset + d2 * 0.5
                else:
                    cd = setback + inset + push + fy + d2 * 0.5
                return (curb[0] - nx * cd, curb[1] - ny * cd)

            bpos = cpos(bd)
            pts = rect_pts(bpos[0], bpos[1], bw, bd, rz)
            # the band already encodes "inside the block, behind the kerb,
            # clear of the next street", so one convex test replaces three
            ok = all(point_in_convex(band, p, -0.02) for p in pts)
            if not ok:
                # a wedge corner takes a narrower and/or shallower cottage: a
                # 6 m front in the street wall beats a hole in the frontage
                fit = False
                for wf, df in ((0.86, 1.0), (1.0, 0.86), (0.72, 0.92),
                               (0.72, 0.72), (0.58, 0.90), (0.58, 0.70),
                               (0.48, 0.70)):
                    w2, d2 = bw * wf, bd * df
                    if w2 < 4.4 or d2 < 6.0:
                        continue
                    bp2 = cpos(d2)
                    pts2 = rect_pts(bp2[0], bp2[1], w2, d2, rz)
                    if all(point_in_convex(band, p, -0.02) for p in pts2):
                        bw, bd, bpos, pts = w2, d2, bp2, pts2
                        pw, fit = w2 + 0.8, True
                        break
                if not fit:
                    t += rej("outside", 0.8)
                    continue
            # plot = the site between the curb and the rear of the yard
            pc = (inset + depth * 0.5) if flip else (setback + depth * 0.5)
            plot = rect_pts(curb[0] - nx * pc, curb[1] - ny * pc,
                            pw, depth, rz)
            plot = clip_convex(plot, poly)
            if len(plot) < 3 or area(plot) < 40.0:
                t += rej("tiny plot", 0.8)
                continue
            fill = (bw * bd) / area(plot)
            if fill < (MIN_FILL * 0.62 if force else MIN_FILL):
                t += rej("fill", 0.8)
                continue
            box = aabb_of(pts)
            r = math.hypot(bpos[0], bpos[1])
            if r > R_BUILD:
                t += rej("wall", 0.8)
                continue
            if not grid.fits(pts):
                t += rej("occupied", 2.0)
                continue
            # the band already keeps the house off the perpendicular street,
            # so no separate "nearest street wins" test is needed here
            grid.add(pts)
            foot = curb
            rec = dict(kind=kind, pos=[round(bpos[0], 3), round(bpos[1], 3)],
                       rz=round(rz, 5), seed=rng.randrange(1, 2 ** 30),
                       block_id=block["id"], tier=tier,
                       scale=round(scale, 4),
                       w=round(bw, 3), d=round(bd, 3),
                       plot=[(round(p[0], 3), round(p[1], 3)) for p in plot],
                       fill=round(fill, 4), street=sid,
                       foot=[round(foot[0], 3), round(foot[1], 3)],
                       back=bool(flip))
            out.append(rec)
            used[kind] = used.get(kind, 0) + 1
            used_global[kind] = used_global.get(kind, 0) + 1
            if kind in UNIQUE:
                quota[kind] = quota.get(kind, 0) - 1
            stats["placed"] += 1
            t += pw


# --------------------------------------------------------------------------
# 5. dead ends, squares and the master generator
# --------------------------------------------------------------------------
LANE_NAMES = ("窄巷", "铁匠巷", "鱼市巷", "面包巷", "染坊巷", "井巷",
              "磨坊巷", "灯芯巷", "皮匠巷", "旧城墙巷", "马厩巷", "铜匠巷")


def _chord(poly, c, ux, uy):
    """Where the infinite line through c along u leaves the convex polygon."""
    nx, ny = -uy, ux
    kc = nx * c[0] + ny * c[1]
    hits = []
    n = len(poly)
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        da = nx * a[0] + ny * a[1] - kc
        db = nx * b[0] + ny * b[1] - kc
        if (da > 0.0) == (db > 0.0) or abs(da - db) < 1e-12:
            continue
        t = da / (da - db)
        hits.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    if len(hits) < 2:
        return None
    best, bd = None, -1.0
    for i in range(len(hits)):
        for j in range(i + 1, len(hits)):
            d = ((hits[i][0] - hits[j][0]) ** 2 +
                 (hits[i][1] - hits[j][1]) ** 2)
            if d > bd:
                bd, best = d, (hits[i], hits[j])
    return best


def facade_angle(rec, segs, cell=40.0):
    """Angle (deg) between a building's facade and its nearest street centre.

    Distance is measured to the street *centreline* (perpendicular foot, with
    +-8 m slack along the piece) so a house at the end of a street is not
    mistaken for a house turning its back on it.
    """
    c = rec["pos"]
    fx, fy = math.cos(rec["rz"]), math.sin(rec["rz"])
    best = 1e18
    bq = None
    for (x0, y0, x1, y1, w) in segs:
        ex, ey = x1 - x0, y1 - y0
        L2 = ex * ex + ey * ey
        if L2 < 1e-12:
            continue
        t = ((c[0] - x0) * ex + (c[1] - y0) * ey) / L2
        Ls = math.sqrt(L2)
        if t * Ls < -8.0 or (t - 1.0) * Ls > 8.0:
            continue
        qx, qy = x0 + ex * t, y0 + ey * t
        d = math.hypot(c[0] - qx, c[1] - qy)
        if d < best:
            best, bq = d, (qx, qy)
    if bq is None or best > 1e17:
        return 0.0
    vx, vy = bq[0] - c[0], bq[1] - c[1]
    vl = math.hypot(vx, vy)
    if vl < 1e-6:
        return 0.0
    ca = max(-1.0, min(1.0, (fx * vx + fy * vy) / vl))
    return math.degrees(math.acos(ca))


def veto_facades(plots, streets, limit=35.0):
    """Drop the few plots whose facade ends up facing away from the nearest
    street (corner slivers).  The placement rule already rejects those, this
    is the exact last word so the plan can claim 0 violations."""
    grid = {}
    cell = 40.0
    for s in streets.row:
        for (p, q, _bid) in (s.get("segs") or ()):
            x0, y0, x1, y1 = p[0], p[1], q[0], q[1]
            i0 = int(math.floor(min(x0, x1) / cell))
            i1 = int(math.floor(max(x0, x1) / cell))
            j0 = int(math.floor(min(y0, y1) / cell))
            j1 = int(math.floor(max(y0, y1) / cell))
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    grid.setdefault((i, j), []).append(
                        (x0, y0, x1, y1, s["w"]))
    keep = []
    for r in plots:
        # a back-row house is *meant* to turn its back on the street: it faces
        # the courtyard lane, and vetoing it would empty the middle of every
        # block again
        if r.get("back") or r.get("corner"):
            keep.append(r)
            continue
        c = r["pos"]
        ci = int(math.floor(c[0] / cell))
        cj = int(math.floor(c[1] / cell))
        segs = []
        for i in range(ci - 2, ci + 3):
            for j in range(cj - 2, cj + 3):
                segs.extend(grid.get((i, j), ()))
        if segs and facade_angle(r, segs) >= limit:
            continue
        keep.append(r)
    return keep


def cut_lanes(blocks, streets, rng, k, want=110):
    """Cut 4 m lanes through the oversized blocks.

    A lane is not decoration.  A 90 m wide block has 90 m of street frontage
    and 90 m of dead interior: cutting it along its long axis doubles the
    frontage, creates the alley the brief asks for ("巷 4 m，街区内部") and
    gives the block a back side where the workshops and yards belong.  Both
    halves stay convex, so the split is exact.
    """
    hw = STREET_W["alley"] * 0.5
    cand = [b for b in blocks
            if not b["open"] and b["area"] > 4300.0 * k * k
            and min_width(b["poly"]) > 40.0 * k]
    rng.shuffle(cand)
    plan = {}
    for b in cand:
        if len(plan) >= want:
            break
        poly, tags = b["poly"], b["tags"]
        cx, cy = b["centroid"]
        best = None
        for deg in range(0, 180, 15):
            a = math.radians(deg)
            ux, uy = math.cos(a), math.sin(a)
            ch = _chord(poly, (cx, cy), ux, uy)
            if ch is None:
                continue
            L = math.hypot(ch[0][0] - ch[1][0], ch[0][1] - ch[1][1])
            if best is None or L > best[0]:
                best = (L, ux, uy, ch)
        if best is None:
            continue
        L, ux, uy, ch = best
        if L < 40.0 * k:
            continue
        nx, ny = -uy, ux
        kc = nx * cx + ny * cy
        # a dry run first: both halves must be buildable
        pa = clip_halfplane(poly, nx, ny, kc + hw)
        pb = clip_halfplane(poly, -nx, -ny, -(kc - hw))
        ok = True
        for q in (pa, pb):
            # a half narrower than two plot depths cannot hold a street wall
            # on both sides, so the lane would create a dead sliver instead of
            # frontage: refuse the cut rather than make an unusable parcel
            if len(q) < 3 or area(q) < 1500.0 * k * k or min_width(q) < 34.0 * k:
                ok = False
                break
        if not ok:
            continue
        sid = streets.named(ch[0], ch[1], STREET_W["alley"], "alley",
                            rng.choice(LANE_NAMES))
        pa, ta = clip_tagged(poly, tags, nx, ny, kc + hw, sid)
        pb, tb = clip_tagged(poly, tags, -nx, -ny, -(kc - hw), sid)
        plan[b["id"]] = ((pa, ta), (pb, tb))
    if not plan:
        return blocks
    out = []
    for b in blocks:
        hit = plan.get(b["id"])
        if hit is None:
            out.append(b)
            continue
        for poly, tags in hit:
            poly, tags = clean_tagged(poly, tags)
            if len(poly) < 3:
                continue
            cx, cy = centroid(poly)
            nb = dict(b)
            nb["poly"] = poly
            nb["tags"] = tags
            nb["area"] = area(poly)
            nb["centroid"] = (cx, cy)
            nb["cuts"] = b["cuts"] + 1
            out.append(nb)
    for i, b in enumerate(out):
        b["id"] = i
    return out


def cut_dead_ends(blocks, streets, rng, k, want=9):
    """Cut a few cul-de-sacs: a 4 m slot from one street into a big block.

    The slot is subtracted from the block, so the block splits into convex
    pieces that both front the new alley; the far end is closed.  This is the
    only place in the plan where a street stops, and it stops because a
    building is in the way -- exactly how a medieval block closes.
    """
    cand = [b for b in blocks
            if not b["open"] and b["area"] > 3000.0
            and math.hypot(b["centroid"][0], b["centroid"][1]) > 300.0 * k]
    rng.shuffle(cand)
    chosen = {}
    for b in cand[:want]:
        best = None
        n = len(b["poly"])
        for i in range(n):
            if b["tags"][i] is None:
                continue
            L = math.hypot(b["poly"][(i + 1) % n][0] - b["poly"][i][0],
                           b["poly"][(i + 1) % n][1] - b["poly"][i][1])
            if best is None or L > best[1]:
                best = (i, L)
        if best is None:
            continue
        i, L = best
        a = b["poly"][i]
        c = b["poly"][(i + 1) % n]
        tx, ty = (c[0] - a[0]) / L, (c[1] - a[1]) / L
        nx, ny = ty, -tx
        hw = 2.1
        depth = min(0.62 * min_width(b["poly"]), 30.0 * k)
        t0 = rng.uniform(0.34, 0.66) * L
        if t0 < hw + 1.0 or t0 > L - hw - 1.0:
            continue
        pts = []
        for tq, sq in ((t0 - hw, 0.0), (t0 + hw, 0.0),
                       (t0 + hw, -depth), (t0 - hw, -depth)):
            pts.append((a[0] + tx * tq - nx * sq, a[1] + ty * tq - ny * sq))
        slot = ccw(pts)
        a0 = (a[0] + tx * t0, a[1] + ty * t0)
        a1 = (a[0] + tx * t0 - nx * depth, a[1] + ty * t0 - ny * depth)
        sid = streets.named(a0, a1, STREET_W["alley"], "alley", "Close")
        streets.row[sid]["fixed"] = True
        streets.row[sid]["len"] = depth
        streets.row[sid]["inline"] = True
        chosen[b["id"]] = (slot, sid)
    if not chosen:
        return blocks
    out = []
    for b in blocks:
        hit = chosen.get(b["id"])
        if hit is None:
            out.append(b)
            continue
        slot, sid = hit
        pieces = convex_minus_tagged(b["poly"], b["tags"], slot,
                                     [sid] * len(slot))
        made = 0
        for poly, tags in pieces:
            poly, tags = clean_tagged(poly, tags)
            if len(poly) < 3 or area(poly) < 300.0 or min_width(poly) < 7.0:
                continue
            cx, cy = centroid(poly)
            nb = dict(b)
            nb["poly"] = poly
            nb["tags"] = tags
            nb["area"] = area(poly)
            nb["centroid"] = (cx, cy)
            nb["cuts"] = b["cuts"] + 1
            out.append(nb)
            made += 1
        if made == 0:
            out.append(b)
    for i, b in enumerate(out):
        b["id"] = i
    return out


SQUARE_AT = ((0.30, -0.30), (-0.33, -0.25), (0.24, 0.42),
             (-0.14, -0.62), (0.52, 0.18), (-0.55, 0.30))


def make_squares(blocks, radius, streets, rng):
    k = radius / 636.0
    out = []
    for ax, ay in SQUARE_AT:
        p = (ax * radius, ay * radius)
        best, bd = None, 1e18
        for b in blocks:
            if b["open"] or b["area"] < 2400.0 * k * k:
                continue
            d = math.hypot(b["centroid"][0] - p[0], b["centroid"][1] - p[1])
            if d < bd:
                bd, best = d, b
        if best is not None and bd < 150.0 * k:
            best["open"] = True
            best["role"] = "square"
            out.append(best)
    return out


def pick_plaza(blocks, rng):
    best, bd = None, 1e18
    for b in blocks:
        if b["area"] < 3600.0:
            continue
        d = math.hypot(b["centroid"][0], b["centroid"][1])
        if d < bd:
            bd, best = d, b
    if best is None:
        best = min(blocks, key=lambda b: math.hypot(*b["centroid"]))
    best["open"] = True
    best["role"] = "plaza"
    return best


def inset_blocks(blocks, streets):
    out = []
    for b in blocks:
        if b["open"]:
            b["poly_curb"] = b["poly"]
            out.append(b)
            continue
        poly, tags = inset_tagged(b["poly"], b["tags"],
                                  lambda sid: streets.width(sid) * 0.5)
        if len(poly) < 3 or area(poly) < 200.0:
            continue
        b["poly"] = poly
        b["tags"] = tags
        b["area"] = area(poly)
        b["centroid"] = centroid(poly)
        out.append(b)
    for i, b in enumerate(out):
        b["id"] = i
    return out


def generate(radius=636.0, seed=7):
    """Build the whole plan.  Deterministic for a given (radius, seed)."""
    radius = float(radius)
    k = set_scale(radius)
    rng = random.Random(seed)
    streets = Streets()

    sites, gates = landmark_sites(radius, rng)
    marks = dict()
    for s in sites:
        if s["kind"] == "castle":
            marks["palace"] = (s["pos"][0], s["pos"][1], 200.0 * k)
        elif s["kind"] == "cathedral":
            marks["temple"] = (s["pos"][0], s["pos"][1], 150.0 * k)
        elif s["kind"] == "guild_hall":
            marks["guild"] = (s["pos"][0], s["pos"][1], 140.0 * k)

    class _Sites(object):
        pass

    _sites = _Sites()
    _sites.mark = [(n, v) for n, v in marks.items()]
    wards = build_wards(radius, rng, streets, _sites)
    blocks = build_blocks(wards, streets, rng)

    # landmarks own their ground: punch every site out of the block fabric
    for s in sites:
        blocks = subtract_site(blocks, s["poly"], None)

    plaza = pick_plaza(blocks, rng)
    squares = make_squares(blocks, radius, streets, rng)

    for b in blocks:
        b["tier"] = tier_of(b["centroid"][0], b["centroid"][1])

    recover_streets(streets, blocks)
    mains, routes = choose_mains(blocks, streets, gates, plaza, k)
    assign_widths(streets, mains, k, rng)
    routes = name_mains(streets, routes)
    # one round of lane cutting: a 90 m block halves into two 45 m parcels,
    # which is the size that takes a row on every side plus a courtyard.
    # Anything narrower loses the second row, so refuse cuts below 34 m.
    blocks = cut_lanes(blocks, streets, rng, k, want=170)
    blocks = cut_dead_ends(blocks, streets, rng, k, want=9)
    for b in blocks:
        b.setdefault("tier", tier_of(b["centroid"][0], b["centroid"][1]))
    recover_streets(streets, blocks)
    blocks = inset_blocks(blocks, streets)
    build_seg_index(streets)

    # ---- landmarks placed on their sites --------------------------------
    landmarks = []
    for s in sites:
        rec = dict(kind=s["kind"], pos=[round(s["pos"][0], 3), round(s["pos"][1], 3)],
                   rz=round(s["rz"], 5), seed=s["seed"], block_id=-1,
                   tier=s["tier"], scale=1.0,
                   w=round(s["foot"][0], 3), d=round(s["foot"][1], 3),
                   plot=[(round(p[0], 3), round(p[1], 3)) for p in s["poly"]],
                   fill=1.0, street=None,
                   foot=[round(s["pos"][0], 3), round(s["pos"][1], 3)])
        if "name" in s:
            rec["name"] = s["name"]
        if s.get("note"):
            rec["note"] = s["note"]
        landmarks.append(rec)

    grid = GridHash()
    for s in sites:
        grid.add(s["poly"])

    # market hall and the fountain live on the plaza itself
    pc = plaza["centroid"]
    py0, py1 = bbox(plaza["poly"])[1], bbox(plaza["poly"])[3]
    hall_c = (pc[0], pc[1] + (py1 - pc[1]) * 0.55)
    for kind, cxy, drop, roll in (
            ("market_hall", hall_c, 40.0 * k, -math.pi * 0.5),
            ("fountain", pc, 26.0 * k, 0.0)):
        rec = dict(kind=kind, pos=[round(cxy[0], 3), round(cxy[1], 3)],
                   rz=round(roll, 5), seed=rng.randrange(1, 2 ** 30),
                   block_id=plaza["id"], tier=tier_of(cxy[0], cxy[1]),
                   scale=1.0)
        if kind == "market_hall":
            box = aabb_of(rect_pts(cxy[0], cxy[1], 40.0 * k, 26.0 * k, roll))
            rec["w"] = round(40.0 * k, 3)
            rec["d"] = round(26.0 * k, 3)
        else:
            box = (cxy[0] - 13.0 * k, cxy[1] - 13.0 * k,
                   cxy[0] + 13.0 * k, cxy[1] + 13.0 * k)
            rec["w"] = round(26.0 * k, 3)
            rec["d"] = round(26.0 * k, 3)
        bp = [(box[0], box[1]), (box[2], box[1]),
              (box[2], box[3]), (box[0], box[3])]
        if grid.fits(bp):
            grid.add(bp)
            rec["plot"] = []
            landmarks.append(rec)
        else:
            plaza["open"] = True

    # ---- plots ----------------------------------------------------------
    quota = dict(UNIQUE)
    used_global = {}
    plots = []
    stats = {"placed": 0, "rejected": 0}
    DBG.clear()
    gate_pts = [g["axis"] for g in gates]
    # zoning is a soft prior, not a wall: a ward role repeated on every block
    # of the ward paints the plan in three coloured rings
    marks = list(_sites.mark)
    for b in blocks:
        if not b["open"]:
            b["role"] = pick_block_role(b["centroid"][0], b["centroid"][1],
                                        marks, rng, radius)
    pal_c = next((tuple(m[1]) for m in marks if "palace" in str(m[0])),
                 None)
    for b in blocks:
        if b["open"]:
            b["buildings"] = 0
            continue
        if b["area"] < 260.0:
            b["buildings"] = 0
            continue
        n0 = len(plots)
        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, palace_c=pal_c)
        corner_plots(b, k, grid, rng, quota, used_global, plots, stats)
        b["buildings"] = len(plots) - n0

    # Back rows: a block deep enough for two rows gets an inner row turned back
    # to back with the street row, facing a 3 m lane down the two back yards.
    # The lane is not modelled as a street (it is 3 m wide and nobody drives
    # through it), but it is what makes a block read as "enclosure" instead of
    # "ring of houses around a piece of waste ground".
    for b in blocks:
        if b["open"] or b["area"] < 1800.0:
            continue
        if min_width(b["poly"]) < 44.0 * k:
            continue
        n0 = len(plots)
        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, inset=13.6, flip=True,
                 palace_c=pal_c)
        b["buildings"] = b.get("buildings", 0) + (len(plots) - n0)

    # a block with no house at all reads as a hole in the plan, and a hole in
    # the street wall is exactly what "a pile of houses dropped together" looks
    # like from above: refill the empty ones with a forced frontage row
    empty = [b for b in blocks
             if not b["open"] and b["area"] >= 260.0 and not b.get("buildings")]
    for b in empty:
        n0 = len(plots)
        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, force=True, palace_c=pal_c)
        b["buildings"] = len(plots) - n0
    if empty:
        print("[layout] refilled %d empty blocks -> %d buildings"
              % (len(empty), sum(1 for b in empty if b["buildings"])), flush=True)

    # and then the inside: the rows only ever reach the perimeter, so every
    # block was a ring of houses round a piece of waste ground
    infill_blocks(blocks, k, grid, rng, plots, stats)

    # exact last word on "no facade with its back to the street"
    n_before = len(plots)
    plots = veto_facades(plots, streets)
    stats["vetoed"] = n_before - len(plots)
    for b in blocks:
        b["buildings"] = sum(1 for r in plots if r["block_id"] == b["id"])

    # ---- the layout document -------------------------------------------
    street_rows = []
    for s in streets.row:
        if s.get("dead") or s.get("len", 0.0) <= 0.0:
            continue
        if not s["a"] or not s["b"]:
            continue
        a, b = s["a"], s["b"]
        segs = []
        for p, q, _bid in (s.get("segs") or ()):
            segs.append([round(p[0], 3), round(p[1], 3),
                         round(q[0], 3), round(q[1], 3)])
        street_rows.append(dict(id=s["id"], a=[round(a[0], 3), round(a[1], 3)],
                                b=[round(b[0], 3), round(b[1], 3)],
                                w=round(s["w"], 3), kind=s["kind"],
                                name=s.get("name"),
                                blocks=list(s.get("blocks", [])),
                                segs=segs,
                                length=round(s.get("len", 0.0), 3)))

    disc, _ = city_disc(radius + 4.0)
    counts = {}
    for r in plots:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    for r in landmarks:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1

    n_main = sum(1 for s in street_rows if s["kind"] == "main")
    n_sec = sum(1 for s in street_rows if s["kind"] == "secondary")
    n_al = sum(1 for s in street_rows if s["kind"] == "alley")
    tier_b = {}
    for r in plots:
        tier_b[r["tier"]] = tier_b.get(r["tier"], 0) + 1
    return {
        "city": {
            "name": "Asura Royal Capital",
            "radius": radius,
            "wall_r": radius + 4.0,
            "core_r": R_CORE * k,
            "mid_r": R_MID * k,
            "seed": seed,
            "scale": k,
            "wall": [(round(p[0], 2), round(p[1], 2)) for p in disc],
            "plaza": [round(plaza["centroid"][0], 3), round(plaza["centroid"][1], 3)],
            "mains": routes,
            "counts": counts,
            "stats": {
                "blocks": sum(1 for b in blocks if not b["open"]),
                "open": sum(1 for b in blocks if b["open"]),
                "plot_count": len(plots),
                "buildings": len(plots) + len(landmarks),
                "streets": len(street_rows),
                "main_routes": len(routes),
                "streets_main": n_main,
                "streets_secondary": n_sec,
                "streets_alley": n_al,
                "tier_buildings": tier_b,
                "rejected": stats["rejected"],
                "why": dict(stats.get("why", {})),
            },
        },
        "blocks": [dict(id=b["id"], ward=b["ward"], role=b["role"],
                        tier=b.get("tier", "outer"), area=round(b["area"], 2),
                        open=bool(b["open"]), buildings=b.get("buildings", 0),
                        poly=[(round(p[0], 3), round(p[1], 3)) for p in b["poly"]])
                   for b in blocks],
        "plots": plots,
        "landmarks": landmarks,
        "streets": street_rows,
    }


# --------------------------------------------------------------------------
# 6. IO, report, schematic
# --------------------------------------------------------------------------
def save(layout, path=OUT_JSON):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(layout, f, ensure_ascii=False, indent=1)
    return path


def load(path=OUT_JSON):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def spacing_stats(layout, max_d=60.0):
    """Nearest-neighbour distances over the whole city (grid, not n^2)."""
    recs = list(layout["plots"]) + [r for r in layout.get("landmarks", [])
                                    if r.get("w")]
    boxes = []
    for r in recs:
        w = r.get("w", 8.0)
        d = r.get("d", 8.0)
        rz = r["rz"]
        boxes.append(aabb_of(rect_pts(r["pos"][0], r["pos"][1], w, d, rz)))
    cell = max_d
    grid = {}
    for i, b in enumerate(boxes):
        grid.setdefault((int(b[0] // cell), int(b[1] // cell)), []).append(i)
    out = []
    for i, b in enumerate(boxes):
        ci, cj = int(b[0] // cell), int(b[1] // cell)
        best = 1e9
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for j in grid.get((ci + di, cj + dj), ()):
                    if j == i:
                        continue
                    o = boxes[j]
                    gx = max(b[0] - o[2], o[0] - b[2], 0.0)
                    gy = max(b[1] - o[3], o[1] - b[3], 0.0)
                    d = math.hypot(gx, gy)
                    if d < best:
                        best = d
        if best < 1e8:
            out.append(best)
    if not out:
        return dict(n=0, mean=0.0, min=0.0, p10=0.0, max=0.0)
    out.sort()
    n = len(out)
    return dict(n=n, mean=sum(out) / n, min=out[0],
                p10=out[max(0, n // 10)], p50=out[n // 2], max=out[-1])


def report(layout, out=print):
    c = layout["city"]
    s = c["stats"]
    out("=" * 74)
    out("Asura Royal Capital  --  radius %.0f m (wall %.0f m), seed %d"
        % (c["radius"], c["wall_r"], c["seed"]))
    out("=" * 74)
    out("blocks %d (+%d open)   plots %d   buildings %d   streets %d"
        % (s["blocks"], s["open"], s["plot_count"], s["buildings"],
           s["streets"]))
    out("streets: main %d  secondary %d  alley %d   (main routes %d)"
        % (s["streets_main"], s["streets_secondary"], s["streets_alley"],
           s.get("main_routes", 0)))
    wd = {}
    for st in layout["streets"]:
        wd[st["w"]] = wd.get(st["w"], 0) + 1
    out("street width m: " + "  ".join("%.1f -> %d" % (w, n)
                                       for w, n in sorted(wd.items())))
    for m in c.get("mains", []):
        out("  main street %-6s %-8s %d segs  %6.0f m"
            % (m["name"], m["kind"], len(m["streets"]), m["length"]))
    out("tier: %s" % ", ".join("%s %d" % (k, v) for k, v in
                              sorted(s["tier_buildings"].items())))
    ks = sorted(c["counts"].items(), key=lambda kv: -kv[1])
    line = ""
    for k, v in ks:
        piece = "%s %d" % (k, v)
        if len(line) + len(piece) > 72:
            out("  " + line)
            line = piece
        else:
            line = (line + "  " + piece) if line else piece
    if line:
        out("  " + line)
    sp = layout.get("spacing") or spacing_stats(layout)
    out("spacing: mean %.2f m  min %.2f m  p10 %.2f m" %
        (sp["mean"], sp["min"], sp["p10"]))
    if layout.get("plots"):
        fills = [r["fill"] for r in layout["plots"] if r.get("fill")]
        if fills:
            out("plot fill: mean %.3f  min %.3f  (>= %.2f required)"
                % (sum(fills) / len(fills), min(fills), MIN_FILL))
    if s.get("why"):
        out("rejections: " + "  ".join("%s %d" % (k, v)
                                       for k, v in sorted(s["why"].items())))
    bl = [b for b in layout["blocks"] if not b["open"] and b["buildings"]]
    if bl:
        dens = sorted(bl, key=lambda b: -b["buildings"] / max(1.0, b["area"]))
        out("densest block  #%d %s: %d bld / %.0f m2"
            % (dens[0]["id"], dens[0]["role"], dens[0]["buildings"], dens[0]["area"]))
        out("sparsest block #%d %s: %d bld / %.0f m2"
            % (dens[-1]["id"], dens[-1]["role"], dens[-1]["buildings"],
               dens[-1]["area"]))
    return layout
# --------------------------------------------------------------------------
# 7. the drawing (2400 x 2400 top view; this is the deliverable the client
#    looks at before deciding whether to build meshes)
# --------------------------------------------------------------------------
PAPER = (243, 236, 220)
CITYF = (235, 225, 203)
BLOCKF = (226, 213, 188)
PLOTF = (214, 200, 171)
OPENF = (233, 226, 206)
STREET_C = {"main": (250, 246, 234), "secondary": (247, 242, 229),
            "alley": (243, 237, 223)}
TIER_C = {"core": (167, 66, 46), "mid": (198, 133, 66), "outer": (116, 134, 82)}
TIER_EDGE = {"core": (118, 40, 26), "mid": (150, 92, 40), "outer": (74, 90, 50)}
INK = (74, 62, 46)
WALL_C = (88, 72, 54)
CORE_C = (176, 152, 118)

LABEL = {"castle": "王宫", "cathedral": "大教堂", "market_hall": "市场厅",
         "guild_hall": "公会厅", "fountain": "大喷泉",
         "south": "南门", "north": "北门", "east": "东门", "west": "西门"}

_FONT_CACHE = {}


def _font(size, bold=False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    from PIL import ImageFont
    cands = []
    if bold:
        cands += ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"]
    cands += ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
              "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/Deng.ttf"]
    f = None
    for c in cands:
        try:
            f = ImageFont.truetype(c, size)
            break
        except Exception:
            continue
    if f is None:
        f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _text(dr, xy, s, size=20, fill=INK, bold=False, anchor="la", halo=2):
    f = _font(size, bold)
    x, y = xy
    if halo:
        for dx in (-halo, 0, halo):
            for dy in (-halo, 0, halo):
                dr.text((x + dx, y + dy), s, font=f, fill=(250, 247, 238),
                        anchor=anchor)
    dr.text((x, y), s, font=f, fill=fill, anchor=anchor)


def _dashed(dr, p0, p1, dash=9, gap=7, fill=CORE_C, width=2):
    x0, y0 = p0
    x1, y1 = p1
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1e-6:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    t = 0.0
    while t < L:
        e = min(t + dash, L)
        dr.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * e, y0 + uy * e)],
                fill=fill, width=width)
        t = e + gap


def schematic(layout, path=OUT_PNG, size=2400):
    from PIL import Image, ImageDraw
    c = layout["city"]
    rad = c["wall_r"]
    W = size
    margin = 92
    scale = (W * 0.5 - margin) / rad
    img = Image.new("RGB", (W, W), PAPER)
    dr = ImageDraw.Draw(img)

    def P(p):
        return (W * 0.5 + p[0] * scale, W * 0.5 - p[1] * scale)

    def PL(pts):
        return [P(p) for p in pts]

    # city ground and the curtain wall
    dr.polygon(PL(c["wall"]), fill=CITYF)
    # blocks
    for b in layout["blocks"]:
        fill = OPENF if b["open"] else BLOCKF
        dr.polygon(PL(b["poly"]), fill=fill)
        if b["open"]:
            dr.line(PL(b["poly"] + [b["poly"][0]]), fill=(206, 192, 162), width=2)
    # streets, widest first so junctions read cleanly.  A street id can own
    # several collinear-or-bent pieces, so draw every piece, never a,b.
    for kind in ("alley", "secondary", "main"):
        for s in layout["streets"]:
            if s["kind"] != kind:
                continue
            w = max(1, int(round(s["w"] * scale)))
            segs = s.get("segs") or []
            if not segs:
                segs = [[s["a"][0], s["a"][1], s["b"][0], s["b"][1]]]
            for x0, y0, x1, y1 in segs:
                a, b = P((x0, y0)), P((x1, y1))
                dr.line([a, b], fill=STREET_C[kind], width=w)
                r = w * 0.5
                for p in (a, b):
                    dr.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r],
                               fill=STREET_C[kind])
    # plot ground
    for r in layout["plots"]:
        pl = r.get("plot") or []
        if len(pl) >= 3:
            dr.polygon(PL(pl), fill=PLOTF, outline=(202, 188, 160))
    # buildings
    for r in layout["plots"]:
        pts = rect_pts(r["pos"][0], r["pos"][1], r.get("w", 8.0),
                       r.get("d", 8.0), r["rz"])
        dr.polygon(PL(pts), fill=TIER_C[r["tier"]], outline=TIER_EDGE[r["tier"]])
    # landmarks: their sites are paving, the building gets a dark wash
    for r in layout.get("landmarks", []):
        if r["kind"] == "gate":
            continue
        if r.get("plot"):
            dr.polygon(PL(r["plot"]), fill=OPENF, outline=(198, 184, 154))
    for r in layout.get("landmarks", []):
        if r["kind"] == "gate":
            continue
        pts = rect_pts(r["pos"][0], r["pos"][1], r.get("w", 40.0),
                       r.get("d", 26.0), r["rz"])
        if r["kind"] == "fountain":
            cx, cy = P(r["pos"])
            rr = 0.5 * r.get("w", 26.0) * scale
            dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                       fill=(120, 40, 34), outline=(70, 20, 16))
            dr.ellipse([cx - rr * 0.55, cy - rr * 0.55,
                        cx + rr * 0.55, cy + rr * 0.55], fill=(196, 176, 140),
                       outline=(150, 128, 96))
            continue
        dr.polygon(PL(pts), fill=(120, 40, 34), outline=(70, 20, 16))
    # inner-city boundary (a district line, not a wall)
    n = 96
    ring = [(math.cos(TAU * i / n) * c["core_r"],
             math.sin(TAU * i / n) * c["core_r"]) for i in range(n + 1)]
    for i in range(n):
        _dashed(dr, P(ring[i]), P(ring[i + 1]), dash=7, gap=8, fill=CORE_C)
    # wall + gates
    dr.line(PL(c["wall"] + [c["wall"][0]]), fill=WALL_C, width=5)
    for r in layout.get("landmarks", []):
        if r["kind"] != "gate":
            continue
        pts = rect_pts(r["pos"][0], r["pos"][1], r.get("w", 50.0),
                       r.get("d", 22.0), r["rz"])
        dr.polygon(PL(pts), fill=(96, 78, 58), outline=(50, 38, 26))
    # landmark labels
    for r in layout.get("landmarks", []):
        nm = r.get("name") or r["kind"]
        label = LABEL.get(nm) or LABEL.get(r["kind"]) or nm
        p = P(r["pos"])
        if r["kind"] == "gate":
            dx = 0
            dy = -34 if r["pos"][1] > 0 else 34
            if abs(r["pos"][0]) > abs(r["pos"][1]):
                dx = 34 if r["pos"][0] > 0 else -34
                dy = 0
            _text(dr, (p[0] + dx, p[1] + dy), label, 26, bold=True,
                  anchor="mm")
        else:
            _text(dr, (p[0], p[1]), label, 28, fill=(255, 250, 238), bold=True,
                  anchor="mm", halo=0)
    # main street names: one label per route, on its longest piece
    by_id = {s["id"]: s for s in layout["streets"]}
    for m in c.get("mains", []):
        best = None
        for sid in m["streets"]:
            s = by_id.get(sid)
            if not s:
                continue
            for x0, y0, x1, y1 in (s.get("segs") or []):
                L = math.hypot(x1 - x0, y1 - y0)
                if best is None or L > best[0]:
                    best = (L, x0, y0, x1, y1)
        if best is None:
            continue
        L, x0, y0, x1, y1 = best
        p = P((0.5 * (x0 + x1), 0.5 * (y0 + y1)))
        _text(dr, (p[0], p[1] - 16), m["name"], 20, fill=(120, 96, 66),
              bold=True, anchor="mb", halo=3)

    # ---- furniture -----------------------------------------------------
    _text(dr, (W * 0.5, 40), "阿斯拉王国 · 王都  Asura Royal Capital",
          46, fill=(58, 46, 32), bold=True, anchor="ma")
    _text(dr, (W * 0.5, 96),
          "总平面 r = %.0f m  ·  街区 %d  ·  地块 %d  ·  建筑 %d  ·  seed %d"
          % (c["radius"], c["stats"]["blocks"], c["stats"]["plot_count"],
             c["stats"]["buildings"], c["seed"]),
          24, fill=(104, 88, 66), anchor="ma")

    # legend
    lx, ly = 70, W - 330
    dr.rectangle([lx - 16, ly - 16, lx + 470, ly + 250], fill=(248, 243, 232),
                 outline=(206, 192, 168), width=2)
    _text(dr, (lx, ly), "图例", 26, bold=True)
    yy = ly + 40
    rows = [("core", "内城 建筑 (r<320)"), ("mid", "中带 建筑 (320-480)"),
            ("outer", "外圈 建筑 (>480)")]
    for key, lab in rows:
        dr.rectangle([lx, yy, lx + 26, yy + 18], fill=TIER_C[key],
                     outline=TIER_EDGE[key])
        _text(dr, (lx + 38, yy - 2), lab, 21)
        yy += 28
    for lab, wpx in (("主街 11 m", 11), ("次街 7 m", 7), ("巷 4 m", 4)):
        dr.line([lx, yy + 9, lx + 30, yy + 9], fill=(196, 180, 152),
                width=max(1, int(round(wpx * scale))))
        _text(dr, (lx + 38, yy - 2), lab, 21)
        yy += 28
    dr.rectangle([lx, yy, lx + 26, yy + 18], fill=(120, 40, 34))
    _text(dr, (lx + 38, yy - 2), "地标 / 城门", 21)
    yy += 26
    _text(dr, (lx, yy), "点线：内城界 r=%.0f m" % c["core_r"], 19,
          fill=(140, 120, 92))

    # scale bar
    sx, sy = W - 470, W - 130
    m100 = 100.0 * scale
    dr.rectangle([sx, sy, sx + m100 * 2, sy + 10], fill=(60, 50, 36))
    dr.rectangle([sx, sy, sx + m100, sy + 10], fill=(248, 243, 232))
    dr.line([sx, sy, sx + m100 * 2, sy], fill=(60, 50, 36), width=2)
    for i, lab in enumerate(("0", "100", "200 m")):
        _text(dr, (sx + i * m100, sy + 14), lab, 20, anchor="ma")

    # north arrow
    cx, cy = W - 130, 170
    dr.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], outline=(150, 132, 104),
               width=2)
    dr.polygon([(cx, cy - 40), (cx - 14, cy + 18), (cx, cy + 8), (cx + 14, cy + 18)],
               fill=(72, 60, 44))
    _text(dr, (cx, cy + 26), "北", 22, bold=True, anchor="ma")

    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    img.save(path)
    return path


# --------------------------------------------------------------------------
# 8. drop-in compatibility with the previous 300 m module
# --------------------------------------------------------------------------
def shop_footprint(kind):
    """(w, d, h) -- capital_hd_glue asks for it."""
    return SHOP_FOOT[kind]


def house_footprint(kind):
    return HOUSE_FOOT[kind]


def house_dims(kind):
    w, d = HOUSE_WALL[kind]
    return w, d, HOUSE_FLOORS[kind]


def yaw_of(rec):
    """Record rz -> mesh yaw (the mesh facade is local +Y)."""
    return mesh_yaw(rec["rz"])


def capital_layout_specs(**kw):
    """Old signature, new engine: the radius is read from the spec so the same
    code serves the 300 m legacy build and the 640 m capital."""
    return dict(kw)


def _compat(layout):
    role_of = {b["id"]: b["role"] for b in layout["blocks"]}
    placements = []
    houses = shops = 0
    for r in layout["plots"]:
        src = "house" if r["kind"].startswith("house_") else "shop"
        if src == "house":
            houses += 1
        else:
            shops += 1
        placements.append(dict(kind=r["kind"], source=src, x=r["pos"][0],
                               y=r["pos"][1], z=0.0, yaw=mesh_yaw(r["rz"]),
                               block=r["block_id"], ring=r["tier"],
                               district=role_of.get(r["block_id"], ""),
                               scale=r["scale"], seed=r["seed"]))
    for r in layout.get("landmarks", []):
        placements.append(dict(kind=r["kind"],
                               source="gate" if r["kind"] == "gate" else "landmark",
                               x=r["pos"][0], y=r["pos"][1], z=0.0,
                               yaw=mesh_yaw(r["rz"]), block=-1,
                               ring=r["tier"], district="landmark",
                               scale=1.0, seed=r["seed"]))
    st = layout["city"]["stats"]
    return dict(stats=dict(blocks=st["blocks"], sub_blocks=st["open"],
                           buildings=st["buildings"], houses=houses, shops=shops),
                placements=placements, blocks=layout["blocks"],
                city=layout["city"], plots=layout["plots"],
                landmarks=layout.get("landmarks", []),
                streets=layout["streets"])


def layout_city(specs=None):
    specs = specs or {}
    radius = float(specs.get("radius", specs.get("r_wall", 636.0)))
    seed = int(specs.get("seed", 7))
    return _compat(generate(radius=radius, seed=seed))


def layout(spec=None):
    return layout_city(spec or {})


def city_specs(radius=636.0, seed=7):
    return dict(radius=radius, seed=seed)


if __name__ == "__main__":
    lay = generate(636.0, 7)
    report(lay)
    print("json  ->", save(lay, OUT_JSON))
    print("png   ->", schematic(lay, OUT_PNG))
