"""Plot/street geometry analysis: setbacks, gaps, coverage. Plain python, no bpy."""
import json, math, sys, collections

P = r"E:\My World\Blender\kingdom\layout.json"
D = json.load(open(P, "r", encoding="utf-8"))
plots, blocks, streets = D["plots"], D["blocks"], D["streets"]


def area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def poly_dist(p, pts):
    return min(seg_dist(p, pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))


if plots:
    p0 = plots[0]
    print("plot keys:", sorted(p0.keys()))
    print("plot0:", {k: p0[k] for k in p0 if k != "plot"})
    print("plot0 poly:", p0.get("plot"))
    print("plot0 fill:", p0.get("fill"))
print("block keys:", sorted(blocks[0].keys()))
print("block0:", {k: v for k, v in blocks[0].items() if not isinstance(v, list)})
print("block poly key candidates:",
      [k for k, v in blocks[0].items() if isinstance(v, list) and v and isinstance(v[0], (list, tuple))])

# ---- building footprint rectangles ----
def footprint(pl):
    """centred rect from pos/rz/w/d"""
    cx, cy = pl["pos"]
    rz = pl.get("rz") or 0.0
    w = float(pl.get("w") or 7.0)
    d = float(pl.get("d") or 8.0)
    sc = float(pl.get("scale") or 1.0)
    w *= sc
    d *= sc
    ca, sa = math.cos(rz), math.sin(rz)
    out = []
    for dx, dy in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
        out.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return out

# gap between neighbouring buildings: sample 400 random pairs? better: KD-ish grid
cells = collections.defaultdict(list)
GRID = 12.0
for i, pl in enumerate(plots):
    fp = footprint(pl)
    xs = [p[0] for p in fp]
    ys = [p[1] for p in fp]
    for gx in range(int(min(xs) // GRID), int(max(xs) // GRID) + 1):
        for gy in range(int(min(ys) // GRID), int(max(ys) // GRID) + 1):
            cells[(gx, gy)].append(i)

gaps = []
for i, pl in enumerate(plots):
    fp = footprint(pl)
    cx, cy = pl["pos"]
    best = 1e9
    seen = set()
    for gx in range(int(cx // GRID) - 1, int(cx // GRID) + 2):
        for gy in range(int(cy // GRID) - 1, int(cy // GRID) + 2):
            for j in cells.get((gx, gy), ()):
                if j == i or j in seen:
                    continue
                seen.add(j)
                fp2 = footprint(plots[j])
                dd = min(min(seg_dist(p, fp2[k], fp2[(k + 1) % 4]) for k in range(4)) for p in fp)
                if dd < best:
                    best = dd
    if best < 1e8:
        gaps.append(best)

gaps.sort()
n = len(gaps)


def pct(q):
    return gaps[min(n - 1, int(q * n))]


print("\n== nearest building-to-building gap (m) ==")
for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.95):
    print("  p%-3d %.2f" % (q * 100, pct(q)))
print("  mean %.2f  min %.2f  max %.2f" % (sum(gaps) / n, gaps[0], gaps[-1]))
print("  share <1.0m: %.1f%%   <2m: %.1f%%   >6m: %.1f%%   >10m: %.1f%%" % (
    100.0 * sum(1 for g in gaps if g < 1) / n,
    100.0 * sum(1 for g in gaps if g < 2) / n,
    100.0 * sum(1 for g in gaps if g > 6) / n,
    100.0 * sum(1 for g in gaps if g > 10) / n))

# ---- setbacks: distance from building front to its street centreline ----
by_street = collections.defaultdict(list)
for pl in plots:
    by_street[pl.get("street")].append(pl)
setbacks = []
for s in streets:
    ax, ay = s["a"]
    bx, by = s["b"]
    w = float(s.get("w") or 6.0)
    for pl in by_street.get(s["id"], ()):
        fp = footprint(pl)
        dmin = min(seg_dist(p, (ax, ay), (bx, by)) for p in fp)
        setbacks.append((dmin - w / 2, s.get("kind"), w))
setbacks.sort()
m = len(setbacks)
print("\n== facade setback from kerb (m), n=%d ==" % m)
for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99):
    print("  p%-3d %.2f" % (q * 100, setbacks[min(m - 1, int(q * m))][0]))
print("  mean %.2f" % (sum(s[0] for s in setbacks) / m))
print("  share <1m: %.1f%%  <2m: %.1f%%  >4m: %.1f%%  >8m: %.1f%%" % (
    100.0 * sum(1 for s in setbacks if s[0] < 1) / m,
    100.0 * sum(1 for s in setbacks if s[0] < 2) / m,
    100.0 * sum(1 for s in setbacks if s[0] > 4) / m,
    100.0 * sum(1 for s in setbacks if s[0] > 8) / m))

# ---- per-block coverage ----
tot_b = tot_p = 0.0
cov = []
for b in blocks:
    pts = b.get("poly") or b.get("polygon") or b.get("pts")
    if not pts:
        continue
    ba = area(pts)
    pa = 0.0
    for pl in plots:
        if pl.get("block_id") == b.get("id"):
            pa += area(footprint(pl))
    cov.append((pa / ba, ba, pa, b.get("id"), b.get("role")))
    tot_b += ba
    tot_p += pa
cov.sort(reverse=True)
print("\n== block coverage (building area / block area) ==")
print("  overall %.2f  (buildings %.0f m2 / blocks %.0f m2)" % (tot_p / tot_b, tot_p, tot_b))
for q in (0.1, 0.25, 0.5, 0.75, 0.9):
    print("  p%-3d %.2f" % (q * 100, cov[int((1 - q) * len(cov))][0]))
print("  empty blocks (<0.05):", sum(1 for c in cov if c[0] < 0.05), "of", len(cov))

# ---- building footprint size distribution ----
ws = sorted(float(p.get("w") or 0) * float(p.get("scale") or 1) for p in plots)
ds = sorted(float(p.get("d") or 0) * float(p.get("scale") or 1) for p in plots)
print("\n== footprint w/d ==")
by_kind = collections.defaultdict(lambda: [0, 0.0, 0.0])
for p in plots:
    k = p["kind"]
    by_kind[k][0] += 1
    by_kind[k][1] = max(by_kind[k][1], float(p.get("w") or 0) * float(p.get("scale") or 1))
    by_kind[k][2] = max(by_kind[k][2], float(p.get("d") or 0) * float(p.get("scale") or 1))
for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1][0])[:14]:
    print("  %-20s n=%-4d maxw=%.1f maxd=%.1f" % (k, v[0], v[1], v[2]))
