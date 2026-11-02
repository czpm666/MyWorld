import bpy, sys, os, time, random
HERE = r"E:\My World\Blender\kingdom"
BL = r"E:\My World\Blender"
for p in (HERE, BL):
    if p not in sys.path:
        sys.path.insert(0, p)
import hd_houses as H
import capital as C

K = C.K
K.reset_scene()
MAT = {}
import hd_houses
HMAT = hd_houses.make_mats() if hasattr(hd_houses, "make_mats") else {}

N = int(os.environ.get("BENCH_N", "100"))
rs = random.Random(7)
t0 = time.time()
parts = []
for i in range(N):
    kind = rs.choice(["timber", "stone", "shop", "inn", "manor", "tower", "warehouse", "craft"])
    fr = rs.choice(["eaves", "gable"])
    objs = H.house(HMAT, rs, kind=kind, w=rs.uniform(6, 8), d=rs.uniform(8, 11),
                   floors=rs.choice([2, 3]), frontage=fr)
    K.link_all = None
    parts.extend(objs)
t1 = time.time()
n_obj = len(parts)
tris = sum(len(p.data.polygons) * 2 for p in parts)
print("RAW  %d houses: %.1fs  objects=%d  faces~%d" % (N, t1 - t0, n_obj,
      sum(len(p.data.polygons) for p in parts)), flush=True)

# join each house separately, the way capital would
houses = [parts[i::N] for i in range(N)]
t2 = time.time()
merged = []
for i, hs in enumerate(houses):
    merged.append(C.join_parts("bench%d" % i, hs))
t3 = time.time()
print("JOIN %d houses: %.1fs  objects=%d" % (N, t3 - t2, len(merged)), flush=True)
tot_f = sum(len(o.data.polygons) for o in merged)
tot_t = sum(len(o.data.polygons) - 2 for o in merged)
print("AFTER JOIN: objects=%d faces=%d tris~%d" % (len(merged), tot_f, tot_t), flush=True)
print("per house: %.3fs raw, %.3fs joined" % ((t1 - t0) / N, (t3 - t2) / N), flush=True)
print("BENCH_DONE")
