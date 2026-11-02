import os
import sys

import bpy

blend = r"E:\My World\Blender\renders\kingdom\capital_full.blend"
bpy.ops.wm.open_mainfile(filepath=blend)

KEY = ("bar", "crate", "cart", "prop", "pot", "basket", "sack")
hits = []
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    n = ob.name.lower()
    if not any(k in n for k in KEY):
        continue
    zs = [v[2] for v in ob.bound_box]
    zmin = min(zs) + ob.matrix_world.translation.z
    zmax = max(zs) + ob.matrix_world.translation.z
    if zmin > 2.5:
        hits.append((round(zmin, 1), ob.name, len(ob.data.polygons),
                     tuple(round(c, 1) for c in ob.matrix_world.translation)))

hits.sort(reverse=True)
print("[floaters] %d" % len(hits), flush=True)
for h in hits[:25]:
    print("[floaters] z=%.1f %s faces=%d loc=%s" % h, flush=True)
