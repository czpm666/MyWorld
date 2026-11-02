"""Dense row-house repack of the capital layout.

The stock layout engine packs plots with a 3.6 m setback from the kerb and a 4 m
gap between neighbours; the buildings fill 21 % of the block area.  At the 2.5D
camera (52 deg pitch, 34 m distance, ~35 m of visible ground) that reads as
houses dropped on a car park -- the frame is mostly bare ground.

This module throws that packing away and re-tiles every block the way a walled
medieval town actually grew:

    * a continuous frontage wall along every block edge, facades within a step
      of the kerb, neighbours separated by a hand's width instead of a garden,
    * terraces: one unit's gable wall is the next one's,
    * depth taken from the block, so a back-to-back terrace on a narrow block
      and a deep row on a wide one,
    * a ragged inner line, because a row where every house is equally deep
      reads as a texture repeat from above.

Nothing here touches the street plan, the landmarks or the wall; it only
replaces the plot list with a denser one, so every downstream builder keeps
working unchanged.  Pure python on purpose: the packing can be developed and
checked against layout.json without starting Blender.
"""
import json
import math
import random

# --------------------------------------------------------------------------
# house stock: (kind, floor range, depth range, relative weight)
# --------------------------------------------------------------------------
# `house_X` names are what capital.py's _house_kind() understands; the prefix is
# stripped and mapped onto hd_houses' eight silhouette types.
STOCK = {
    # Heights matter more than anything else for the game camera.  The rig sits
    # 27.8 m up looking down at 52 deg, so a three-storey wall (10-13 m) hides
    # the street behind it and the frame fills with roof.  At one or two
    # storeys the camera sees facade + roof + street at once, which is the
    # "Link's Awakening" read: big roofs, visible doors and windows, and the
    # street still legible.  Tall buildings are the exception now, not the rule.
    "timber":    ("house_timber",    (1, 2), (7.5, 11.0), 5),
    "craft":     ("house_craft",     (1, 2), (8.0, 12.0), 3),
    "stone":     ("house_stone",     (1, 2), (8.5, 12.5), 3),
    "shop":      ("house_shop",      (2, 2), (8.0, 11.5), 2),
    "inn":       ("house_inn",       (2, 3), (9.5, 13.0), 1),
    "manor":     ("house_manor",     (2, 3), (10.0, 13.5), 1),
    "tower":     ("house_tower",     (3, 3), (6.5, 8.5),  1),
    "warehouse": ("house_warehouse", (1, 2), (10.0, 14.0), 2),
}

# district role -> weighted stock keys
DISTRICT = {
    "palace":      (("stone", 5), ("manor", 3), ("timber", 2)),
    "guild":       (("stone", 4), ("shop", 3), ("timber", 3), ("manor", 1)),
    "temple":      (("stone", 5), ("timber", 3), ("manor", 2)),
    "artisan":     (("craft", 5), ("timber", 4), ("stone", 1)),
    "craft":       (("craft", 5), ("timber", 4), ("stone", 1)),
    "residential": (("timber", 6), ("craft", 2), ("stone", 2), ("shop", 1)),
    "dock":        (("warehouse", 4), ("timber", 4), ("craft", 2)),
    "outer":       (("timber", 7), ("craft", 2), ("stone", 1)),
    "ward":        (("timber", 5), ("craft", 3), ("stone", 2)),
}
DEFAULT_DISTRICT = (("timber", 5), ("craft", 3), ("stone", 2))

MIN_W = 4.6          # narrowest unit worth building
GAP = 0.22           # hand's width between two houses in a terrace
SETBACK = 0.75       # kerb -> facade: a step and a gutter, nothing more
MAX_D = 12.5
MIN_D = 6.0
RING_GAP = 0.70      # alley width between two terraces inside a block
REF_R = 636.0        # the radius the density falloff was tuned at

