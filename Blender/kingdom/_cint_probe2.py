# -*- coding: utf-8 -*-
"""Find tall thin objects near the centre line."""
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
for o in objs:
    mw = o.matrix_world
    cs = [mw @ Vector(c) for c in o.bound_box]
    lo = Vector((min(c[i] for c in cs) for i in range(3)))
    hi = Vector((max(c[i] for c in cs) for i in range(3)))
    if abs((lo.x + hi.x) * 0.5) < 1.2 and hi.z - lo.z > 4.0 and hi.x - lo.x < 2.0:
        print("TALL %-22s x %6.2f..%6.2f y %7.2f..%7.2f z %6.2f..%6.2f  mat %s"
              % (o.name, lo.x, hi.x, lo.y, hi.y, lo.z, hi.z,
                 o.data.materials[0].name if o.data.materials else "-"))
