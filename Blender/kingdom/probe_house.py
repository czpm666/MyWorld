import sys, os, random
sys.path.insert(0, r"E:\My World\Blender")
import bpy, medkit, medbuild
from mathutils import Matrix
medkit.reset_scene()
medkit._MAT_CACHE.clear()
rng = random.Random(7)
parts = medbuild.house("h", medkit.T_at(0, 0, 0), W=5.2, D=4.8, rng=rng,
                       walls=medkit.mat_plaster("p", "#ded2b8", "#c0b294"),
                       timber=medkit.mat_wood("w", "#4a3728", "#6b5238"),
                       roof=medkit.mat_tile("r", "#7a3d2c", "#5c2c1f", "#8f4a35"),
                       stone_ground=True, dormers=0)
tot = 0
rows = []
for ob in parts:
    if ob.type != "MESH":
        continue
    n = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    tot += n
    rows.append((n, ob.name))
rows.sort(reverse=True)
print("[probe] parts=%d tris=%d" % (len(parts), tot))
for n, nm in rows[:25]:
    print("   %6d %s" % (n, nm))
print("[probe] smallest:", [(n, nm) for n, nm in rows[-5:]])
