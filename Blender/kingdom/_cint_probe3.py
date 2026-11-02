# -*- coding: utf-8 -*-
"""Ray-cast from a few points to identify what is in front of the camera."""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
import hd_castle_int as CI  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
objs = CI.build(CI.make_mats(), random.Random(1))
dg = bpy.context.evaluated_depsgraph_get()
sc = bpy.context.scene

shots = [("a", (0.0, -23.30, 1.70), (0.0, 6.00, 2.90)),
         ("b", (0.0, -1.20, 1.70), (0.0, 17.00, 3.30)),
         ("c", (0.0, 11.20, 1.70), (0.0, 21.60, 2.55)),
         ("d", (0.0, 20.20, 2.82), (0.0, -24.00, 3.40))]
for nm, p, t in shots:
    d = (Vector(t) - Vector(p)).normalized()
    for k, (dz, dx) in enumerate(((0.0, 0.0), (0.02, 0.0), (0.0, 0.05),
                                  (0.10, 0.0), (-0.08, 0.0))):
        dd = (d + Vector((dx, 0.0, dz))).normalized()
        ok, loc, nor, idx, ob, mw = sc.ray_cast(dg, Vector(p), dd)
        if ok:
            print("%s ray%d hit %-20s at (%.2f, %.2f, %.2f) dist %.2f mat %s"
                  % (nm, k, ob.name, loc.x, loc.y, loc.z, (loc - Vector(p)).length,
                     ob.data.materials[0].name if ob.data.materials else "-"))
        else:
            print("%s ray%d no hit" % (nm, k))
