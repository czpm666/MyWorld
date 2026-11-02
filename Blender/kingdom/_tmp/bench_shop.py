import sys, time, random
sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")
import capital as C
C.K.reset_scene()
C.init_mats()
import capital_hd_glue as G
M = C.hd_mat()
rng = random.Random(3)
tot = 0.0
for k in ("tavern", "blacksmith", "general_store", "clothier", "bakery",
          "chapel", "stable", "adventurers_guild", "magic_shop"):
    t0 = time.time()
    p = G.shop(k, M, rng, 0.0, 0.0, 0.0, 0.0)
    dt = time.time() - t0
    tot += dt
    o, f, t = G.stats(p)
    print("BENCH %-18s %6.2f s  objects=%-5d faces=%-6d tris=%d" % (k, dt, o, f, t), flush=True)
tz = time.time()
for i in range(8):
    G.house(M, rng, 0.0, 0.0, 0.0, 7.0, 9.0, 2 + i % 3, ("timber", "stone", "shop", "inn")[i % 4],
            "gable" if i % 2 else "eaves")
th = (time.time() - tz) / 8.0
print("BENCH house          %6.2f s  (x8 avg)" % th, flush=True)
print("BENCH shops_total    %6.2f s" % tot, flush=True)
