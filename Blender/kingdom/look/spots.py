"""Pick camera viewpoints from the block footprints that are really in the blend.

Why this exists (v3, 2026-11-02)
--------------------------------
v1 and v2 scored street points by "how much facade is within 28 m"; both times
the top picks were inside blocks.  v2 rasterised footprints from a python
re-build of the plan -- and that re-build does not match the blend at all:

    build_v24.log : [capital] plan2: 642 blocks / 63 streets
                    [capital] hd_dense: 12215 placements, 463 dropped
    hd_plan2(seed=7)        -> 326 blocks / 32 streets / 12922 units
    hd_plan2(seed=20261022) -> 331 blocks / 31 streets / 13853 units

So v2 scored spots in a city that does not exist.  Its first pick stood 2.55 m
from a real wall and rendered as 100 % facade -- the `V24_street*.png` bug.

v3 takes its geometry from the blend: `look/_shotgrid.py` dumps the convex hull
of every `city_blk*` object (blocks are merged per block, so the hull is the
footprint of what is standing there).  On that raster it applies the tests the
old version never had:

  * volume, not plan -- eye clearance >= 1.2 m at 1.72 m, on a flat floor;
  * sight line -- 12 m of clear air ahead, sampled every 0.5 m at eye height;
  * the view direction is the corridor's own direction (24 candidates), not one
    of eight compass points.

Everything is vectorised over a lattice: a python loop over 1 M points x 24
directions x 124 steps is ~3e9 raster lookups and never finishes.

Output (consumed by look/render.py):
    look/spots.json
    {"src":"blend", "blocks":n, "stats":{...},
     "picks":     [{score,x,y,ux,uy,w,kind,r,run,clear,game_z,eye}],
     "eye_picks": [{score,x,y,ux,uy,w,kind,r,run,clear,los,eye}]}

    E:\\GameProject\\Python313\\python.exe look\\spots.py --want 12 --want-eye 10
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(KING))
sys.path.insert(0, KING)

RES = 0.62           # metres per raster cell
HALF = 1080.0        # half extent of the raster
PAD = 0.30           # grow every footprint by this much (arm's reach)
EYE_H = 1.72         # the eye camera's height
GAME_PITCH = 52.0    # Unity TopDownCameraRig.cs
GAME_DIST = 34.0
GAME_UP = GAME_DIST * math.sin(math.radians(GAME_PITCH))       # 26.79 m
GAME_BACK = GAME_DIST * math.cos(math.radians(GAME_PITCH))     # 20.93 m

S = 1.48
ROCK_C = (0.0, 205.0 * S)
CATH_C = (-152.0 * S, 58.0 * S)
GUILD_C = (142.0 * S, 66.0 * S)
R_WALL = 300.0 * S

# Hand-built landmarks.  `_reserved()` keeps houses off these, so they are not
# in the block hulls, but they are solid all the same.
LANDMARKS = [
    ("market_hall", "rect", (0.0, 34.0, 20.0, 11.0)),
    ("guild", "rect", (GUILD_C[0], GUILD_C[1], 10.0, 15.0)),
    ("cath_nave", "rect", (CATH_C[0], 78.0, 19.0, 35.0)),
    ("cath_transept", "rect", (CATH_C[0], 93.3, 39.4, 10.0)),
    ("cath_apse", "disc", (CATH_C[0], 118.0, 12.0)),
    ("fountain", "disc", (0.0, 0.0, 6.2)),
    ("castle_rock", "disc", (ROCK_C[0], ROCK_C[1], 96.8)),
]


def arg(name, default=None):
    """Accept flags both before and after `--` (plain python or blender)."""
    a = [v for v in sys.argv[1:] if v != "--"]
    if name in a and a.index(name) + 1 < len(a):
        return a[a.index(name) + 1]
    return default


# --------------------------------------------------------------------------- #
#  geometry in
# --------------------------------------------------------------------------- #
def load_blocks(path=None):
    path = path or os.path.join(HERE, "_shotblocks.json")
    if not os.path.exists(path):
        raise SystemExit("[spots] %s is missing -- run look/_shotgrid.py inside "
                         "blender first; it is the only honest source of block "
                         "footprints" % path)
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    print("[spots] %d block hulls from the blend (eave z p50 %.1f, p90 %.1f, max %.1f)"
          % (d["stats"]["n"], d["stats"]["z_p50"], d["stats"]["z_p90"],
             d["stats"]["z_max"]))
    return d


# --------------------------------------------------------------------------- #
#  raster
# --------------------------------------------------------------------------- #
def raster(polys, marks):
    n = int(2 * HALF / RES)
    grid = np.zeros((n, n), dtype=np.uint8)

    def cell(v):
        return int(math.floor((v + HALF) / RES))

    def fill(x0, x1, y0, y1, inside):
        gx, gy = np.meshgrid((np.arange(x0, x1 + 1) + 0.5) * RES - HALF,
                             (np.arange(y0, y1 + 1) + 0.5) * RES - HALF)
        sub = grid[y0:y1 + 1, x0:x1 + 1]
        sub[inside(gx, gy)] = 1

    for hull in polys:
        a = np.asarray(hull, dtype=np.float64)
        x0 = max(0, cell(a[:, 0].min() - PAD))
        x1 = min(n - 1, cell(a[:, 0].max() + PAD))
        y0 = max(0, cell(a[:, 1].min() - PAD))
        y1 = min(n - 1, cell(a[:, 1].max() + PAD))
        if x1 < x0 or y1 < y0:
            continue
        ar = 0.0
        for i in range(len(a)):
            j = (i + 1) % len(a)
            ar += a[i, 0] * a[j, 1] - a[j, 0] * a[i, 1]
        sgn = -1.0 if ar > 0 else 1.0
        edges = []
        for i in range(len(a)):
            j = (i + 1) % len(a)
            dx, dy = a[j, 0] - a[i, 0], a[j, 1] - a[i, 1]
            edges.append((a[i, 0], a[i, 1], dx, dy, PAD * math.hypot(dx, dy)))

        def inside(gx, gy, edges=edges, sgn=sgn):
            ok = np.ones(gx.shape, dtype=bool)
            for (ax, ay, dx, dy, tol) in edges:
                ok &= (((gx - ax) * dy - (gy - ay) * dx) * sgn >= -tol)
            return ok

        fill(x0, x1, y0, y1, inside)

    for name, kind, g in marks:
        if kind == "rect":
            cx, cy, hw, hd = g
            x0 = max(0, cell(cx - hw - PAD))
            x1 = min(n - 1, cell(cx + hw + PAD))
            y0 = max(0, cell(cy - hd - PAD))
            y1 = min(n - 1, cell(cy + hd + PAD))
            if x1 < x0 or y1 < y0:
                continue
            fill(x0, x1, y0, y1,
                 lambda gx, gy, cx=cx, cy=cy, hw=hw, hd=hd:
                 (np.abs(gx - cx) <= hw + PAD) & (np.abs(gy - cy) <= hd + PAD))
        else:
            cx, cy, r = g
            rr = r + PAD
            x0 = max(0, cell(cx - rr))
            x1 = min(n - 1, cell(cx + rr))
            y0 = max(0, cell(cy - rr))
            y1 = min(n - 1, cell(cy + rr))
            if x1 < x0 or y1 < y0:
                continue
            fill(x0, x1, y0, y1,
                 lambda gx, gy, cx=cx, cy=cy, rr=rr:
                 ((gx - cx) ** 2 + (gy - cy) ** 2) <= rr * rr)

    # the inner curtain: 3 m at R_WALL with a 14.4 m gate gap on each axis
    gx, gy = np.meshgrid((np.arange(n) + 0.5) * RES - HALF,
                         (np.arange(n) + 0.5) * RES - HALF)
    r = np.hypot(gx, gy)
    ring = (r > R_WALL - 1.5 - PAD) & (r < R_WALL + 1.5 + PAD)
    ang = np.abs(((np.arctan2(gy, gx) + math.pi / 4) % (math.pi / 2)) - math.pi / 4)
    grid[ring & ~(ang * r < 14.4 + PAD)] = 1
    return grid


def density(grid, win_m=40.0):
    """Fraction of solid ground inside a win_m box -- the "is this a town?" test.

    Without it the picker happily returns the strip of field that runs between
    the curtain wall and the first row of blocks: a corridor, but not a street.
    """
    k = max(3, int(round(win_m / RES)))
    g = grid.astype(np.float32)
    c = np.cumsum(np.cumsum(g, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    n = g.shape[0]
    half = k // 2
    lo = np.clip(np.arange(n) - half, 0, n)
    hi = np.clip(np.arange(n) - half + k, 0, n)
    out = c[hi][:, hi] - c[lo][:, hi] - c[hi][:, lo] + c[lo][:, lo]
    area = np.outer(hi - lo, hi - lo).astype(np.float32)
    return out / np.maximum(area, 1.0)


def clearance(grid):
    """Chamfer distance in metres from every free cell to the nearest solid."""
    n = grid.shape[0]
    d = np.where(grid > 0, 0.0, 1e6).astype(np.float32)
    a = RES
    b = RES * math.sqrt(2.0)
    for _ in range(2):
        for y in range(1, n):
            row, prev = d[y], d[y - 1]
            np.minimum(row, prev + a, out=row)
            np.minimum(row[1:], prev[:-1] + b, out=row[1:])
            np.minimum(row[:-1], prev[1:] + b, out=row[:-1])
            np.minimum(row[1:], row[:-1] + a, out=row[1:])
        for y in range(n - 2, -1, -1):
            row, nxt = d[y], d[y + 1]
            np.minimum(row, nxt + a, out=row)
            np.minimum(row[1:], nxt[:-1] + b, out=row[1:])
            np.minimum(row[:-1], nxt[1:] + b, out=row[:-1])
            np.minimum(row[1:], row[:-1] + a, out=row[1:])
    return d


# --------------------------------------------------------------------------- #
#  lattice + ray runs
# --------------------------------------------------------------------------- #
def lattice(step, rmin, rmax):
    """World-space lattice points inside an annulus, with their raster index."""
    n = int(2 * HALF / RES)
    v = np.arange(-HALF + step * 0.5, HALF, step)
    X, Y = np.meshgrid(v, v)
    x = X.ravel()
    y = Y.ravel()
    r = np.hypot(x, y)
    keep = (r >= rmin) & (r <= rmax)
    x, y = x[keep], y[keep]
    i = ((x + HALF) / RES).astype(np.int32)
    j = ((y + HALF) / RES).astype(np.int32)
    ok = (i > 1) & (j > 1) & (i < n - 2) & (j < n - 2)
    return x[ok], y[ok], i[ok], j[ok]


def runs(grid, x, y, dirs, limit, step=0.5):
    """Clear-run length from every point along every direction.

    Returns (len(dirs), len(x)) float32.  Vectorised: one (nsteps, npoints)
    boolean block per direction, argmax gives the first blocked sample.
    """
    n = grid.shape[0]
    ts = np.arange(step, limit + 1e-9, step, dtype=np.float64)
    out = np.empty((len(dirs), len(x)), dtype=np.float32)
    for k, (ux, uy) in enumerate(dirs):
        B = np.zeros((len(ts), len(x)), dtype=bool)
        for m, t in enumerate(ts):
            ii = ((x + ux * t + HALF) / RES).astype(np.int32)
            jj = ((y + uy * t + HALF) / RES).astype(np.int32)
            np.clip(ii, 0, n - 1, out=ii)
            np.clip(jj, 0, n - 1, out=jj)
            B[m] = grid[jj, ii] > 0
        hit = B.any(axis=0)
        first = B.argmax(axis=0)
        out[k] = np.where(hit, ts[first] - step, limit).astype(np.float32)
    return out


def directions(n=24):
    return [(math.cos(k * 2.0 * math.pi / n), math.sin(k * 2.0 * math.pi / n))
            for k in range(n)]


def _gather(R, idx, cols):
    return R[idx, cols]


def dedup(rows, want, radius):
    """Greedy spatial spread: no two picks closer than `radius`."""
    out = []
    for row in rows:
        if len(out) >= want:
            break
        if all(math.hypot(row["x"] - p["x"], row["y"] - p["y"]) >= radius
               for p in out):
            out.append(row)
    return out


# --------------------------------------------------------------------------- #
#  pickers
# --------------------------------------------------------------------------- #
def pick_game(grid, clr, den, want, step=2.0, dedup_r=140.0):
    """The 52 deg / 34 m rig: the *player* stands in the street.

    The camera is 26.79 m up, so it clears every eave in town; what decides the
    frame is the corridor the player stands in.  `back` keeps the camera over
    the same street instead of over a roof -- that is what turns the bottom of
    the frame into shingles.
    """
    dirs = directions(24)
    x, y, i, j = lattice(step, 60.0, 930.0)
    c = clr[j, i]
    d = den[j, i]
    # 1.7 m: not jammed against a wall.  5.2 m: still a canyon -- wider means a
    # square or a hole in the block, and those make dull frames because there is
    # no corridor to look down.  Density 0.25-0.75: inside the town, not in the
    # field strip that runs along the curtain wall.
    m = (c >= 1.7) & (c <= 5.2) & (d >= 0.25) & (d <= 0.75)
    x, y, i, j, c = x[m], y[m], i[m], j[m], c[m]
    print("[spots] game lattice %d points" % len(x))
    if not len(x):
        return []

    R = runs(grid, x, y, dirs, 90.0)
    best = R.argmax(axis=0)
    cols = np.arange(len(x))
    run = R[best, cols]
    back = R[(best + 12) % 24, cols]
    lat = np.minimum(R[(best + 6) % 24, cols], R[(best + 18) % 24, cols])

    m = ((run >= 30.0) & (back >= GAME_BACK - 2.0)
         & (lat >= 2.0) & (lat <= 6.5))
    print("[spots] game: %d pass run>=30 / back>=%.1f / 2<=lat<=6.5"
          % (int(m.sum()), GAME_BACK - 2.0))
    if not m.any():
        return []
    x, y, c, run, back, lat, best = x[m], y[m], c[m], run[m], back[m], lat[m], best[m]
    sc = (np.minimum(run, 62.0) * 1.55 + np.minimum(c, 4.0) * 2.0
          + np.minimum(lat, 6.0) * 3.0)
    order = np.argsort(-sc)
    rows = []
    for k in order:
        ux, uy = dirs[best[k]]
        rows.append({"score": round(float(sc[k]), 1),
                     "x": round(float(x[k]), 1), "y": round(float(y[k]), 1),
                     "ux": round(float(ux), 4), "uy": round(float(uy), 4),
                     "w": round(float(lat[k]) * 2.0, 1),
                     "kind": "main" if lat[k] * 2 >= 9.5 else
                             ("secondary" if lat[k] * 2 >= 5.5 else "alley"),
                     "r": round(float(math.hypot(x[k], y[k])), 0),
                     "run": round(float(run[k]), 1),
                     "back": round(float(back[k]), 1),
                     "clear": round(float(c[k]), 2),
                     "game_z": round(EYE_H + GAME_UP, 2),
                     "eye": [round(float(x[k]), 1), round(float(y[k]), 1), EYE_H]})
    return dedup(rows, want, dedup_r)


def pick_eye(grid, clr, den, want, step=1.5, dedup_r=130.0):
    """The 1.72 m eye: it has to stand, it has to breathe, it has to see."""
    dirs = directions(24)
    x, y, i, j = lattice(step, 80.0, 820.0)
    c = clr[j, i]
    d = den[j, i]
    m = (c >= 1.2) & (c <= 5.6) & (d >= 0.25) & (d <= 0.75)
    x, y, i, j, c = x[m], y[m], i[m], j[m], c[m]
    # flat floor: the four neighbours must be about as open (a plinth, a step or
    # a fountain rim is a refusal -- you cannot stand on a kerb)
    spread = np.maximum.reduce([
        np.abs(clr[np.clip(j + a, 0, clr.shape[0] - 1), np.clip(i + b, 0, clr.shape[1] - 1)] - c)
        for (a, b) in ((1, 0), (-1, 0), (0, 1), (0, -1))])
    m = spread <= 0.9
    x, y, i, j, c = x[m], y[m], i[m], j[m], c[m]
    print("[spots] eye lattice %d points" % len(x))
    if not len(x):
        return []

    R = runs(grid, x, y, dirs, 40.0)
    best = R.argmax(axis=0)
    cols = np.arange(len(x))
    run = R[best, cols]
    lat = np.minimum(R[(best + 6) % 24, cols], R[(best + 18) % 24, cols])

    m = (run >= 12.0) & (lat >= 1.2) & (lat <= 6.0)
    print("[spots] eye: %d pass run>=12 / 1.2<=lat<=6.0" % int(m.sum()))
    if not m.any():
        return []
    x, y, c, run, lat, best = x[m], y[m], c[m], run[m], lat[m], best[m]
    sc = (np.minimum(run, 40.0) * 2.2 + np.minimum(c, 4.0) * 1.5
          + np.minimum(lat, 6.0) * 4.0)
    order = np.argsort(-sc)
    rows = []
    for k in order:
        ux, uy = dirs[best[k]]
        rows.append({"score": round(float(sc[k]), 1),
                     "x": round(float(x[k]), 1), "y": round(float(y[k]), 1),
                     "ux": round(float(ux), 4), "uy": round(float(uy), 4),
                     "w": round(float(lat[k]) * 2.0, 1),
                     "kind": "main" if lat[k] * 2 >= 9.0 else
                             ("secondary" if lat[k] * 2 >= 5.0 else "alley"),
                     "r": round(float(math.hypot(x[k], y[k])), 0),
                     "run": round(float(run[k]), 1),
                     "clear": round(float(c[k]), 2),
                     "los": round(float(run[k]), 1),
                     "eye": [round(float(x[k]), 1), round(float(y[k]), 1), EYE_H]})
    return dedup(rows, want, dedup_r)


# --------------------------------------------------------------------------- #
def main():
    want = int(arg("--want", 12))
    want_eye = int(arg("--want-eye", 10))
    out_path = arg("--out", os.path.join(HERE, "spots.json"))

    d = load_blocks(arg("--blocks"))
    grid = raster([b["hull"] for b in d["blocks"]], LANDMARKS)
    print("[spots] raster %d x %d at %.2f m, %.1f%% solid"
          % (grid.shape[0], grid.shape[1], RES, 100.0 * grid.mean()))
    clr = clearance(grid)
    den = density(grid, 40.0)
    print("[spots] clearance: p50 %.2f p90 %.2f max %.1f | density p50 %.2f"
          % (float(np.percentile(clr, 50)), float(np.percentile(clr, 90)),
             float(clr.max()), float(np.percentile(den, 50))))

    picks = pick_game(grid, clr, den, want)
    eyes = pick_eye(grid, clr, den, want_eye)
    print("[spots] %d game picks, %d eye picks" % (len(picks), len(eyes)))
    for p in picks:
        print("[spots] game %6.1f (%7.1f,%7.1f) r=%3.0f run=%4.1f w=%4.1f "
              "clear=%.2f back=%4.1f" % (p["score"], p["x"], p["y"], p["r"],
                                         p["run"], p["w"], p["clear"], p["back"]))
    for p in eyes:
        print("[spots] eye  %6.1f (%7.1f,%7.1f) r=%3.0f run=%4.1f w=%4.1f "
              "clear=%.2f" % (p["score"], p["x"], p["y"], p["r"], p["run"],
                              p["w"], p["clear"]))

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"src": "blend", "blocks": len(d["blocks"]),
                   "stats": d["stats"], "picks": picks, "eye_picks": eyes},
                  fh, indent=1)
    print("[spots] wrote %s" % out_path)


if __name__ == "__main__":
    main()
