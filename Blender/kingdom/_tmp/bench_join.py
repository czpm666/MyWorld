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
HMAT = H.make_mats() if hasattr(H, "make_mats") else {}
N = int(os.environ.get("BENCH_N", "40"))
rs = random.Random(7)
houses = []
t0 = time.time()
for i in range(N):
    kind = rs.choice(["timber", "stone", "shop", "inn", "manor", "tower", "warehouse", "craft"])
    objs = H.house(HMAT, rs, kind=kind, w=rs.uniform(6, 8), d=rs.uniform(8, 11),
                   floors=rs.choice([2, 3]), frontage=rs.choice(["eaves", "gable"]))
    houses.append(objs)
t1 = time.time()
print("RAW %d houses %.1fs objects=%d" % (N, t1 - t0, sum(len(h) for h in houses)), flush=True)

ctx = bpy.context
t2 = time.time()
fails = 0
for i, hs in enumerate(houses):
    if not hs:
        continue
    try:
        bpy.ops.object.select_all(action='DESELECT')
        for o in hs:
            o.select_set(True)
        ctx.view_layer.objects.active = hs[0]
        bpy.ops.object.join()
    except Exception as e:
        fails += 1
        if fails < 3:
            print("join fail", e, flush=True)
t3 = time.time()
print("OPS JOIN %d houses %.1fs fails=%d" % (N, t3 - t2, fails), flush=True)
print("per house: %.3fs build, %.3fs join" % ((t1 - t0) / N, (t3 - t2) / N), flush=True)
print("objects now:", len([o for o in bpy.data.objects if o.type == 'MESH']), flush=True)
print("BENCH_DONE")
