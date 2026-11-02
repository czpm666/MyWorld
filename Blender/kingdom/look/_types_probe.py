"""Scratch probe: how big are the blocks in layout.json?  Deleted after use."""
import sys, json, math, collections

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_dense as DN

D = json.load(open(r"E:\My World\Blender\kingdom\layout.json", encoding="utf-8"))
res = dict(blocks=D["blocks"], streets=D["streets"])
blocks = res["blocks"]
print("blocks", len(blocks), "streets", len(res["streets"]))

rows = []
for b in blocks:
    poly = b.get("poly") or ()
    if len(poly) < 3 or b.get("open"):
        continue
    a = abs(DN._area(poly))
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    rows.append((a, max(xs) - min(xs), max(ys) - min(ys), b.get("role"), b.get("id")))

rows.sort(reverse=True)
print("largest 12 blocks (area, bbox w, bbox d, role, id):")
for r in rows[:12]:
    print("  %7.0f m2  %5.1f x %5.1f  %-12s %s" % (r[0], r[1], r[2], r[3], r[4]))
areas = sorted(r[0] for r in rows)
print("block area p50 %.0f p90 %.0f max %.0f" % (areas[len(areas) // 2],
                                                 areas[int(len(areas) * 0.9)], areas[-1]))
print("by role:", collections.Counter(r[3] for r in rows).most_common())
for role in ("palace", "guild", "outer", "craft", "dock", "residential", "temple", "artisan"):
    sub = [r for r in rows if r[3] == role]
    if not sub:
        continue
    sub.sort(reverse=True)
    print("  %-12s n=%4d  biggest %5.1f x %5.1f (%4.0f m2)" % (role, len(sub), sub[0][1],
                                                               sub[0][2], sub[0][0]))
print("blocks with bbox>=46x34:", sum(1 for r in rows if r[1] >= 46 and r[2] >= 34))
print("blocks with bbox>=34x46:", sum(1 for r in rows if r[1] >= 34 and r[2] >= 46))
print("blocks with bbox>=30x40 or 40x30:", sum(1 for r in rows if (r[1] >= 30 and r[2] >= 40) or (r[1] >= 40 and r[2] >= 30)))
print("blocks with bbox>=20x26 or 26x20:", sum(1 for r in rows if (r[1] >= 20 and r[2] >= 26) or (r[1] >= 26 and r[2] >= 20)))
print("streets sample:", res["streets"][0] if res["streets"] else None)
print("city:", D.get("city"))
