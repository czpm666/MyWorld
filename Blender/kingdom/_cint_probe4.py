# -*- coding: utf-8 -*-
"""Probe: does the afternoon sun actually reach the interior?"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from mathutils import Vector

import hd_common as H
import hd_castle_int as CI

H._clear()
objs = CI.build(CI.make_mats(), random.Random(20261030))
print("BUILD", len(objs), H.tri_count(objs))

dg = bpy.context.evaluated_depsgraph_get()
sc = bpy.context.scene


def cast(o, d):
    hit, loc, nor, idx, ob, mx = sc.ray_cast(dg, Vector(o), Vector(d))
    if not hit:
        return None, 999.0
    return ob.name, (Vector(loc) - Vector(o)).length


for dname, d in (("sunA", (-0.54, 0.40, -0.74)),
                 ("sunB", (-0.62, -0.28, -0.73)),
                 ("sunC", (-0.40, -0.10, -0.90))):
    v = Vector(d).normalized()
    ok = 0
    tot = 0
    hits = {}
    for i in range(300):
        x = random.uniform(-8.0, 8.0)
        y = random.uniform(-20.0, 20.0)
        z = random.uniform(0.5, 14.0)
        nm, dist = cast((x, y, z), -v)
        tot += 1
        if nm is None:
            ok += 1
        else:
            hits[nm] = hits.get(nm, 0) + 1
    top = sorted(hits.items(), key=lambda kv: -kv[1])[:6]
    print("SUN", dname, "escape %d/%d" % (ok, tot), top)

# where does a sun ray entering the +X clerestory land?
v = Vector((-0.62, -0.28, -0.73)).normalized()
for z0 in (13.4, 14.6):
    for x0 in (8.6, 9.2):
        nm, dist = cast((x0, 0.0, z0), -v)
        print("LAND", x0, z0, "->", nm, round(dist, 2))
