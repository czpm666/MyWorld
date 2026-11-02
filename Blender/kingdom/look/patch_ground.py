"""Patch the paving of an already-built capital blend, without rebuilding it.

Re-opening a saved city costs seconds; rebuilding costs twelve minutes.  This
swaps the flat per-street boxes for hd_street's crowned carriageway, lifts the
block slabs a hand's width so the kerb reads, and saves under a new name.

    blender -b <file.blend> --python look/patch_ground.py -- --out NAME
"""
import os
import sys
import time

import bpy


def opts():
    a = sys.argv
    a = a[a.index("--") + 1:] if "--" in a else []
    o = {}
    i = 0
    while i < len(a):
        if a[i].startswith("--"):
            k = a[i][2:]
            if i + 1 < len(a) and not a[i + 1].startswith("--"):
                o[k] = a[i + 1]
                i += 2
            else:
                o[k] = True
                i += 1
        else:
            i += 1
    return o


def main():
    o = opts()
    sys.path.insert(0, r"E:\My World\Blender\kingdom")
    sys.path.insert(0, r"E:\My World\Blender")
    import medkit as K
    import hd_street as HS
    import json

    lay = json.load(open(r"E:\My World\Blender\kingdom\layout.json", "r",
                         encoding="utf-8"))
    MAT = {m.name: m for m in bpy.data.materials}
    # capital.py's slots are not always named after their key
    if "town_street" in MAT:
        MAT["street"] = MAT["town_street"]
    print("[patch] materials", len(MAT), flush=True)

    gone = 0
    for ob in list(bpy.data.objects):
        n = ob.name
        if n.startswith("st_") or n.startswith("stc_") or n.startswith("streets_"):
            bpy.data.objects.remove(ob, do_unlink=True)
            gone += 1
    print("[patch] removed %d old street objects" % gone, flush=True)

    # the kerb: the block slabs are the pavement, so they have to sit a kerb's
    # height above the crown of the road, not three millimetres above it
    lifted = 0
    for ob in bpy.data.objects:
        if ob.name.startswith("blk_") and ob.type == "MESH":
            for v in ob.data.vertices:
                v.co.z = 0.09
            lifted += 1
    print("[patch] lifted %d block slabs" % lifted, flush=True)

    t0 = time.time()
    obs = HS.build(K, MAT, lay["streets"])
    print("[patch] streets: %d objects in %.1f s" % (len(obs), time.time() - t0),
          flush=True)
    for ob in obs:
        print("   %-20s faces %d" % (ob.name, len(ob.data.polygons)), flush=True)

    out = o.get("out")
    if out:
        path = os.path.join(r"E:\My World\Blender\renders\kingdom", "%s.blend" % out)
        bpy.ops.wm.save_as_mainfile(filepath=path)
        print("[patch] saved", path, os.path.getsize(path), flush=True)
    print("PATCH_DONE")


main()
