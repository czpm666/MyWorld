"""_nature_probe.py -- inspect capital_full.blend for the greenery pass.

Reports: object groups, water, existing foliage, ground height samples, plaza
free space.  Run headless:
    blender -b <blend> --python _nature_probe.py -- --blend path
"""

import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))


def groups():
    g = {}
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        n = ob.name.split("_")[0]
        d = g.setdefault(n, [0, 0, [1e9, 1e9, 1e9], [-1e9, -1e9, -1e9]])
        d[0] += 1
        d[1] += len(ob.data.polygons) if ob.data else 0
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            for i in range(3):
                d[2][i] = min(d[2][i], w[i])
                d[3][i] = max(d[3][i], w[i])
    return g


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    print("[probe] objects=%d meshes=%d mats=%d" % (
        len(bpy.data.objects),
        len([o for o in bpy.data.objects if o.type == "MESH"]),
        len(bpy.data.materials)), flush=True)
    g = groups()
    for k, d in sorted(g.items(), key=lambda kv: -kv[1][1]):
        print("[probe] %-10s n=%-6d faces=%-7d z=[%.2f..%.2f] xy=[%.0f..%.0f]x[%.0f..%.0f]" % (
            k, d[0], d[1], d[2][2], d[3][2], d[2][0], d[3][0], d[2][1], d[3][1]), flush=True)
    names = [o.name for o in bpy.data.objects]
    for pat in ("river", "water", "tree", "foliage", "grass", "leaf", "bush",
                "lake", "pond", "fountain", "canal"):
        hit = [n for n in names if pat in n.lower()]
        print("[probe] name~%-9s %d  %s" % (pat, len(hit), hit[:6]), flush=True)
    print("[probe] materials: %s" % sorted(m.name for m in bpy.data.materials), flush=True)

    # raycast the ground from above on a few rings
    deps = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    for r in (0, 20, 60, 120, 240, 400, 600, 630, 645, 660, 700, 760, 800, 900, 1000):
        zs = []
        for i in range(8):
            a = i * math.tau / 8
            x, y = r * math.cos(a), r * math.sin(a)
            ok, loc, nor, idx, ob, mat = sc.ray_cast(deps, Vector((x, y, 400.0)),
                                                     Vector((0, 0, -1)))
            zs.append(round(loc.z, 2) if ok else None)
        print("[probe] ground r=%-5s z=%s" % (r, zs), flush=True)


main()
