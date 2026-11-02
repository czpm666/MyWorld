"""A street plan for the capital that is a *network*, not a spray of chords.

The old hd_layout engine grew streets by throwing segments at the disc and
keeping the ones that looked organic.  The result was a set of long chords that
crossed each other at arbitrary angles: no hierarchy, no continuity, and blocks
that were voronoi leftovers.  Terraced along those edges, the plan read as
shattered glass and the streets were invisible from the game camera.

This module plans the roads first, the way a town actually grows around a
castle:

  * ring roads that follow a wobbling radius, so they never look compass-drawn;
  * radial avenues from the gates to the castle, dead straight, because a
    straight avenue is the one thing that reads from a 30 m wide camera view:
    you see the whole street to its vanishing point;
  * every sector boundary carries a street, 4.5 m lanes between 8 m secondaries
    and 13 m avenues, so the hierarchy is visible in the plan and in the fog;
  * the whole plan is pushed through a smooth displacement field, which keeps
    the topology (streets continuous, block edges shared) but destroys the
    bullseye look.

Block polygons are built on the **kerb lines**, not the street centre lines, so
a house set back from the block edge is set back from the pavement and never
stands in the road.  Output is the same dict shape as layout.json, so hd_dense
and capital.py consume it unchanged.

    python hd_plan2.py 947            # write look/_plan2.png + stats
"""
import math
import os
import random
import sys

REF_R = 636.0

# Street widths.  Widening a street is cheap; a city whose main avenue is not
# visibly wider than its alleys has no hierarchy for the eye to read.
W_AVENUE = 13.0
W_RING = 11.0
W_SECOND = 8.0
W_LANE = 4.5

# Block size is set by ring spacing and sector angle: ~74 m between rings and
# 48 sectors gives 60-110 m blocks, which is one terrace row plus a courtyard -
# the unit a 2.5D camera can actually read.
SECTORS = 48
RING_STEP = 74.0


def _rng(seed):
    return random.Random(seed)


def _noise1(t, seed):
    """Cheap smooth 1-D noise in [-1, 1]: three out-of-phase sines."""
    r = _rng(seed)
    a, b, c = r.uniform(0, 6.28), r.uniform(0, 6.28), r.uniform(0, 6.28)
    return (math.sin(t * 1.0 + a) * 0.55 + math.sin(t * 2.3 + b) * 0.30
            + math.sin(t * 5.1 + c) * 0.15)


def _ang_noise(th, seed, harm=(1, 2, 3, 5)):
    """Smooth noise that is exactly 2*pi periodic in `th`.

    The first version fed a non-periodic sum of sines to the ring radii and to
    the warp, which left a seam at theta = 0: the ring radius at 0 and at 2*pi
    disagreed by tens of metres, blocks that straddled the seam were built from
    two different shapes, and houses ended up standing in the avenue.  Only
    integer harmonics are allowed here, so the loop closes exactly.
    """
    r = _rng(seed)
    out = 0.0
    tot = 0.0
    for h in harm:
        out += math.sin(h * th + r.uniform(0.0, 6.283185)) / float(h)
        tot += 1.0 / float(h)
    return out / tot


def _pt(r, th):
    return (r * math.cos(th), r * math.sin(th))


def _warp(r, th, R):
    """Push the plan through a smooth displacement field.

    A radial-concentric grid is legible but reads as a bullseye: perfect
    circles, perfect spokes, identical annular sectors.  Real towns are the
    same topology drawn by hand.  The field depends only on theta, so every
    ring is a scaled copy of the same wobbly outline: streets stay continuous,
    neighbouring blocks keep sharing their edge, and there is no seam.
    """
    dr = (0.150 * _ang_noise(th, 11, (1, 2)) + 0.050 * _ang_noise(th, 23, (3, 4, 5))
          + 0.022 * _ang_noise(th, 29, (7, 9, 11)))
    dth = 0.048 * _ang_noise(th, 37, (2, 3, 5)) + 0.018 * _ang_noise(th, 41, (3, 4, 7))
    return _pt(r * (1.0 + dr), th + dth)