# measured footprints of hd_shops' specialty buildings; capital.py overrides this
# with hd_shops.FOOTPRINT itself, the copy is here so the packer can be checked
# without bpy
FALLBACK_FOOT = {
    "adventurers_guild": (12.0, 12.5), "apothecary": (10.0, 11.1),
    "auction_house": (12.9, 15.6), "bakery": (11.1, 10.8),
    "bathhouse": (11.5, 16.4), "blacksmith": (10.6, 10.3),
    "chapel": (10.1, 16.5), "clothier": (7.7, 10.9),
    "general_store": (11.7, 11.9), "guard_post": (9.6, 11.8),
    "inn": (13.2, 13.8), "library": (16.8, 14.6),
    "magic_shop": (7.9, 9.5), "mill": (13.4, 13.4),
    "noble_manor": (15.2, 15.6), "stable": (16.7, 12.3),
    "tavern": (11.3, 12.8), "warehouse": (13.9, 13.9),
    "weaponsmith": (10.3, 13.2),
}


# --------------------------------------------------------------------------
# small geometry helpers
# --------------------------------------------------------------------------
def _area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return a * 0.5


def _ccw(pts):
    return list(pts) if _area(pts) > 0 else list(reversed(pts))


def _unit(dx, dy):
    L = math.hypot(dx, dy)
    return (dx / L, dy / L) if L > 1e-9 else (0.0, 0.0)


def _offset(pts, dist):
    """Inset a CCW polygon by `dist` (moves every edge inward along its normal).

    Vertices land on the intersection of the two neighbouring offset lines.  A
    block is convex or very nearly so; on the few that are not, the caller's
    overlap test throws the bad units away.
    """
    n = len(pts)
    lines = []
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ux, uy = _unit(bx - ax, by - ay)
        nx, ny = uy, -ux                       # outward normal of a CCW polygon
        lines.append(((ax - nx * dist, ay - ny * dist), (ux, uy)))
    out = []
    for i in range(n):
        (p1, d1) = lines[i - 1]
        (p2, d2) = lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9:                    # collinear edges: keep the point
            out.append(p2)
            continue
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append((p1[0] + d1[0] * t, p1[1] + d1[1] * t))
    return out


def _obb(cx, cy, rz, w, d):
    """Corner points of a w x d rectangle centred at (cx, cy), facing rz.

    `rz` is the direction the facade looks in (the outward normal of the block
    edge), so the frontage width runs along the tangent and the depth runs back
    along the normal.  Getting these two the wrong way round makes every unit
    collide with its neighbours and the row packs at half density.
    """
    fx, fy = math.cos(rz), math.sin(rz)        # facade normal (outward)
    tx, ty = -fy, fx                           # along the facade
    hw, hd = w * 0.5, d * 0.5
    return ((cx - tx * hw - fx * hd, cy - ty * hw - fy * hd),
            (cx + tx * hw - fx * hd, cy + ty * hw - fy * hd),
            (cx + tx * hw + fx * hd, cy + ty * hw + fy * hd),
            (cx - tx * hw + fx * hd, cy - ty * hw + fy * hd))


def _sep(a, b, tol):
    """Separating-axis test for two convex quads; True when they do not overlap."""
    for poly in (a, b):
        for i in range(4):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % 4]
            ax, ay = -(y2 - y1), (x2 - x1)
            L = math.hypot(ax, ay)
            if L < 1e-9:
                continue
            ax, ay = ax / L, ay / L
            amin = min(p[0] * ax + p[1] * ay for p in a)
            amax = max(p[0] * ax + p[1] * ay for p in a)
            bmin = min(p[0] * ax + p[1] * ay for p in b)
            bmax = max(p[0] * ax + p[1] * ay for p in b)
            if amax - tol <= bmin or bmax - tol <= amin:
                return True
    return False


def _pick(rng, table):
    tot = sum(w for _k, w in table)
    r = rng.random() * tot
    for k, w in table:
        r -= w
        if r <= 0:
            return k
    return table[-1][0]


