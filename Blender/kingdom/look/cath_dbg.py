# -*- coding: utf-8 -*-
"""Ad-hoc diagnostic: build the cathedral interior and report stray geometry."""
import os
import sys
from collections import Counter

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, os.path.dirname(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import hd_cathedral_int as M

M.build()
print("[dbg] objs=%d" % len(M.PARTS))
bad = []
for ob in M.PARTS:
    vs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [v.x for v in vs]
    ys = [v.y for v in vs]
    zs = [v.z for v in vs]
    if min(ys) < -46.0 or max(ys) > 43.0 or min(xs) < -35.0 or max(xs) > 35.0:
        bad.append((ob.name, round(min(xs), 2), round(max(xs), 2), round(min(ys), 2),
                    round(max(ys), 2), round(min(zs), 2), round(max(zs), 2)))
print("[dbg] bad=%d" % len(bad))
cnt = Counter()
for b in bad:
    cnt[b[0].split("_")[0]] += 1
print("[dbg] by prefix:", cnt.most_common(20))
for b in bad[:45]:
    print("[dbg] ", b)
