"""Street paving for the capital.

`ground_hd()` lays one flat box per street, so at the 2.5D camera the whole
town is a pale plane with a few lighter rectangles on it: no kerb, no gutter, no
crown, nothing for the sun to catch.  This module replaces that with a real
road: a crowned cobble carriageway with a worn gutter down the middle and a
kerb band at each edge, following the street's own polyline instead of the
straight chord between its ends (a chord cuts every corner and leaves unpaved
wedges wherever a street bends).

After the roofs the street is the surface the player sees most of, so it is
worth modelling instead of texturing.
"""
import math

BASE_Z = 0.020          # carriageway sits just under the block slabs (0.06)
PITCH = 3.2             # metres between cross sections
EDGE = 0.28             # kerb band at each edge
CROWN = 1.10            # distance from the centre line that reaches full crown
HALF_GUT = 0.26         # half width of the centre channel
Z_CROWN = 0.030
Z_EDGE = 0.012
Z_GUT = 0.008


def _unit(dx, dy):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-9 else (0.0, 0.0)


def profile(half):
    """(points, gutter_band_start, gutter_band_end) across the road.

    Bands are the faces between consecutive points, left to right; the middle
    ones are the worn channel and get a darker stone.
    """
    h = half
    e = min(EDGE, h * 0.30)
    c = min(CROWN, h - e - 0.05)
    if c < HALF_GUT + 0.10:                  # an alley: crown only, no kerb
        return ((-h, 0.0), (-h + e, Z_EDGE), (-HALF_GUT, Z_GUT * 1.6),
                (HALF_GUT, Z_GUT * 1.6), (h - e, Z_EDGE), (h, 0.0)), 2, 3
    return ((-h, 0.0), (-h + e, Z_EDGE), (-c, Z_CROWN), (-HALF_GUT, Z_CROWN),
            (-HALF_GUT, Z_GUT), (HALF_GUT, Z_GUT), (HALF_GUT, Z_CROWN),
            (c, Z_CROWN), (h - e, Z_EDGE), (h, 0.0)), 3, 6


def _segments(street):
    """The street's centre line as a list of [(x, y), (x, y)] pieces.

    `segs` holds flat [x1, y1, x2, y2] records that are *mostly* chained end to
    end, but the list also carries partial duplicates and reversed copies, so
    the pieces have to be stitched rather than trusted in order.  `a`/`b` are
    only the straight chord between the two ends: using them directly cuts
    every corner and throws paving across whole blocks.
    """
    out = []
    for seg in (street.get("segs") or ()):
        try:
            if isinstance(seg[0], (list, tuple)):
                pts = [(float(p[0]), float(p[1])) for p in seg]
            else:
                pts = [(float(seg[0]), float(seg[1])), (float(seg[2]), float(seg[3]))]
        except (TypeError, IndexError, ValueError):
            continue
        for i in range(len(pts) - 1):
            if math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) > 0.05:
                out.append((pts[i], pts[i + 1]))
    if not out:
        a, b = street.get("a"), street.get("b")
        if a and b:
            out.append(((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
    return out


def _chains(street, tol=0.75):
    """Stitch the street's pieces into one or more continuous runs."""
    segs = _segments(street)
    runs = []
    while segs:
        run = list(segs.pop(0))
        grew = True
        while grew:
            grew = False
            ex, ey = run[-1]
            sx, sy = run[0]
            for i, (p, q) in enumerate(segs):
                if math.hypot(q[0] - ex, q[1] - ey) <= tol:
                    run.append(p)
                elif math.hypot(p[0] - ex, p[1] - ey) <= tol:
                    run.append(q)
                elif math.hypot(q[0] - sx, q[1] - sy) <= tol:
                    run.insert(0, p)
                elif math.hypot(p[0] - sx, p[1] - sy) <= tol:
                    run.insert(0, q)
                else:
                    continue
                segs.pop(i)
                grew = True
                break
        if len(run) >= 2:
            runs.append(run)
    return runs


def _resample(run):
    """Points every PITCH metres along one run."""
    out = []
    for i in range(len(run) - 1):
        ax, ay = run[i]
        bx, by = run[i + 1]
        n = max(1, int(math.hypot(bx - ax, by - ay) / PITCH))
        for k in range(n):
            t = k / float(n)
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    out.append(run[-1])
    return out


def _frames(pts):
    """(point, left unit vector) at every vertex, mitred across bends."""
    frames = []
    n = len(pts)
    for i in range(n):
        if i == 0:
            ux, uy = _unit(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
            k = 1.0
        elif i == n - 1:
            ux, uy = _unit(pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
            k = 1.0
        else:
            ax, ay = _unit(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
            bx, by = _unit(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            mx, my = ax + bx, ay + by
            if math.hypot(mx, my) < 1e-6:            # a hairpin: fall back
                mx, my = ax, ay
            ux, uy = _unit(mx, my)
            c = max(0.35, ux * ax + uy * ay)
            k = min(2.6, 1.0 / c)
        frames.append((pts[i], (-uy * k, ux * k)))
    return frames


def _strip(sections, lo, hi):
    """Faces between profile bands [lo, hi) along a list of sections."""
    verts, faces = [], []
    np_ = len(sections[0])
    for sec in sections:
        verts.extend(sec)
    for i in range(len(sections) - 1):
        a = i * np_
        b = (i + 1) * np_
        for k in range(lo, hi):
            # profile points run right -> left, so this order (and not the
            # obvious one) is what leaves the normal pointing at the sky
            faces.append((a + k, b + k, b + k + 1, a + k + 1))
    return verts, faces


def pave(streets, min_w=3.0):
    """Two (verts, faces) pools: the carriageway and the centre channel."""
    bed = ([], [])
    gut = ([], [])
    for idx, s in enumerate(streets):
        w = float(s.get("w") or 6.0)
        if w < min_w:
            continue
        prof, gs, ge = profile(w * 0.5)
        # a hair of vertical separation per street: two ribbons that cross are
        # otherwise exactly coplanar and strobe along the junction.  0.9 mm was
        # enough of a step for the shadow map to draw a hard dark seam across
        # every junction in the render, so it is now 0.15 mm -- below the
        # shadow bias, still enough to break the tie.
        z0 = BASE_Z + 0.00015 * (idx % 9)
        for run in _chains(s):
            pts = _resample(run)
            if len(pts) < 2:
                continue
            frames = _frames(pts)
            sections = []
            for (p, (lx, ly)) in frames:
                px, py = p
                sections.append([(px + lx * o, py + ly * o, z0 + dz) for (o, dz) in prof])
            v, f = _strip(sections, 0, gs)
            n0 = len(bed[0])
            bed[0].extend(v)
            bed[1].extend(tuple(i + n0 for i in q) for q in f)
            v, f = _strip(sections, gs, ge)
            n1 = len(gut[0])
            gut[0].extend(v)
            gut[1].extend(tuple(i + n1 for i in q) for q in f)
            v, f = _strip(sections, ge, len(prof) - 1)
            n2 = len(bed[0])
            bed[0].extend(v)
            bed[1].extend(tuple(i + n2 for i in q) for q in f)
    return bed, gut


def build(K, MAT, streets, name_bed="streets_bed", name_gut="streets_gutter"):
    """Create the paving objects; returns a list of objects."""
    bed, gut = pave(streets)
    out = []
    if bed[1]:
        ob = K.mesh_obj(name_bed, bed[0], bed[1])
        K.assign(ob, MAT["cobble"])
        out.append(ob)
    if gut[1]:
        ob = K.mesh_obj(name_gut, gut[0], gut[1])
        K.assign(ob, MAT["street"])
        out.append(ob)
    return out