# --------------------------------------------------------------------------
# street lookup: which street does a block edge front, and how wide is it
# --------------------------------------------------------------------------
class _Streets(object):
    CELL = 24.0

    def __init__(self, streets):
        self.seg = []
        self.grid = {}
        for s in streets:
            kind = str(s.get("kind") or "")
            w = float(s.get("w") or 6.0)
            for (x1, y1, x2, y2) in (s.get("segs") or []):
                i = len(self.seg)
                self.seg.append((x1, y1, x2, y2, kind, w))
                gx0 = int(math.floor(min(x1, x2) / self.CELL))
                gx1 = int(math.floor(max(x1, x2) / self.CELL))
                gy0 = int(math.floor(min(y1, y2) / self.CELL))
                gy1 = int(math.floor(max(y1, y2) / self.CELL))
                for gx in range(gx0, gx1 + 1):
                    for gy in range(gy0, gy1 + 1):
                        self.grid.setdefault((gx, gy), []).append(i)

    def near(self, x, y, r=26.0):
        gx, gy = int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL))
        best, bk, bw, bd = None, "", 6.0, r
        for ix in (gx - 1, gx, gx + 1):
            for iy in (gy - 1, gy, gy + 1):
                for i in self.grid.get((ix, iy), ()):
                    x1, y1, x2, y2, kind, w = self.seg[i]
                    d = _segdist(x, y, x1, y1, x2, y2)
                    if d < bd:
                        bd, bk, bw, best = d, kind, w, i
        if best is None:
            return None, 6.0, r
        return bk, bw, bd

    def width(self, x, y):
        k, w, _d = self.near(x, y)
        return w


def _segdist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


# --------------------------------------------------------------------------
# the packer
# --------------------------------------------------------------------------
def _depth_for(block):
    """Row depth for a block: deep enough to be back-to-back, never absurd."""
    a = abs(_area(block["poly"]))
    per = 0.0
    p = block["poly"]
    for i in range(len(p)):
        per += math.hypot(p[(i + 1) % len(p)][0] - p[i][0], p[(i + 1) % len(p)][1] - p[i][1])
    half = (2.0 * a / max(1.0, per)) if per > 1.0 else 8.0
    return max(4.2, min(MAX_D, half * 0.62))


_STATS = {"rows": 0, "placed": 0, "collide": 0, "skip": 0, "guard": 0,
          "short": 0, "edge_len": 0.0}


