# -*- coding: utf-8 -*-
"""Probe: which objects' world bbox contains a given point (x y z ...).

usage: blender -b --factory-startup --python hd_gate_probe2.py -- 0 22 0.05
"""
import os
import sys
import random

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hd_gate as G
import hd_common as H

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
pts = []
for i in range(0, len(argv) - 2, 3):
    pts.append((float(argv[i]), float(argv[i + 1]), float(argv[i + 2])))

H._clear()
MAT = G.make_materials()
rng = random.Random(7)
parts = G._flat(G.build(MAT, rng))
print("[probe] parts=%d pts=%s" % (len(parts), pts))
for (px, py, pz) in pts:
    print("[probe] --- point (%.2f, %.2f, %.2f)" % (px, py, pz))
    for ob in parts:
        if ob is None or ob.type != "MESH":
            continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        lo = (min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))
        hi = (max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb))
        if lo[0] <= px <= hi[0] and lo[1] <= py <= hi[1] and lo[2] <= pz <= hi[2]:
            mats = [m.name if m else "-" for m in ob.data.materials]
            print("   %-18s %5d mats=%s z=%.2f..%.2f y=%.2f..%.2f"
                  % (ob.name, len(ob.data.polygons), mats, lo[2], hi[2], lo[1], hi[1]))
