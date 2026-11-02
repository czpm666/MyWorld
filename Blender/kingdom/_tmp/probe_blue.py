# -*- coding: utf-8 -*-
"""What is the blue band on top of the curtain wall?  Ray-cast from the shot."""
import sys
import os

BL = r"E:\My World\Blender"
sys.path.insert(0, BL)
sys.path.insert(0, os.path.join(BL, "kingdom"))

import bpy                                                   # noqa: E402
import mathutils                                             # noqa: E402

blend = os.path.join(BL, "renders", "kingdom", "capital_full.blend")
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene

import capital as C                                          # noqa: E402

shot = dict((s[0], s) for s in C.HD_SHOTS)["b5_gate_in"]
loc, look, lens = mathutils.Vector(shot[1]), mathutils.Vector(shot[2]), shot[3]
d = (look - loc).normalized()
right = d.cross(mathutils.Vector((0, 0, 1))).normalized()
up = right.cross(d).normalized()
# 36 mm sensor, 16:9 frame: half width in metres at unit distance
hw = 18.0 / lens
hh = hw * 9.0 / 16.0

for px, py in [(0.10, 0.50 + 0.02 * i) for i in range(12)] + [(0.92, 0.50 + 0.02 * i) for i in range(12)]:
    u = (px - 0.5) * 2 * hw
    v = (0.5 - py) * 2 * hh
    origin = loc + right * u + up * v
    hit, hloc, hnor, idx, ob, _m = sc.ray_cast(bpy.context.view_layer.depsgraph,
                                               origin, d)
    if not hit:
        print("px %.2f %.2f  MISS" % (px, py), flush=True)
        continue
    me = ob.data
    mat = ""
    if hasattr(me, "polygons") and idx < len(me.polygons):
        mi = me.polygons[idx].material_index
        if mi < len(ob.material_slots) and ob.material_slots[mi].material:
            mat = ob.material_slots[mi].material.name
    print("px %.2f %.2f  ob=%-22s mat=%-18s at %s"
          % (px, py, ob.name, mat, tuple(round(x, 1) for x in hloc)), flush=True)