def _row(poly, outward, grown, rng, stock_table, dmax, street, block_id, tier,
         district, out, foot, shop_chance, depth_bias=1.0, skip=0.0, ring_no=0):
    """March along every edge of `poly` and stack a terrace against it.

    `outward` = True  -> facades look away from the polygon (street frontage)
    `outward` = False -> facades look into the polygon (courtyard frontage)
    `grown`   = how far the *centre* line sits inside the edge (setback + d/2).
    `ring_no` = 0 for the street-facing row, 1+ for the terraces behind it.
    """
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ux, uy = _unit(bx - ax, by - ay)
        if ux == 0.0 and uy == 0.0:
            continue
        L = math.hypot(bx - ax, by - ay)
        _STATS["rows"] += 1
        _STATS["edge_len"] += L
        # outward normal for a CCW polygon is the right-hand side of travel
        nx, ny = uy, -ux
        if not outward:
            nx, ny = -nx, -ny
        rz = math.atan2(ny, nx)                       # facade direction
        skind, sw, sd = street.near((ax + bx) * 0.5, (ay + by) * 0.5)
        main_front = skind in ("main", "secondary")
        t = 0.0
        guard = 0
        while t < L - MIN_W and guard < 400:
            guard += 1
            key = _pick(rng, stock_table)
            kind, flo, dep, _w = STOCK[key]
            w = rng.choice((5.0, 5.6, 6.2, 7.0, 7.8, 8.6, 9.6, 10.8, 12.0))
            w *= rng.uniform(0.94, 1.06)
            if t + w > L - 0.05:
                w = L - t - 0.05
            if w < MIN_W:
                _STATS["short"] += 1
                break
            d = rng.uniform(0.78, 1.02) * dmax
            if d < 3.6:
                d = 3.6
            w *= 1.0
            floors = rng.randint(*flo)
            # shop frontage only on the street side, only where people pass
            is_shop = False
            if shop_chance > 0.0 and outward and main_front and rng.random() < shop_chance:
                cand = _shop_candidate(rng, district, foot, w, dmax)
                if cand is not None:
                    sk, sw2, sd2 = cand
                    if t + sw2 <= L - 0.05 and sw2 <= w + 3.0:
                        kind, w, d, is_shop = sk, sw2, sd2, True
            cx = ax + ux * (t + w * 0.5) - nx * (grown + d * 0.5)
            cy = ay + uy * (t + w * 0.5) - ny * (grown + d * 0.5)
            quad = _obb(cx, cy, rz, w, d)
            # hard invariant: no house in a carriageway, whatever the block
            # polygon does at the rim.  The polygon is cut on the kerb line, so
            # a correct terrace sits >= 0.75 m outside it; this catches the
            # handful of blocks whose rim polygon overlaps a ring road.
            nk, nw, nd = street.near(cx, cy)
            if nd < nw * 0.5 + 0.45:
                _STATS["road"] = _STATS.get("road", 0) + 1
                t += 0.45
                continue
            bad = False
            for q in out:
                if not _sep(quad, q["quad"], 0.02):
                    bad = True
                    break
            if bad:
                _STATS["collide"] += 1
                t += 0.45                          # slide up to the collision
                continue
            if skip > 0.0 and rng.random() < skip:
                _STATS["skip"] += 1
                t += w + GAP                       # a missing house in the row
                continue
            rec = dict(kind=kind, x=cx, y=cy, z=0.0,
                       yaw=math.atan2(-math.cos(rz), math.sin(rz)),
                       block=block_id, ring=ring_no, tier=tier, district=district,
                       scale=1.0, seed=rng.getrandbits(30), quad=quad,
                       w=w, d=d, floors=floors,
                       variant="gable" if rng.random() < 0.32 else "eaves",
                       source="shop" if is_shop else "house")
            if is_shop:
                rec.pop("w", None)
                rec.pop("d", None)
                rec.pop("floors", None)
            out.append(rec)
            _STATS["placed"] += 1
            t += w + GAP
        if guard >= 400:
            _STATS["guard"] += 1


def _shop_candidate(rng, district, foot, w, dmax):
    """A specialty building that fits a gap of `w` and a row `dmax` deep."""
    pool = {
        "palace": ("noble_manor", "chapel", "library"),
        "guild": ("adventurers_guild", "general_store", "clothier", "auction_house",
                  "magic_shop", "apothecary"),
        "temple": ("chapel", "library", "apothecary"),
        "artisan": ("blacksmith", "bakery", "weaponsmith", "clothier"),
        "craft": ("blacksmith", "bakery", "weaponsmith", "mill"),
        "residential": ("tavern", "inn", "bakery", "general_store", "apothecary"),
        "dock": ("warehouse", "tavern", "inn"),
        "outer": ("stable", "bakery", "tavern", "guard_post"),
    }.get(district)
    if not pool:
        return None
    for _ in range(6):
        kind = rng.choice(pool)
        if kind not in foot:
            continue
        fw, fd = float(foot[kind][0]), float(foot[kind][1])
        if fd > dmax + 0.5:
            continue
        if fw > w * 2.2:
            continue
        return kind, float(fw), float(fd)
    return None


