"""What material is actually on the roofs?  Count upward-facing high faces."""
import bpy, sys
from collections import Counter

objs = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("city_blk")]
c = Counter()
for ob in objs:
    me = ob.data
    slots = [s.material.name if s.material else "?" for s in ob.material_slots]
    if not slots:
        continue
    n = len(me.polygons)
    if n == 0:
        continue
    step = max(1, n // 4000)
    for i in range(0, n, step):
        p = me.polygons[i]
        if p.normal.z < 0.35:
            continue
        ctr = p.center
        if ctr.z < 4.0:
            continue
        c[slots[min(p.material_index, len(slots) - 1)]] += 1
print("[roofmats] sampled upward faces above z=4:")
for name, k in c.most_common(24):
    print("   %-28s %6d" % (name, k))

# and the material node tree of the top one
if c:
    top = c.most_common(1)[0][0]
    m = bpy.data.materials.get(top)
    print("[roofmats] %s nodes:" % top)
    for nd in m.node_tree.nodes:
        print("   %-24s %s" % (nd.bl_idname, nd.name))
