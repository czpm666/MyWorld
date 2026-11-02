# -*- coding: utf-8 -*-
import collections
import math
import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
import hd_layout as L            # noqa: E402

lay = L.generate(radius=636.0, seed=20261022)
pl = lay["plots"]
gates = [tuple(lm["pos"]) for lm in lay["landmarks"] if lm["kind"] == "gate"]
castle = next((tuple(lm["pos"]) for lm in lay["landmarks"]
               if lm["kind"] == "castle"), None)
print("gates", gates, "castle", castle)


def near(p, pts):
    return min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in pts)


buckets = collections.defaultdict(list)
for p in pl:
    buckets[p["kind"]].append(round(near(p["pos"], gates), 0))
rows = []
for kk, ds in buckets.items():
    ds.sort()
    rows.append((len(ds), kk, ds[len(ds) // 2], ds[0], ds[-1]))
rows.sort(reverse=True)
for n, kk, med, lo, hi in rows[:16]:
    print("%-18s n=%-4d to-gate med %4.0f  [%3.0f..%4.0f]" % (kk, n, med, lo, hi))
man = [p for p in pl if "manor" in p["kind"]]
if man and castle:
    ds = sorted(round(math.hypot(p["pos"][0] - castle[0], p["pos"][1] - castle[1]), 0)
                for p in man)
    print("manor n=%d to-castle med %.0f [%.0f..%.0f]" % (len(ds), ds[len(ds) // 2], ds[0], ds[-1]))