def _seg(a, b):
    return [a[0], a[1], b[0], b[1]]


def _area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def _centroid(poly):
    n = float(len(poly))
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


# --------------------------------------------------------------------------
def build(radius=636.0, seed=7, reserved=(), core_r=None):
    """Return {'city','blocks','streets','landmarks'} for a capital of `radius`.

    `reserved` is a list of (cx, cy, r) discs that must stay empty: the castle
    rock, the cathedral close, the market square, the gatehouses.
    """
    rng = _rng(seed)
    R = float(radius)
    R_inner = R * 0.475
    if core_r is None:
        # the castle rock is ~120 m across; the town starts at its foot, not
        # 200 m away.  An empty disc in the middle is the loudest "generated"
        # tell a plan can have.
        core_r = R * 0.130

    # Sector boundaries are not evenly spaced.  A perfect 7.5 deg fan is what
    # makes a radial plan look like a radar; real wards are wider than others.
    ang = []
    a = 0.0
    for j in range(SECTORS):
        ang.append(a)
        a += (2.0 * math.pi / SECTORS) * rng.uniform(0.62, 1.38)
    scale = 2.0 * math.pi / a
    ang = [x * scale for x in ang]

    streets = []
    sid = [0]

    def add_street(kind, w, pts, name=""):
        segs = [_seg(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        if not segs:
            return None
        ln = sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in segs)
        rec = dict(id=sid[0], a=pts[0], b=pts[-1], w=w, kind=kind, name=name,
                   segs=segs, length=ln, blocks=[])
        sid[0] += 1
        streets.append(rec)
        return rec

    # -- wards: not every sector boundary gets a street ---------------------
    # A street on every one of the 48 boundaries, each running dead straight
    # from the castle to the wall, is what made the plan read as a radar
    # wheel: 48 identical spokes and ~640 identical wedge-shaped blocks.  A
    # real town is a handful of through-roads plus a lot of short lanes that
    # stop at a neighbour's wall.  So the fan is partitioned into wards one to
    # three sectors wide, and only ward boundaries become streets.  The blocks
    # then differ in size by up to 3x and the spokes stop being a fan.
    groups = []
    need = set()
    for _a in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
        # the four gates have to land on a street, not in the middle of a
        # terrace, so a ward boundary is forced at each cardinal axis
        need.add(min(range(SECTORS),
                     key=lambda j: abs(((ang[j] - _a + math.pi) % (2 * math.pi)) - math.pi)))
    j = 0
    while j < SECTORS:
        left = SECTORS - j
        span = rng.choices((1, 2, 3), (0.30, 0.44, 0.26))[0]
        nxt = [b for b in need if j < b < j + span]
        if nxt:
            span = min(nxt) - j
        span = max(1, min(span, left))
        if left - span == 1 and not [b for b in need if j < b < left]:
            span = left          # never strand a single-sector sliver at the end
        groups.append((j, span))
        j += span

    # -- per-ward jog of every ring ---------------------------------------
    # The ward grouping fixed the spokes but left the rings as continuous
    # circles: from the air the plan still read as a bullseye, because a ring
    # road that is one smooth arc all the way round does not exist in a town.
    # Real ring streets are chains of separate streets that step in and out at
    # every ward corner, following whatever was there first.  So each ring gets
    # a per-ward radial offset (+-2 % of R, i.e. +-19 m at 947 m), blended over
    # a narrow band at the ward corner so the kerb jogs instead of teleporting.
    ward_starts = sorted(ang[j0] for (j0, _s) in groups)
    ward_starts.append(2.0 * math.pi)
    n_wards = len(ward_starts) - 1
    ward_jog = []
    for _i in range(24):                      # more than any ring count
        ward_jog.append([0.020 * _noise1(_i * 31.7 + _k * 7.3, 97)
                         for _k in range(n_wards)])

    def _jogf(i, th):
        """Radial offset of ring `i` as a fraction of R, per ward."""
        t = th % (2.0 * math.pi)
        k = 0
        for _k in range(n_wards):
            if ward_starts[_k] <= t:
                k = _k
            else:
                break
        a0 = ward_starts[k]
        a1 = ward_starts[k + 1]
        row = ward_jog[i % len(ward_jog)]
        band = min(0.011, 0.30 * (a1 - a0))    # ~10 m of arc
        if band > 1e-6 and t - a0 < band:
            f = 0.5 + 0.5 * (t - a0) / band
            return row[(k - 1) % n_wards] * (1.0 - f) + row[k] * f
        if band > 1e-6 and a1 - t < band:
            f = 0.5 * (a1 - t) / band
            return row[(k + 1) % n_wards] * (1.0 - f) + row[k] * f
        return row[k]

    def _ring_r(nz, base, i, th):
        return base * (1.0 + 0.030 * _ang_noise(th, nz) + _jogf(i, th))

    # -- ring roads --------------------------------------------------------
    ring_radii = []
    r = core_r
    while r < R * 0.985:
        ring_radii.append(r)
        r += RING_STEP * rng.uniform(0.74, 1.26) * (1.0 + 0.10 * (r / R))
    ring_radii.append(R * 0.985)
    for f in (1.13, 1.29, 1.47):
        ring_radii.append(R * f)

    ring_meta = []
    n_rings = len(ring_radii)
    rim_pts = []
    rim_nz = 0
    rim_w = 0.0
    gates = []
    for i, base in enumerate(ring_radii):
        nz = 31 + i * 7
        pts = []
        for s in range(121):
            th = s * 2.0 * math.pi / 120.0
            # same wobble the blocks are cut from (ring_r_at) - when the street
            # and the block edge used different noise the kerb drifted up to
            # 6 % of the radius, i.e. 40 m at the rim, and whole terraces ended
            # up standing in the ring road
            pts.append(_warp(_ring_r(nz, base, i, th), th, R))
        # Not every ring is a road.  Fourteen concentric ring roads is the
        # loudest "generated" tell a plan can have; a town has three or four
        # through-rings and the rest of the annuli are back-to-back terraces
        # sharing a party wall.
        is_street = (i % 3 == 0) or (base > R * 0.98) or (i == n_rings - 1)
        if is_street:
            kind = "main" if (i % 3 == 0 or base > R) else "secondary"
            w = W_RING if kind == "main" else W_SECOND
            add_street(kind, w, pts, "ring %d" % i)
        else:
            w = 0.0
        ring_meta.append((base, nz, w))
        if abs(base - R * 0.985) < 1.0:
            # the curtain wall has to follow this line.  A circle drawn at
            # 0.985 R cuts through the outermost terraces wherever the plan
            # bulges and leaves a ring of bare ground where it pinches in.
            rim_nz, rim_w = nz, w
            rim_pts = [_warp(_ring_r(nz, base, i, s * 2.0 * math.pi / 120.0)
                             + w * 0.5 + 2.0,
                             s * 2.0 * math.pi / 120.0, R) for s in range(120)]

    rad_w = [0.0] * SECTORS
    rad_start = [0] * SECTORS
    n_rb = max(1, len(ring_radii) - 1)
    for gi, (j0, span) in enumerate(groups):
        # Only the through-roads reach the castle.  When all 25 spokes began at
        # the same point the middle of the plan was a spider web no matter how
        # much noise the outer rings had; letting the lanes start one or two
        # rings out breaks the convergence and reads as a town that grew.
        if gi % 5 == 0 or j0 in need:
            kind, w, drift_max, r0_i = "main", W_AVENUE, 0.000, 0
        elif gi % 2 == 0:
            kind, w, drift_max, r0_i = "secondary", W_SECOND, 0.030, min(1, n_rb)
        else:
            kind, w, drift_max, r0_i = "alley", W_LANE, 0.075, min(2, n_rb)
        rad_w[j0] = w
        rad_start[j0] = r0_i
        th0 = ang[j0]
        r0 = ring_radii[r0_i] * 0.985
        pts = [_warp(r0, th0, R)]
        steps = 30
        for s in range(1, steps + 1):
            t = s / float(steps)
            rr = r0 + (R * 1.55 - r0) * t
            drift = drift_max * _noise1(t * 2.2 + j0 * 0.9, 77 + j0) * t
            pts.append(_warp(rr, th0 + drift, R))
        add_street(kind, w, pts, "radial %d" % j0)
        if j0 in need and rim_nz:
            # where this avenue meets the wall: the warp rotates the whole
            # plan, so the gate is not on the mathematical axis any more and
            # capital.py has to be told where it actually is
            gp = _warp(R * 0.985 * (1.0 + 0.030 * _ang_noise(th0, rim_nz))
                       + rim_w * 0.5 + 2.0, th0, R)
            gates.append((gp, math.atan2(gp[1], gp[0])))

    # -- blocks, on the kerb lines ----------------------------------------
    blocks = []
    bid = [0]

    def ring_r_at(i, th):
        base, nz, _w = ring_meta[i]
        return _ring_r(nz, base, i, th)

    def kerb(i, th, dr):
        """A point `dr` metres outside ring i (negative = inside)."""
        return _warp(ring_r_at(i, th) + dr, th, R)

    def _kink(i, j0):
        """Angular kink of the ward edge at (ring i, ward start j0).

        Deterministic on purpose: the block inside ring i and the block outside
        it both call this with the same arguments, so a boundary with no street
        on it stays a shared party wall instead of two mismatched wobbly edges
        overlapping by ten metres.
        """
        return 0.020 * math.sin(i * 12.9898 + j0 * 78.233)

    def add_block(poly, role, tier):
        if len(poly) < 3 or _area(poly) < 150.0:
            return None
        cx, cy = _centroid(poly)
        for (rx, ry, rr) in reserved:
            if math.hypot(cx - rx, cy - ry) < rr:
                return None
        rec = dict(id=bid[0], poly=[(float(p[0]), float(p[1])) for p in poly],
                   role=role, tier=tier, area=_area(poly))
        bid[0] += 1
        blocks.append(rec)
        return rec

    n_ring_blocks = len(ring_radii) - 1
    for i in range(n_ring_blocks):
        wi = ring_meta[i][2] * 0.5
        wo = ring_meta[i + 1][2] * 0.5
        for (j0, span) in groups:
            j1 = j0 + span
            th_a = ang[j0]
            th_b = ang[j1 % SECTORS] + (2.0 * math.pi if j1 >= SECTORS else 0.0)
            mid = 0.5 * (th_a + th_b)
            r_mid = max(30.0, 0.5 * (ring_radii[i] + ring_radii[i + 1]))
            # the ward boundary's half width, expressed as an angle at this
            # radius: this is what puts the block edge on the kerb instead of
            # the centre line, so houses never stand in the road
            # a lane that starts two rings out leaves no gap in the rings
            # inside it: the two wards there share a party wall
            rw_in = rad_w[j0] if rad_start[j0] <= i else 0.0
            jb = j1 % SECTORS
            rw_out = rad_w[jb] if rad_start[jb] <= i else 0.0
            da = (rw_in * 0.5) / r_mid
            db = (rw_out * 0.5) / r_mid
            t0 = th_a + da
            t1 = th_b - db
            if t1 - t0 < 0.004:
                continue
            # a kerb line that runs dead straight between two rings reads as a
            # machined cut; every edge gets one kink.  The kink is a pure
            # function of (ring, ward) so the two blocks that meet on a
            # boundary without a street still share the exact same edge.
            jt_in = _kink(i, j0)
            jt_out = _kink(i + 1, j0)
            poly = [kerb(i, t0, wi), kerb(i, mid + jt_in, wi), kerb(i, t1, wi),
                    kerb(i + 1, t1, -wo), kerb(i + 1, mid + jt_out, -wo),
                    kerb(i + 1, t0, -wo)]
            tier = "core" if i == 0 else ("mid" if i <= 2 else "outer")
            role = _role_for(mid, i, n_ring_blocks)
            if ring_radii[i] > R * 0.985:
                role = "outer"
            add_block(poly, role, tier)

    city = dict(radius=R, wall_r=R * 0.985, core_r=core_r, mid_r=R_inner,
                seed=seed, rim=rim_pts,
                gates=[[[float(g[0][0]), float(g[0][1])], float(g[1])]
                       for g in gates],
                stats=dict(blocks=len(blocks), streets=len(streets),
                           buildings=0, houses=0, shops=0, open=0))
    return dict(city=city, blocks=blocks, streets=streets, landmarks=[])


def _role_for(mid, i, n):
    """District flavour.  Temple and guild wards sit on the avenues that face
    the cathedral and the guild hall; the rest is residential with craft and
    dock pockets, which is what makes shops cluster instead of scattering one
    per block."""
    deg = (math.degrees(mid) + 360.0) % 360.0
    if i == 0:
        return "palace" if 60.0 < deg < 120.0 else "guild"
    if abs(deg - 135.0) < 24.0:
        return "temple"
    if abs(deg - 20.0) < 24.0:
        return "guild"
    if abs(deg - 270.0) < 30.0:
        return "dock"
    if i >= n - 1:
        return "outer"
    return "residential" if (int(deg / 45.0) % 3) else "craft"


# --------------------------------------------------------------------------
def _main(argv):
    R = float(argv[1]) if len(argv) > 1 else 947.0
    plan = build(radius=R, seed=7)
    bs = sorted(b["area"] for b in plan["blocks"])
    print("radius %.0f" % R)
    print("  blocks %d   streets %d   total block area %.0f m2"
          % (len(plan["blocks"]), len(plan["streets"]), sum(bs)))
    if bs:
        print("  block area  p10 %.0f  median %.0f  p90 %.0f"
              % (bs[len(bs) // 10], bs[len(bs) // 2], bs[9 * len(bs) // 10]))
    for kind in ("main", "secondary", "alley"):
        ss = [s for s in plan["streets"] if s["kind"] == kind]
        print("  %-9s %3d streets  %.0f m"
              % (kind, len(ss), sum(s["length"] for s in ss)))
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return
    px = 1600
    half = R * 1.75
    sc = px * 0.5 / half
    img = Image.new("RGB", (px, px), (14, 15, 18))
    dr = ImageDraw.Draw(img)

    def T(x, y):
        return (px * 0.5 + x * sc, px * 0.5 - y * sc)

    for b in plan["blocks"]:
        dr.polygon([T(*p) for p in b["poly"]], fill=(33, 36, 44))
    for s in plan["streets"]:
        w = max(1, int(round(s["w"] * sc)))
        col = {"main": (120, 126, 138), "secondary": (96, 100, 110),
               "alley": (74, 77, 85)}[s["kind"]]
        for seg in s["segs"]:
            dr.line([T(seg[0], seg[1]), T(seg[2], seg[3])], fill=col, width=w)
    for rr in (R * 0.985, R * 0.475):
        dr.ellipse([T(-rr, rr), T(rr, -rr)], outline=(140, 84, 64), width=2)
    dr.text((10, 10), "plan2 r=%.0f  blocks %d  streets %d"
            % (R, len(plan["blocks"]), len(plan["streets"])), fill=(220, 220, 220))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "look", "_plan2_%d.png" % R)
    img.save(out)
    print("  ->", out)


if __name__ == "__main__":
    _main(sys.argv)
