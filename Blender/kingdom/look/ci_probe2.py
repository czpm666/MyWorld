# -*- coding: utf-8 -*-
"""ci_probe2.py - what do the feast-hall lamps actually look like in the scene?"""
import os
import sys

for _p in (r"E:\My World\Blender", r"E:\My World\Blender\kingdom"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
import medkit as K  # noqa: E402
import hd_castle_int as C  # noqa: E402

K.reset_scene()
MAT = C.make_mats()
P = C.build(K, MAT, seed=3)
print("PARTS", len(P))
for ob in P:
    if ob is None or ob.type != "LIGHT":
        continue
    L = ob.data
    n = ob.name
    if not any(n.startswith(k) for k in ("ci_f_", "ci_ch", "ci_fp")):
        continue
    print("LAMP %-18s %-6s E=%-8.0f loc=(%6.2f,%6.2f,%6.2f) shape=%s size=%s rot=%s"
          % (n, L.type, L.energy,
             ob.location.x, ob.location.y, ob.location.z,
             getattr(L, "shape", "-"), getattr(L, "size", "-"),
             tuple(round(a, 3) for a in ob.rotation_euler)))
    if n.startswith("ci_f_roomfill"):
        print("     shadow=%s  visible_diffuse=%s" %
              (L.use_shadow, ob.visible_diffuse))

# how much light lands on the feast floor at the middle of the room?
sc = bpy.context.scene
print("EXPOSURE", sc.view_settings.exposure, sc.view_settings.look)
print("WORLD", sc.world and sc.world.name)