def _self_intersects(pts):
    """True when an inset polygon folded over itself.

    Offsetting a block with a sharp concave corner by more than the corner
    radius produces a bow-tie.  Marching a row along it places quads that
    overlap each other and the row collapses into a pile of collisions, so the
    caller stops terracing at that ring instead.
    """
    n = len(pts)

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def hit(p1, p2, p3, p4):
        d1 = cr(p3, p4, p1)
        d2 = cr(p3, p4, p2)
        d3 = cr(p1, p2, p3)
        d4 = cr(p1, p2, p4)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if hit(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
                return True
    return False


def _covered(poly, blocks, barea):
    """Fraction of the block already taken by the units placed so far."""
    if barea <= 1.0:
        return 1.0
    tot = 0.0
    for q in blocks:
        tot += q.get("w", 0.0) * q.get("d", 0.0)
    return tot / barea


def placements(res, foot_override=None, seed=7, open_roles=("square", "plaza", None),
               dense_outer=0.82, shop_chance=0.10, courtyard=True,
               cov_max=0.36):
    """Return a placement list for `res` in the shape capital.py's hd_pick wants.

    cov_max is the fraction of a block's area that may end up covered.  A city
    that is packed to 67 % reads as a carpet of roofs from the 2.5D camera and
    the streets disappear; 0.32-0.40 leaves courtyards and gardens behind the
    frontage row, which is both more medieval and far more legible.
    """
    foot = dict(FALLBACK_FOOT)
    if foot_override:
        foot.update(foot_override)
    rng = random.Random(seed + 3301)
    street = _Streets(res.get("streets") or ())
    out = []
    blocks_used = 0
    city_r = float((res.get("city") or {}).get("radius") or REF_R)
    for b in res.get("blocks") or ():
        poly = b.get("poly") or ()
        if len(poly) < 3 or b.get("open"):
            continue
        role = b.get("role")
        if role in open_roles:
            continue
        if abs(_area(poly)) < 120.0:
            continue
        # the outer ring keeps a ragged edge instead of a razor-cut boundary,
        # but the gaps have to be individual houses: dropping whole blocks left
        # parking-lot sized holes in the plan
        cx = sum(p[0] for p in poly) / float(len(poly))
        cy = sum(p[1] for p in poly) / float(len(poly))
        u = min(1.0, math.hypot(cx, cy) / max(city_r, 1.0))
        skip = 0.0 if u < dense_outer else min(0.62, (u - dense_outer) / (1.0 - dense_outer) * 0.62)
        if skip >= 0.62:
            continue
        blocks_used += 1
        tier = b.get("tier")
        district = role or ""
        table = DISTRICT.get(district, DEFAULT_DISTRICT)
        dmax = _depth_for(b)
        blocks = []
        # march the *facade line* (the block outline pushed in by the setback),
        # so the mitre at every corner is where one row stops and the next
        # starts; marching the raw outline made each row run into the corner and
        # slide blindly past a full row's depth, throwing away ~40 % of the
        # frontage on a five-sided block
        face = _offset(_ccw(poly), SETBACK)
        if len(face) >= 3 and abs(_area(face)) > 40.0:
            _row(face, True, 0.0, rng, table, dmax, street, b.get("id"),
                 tier, district, blocks, foot, shop_chance, skip=skip, ring_no=0)
        # terrace inward only while the block is still under its coverage cap:
        # the frontage row is what makes a street read, and everything behind it
        # is courtyard.  Packing every ring was what turned the plan into a
        # carpet of roofs with no visible streets.
        #
        # Ring k faces *into* the courtyard, so its facade line sits at the far
        # side of the terrace and the body grows back out towards ring k-1.
        # Getting that backwards makes every courtyard unit overlap the frontage
        # unit in front of it, and the row dies of collisions.
        if courtyard:
            barea = abs(_area(poly))
            cursor = SETBACK + dmax + RING_GAP
            for k in range(1, 4):
                if cov_max > 0.0 and _covered(poly, blocks, barea) >= cov_max:
                    break
                dk = dmax * (0.92 - 0.12 * k)
                inner = _offset(_ccw(poly), cursor + dk)
                if len(inner) < 3 or abs(_area(inner)) < 90.0:
                    break
                if _self_intersects(inner):
                    break
                _row(inner, False, 0.0, rng, table, dk,
                     street, b.get("id"), tier, district, blocks, foot, 0.0,
                     ring_no=k)
                cursor += dk + RING_GAP
        out.extend(blocks)
    return out


# --------------------------------------------------------------------------
# standalone check: prints the packing numbers and draws a schematic
# --------------------------------------------------------------------------
def _main():
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout.json")
    D = json.load(open(p, "r", encoding="utf-8"))
    res = dict(blocks=D["blocks"], streets=D["streets"])
    pl = placements(res, seed=7)
    ba = sum(abs(_area(b["poly"])) for b in D["blocks"] if len(b["poly"]) >= 3)
    pa = sum(q["w"] * q["d"] for q in pl if q["source"] == "house")
    for q in pl:
        if q["source"] == "shop":
            q.setdefault("_a", 0.0)
    print("placements %d  (houses %d / shops %d)"
          % (len(pl), sum(1 for q in pl if q["source"] == "house"),
             sum(1 for q in pl if q["source"] == "shop")))
    print("block area %.0f m2, house footprint %.0f m2 -> coverage %.1f %% (was 20.6 %%)"
          % (ba, pa, 100.0 * pa / ba))
    widths = sorted(q["w"] for q in pl if q["source"] == "house")
    depths = sorted(q["d"] for q in pl if q["source"] == "house")
    print("unit width  p10 %.1f  median %.1f  p90 %.1f" %
          (widths[len(widths) // 10], widths[len(widths) // 2], widths[9 * len(widths) // 10]))
    print("unit depth  p10 %.1f  median %.1f  p90 %.1f" %
          (depths[len(depths) // 10], depths[len(depths) // 2], depths[9 * len(depths) // 10]))
    try:
        from PIL import Image, ImageDraw
    except Exception:
        print("(no PIL, schematic skipped)")
        return
    S = 1.6
    W = int(1400 * S)
    img = Image.new("RGB", (W, W), (16, 17, 20))
    dr = ImageDraw.Draw(img)
    C = W * 0.5
    sc = W * 0.5 / 700.0

    def T(x, y):
        return (C + x * sc, C - y * sc)

    for b in D["blocks"]:
        if len(b["poly"]) >= 3:
            dr.polygon([T(*p) for p in b["poly"]], fill=(34, 37, 46))
    for s in D["streets"]:
        for (x1, y1, x2, y2) in (s.get("segs") or []):
            dr.line([T(x1, y1), T(x2, y2)], fill=(96, 100, 110), width=1)
    for q in pl:
        quad = [T(*p) for p in q["quad"]]
        col = (226, 138, 96) if q["source"] == "shop" else (206, 202, 192)
        dr.polygon(quad, fill=col)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "look", "_plan_dense.png")
    img.save(out)
    print("schematic ->", out)
    # per-block coverage, worst first
    per = {}
    for q in pl:
        s = per.setdefault(q["block"], [0.0, 0])
        s[0] += q["w"] * q["d"] if q["source"] == "house" else (q["quad"] and 1.0)
        s[1] += 1
    rows = []
    for b in D["blocks"]:
        if len(b["poly"]) < 3 or b.get("open"):
            continue
        a = abs(_area(b["poly"]))
        if a < 120:
            continue
        got = per.get(b["id"], [0.0, 0])
        rows.append((got[0] / a, a, got[1], b["id"], b["role"]))
    rows.sort()
    print("\nper-block coverage: %d blocks" % len(rows))
    for q in (0.05, 0.25, 0.5, 0.75, 0.95):
        r = rows[int(q * (len(rows) - 1))]
        print("  p%-3d %.0f m2  n=%-3d cov %.2f  %s" % (q * 100, r[1], r[2], r[0], r[4]))
    print("  zero-unit blocks:", sum(1 for r in rows if r[2] == 0))


if __name__ == "__main__":
    _main()
